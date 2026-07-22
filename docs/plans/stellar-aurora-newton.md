# 作业小龙 · 语音聊天功能实现方案（Voice Chat）

> 规划产出日期：2026-07-22 ｜ 基于现有「小龙陪聊系统」(Companion Chat) 增量改造
> 决策（已与用户确认）：语音输入=**服务端 ASR**；语音输出=**服务端流式 TTS**；后端 `/api/chat/message` **改造成 SSE 流式**
> 运行环境：Railway 托管的 Web 应用（HTTPS），主要在**微信内置浏览器(WebView)** 与 Chrome 打开

---

## 0. 项目结构地图（trellis 式导航）

```
homework-pet/
├── app/
│   ├── main.py            # 后端主程序；陪聊路由在 2619-2675 行
│   ├── chat_proxy.py      # ★核心：Hermes 桥接(异步) + 本次新增 ASR/TTS 函数
│   ├── database.py        # 数据库(16 表)；聊天上下文由 Hermes 服务端按 session_id 维护，前端不落库
│   ├── run_local.py       # 本地启动(端口5001)
│   ├── templates/index.html  # 前端单页；陪聊 JS 在 3792-3986 行，聊天面板 HTML 在 3945-3970 行
│   └── static/            # 静态资源(立绘/皮肤)
├── Procfile / railway.json / requirements.txt   # Railway 部署(python app/main.py)
└── docs/plans/companion-chat-plan.md            # 既有陪聊设计文档(参考)
```

**关键现状（已读代码确认）**
- `POST /api/chat/message` → `chat_proxy.hermes_chat()` → `call_hermes()`（**当前 `stream:False` 非流式**）→ 返回 JSON `{text, session_id, pet_mood, blocked}`。
- 前端 `sendChatMessage()` 只发送 `{text, session_id}`；**上下文连续性由 Hermes 服务端按 `session_id` 维护**，前端 `chatHistory` 实际未回传。→ 这意味着「语音/文本切换」天然无缝：两者最终都只是给后端送 `{text, session_id}`。
- TTS 现状：`speakText()` 用浏览器 `window.speechSynthesis`（**非流式、无音量/中断 UI**），**微信 WebView 内基本不可用**。
- 语音输入现状：仅 input 占位提示「长按输入框可微信语音输入」——依赖微信键盘听写，**无真实麦克风采集、无 ASR、无服务端 TTS**。
- 部署：Railway 提供 HTTPS（麦克风所需安全上下文 ✓）。ASR/TTS **不是** Railway 能力，必须走外部云 API 或现有 Linux 服务器(47.242.10.160，与 Hermes 同机)。

---

## 1. 总体架构（目标态）

```
微信 WebView / Chrome
  ├─ 麦克风(MediaRecorder) ──录音 blob──▶ POST /api/chat/voice ──▶ 服务端 ASR(讯飞/腾讯云) ──▶ {text}
  │                                            │
  │        (ASR 文本复用现有消息管线)           │
  ├─ 文本/语音 同一输入框 ──▶ POST /api/chat/message (SSE 流式) ──▶ chat_proxy ──▶ Hermes(:8642, stream:True)
  │                                            │ 逐字流式返回 text
  │                                            ▼
  └─ 前端按句切分 → GET /api/chat/tts?text=句 → 服务端流式 TTS → <audio>/WebAudio 顺序播放(首句优先)
```

**核心原则**：语音输入 = 音频→ASR→文本→**原样喂给现有 `/api/chat/message`**；语音输出 = 对小龙 `text` 做 TTS。所有对话在底层都是文本，因此「切换无感知、上下文不丢失」自动成立。

---

## 1.5 ASR / TTS 技术选型深度分析（用户补充：资源受限 + 移动端约束）

> **约束回顾**：① Hermes 跑在 **2核2G Linux 云服务器**，内存/CPU 极度紧张；② 前端在 **Railway**（仅 Web 托管 + HTTPS，无 GPU、无 ASR/TTS 服务、文件系统临时）；③ 访问端为 **手机微信内置浏览器(WebView) + Chrome**，需移动端麦克风采集与音频播放兼容。
> **一句话结论**：ASR 与 TTS **都走云端 API**，由 Railway 后端持有密钥并调用 → 2C2G 服务器零额外负载、零 OOM 风险；**本地模型在 2C2G 上不可行**（会与 Hermes 争内存）。移动端兼容由「`getUserMedia` + `MediaRecorder`(mime 自适应) + 服务端 ffmpeg 转码 + `<audio>` 播放」解决。

### A. ASR 方案对比

| 方案 | 优点 | 缺点 | 2C2G 可行性 | 移动端/微信兼容 | 部署维护成本 |
|---|---|---|---|---|---|
| **云端中文 ASR**（讯飞/腾讯云/阿里云/百度，实时语音识别 WebSocket） | 中文(尤其童声)识别准；支持**流式 partial 实时回显**；中国机房延迟低(200–500ms)；免费额度够单孩用；**服务端调用零本机负载** | 需注册 + API 密钥(服务端保管)；有网络依赖 | ✅ 不涉及本机算力 | ✅ 前端只传音频，与服务端无关 | 低（配密钥 + SDK） |
| OpenAI Whisper API | 多语种；接口简单 | 中文童声弱于国产云；**国内访问需代理/常被墙**；按分钟计费 | ✅ 云端 | ✅ | 低，但网络不稳 |
| 本地 faster-whisper(small) / whisper.cpp | 可离线；开源免费 | small 模型 ~1GB RAM、CPU 推理慢(短句数秒)；**与 Hermes 争 2C2G 内存易 OOM**；中文童声不及国产云 | ⚠️ 勉强但高风险(内存) | ✅ | 高（模型下载/更新/调优） |
| 本地 FunASR(Paraformer) | 中文强、可流式 | 仍是本机 CPU 推理占内存；部署复杂 | ⚠️ 同左上 | ✅ | 高 |
| 微信 JS-SDK `translateVoice` | 微信内识别最准、零前端工作 | 需**公众号 appId + 后端 jsapi_ticket 签名 + 备案域名**；仅限微信内；接入重 | ✅ 云端 | 仅微信 | 中-高（需公众号资质） |

**ASR 最终推荐**：单孩低频场景**主用百度（5万次永久免费）**以实现近乎零成本；若实测童声识别率不足，**一键切讯飞**（中文童声最准、流式 partial 回显、方言最多；免费 1万次/3个月，正式期约¥1300/年），切换仅改环境变量（见 1.6 可插拔设计）。兜底：换另一家国产云（腾讯↔讯飞↔阿里互备）；**真正离线兜底不建议在本机跑模型**（OOM 风险），而是降级为文字输入（见弱网策略）。微信 JS-SDK 作为后续可选增强（仅当用户有公众号且追求极致微信体验时）。

### B. TTS 方案对比

| 方案 | 优点 | 缺点 | 2C2G 可行性 | 移动端/微信兼容 | 部署维护成本 |
|---|---|---|---|---|---|
| **云端流式 TTS**（腾讯云/讯飞/火山引擎，多音色含儿童/情感） | 音质自然；**支持流式 → 首句优先易实现**；零本机负载；中文最优 | 需密钥(服务端)；网络依赖 | ✅ 云端 | ✅ 返回 mp3/opus，`<audio>` 直播 | 低 |
| edge-tts（微软 XiaoxiaoNeural） | **免费、无需密钥、流式、中文很自然** | 非官方接口，ToS 灰区；国内连 MS 网络偶发不稳 | ✅ 云端调用 | ✅ | 极低（pip 装库） |
| 本地 Piper TTS | 极轻量(C++/onnx，~100MB RAM)、可离线、**CPU 友好** | 中文音质一般(不如云)；需自备中文嗓模型 | ✅ **唯一可行的本机 TTS** | ✅ | 中（模型 + 服务） |
| 本地 CosyVoice / GPT-SoVITS | 童声定制极佳 | **需 GPU 实时推理**，2C2G 不可能 | ❌ 不可行 | ✅ | 极高 |
| 浏览器 speechSynthesis | 零成本、已有代码 | **微信 WebView(尤其安卓)基本不可用**；音色机械 | ✅ | ⚠️ 仅桌面可用 | 零 |

**TTS 最终推荐（2026-07-22 定稿：全百度）**：主用 **百度短文本在线合成-基础音库**（5万次永久免费、零成本、音质稳定）；兜底 **edge-tts**（XiaoxiaoNeural 免费流式）；**离线兜底**用 **Piper TTS**（轻量）或浏览器 `speechSynthesis`。**不引入 GPU 模型**。百度 TTS 非句级流式，前端按句切分、逐句请求合成、队列顺序播放以模拟「首句优先」。

### C. 移动端兼容性专题（麦克风权限 + 音频格式）

1. **安全上下文**：麦克风要求 HTTPS。Railway 默认 HTTPS ✅；确保生产域名全 HTTPS（含微信内打开）。
2. **麦克风权限**：
   - 必须在**用户手势**(点按钮)内调用 `getUserMedia({audio:true})`；首次触发系统/微信授权弹窗。
   - 微信 WebView：现代版本支持 `getUserMedia`；若拒绝 → 前端 Toast 引导「在微信/浏览器设置里允许麦克风」并降级文字。
   - Chrome 移动：标准支持。
3. **录音格式自适应**（MediaRecorder mime 差异大）：
   | 环境 | 推荐 mime | 说明 |
   |---|---|---|
   | Chrome / Android Chromium | `audio/webm;codecs=opus` | 通用 |
   | Safari / 微信 iOS(WKWebView) | `audio/mp4`(AAC) | iOS 仅支持 mp4 |
   | 安卓微信(X5) | `audio/aac` / `audio/mp4` | 用 `MediaRecorder.isTypeSupported` 探测 |
   - 实现：录音前 `['audio/webm','audio/mp4','audio/aac'].filter(MediaRecorder.isTypeSupported)` 选第一个支持项。
4. **服务端转码**：为兼容各家 ASR 输入，在服务器装 **ffmpeg**，将上传音频统一转 **16kHz 单声道 PCM/WAV**（ASR 最稳格式）。短音频转码 CPU 开销极小，2C2G 无压力。
5. **播放兼容**：服务端 TTS 返回 mp3/opus，用 `<audio>` 或 Web Audio `AudioContext` 播放，微信 WebView / Chrome / Safari 全支持。**iOS 自动播放限制**：首次播放须在用户手势链内触发（点击发送/录音即手势），后续播放通常允许；`audio.play()` 包在手势回调。

### D. 部署拓扑（更新）

```
Railway (前端 + FastAPI)
  ├─ 持有 ASR/TTS 云 API 密钥(环境变量，不下发前端)
  ├─ POST /api/chat/voice → 调 云端 ASR        (不占 2C2G)
  ├─ GET  /api/chat/tts   → 调 云端 TTS(流式)   (不占 2C2G)
  └─ POST /api/chat/message (SSE) → 调 Hermes(47.242.10.160:8642)
2C2G Linux: 仅跑 Hermes (+ 可选 ffmpeg / Piper 离线兜底)
```
- **密钥安全**：云 API Secret 仅存 Railway 环境变量；前端只与同源后端通信，杜绝 CORS / 密钥泄露。
- **为何不让 2C2G 跑 ASR/TTS**：内存 2G 已被 Hermes 占用相当部分，再加载模型必 OOM；云端方案把算力外移，最稳、最省心。
- **完整推荐方案小结**：前端 MediaRecorder 采集(格式自适应) → Railway `/api/chat/voice`(ffmpeg 转码 + 云端流式 ASR) → 文本复用现有管线 → Hermes 流式回复 → 按句切分 → Railway `/api/chat/tts`(云端流式 TTS) → `<audio>` 首句优先播放。离线/失败逐级降级到文字模式。

---

## 1.6 多厂商可插拔设计（随时可切换：百度 ⇄ 讯飞 ⇄ 腾讯云 ⇄ 火山）

> 用户关切：现在选百度，以后能否轻松换成讯飞/腾讯云/其他？**结论：能，且几乎零成本——前提是按「适配器模式」落地，而非把厂商 SDK 直接写进路由。** 当前(T1/T2)仅落地百度适配器；讯飞/腾讯云/火山适配器按需求再补。

### 为什么能轻松切换
- 所有厂商在概念上 I/O 完全一致：**ASR = 音频字节 → 文本**；**TTS = 文本 → 音频流**。差异只在鉴权方式、接受的音频格式、请求协议(WebSocket/REST)、返回解析——这些都封装进各自适配器内部。
- 前端完全不感知厂商：它只调同源后端的 `/api/chat/voice` 与 `/api/chat/tts`。

### 落地结构（计划 T1/T2 即按此实现）
```
app/speech/
  base.py            # 抽象：class ASRProvider / class TTSProvider + access_token 缓存 + Mock 降级
  baidu_asr.py       # 百度短语音识别标准版（REST POST vop.baidu.com/server_api，dev_pid=1537）✅ 已实现(T1)
  baidu_tts.py       # 百度短文本在线合成（REST POST tsn.baidu.com/text2audio，度丫丫 per=4）✅ 已实现(T2)
  baidu_tts_stream.py# 百度流式文本在线合成（WebSocket，首句优先/边合成边播放，童声 per=110）✅ 已实现
  factory.py         # get_asr_provider()/get_tts_provider() 读 SPEECH_*_PROVIDER / SPEECH_TTS_MODE 选择
  # 注：讯飞/腾讯云/edge_tts 适配器在全百度架构下非必需，预留位暂不实现
```
- `chat_proxy.transcribe_audio()` / `synthesize_speech()` 改为调用 factory 返回的适配器，**路由层/前端零改动**。
- 环境变量切换：`SPEECH_ASR_PROVIDER=baidu|iflytek|tencent`、`SPEECH_TTS_PROVIDER=baidu|iflytek|...`；百度密钥 `BAIDU_API_KEY` / `BAIDU_SECRET_KEY` / `BAIDU_APPID`（已配 Railway）；讯飞密钥 `XF_APPID`/`XF_API_KEY`/`XF_API_SECRET`（预留）。

### 切换成本量化
- **百度 ↔ 讯飞（仅改配置）**：改 `SPEECH_ASR_PROVIDER`/`SPEECH_TTS_PROVIDER` + 填对应密钥(env)，重新部署即可。**路由、前端、业务逻辑一行不改。**（前提是目标适配器已存在；百度已实现，讯飞/腾讯云待补约半天/个。）
- **ASR 与 TTS 可独立混搭**：如 `ASR=讯飞 + TTS=火山`，互不影响。

### 为什么「归一化」让切换更稳
- **输入侧**：计划已在服务端用 ffmpeg 将任意上传音频统一转 **16k 单声道 wav**，各厂商收到的格式一致 → 切换厂商不必改前端录音格式。
- **输出侧**：TTS 端点只流式返回音频字节 + `Content-Type`，前端 `<audio>` 通吃 mp3/wav/opus → 切换厂商不必改播放代码。

### 切换时唯一要「重新评估」的非代码项
- 音色/识别率会有差异（产品体验，非代码）；
- 免费额度语义不同（百度永久 vs 讯飞3个月有效 vs 腾讯云按月过期）→ 成本画像变化，但代码不变。

### 1.7 实现校验与官方文档端点（2026-07-22 对照 cloud.baidu.com/doc/SPEECH 校验）

> 本方案适配器**已按官方文档逐项校验**（非凭记忆），并修复一处会导致生产彻底失败的错误。

**官方端点清单（已核验）**
| 能力 | 端点 | 鉴权 | 说明 |
|---|---|---|---|
| 短语音识别（标准版） | `POST https://vop.baidu.com/server_api` | body `token`=access_token | `dev_pid=1537`（普通话+标点）；60s 内、16k 单声道 |
| 短语音识别（极速版） | `POST https://vop.baidu.com/pro_api` | body `token` | `dev_pid=80001`（强制）；快 2×、准 +15%，另算额度 |
| 短文本在线合成 | `POST https://tsn.baidu.com/text2audio` | `tok`=access_token（表单） | `per=4`(度丫丫)/`aue=3`(mp3)；tex≤1024GBK 字节 |
| 流式文本在线合成 | `WebSocket wss://aip.baidubce.com/ws/2.0/speech/publiccloudspeech/v1/tts?access_token=&per=` | query `access_token`/`per` | 帧：`system.start`→`text`→`system.finish`；收 binary 音频帧→`system.finished`；`per=110`(度小童童声) |
| access_token | `GET https://aip.baidubce.com/oauth/2.0/token` | `client_id`=API Key, `client_secret`=Secret Key | 有效期 30 天，已做内存缓存 |

**关键修正（生产必挂 bug 已修）**
- ⚠️ 初版 ASR 端点误写为 `aip.baidubce.com/rpc/2.0/ai_custom/v1/ws_0`（非短语音识别接口）→ 已改为 `vop.baidu.com/server_api`。
- TTS 由 GET 拼接 query 改为 **POST 表单**（`data=`），规避 `tex` 中 `+`/`&`/`=` 因单次 urlencode 丢失的官方提示坑。
- 新增 `baidu_tts_stream.py`（WebSocket 流式），天然实现「边合成边播放 / 首句优先」，配合 T3(SSE)+T5(前端) 达最低延迟；默认 `SPEECH_TTS_MODE=short` 走整句，设 `stream` 启用。

**环境变量（全百度）**
```
SPEECH_ASR_PROVIDER=baidu
SPEECH_TTS_PROVIDER=baidu
SPEECH_TTS_MODE=short|stream      # 默认 short；stream=WebSocket 流式(童声)
BAIDU_API_KEY= / BAIDU_SECRET_KEY= / BAIDU_APPID=   # 已配 Railway
BAIDU_TTS_PER=110                 # 童声(度小童)；短文本默认 4(度丫丫)，可统一设 110
```

**验证**：`scripts/test_speech_baidu_requests.py`（mock 注入，无需真密钥）覆盖端点/请求体/响应解析/流式帧协议/工厂降级，24 项全通过。

---

## 2. 分模块实现方案

### 2.1 语音输入（服务端 ASR）
- **采集**：`navigator.mediaDevices.getUserMedia({audio:true})` + `MediaRecorder`（用 `MediaRecorder.isTypeSupported` 选 mime：Chrome/FF=`audio/webm`，Safari=`audio/mp4`，微信 iOS=`audio/mp4`，安卓 X5 优先 `audio/aac`）。录音停止后 `Blob` → `FormData` 上传。
- **新端点** `POST /api/chat/voice`（multipart `audio` + `session_id`）：
  - `chat_proxy.transcribe_audio(bytes, fmt)` → 调用 ASR 引擎 → 返回 `{text, confidence}`。
  - **ASR 引擎选型（全百度）**：主用 **百度短语音识别-中文普通话**（5万次永久免费，REST 最简，无需客户端的流式 SDK）；兜底 重试 + 降级文字输入。
  - 返回 `text` 后前端填入输入框并**自动发送**（走 `sendChatMessage`），即复用现有管线。
- **实时回显与纠错（MVP）**：ASR 返回整句文本后，显示在「可编辑确认气泡」中，用户可改字后点发送（纠错）。**增强项**：改用 **百度实时语音识别**（独立 SKU，WebSocket 流式 partial result），录音过程中实时回显 interim 文本。MVP 先整句（短语音识别标准版），增强项后做。
- **降噪**：`getUserMedia` 的 `autoGainControl/noiseSuppression/echoCancellation:true`（浏览器/WebView 原生支持）；如需更强，可在服务端用 `webrtcvad`/RNNoise 做语音端点检测(VAD)裁剪静音段，降低 ASR 误识与计费。

### 2.2 语音输出（服务端流式 TTS）
- **新端点** `GET /api/chat/tts?text=<句>`（或 POST）：`chat_proxy.synthesize_speech(text)` → 调用 TTS → 以 `audio/mpeg`(或 opus) **分块流式**返回（`StreamingResponse`）。
- **TTS 引擎选型**：主用 **百度流式文本在线合成（WebSocket，童声 per=110，边合成边播放）**；默认 `SPEECH_TTS_MODE=short` 走 **百度短文本在线合成（REST 整句，度丫丫 per=4）** 亦可。兜底 **edge-tts**(XiaoxiaoNeural，免费流式，国内网络一般可用)；最后兜底 浏览器 `speechSynthesis`（仅桌面 Chrome/Edge/Safari）。
- **流式播放 + 首句优先**：前端收到 Hermes 流式文本后，按句边界（`。！？\n`）切分；**第一句一完整立即请求其 TTS 并开始播放，同时后续句子继续生成/TTS** → 首句优先。用队列管理多句顺序播放。
- **音量控制**：`<audio>` 或 Web Audio `GainNode` 绑定音量滑块。
- **中断与恢复（barge-in）**：点麦克风/停止键 → `audio.pause()+currentSource.stop()` 取消当前播放并立即开始录音；播放条提供 暂停/继续 按钮（记录已播放 offset，恢复时 `audio.currentTime` 续播）。

### 2.3 后端流式改造（支撑低延迟）
- `chat_proxy.py` 新增 `call_hermes_stream(messages, session_id)`：`stream:True`，解析 Hermes 的 SSE(`data:{...}`/`[DONE]`)，`yield` 文本增量。
- `main.py` 的 `POST /api/chat/message` 改为返回 `text/event-stream`：`data: {"content":<增量>,"pet_mood":<当前>}`，结尾 `data: [DONE]`。（⚠️破坏性：前端读取逻辑需同步改；做好版本兼容或一次性切换。）
- 实施期用 `curl` 验证 Hermes 能返回 `stream:True` 的 SSE（companion-chat-plan.md 已规划流式，但当前代码 `stream:False`，先确认服务端支持）。

### 2.4 前端 UI 交互设计
- **输入栏重做**（`index.html` 3965-3968 区域）：
  - 模式切换控件：⌨️文本 / 🎤语音 切换按钮（同一 `chat-input-bar`，切换不清除 `chatMessages` 与 `session_id`）。
  - 语音模式：大圆形麦克风按钮，三态：
    - 空闲（idle）：静态麦克风图标
    - 录音中（recording）：红色脉冲圈 + 波形/声波动画(CSS `@keyframes` + `AnalyserNode` 实时振幅)
    - 识别中（recognizing）：转圈 spinner + 「识别中…」
  - **权限引导**：首次 `getUserMedia` 被拒 → 顶部 Toast「需要在浏览器/微信里允许麦克风权限」+ 图文引导；微信内若限制 → 提示「可改用键盘语音或文字」。
- **语音状态指示器**：全局小条显示 聆听中/思考中/说话中（与 `pet_mood` 联动，复用 `updateChatMood`）。
- 每条小龙消息保留 🔊 按钮（手动重听）；自动朗读开关（设置项）。

### 2.5 语音↔文本 无缝切换
- 两者共用 `chatMessages` 容器、`chatSessionId`、`session_id`；切换仅改输入控件形态，历史与上下文完全保留。
- 语音产生的消息与文字消息在 UI 上无差别（都是 `chat-msg-user`/`chat-msg-dragon`），对话链路连续。

### 2.6 浏览器兼容性与 Polyfill 策略
| 能力 | Chrome/Edge | Firefox | Safari | 微信 WebView | 策略 |
|---|---|---|---|---|---|
| `getUserMedia` | ✓ | ✓ | ✓ | ✓(HTTPS) | 特性检测，缺失→隐藏麦克风强制文字 |
| `MediaRecorder` | ✓webm | ✓webm | ✓mp4 | iOS✓ / 安卓X5✓(选 aac/mp4) | `isTypeSupported` 动态选 mime |
| Web Speech 识别 | ✓ | ✗ | 部分 | ✗ | **不依赖**；服务端 ASR 替代 |
| `speechSynthesis` | ✓ | ✓ | ✓ | 安卓基本✗ | 仅作桌面 TTS 兜底 |
| `<audio>`/WebAudio | ✓ | ✓ | ✓ | ✓ | 主播放通道 |
- Polyfill：不引第三方 polyfill（API 无可靠 polyfill）；以**特性检测 + 优雅降级到文字模式**为主策略。

### 2.7 弱网降级策略
- **离线**：`navigator.onLine` + `online/offline` 事件 → 显示离线条；待发消息入队，恢复后自动补发。
- **ASR 上传失败**：指数退避重试 3 次 → 仍失败提示「识别失败，请重试或用文字」→ 自动回退文字模式。
- **TTS 拉取失败**：依次降级 服务端TTS→edge-tts→`speechSynthesis`→纯文字(保留🔊重试)。
- **Hermes/后端超时**：现有 `chat_proxy` 已有超时兜底文案，补充「网络恢复后重试」提示。

### 2.8 Railway 对语音服务的支持评估
- Railway 仅提供 **Web 托管 + HTTPS**，无 ASR/TTS/音频处理服务、无 GPU、文件系统临时。**不要把 ASR/TTS 跑在 Railway 上**。
- 推荐：ASR/TTS 走**云端 API**（服务端用 `httpx` 调用，密钥存 Railway 环境变量），由 Railway 后端代理转发（避免浏览器直连云 API 的 CORS/密钥暴露）。
- 音频上传体积：单条录音 ≤~500KB，Railway 带宽足够；`/api/chat/voice` 用普通 POST 即可，无需特殊配置。
- Hermes 仍在 `47.242.10.160:8642`（经 `HERMES_API_URL` 环境变量），Railway 后端跨服调用，延迟可接受（同区域）。

---

## 3. 小程序 / 原生 App 可行性评估（用户要求）

| 维度 | 微信小程序 | 原生 App(iOS/Android) | 维持 Web(WebView) |
|---|---|---|---|
| 语音可靠性 | **最高**（原生 `RecorderManager`+同声传译插件/JS-SDK，微信内无 WebView 限制） | 最高（原生 Speech 框架） | 中（MediaRecorder+服务端ASR 已可用，但低端安卓微信偶有兼容坑） |
| 改动成本 | **高**：UI 需重写为 WXML/WXSS/JS，需小程序账号+审核 | 极高：双端开发+上架+长期维护 | **低**：本方案增量改造，复用 95% 代码 |
| 后端复用 | **完全复用**（SSE `/api/chat/message`、新增 `/api/chat/voice`、`/api/chat/tts` 全是 HTTP，小程序直接调） | 完全复用 | 完全复用 |
| 推荐度 | 阶段二候选 | 不推荐(投入产出比低) | **阶段一首选** |

**推荐方案与理由**：
1. **阶段一（现在）维持 Web**：本方案用「MediaRecorder+服务端ASR/TTS」绕开了 Web Speech 在微信 WebView 不可用的问题，成本最低、后端零重构、上下文连续性天然保证。先上线实测真实微信环境。
2. **阶段二（按需）迁移微信小程序**：**当且仅当** 真机测试发现部分低端安卓微信 WebView 的麦克风/音频仍不稳定时，再开小程序。因后端 API 已 HTTP 化、与客户端解耦，**小程序只需重写 UI 层**，后端与 ASR/TTS 完全复用，迁移路径清晰、风险可控。
3. **原生 App 不推荐**：投入产出比低，且会丧失「网页即开即用、免安装」的优势。

---

## 4. 任务分解（trellis 式，实施时建任务卡）

| # | 任务 | 关键改动文件 | 验收 |
|---|---|---|---|
| T1 | 后端 ASR 接入 ✅ | `main.py`(`/api/chat/voice`) + `_transcode_to_wav`(ffmpeg→16k mono wav) + `app/speech/baidu_asr.py` + Railway 密钥已配 | curl/前端上传录音返回正确中文文本；本地 mock 9/9 通过 |
| T2 | 后端 TTS 接入 ✅ | `main.py`(`/api/chat/tts`) + `app/speech/baidu_tts.py`(短文本整句，per=4 度丫丫) + `baidu_tts_stream.py`(WebSocket 流式童声 per=110) | 浏览器/Postman 播放返回 audio/mpeg；`SPEECH_TTS_MODE=stream` 启用流式 |
| T3 | 后端改 SSE 流式 | `chat_proxy.py`(call_hermes_stream) + `main.py`(改返回 media_type) | 前端能逐字收到 content |
| T4 | 前端采集+上传+识别态 | `index.html`(录音按钮/状态机/MediaRecorder) | 微信内可录音→识别→自动发送 |
| T5 | 前端流式 TTS 播放 | `index.html`(句切分+队列+音量+中断恢复) | 首句优先播放、可中断续播 |
| T6 | 模式切换 UI+权限引导 | `index.html`(切换控件/Toast/动画) | 文本↔语音切换无刷新、历史保留 |
| T7 | 兼容/降级/弱网 | `index.html`+`chat_proxy.py` | 拒权/离线/失败均优雅降级 |
| T8 | 联调+真机(微信)测试 | 全量 | 微信内端到端语音对话可用 |
| T9 | 文档+trellis 地图更新 | `docs/` + `.workbuddy/memory` | 更新导航总结 |

### 4.1 后端路由契约（T1/T2 已实现，2026-07-22）

**POST /api/chat/voice（ASR）**
- 入参（二选一）：
  - `multipart/form-data`：`file` = 录音文件（推荐，浏览器 MediaRecorder 直传）
  - `application/x-www-form-urlencoded` 或 JSON：`audio_base64` + `fmt`（webm/mp4/m4a…）
- 流程：接收 → ffmpeg 转码 16k 单声道 wav → `get_asr_provider().recognize()` → 文本
- 成功：`{"text": "...", "confidence": ...}`；识别为空：`{"text":"", "empty":true}`
- 失败：`{"error": "..."}`（含 ffmpeg 缺失/转码失败/网络错误可读提示），HTTP 500
- 无密钥时自动走 `MockASR`（返回 `[mock-asr]...`），便于联调

**POST /api/chat/tts（TTS）**
- 入参（JSON）：`{"text": "...", "per": 4(可选音色)}`
- 流程：`get_tts_provider().synthesize(text)` → 音频字节
- 成功：HTTP 200，`Content-Type: audio/mpeg`，body=mp3 字节
- 失败：`{"error": "..."}`，HTTP 500；无密钥走 `MockTTS`（ID3 头占位字节）
- 文本安全上限 512 字（百度短文本单次 1024GBK 字节约束）

> 前端调用顺序（语音对话一次）：录音 → POST `/api/chat/voice` 得文本 → POST `/api/chat/message` 得小龙回复 → POST `/api/chat/tts` 得语音 → `<audio>`/Web Audio 播放。

---

## 5. 关键技术坑与决策点
- **Hermes 流式需先验证**：当前 `call_hermes` 用 `stream:False`，T3 前用 `curl` 确认 `:8642/v1/chat/completions` 支持 `stream:True` 的 SSE，否则 T3 退回「整段返回+TTS 整段流式」也可。
- **ASR/TTS 密钥安全**：云 API 密钥仅存 Railway 环境变量，**绝不下发前端**；前端只与同源后端通信。
- **句切分正则**：用 `/(?<=[。！？!?\n])/` 切分，避免把半句话送 TTS 导致破音。
- **微信 WebView 自动播放限制**：首次播放需用户手势触发（点麦克风/发送即手势），后续 TTS 播放因在同一手势链内通常允许；iOS 需 `audio.play()` 在用户事件回调内。
- **2C2G 资源**：Hermes 已占一定内存，ASR/TTS 走云端不占本机；若未来自托管 TTS(童声)需另购 GPU 服务器（阶段二以后）。
- **starlette 版本 `JSONResponse` 参数名**：生产 `requirements.txt` 锁 `fastapi==0.109.0`（starlette 0.35 仍接受 `status=` 别名），但本地测试环境为 `starlette 1.0.1` 已移除该别名，必须用 `status_code=`。所有返回统一用 `status_code=` 以兼容两版本（见 `app/main.py` 已实现）。
- **Railway 无 ffmpeg**：默认 Python 镜像不含 ffmpeg，已在仓库根加 `nixpacks.toml`（`[phases.setup] aptPkgs=["ffmpeg"]`）。本地若也缺 ffmpeg，路由会返回清晰错误提示，不会静默失败。

---

## 6. 验收清单（概要）
- [ ] 微信内长按/点击麦克风→录音→实时动画→松手识别→文本自动进对话→小龙流式回复→语音播放
- [ ] 文本/语音切换不丢上下文、不刷新、历史连续
- [ ] 音量滑块、暂停/继续、点麦打断生效
- [ ] 拒权/无网/ASR失败 均有降级提示且不崩
- [ ] Chrome/Edge/Firefox/Safari/微信WebView 至少主路径可用
- [ ] 后端 SSE 流式返回正常，首句优先播放体感 < 1.5s

---

## 7. 不在本次范围（明确边界）
- 自托管童声 TTS(GPU)、流式 ASR interim 实时回显（列为增强项，MVP 后做）
- 微信小程序/原生 App 实际开发（仅评估+预留后端复用，阶段二再启动）
- 多用户/家长端听音（已有后续路线，不在此方案）
