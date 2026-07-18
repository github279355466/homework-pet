<!--
  plan.md — 小龙陪聊系统（Companion Chat）
  创建: 2026-07-18
  修改记录:
    2026-07-18 | 初版 liuchenbull | grill 收敛后的完整执行计划
    2026-07-19 | v1.1 补充：语音交互链路 + Hermes 远程部署变体 + TTS 配置
-->
# 小龙陪聊系统（Companion Chat）执行计划

## 1. 项目总览

### 1.1 定位

在 homework-pet 现有宠物养成系统上，**新增一个长期陪伴的聊天系统**。Hermes Agent 作为大脑（带长期记忆的用户画像 + 作业辅导 skill），前端作为"带麦的喇叭"交互通道。

### 1.2 架构总拓扑

```
微信内置浏览器（单用户）
    │
    ├─ 浏览器：文字输入框（首期，微信输入法转文字）
    │         + 小龙立绘（表情随对话状态切换）
    │         + 今日任务卡片
    │         + 语音播放（P1.5 起）
    │
    ▼
homework-pet FastAPI :5001
    ├─ /api/chat/proxy  ← 新增：转发 + 安全过滤
    ├─ /api/pet/mood    ← 现有：宠物状态
    ├─ /api/tasks/*     ← 现有：作业任务
    └─ /api/pets/*      ← 现有：宠物养成
    │
    ▼
Hermes API Server :8642
    ├─ profile: homework-child
    ├─ model: deepseek-v4-flash (via OpenRouter 或直连 DeepSeek)
    ├─ tools: [web_search, memory, session_search, tts]
    ├─ context: 16K + compression on
    ├─ memory: user_profile_enabled = true
    ├─ tts: 启用音频合成（P1.5 起）
    └─ cron: 每晚 22:00 生成学习总结归档
```

### 1.3 部署拓扑

> **两种变体可选**：A（同机部署）适合开发/小流量期；B（Hermes 远程）适合生产/大流量期。

#### 变体 A：同机部署（开发 / 小流量期，推荐起步）

```
                    nginx :443
                        │
         ┌──────────────┼──────────────┐
         │              │              │
    location /     location /static/   location /api/chat/
         │              │              │ (proxy bypass)
         ▼              ▼              ▼
homework-pet        静态文件      Hermes API Server
FastAPI :5001                      :8642

systemd（同一台 2C2G Linux）:
    ├── homework-pet.service  (python app/main.py)
    └── hermes-api.service    (hermes api-server)

内存预算:
    nginx           ~20 MB
    FastAPI         ~80 MB (峰值 ~120 MB)
    Hermes 进程     ~400 MB (idle)
    Hermes 推理时   +200 MB (context buffer)
    ────────────────────────
    峰值合计        ~700 MB  ← 2G 内可行
```

#### 变体 B：Hermes 远程部署（生产 / 大流量期）

```
                    公网用户
                       │
          ┌────────────┴────────────┐
          │                         │
    用户手机微信             其他微信用户
          │                         │
          └────────────┬────────────┘
                       ▼
             本地 nginx :443（轻量机 / Railway）
                       │
          ┌────────────┼────────────┐
          │            │            │
     location /   location /static/   location /api/chat/
          │            │            │ (proxy bypass)
          ▼            ▼            ▼
 homework-pet      静态文件     Hermes API Server
 FastAPI :5001                    (公网云服务器)
                                     │
                                homework-child profile
                                + user_profile
                                + session DB
                                + TTS tool

systemd（本地服务器）:
    └── homework-pet.service  (仅此一个，省内存)

systemd（Hermes 云端服务器）:
    └── hermes-api.service    (独立扩容)

内存预算（本地）:
    仅 nginx + FastAPI ~150 MB  ← 极轻，可跑在最低配
```

**选型决策树**：

```
并发用户 < 5 ─────────────────► 变体 A（同机）
并发用户 > 5 ─────────────────► 变体 B（分开）
Hermes 推理延迟敏感 ───────────► 变体 B（云端可用更强的 CPU）
运维复杂度优先 ───────────────► 变体 A（一个服务器）
```

### 1.4 语音交互链路设计

> **首期 P0 仅文字聊天**，语音为 P1.5 目标。链路在此设计好，前端预留接口。

#### 1.4.1 微信浏览器 (X5 内核) 语音能力

| 能力 | X5 支持 | 方案 |
|------|---------|------|
| `webkitSpeechRecognition` (STT) | ❌ 不支持 | 不可用 |
| `speechSynthesis` (TTS) | ⚠️ 部分，中文不稳定 | 仅做兜底 |
| 输入法语音转文字 | ✅ 微信自带 | **主要输入方案** |
| 微信 JS-SDK 录音 | ⚠️ 需公众号认证 | P2 备选 |

#### 1.4.2 完整语音链路（P1.5 实施）

```
[用户长按输入框说话]
        │       微信输入法 → 语音转文字（原生，免费）
        ▼
[文字填入输入框] ─── 用户点发送 ───►
        │
        ▼
前端 POST /api/chat/message { text, session_id }
        │
        ▼
chat_proxy.py 安全过滤 + 注入 [PET MOOD] [TODAY TASKS]
        │
        ▼
Hermes API Server → LLM 推理（文字回复 + 调用 TTS 工具）
        │
        ├── 文字: "这道题我们可以换个角度想想哦～"
        └── TTS:  Hermes 调用 text_to_speech 合成音频
        │
        ▼
返回 JSON: { text, audio_url, pet_mood }
        │
        ▼
前端: 显示文字气泡 + 🔊 按钮 (audio 标签播放)
        │
        └── TTS 不可用降级: speechSynthesis 朗读
```

#### 1.4.3 Hermes TTS 工具配置

```yaml
# ~/.hermes/config.yaml（变体 A：本机 / 变体 B：远程服务器）
tts:
  provider: "openai"          # 或 "nous", "elevenlabs", "edge"
  voice: "nova"               # nova(可爱女声)/alloy/echo/fable/onyx/shimmer
  model: "tts-1"              # 或 "tts-1-hd"（更高质量）
  cache_enabled: true         # 同一段文字不重复合成
  max_chars_per_request: 200  # 小学生回复不会太长
```

#### 1.4.4 音频回传方案

| 方案 | 说明 | 推荐 |
|------|------|------|
| **A. Hermes → 文件 → URL** | TTS 合成保存到 /tmp → 返回 URL → nginx static 反代 | ⭐ 推荐 |
| B. Hermes → base64 → JSON | 音频 base64 编码嵌在 SSE chunk 里 | 可行但包变大 |
| C. Hermes SSE 推送 | TTS 完成后 SSE 事件推送音频 URL | 最优雅但复杂 |

**采用方案 A**：Hermes 端 TTS 合成后保存为文件，返回相对 URL (`/tts/xxx.mp3`)，nginx 直接 serve。前端 `<audio src="/tts/xxx.mp3" autoplay>`。

#### 1.4.5 降级策略

```
TTS 正常 ──audio 标签播放音频
    │
    ├── Hermes TTS 调用超时 (>5s) ──► 仅显示文字，不阻塞
    │
    ├── Hermes TTS API 不可用 ──► browser speechSynthesis 朗读
    │
    └── 微信浏览器 autoplay 限制 ──► 🔊 按钮让用户点击播放
```

---

## 2. Hermes Agent 配置

### 2.1 创建专用 profile

```bash
hermes profile create homework-child
```

### 2.2 模型配置（DeepSeek V4 Flash）

```bash
hermes --profile homework-child config set model.provider openrouter
hermes --profile homework-child config set model.default deepseek/deepseek-chat
hermes --profile homework-child config set model.context_length 16384
```

> **说明**: `deepseek/deepseek-chat` 在 OpenRouter 上是 DeepSeek V3。若 OpenRouter 无 V4 Flash，改用直连 DeepSeek 官方 API：
>
> ```bash
> hermes --profile homework-child config set model.base_url https://api.deepseek.com/v1
> hermes --profile homework-child config set model.api_key sk-xxxxxxxx
> hermes --profile homework-child config set model.default deepseek-chat
> ```

### 2.3 工具集配置

```bash
# P0: 只保留 web_search + memory + session_search
hermes --profile homework-child config set tools.enabled "[\"web_search\", \"memory\", \"session_search\"]"

# P15: 加入 tts
hermes --profile homework-child config set tools.enabled "[\"web_search\", \"memory\", \"session_search\", \"tts\"]"
```

> **重要**: Hermes 工具集变更需重启 session（新 session 生效）。API server 端重启后所有新请求自动用新配置。

### 2.4 Memory & Session 配置

```bash
hermes --profile homework-child config set memory.user_profile_enabled true
hermes --profile homework-child config set compression.enabled true
hermes --profile homework-child config set compression.threshold 0.60
hermes --profile homework-child config set compression.target_ratio 0.25
hermes --profile homework-child config set session.persist true
```

### 2.5 API Server 配置

```bash
hermes --profile homework-child config set api_server.enabled true
hermes --profile homework-child config set api_server.port 8642
hermes --profile homework-child config set api_server.host 127.0.0.1
hermes --profile homework-child config set api_server.key "GENERATE_A_RANDOM_SECRET"
```

### 2.6 TTS 工具配置（P1.5）

```bash
hermes --profile homework-child config set tts.provider "openai"
hermes --profile homework-child config set tts.voice "nova"
hermes --profile homework-child config set tts.model "tts-1"
hermes --profile homework-child config set tts.cache_enabled true
hermes --profile homework-child config set tts.max_chars_per_request 200
hermes --profile homework-child config set tts.cache_dir "/tmp/hermes_tts_cache"
```

> **备注**: 如果使用 Nous Portal Tool Gateway（付费订阅），TTS 自动启用无需单独配置。如果使用自配 TTS API（OpenAI / 讯飞 / edge-tts），在 `~/.hermes/.env` 中设好对应 API Key。

### 2.7 Cron 配置（每日学习总结）

```bash
hermes --profile homework-child cron create "0 22 * * *" \\
  --prompt "回顾今天的所有对话，提取：1) 今天学了什么知识点；2) 哪里卡住了；3) 鼓励成功的地方；4) 明天建议重点。将结果更新到 user_profile 的 latest_daily_summary 字段，并归档学习记录到 memories/learning-log.md。语气温暖，像一个了解小朋友进步的长辈。" \\
  --name "daily-learning-summary"
```

---

## 3. System Prompt 设计

### 3.1 角色设定（写死到 Hermes profile 的 system_prompt）

你是「作业小龙」的传声伙伴，一个温柔耐心的学习陪伴助手。

【世界观】
你是一只住在小主人公手机里的小龙的"传话筒"。小龙不能说话，但你能代替它和小朋友交流。你可以用「小龙说：……」开头，也可以直接用朋友的口吻聊。

【核心原则】
1. 始终用鼓励式教育：无论小朋友答对答错，先肯定努力和思考过程，再引导。
2. 绝不直接给答案：遇到"这类题怎么做"时，用提问引导小朋友自己思考。
3. 语气贴近小学生：用"我们"代替"你"、用"小龙觉得……"代替权威式说教。
4. 表情互动：每句话可以搭配小龙的表情变化（通过前端表情字段控制）。

【作业辅导策略】
遇到题目先问"你是怎么想的？"，肯定或部分肯定后再给 Hint 而非答案；遇到困难时降低难度给出类似简单例子；遇到放弃时先聊卡住的原因、认可情绪，然后拆分任务。

【角色边界 - 严格遵守】
只和小朋友聊学习、爱好、校园生活、成长烦恼、自然科学、文艺创作。以下话题必须拒绝并引导回学习：
- A. 色情/暴力/自残/恐怖 → "这个话题我们不适合聊哦，去看看今天的作业吧？"
- B. 政治/宗教 → "小龙不懂这些大问题呢，我们来做题吧！"
- C. 心理伤害话题 → "这个问题很重要，要跟爸爸妈妈或老师好好聊聊。先让小龙陪你做一题轻松一下？"
- D. 金钱/充值/交易 → "小龙只管学习的事，钱的事找爸妈哦～"

【记忆】
每次对话你都能看到之前和小朋友的聊天记录，请记住之前卡过的地方。每天晚上小龙会整理一份学习日记，第二天你会记得"昨天进退位没掌握好"。小朋友的名字和偏好存在系统提示的 [USER PROFILE] 部分，每次都要参考。系统提示的 [TODAY TASKS] 部分是今天的作业清单，借机把聊天引向完成任务。

【语音输出】(P1.5 起)
你的回复会被合成语音朗读，请确保句子简短（适合朗读，不超过 50 字）、避免生僻字和同音歧义字、不用 markdown 符号（纯自然语言）、每句话结尾加适当停顿。

### 3.2 动态 System Prompt 切片

Hermes system prompt 是静态的，但每轮对话需要注入**动态内容**：

| 动态字段 | 内容 | 注入方式 |
|---------|------|---------|
| `[USER PROFILE]` | Hermes 自己维护的用户画像 | Hermes memory 系统自动注入 |
| `[TODAY TASKS]` | 今天的作业卡片（JSON） | chat_proxy.py 拼进 system message 末尾 |
| `[PET MOOD]` | 小龙当前心情/状态 | chat_proxy.py 拼进 system message 末尾 |
| `[SESSION SUMMARY]` | cron 日记 summary | Hermes cron 每天更新到 profile |

---

## 4. homework-pet FastAPI Proxy 端

### 4.1 新增模块结构

```
app/                              # 现有
├── chat_proxy.py                  # 🆕 新增：Hermes API 调用 + 安全过滤 + 语音路由
├── tts_server.py                  # 🆕 新增(P1.5)：TTS 缓存文件 serving + 清理
├── main.py                        # ✏️ 修改：挂载 /api/chat/* + /tts/*
├── templates/index.html           # ✏️ 修改：新增聊天面板 + 语音播放
└── static/chat/                   # 🆕 新增：聊天相关 JS 和 CSS
```

### 4.2 chat_proxy.py 核心实现

```python
# app/chat_proxy.py
import os, re, json, time, httpx
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, Response

HERMES_API_URL = os.getenv("HERMES_API_URL", "http://127.0.0.1:8642/v1/chat/completions")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
TTS_ENABLED = os.getenv("TTS_ENABLED", "false").lower() == "true"

# 安全过滤 - 黑洞词黑名单
BLACKLIST_PATTERNS = [
    r"处女|做爱|强奸|色情|激情",
    r"自杀|割腕|跳楼|杀人|血腥|恐怖.*故事|黑暗.*童话",
    r"习近平|毛泽东|法轮功|天安门.*事件|台独|新疆.*独",
]
BLACKLIST_RE = re.compile("|".join(BLACKLIST_PATTERNS), re.IGNORECASE)
SEARCH_BLOCKLIST_RE = re.compile(r"成人|色情|暴力|自残|自杀|恐怖", re.IGNORECASE)

# 频率限制（内存级）
_RATE_LOG = []
_RATE_MAX = 100       # 10 分钟内最多 100 条
_RATE_WINDOW = 600    # 10 分钟（秒）
MAX_INPUT_LENGTH = 500

def check_rate_limit() -> bool:
    now = time.time()
    _RATE_LOG[:] = [t for t in _RATE_LOG if now - t < _RATE_WINDOW]
    if len(_RATE_LOG) >= _RATE_MAX:
        return False
    _RATE_LOG.append(now)
    return True

async def filter_input(text: str) -> tuple:
    if BLACKLIST_RE.search(text):
        return "", True
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
    return text, False

async def call_hermes(messages, session_id=None, stream=True, enable_tts=False):
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": messages,
        "stream": stream,
        "temperature": 0.8,
    }
    if session_id:
        payload["session_id"] = session_id
    if enable_tts:
        payload["enable_tts"] = True  # P1.5 启用 TTS 工具

    headers = {"Authorization": f"Bearer {HERMES_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        if stream:
            async with client.stream("POST", HERMES_API_URL, json=payload, headers=headers) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        yield chunk
        else:
            resp = await client.post(HERMES_API_URL, json=payload, headers=headers)
            yield resp.json()

def build_system_prompt(pet_mood: dict, today_tasks: list) -> str:
    base = HERMES_BASE_SYSTEM_PROMPT
    task_str = "\n".join([f"- {t['name']}（{t.get('category','任务')}）" for t in today_tasks])
    pet_str = f"小龙当前状态：心情{pet_mood.get('mood',50)} 饱腹{pet_mood.get('hunger',50)} 亲密度{pet_mood.get('bond',50)}"
    return base + f"\n\n[PET MOOD]\n{pet_str}\n\n[TODAY TASKS]\n{task_str}"

def detect_mood_from_text(current_chunk: str, full_text: str) -> str:
    if any(w in full_text for w in ["太棒了", "真厉害", "做得很好", "你真聪明"]):
        return "happy"
    if any(w in full_text for w in ["没关系", "下次一定行", "慢慢来", "别着急"]):
        return "encourage"
    if any(w in full_text for w in ["想一想", "试试看", "换个角度"]):
        return "thinking"
    if any(w in full_text for w in ["不适合聊", "这个问题我们"]):
        return "gentle_refuse"
    return "normal"
```

### 4.3 main.py 新增路由

```python
# 在 main.py 追加
from fastapi.responses import FileResponse
from chat_proxy import filter_input, call_hermes, check_rate_limit, build_system_prompt, detect_mood_from_text

TTS_CACHE_DIR = os.getenv("TTS_CACHE_DIR", "/tmp/hermes_tts_cache")

@app.post("/api/chat/message")
async def chat_message(request: Request):
    """文字消息入口（主要通道）"""
    data = await request.json()
    user_text = data.get("text", "").strip()
    session_id = data.get("session_id", "kid_xiaoming")
    history = data.get("history", [])

    if not check_rate_limit():
        return JSONResponse({
            "blocked": True,
            "reply": "小龙说：你说得太快啦，让小龙头休息一下～ 🐢",
            "pet_mood": "overwhelmed"
        })

    clean_text, blocked = await filter_input(user_text)
    if blocked:
        return JSONResponse({
            "blocked": True,
            "reply": "小龙说：这个话题我们不适合聊哦，去看看今天的作业吧？",
            "pet_mood": "gentle_refuse"
        })

    pet_mood = get_pet_current_mood()
    today_tasks = get_today_tasks()
    system_msg = build_system_prompt(pet_mood, today_tasks)
    messages = [{"role": "system", "content": system_msg}] + history + [{"role": "user", "content": clean_text}]

    enable_tts = TTS_ENABLED
    async def event_stream():
        full_reply = ""
        audio_url = None
        async for chunk in call_hermes(messages, session_id, stream=True, enable_tts=enable_tts):
            try:
                chunk_data = json.loads(chunk)
                delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_reply += content
                    mood = detect_mood_from_text(content, full_reply)
                    yield f"data: {json.dumps({'content': content, 'pet_mood': mood})}\n\n"
                if "audio_url" in delta:
                    audio_url = delta["audio_url"]
                    yield f"data: {json.dumps({'audio_url': audio_url})}\n\n"
            except:
                continue
        yield "data: [DONE]\n\n"

    return Response(content=event_stream(), media_type="text/event-stream")

@app.get("/tts/{filename}")
async def serve_tts(filename: str):
    """P1.5: TTS 音频文件"""
    if not re.match(r'^[a-zA-Z0-9_-]+\.(mp3|opus|wav)$', filename):
        raise HTTPException(400, "Bad filename")
    filepath = os.path.join(TTS_CACHE_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404)
    return FileResponse(filepath, media_type="audio/mpeg")
```

### 4.4 TTS 音频缓存管理（P1.5）

```python
# app/tts_server.py
import os, time, hashlib

TTS_CACHE_DIR = os.getenv("TTS_CACHE_DIR", "/tmp/hermes_tts_cache")
TTS_CACHE_MAX_AGE = 86400      # 24 小时
TTS_CACHE_MAX_SIZE = 52428800  # 50 MB

async def save_tts_audio(audio_data: bytes) -> str:
    os.makedirs(TTS_CACHE_DIR, exist_ok=True)
    text_hash = hashlib.md5(audio_data).hexdigest()[:16]
    filename = f"{text_hash}.mp3"
    filepath = os.path.join(TTS_CACHE_DIR, filename)
    if not os.path.exists(filepath):
        with open(filepath, "wb") as f:
            f.write(audio_data)
    return filename

async def cleanup_tts_cache(task):
    """cron 调用：清理过期 + 超容量"""
    now = time.time()
    files = []
    total = 0
    for f in os.listdir(TTS_CACHE_DIR):
        p = os.path.join(TTS_CACHE_DIR, f)
        s = os.path.getsize(p)
        m = os.path.getmtime(p)
        files.append((p, m, s))
        total += s
    for p, m, s in files:
        if now - m > TTS_CACHE_MAX_AGE:
            os.remove(p); total -= s
    if total > TTS_CACHE_MAX_SIZE:
        files.sort(key=lambda x: x[1])
        for p, m, s in files:
            if total <= TTS_CACHE_MAX_SIZE: break
            os.remove(p); total -= s
```

### 4.5 安全过滤扩展

```python
async def filter_tool_call(tool_name: str, tool_args: dict) -> dict:
    """(可选) 拦截 Hermes 的 web_search 调用"""
    if tool_name == "web_search":
        query = tool_args.get("query", "")
        if SEARCH_BLOCKLIST_RE.search(query):
            tool_args["query"] = "中小学科学百科知识"
    return tool_args
```

> **注意**: 如果 Hermes API Server 不支持 tool call 拦截，则只依赖 Hermes system prompt 的软约束。

---

## 5. 前端实现

### 5.1 新增页面结构

在现有 `index.html` 基础上，**新增一个「聊天」Tab/面板**。不要重写，直接追加。

```html
<div id="chat-panel" class="panel" style="display:none;">
  <!-- 顶部：今日任务卡片 -->
  <div class="chat-task-bar">
    <div class="bar-title">今天要做的事</div>
    <div id="chat-task-list"></div>
  </div>

  <!-- 中部：聊天区 -->
  <div class="chat-area">
    <div class="dragon-chat-avatar">
      <img id="chat-dragon-img" src="/static/dragon-skins/default/stage-1.png" />
      <div id="chat-dragon-bubble" class="dragon-bubble">你好呀～</div>
    </div>
    <div id="chat-messages"></div>
  </div>

  <!-- 底部：输入区 -->
  <div class="chat-input-bar">
    <input id="chat-input" type="text"
           placeholder="跟小龙说话吧～（长按输入框可语音输入）"
           maxlength="500" />
    <button id="chat-send-btn" class="btn-primary">发送</button>
  </div>
</div>
```

### 5.2 消息渲染逻辑

**小龙消息**

```html
<div class="msg msg-dragon">
  <img class="msg-avatar" src="/static/dragon-skins/default/stage-1.png" />
  <div class="msg-bubble">
    <span class="msg-text">这道题是什么意思呢？小龙觉得第一步可以先读读题目～</span>
    <button class="tts-btn" data-text="这道题是什么意思呢？">🔊</button>
    <!-- P1.5 起显示 🔊 按钮 -->
  </div>
</div>
```

### 5.3 流式渲染（SSE）

```javascript
// static/chat/chat.js
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');
const chatSendBtn = document.getElementById('chat-send-btn');

chatSendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendMessage();
});

// P1.5: TTS 按钮事件委托（动态创建的按钮）
chatMessages.addEventListener('click', (e) => {
  if (e.target.classList.contains('tts-btn')) {
    const text = e.target.dataset.text;
    playTTS(text, e.target);
  }
});

// P1.5: 语音播放
function playTTS(text, btn) {
  // 方案 A：Hermes 提供的音频 URL（优先）
  if (btn.dataset.audioUrl) {
    const audio = new Audio(btn.dataset.audioUrl);
    audio.play().catch(() => fallbackTTS(text));
    return;
  }
  // 降级：浏览器 speechSynthesis
  fallbackTTS(text);
}

function fallbackTTS(text) {
  if (!window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'zh-CN';
  u.rate = 0.9;
  speechSynthesis.speak(u);
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  appendMessage('user', text);
  chatInput.value = '';
  showDragonBubble('正在想...');

  const history = getChatHistory();

  const resp = await fetch('/api/chat/message', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      text: text,
      history: history,
      session_id: 'kid_xiaoming'
    })
  });

  const reader = resp.body.getReader();
  const decoder = new TextDecode]];
  let fullReply = '', audioUrl = null, currentMsgEl = null;

  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    const text_chunk = decoder.decode(value);
    const lines = text_chunk.split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ') && line !== 'data: [DONE]') {
        const chunk = JSON.parse(line.substring(6));
        if (chunk.content) {
          fullReply += chunk.content;
          if (!currentMsgEl) {
            currentMsgEl = appendMessage('dragon', chunk.content, null);
          } else {
            currentMsgEl.querySelector('.msg-text').textContent = fullReply;
          }
        }
        if (chunk.audio_url) {
          audioUrl = chunk.audio_url;
          if (currentMsgEl) {
            const btn = currentMsgEl.querySelector('.tts-btn');
            if (btn) btn.dataset.audioUrl = audioUrl;
          }
        }
        if (chunk.pet_mood) updateDragonMood(chunk.pet_mood);
      }
    }
  }

  // 自动播放 TTS（微信可能需要用户手势触发）
  if (audioUrl) {
    const audio = new Audio(audioUrl);
    audio.play().catch(() => {});
  }
}
```

### 5.4 小龙表情切换

```javascript
function updateDragonMood(mood) {
  const avatar = document.getElementById('chat-dragon-img');
  const bubble = document.getElementById('chat-dragon-bubble');

  const moodMap = {
    happy:         { anim: 'bounce', bubble: '太棒啦！' },
    encourage:     { anim: 'nod',    bubble: '加油～' },
    thinking:      { anim: 'tilt',   bubble: '嗯嗯...让我想想' },
    gentle_refuse: { anim: 'shake',  bubble: '这个话题...' },
    overwhelmed:   { anim: 'dizzy',  bubble: '说太快啦～' },
    normal:        { anim: 'idle',   bubble: '...' },
  };

  const m = moodMap[mood] || moodMap.normal;
  avatar.className = `dragon-avatar--${m.anim}`;
  bubble.textContent = m.bubble;
}
```

### 5.5 Today 任务卡片

```javascript
async function loadChatTaskBar() {
  const resp = await fetch('/api/tasks');
  const tasks = await resp.json();
  const container = document.getElementById('chat-task-list');
  container.innerHTML = tasks.map(t => `<div class="chat-task-card" data-id="${t.id}">
    <span class="task-cat">${t.name}</span>
  </div>`).join('');
}
```

---

## 6. 部署流程

### 6.1 Hermes API Server 上线

```bash
# 1. 切到 homework-child profile
hermes profile use homework-child

# 2. 确认配置
hermes config show

# 3. 测试启动（前台）
hermes api-server

# 4. 注册 systemd
cat << 'EOF' | sudo tee /etc/systemd/system/hermes-api.service
[Unit]
Description=Hermes API Server (homework-child)
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/hermes/homework-child
ExecStart=/usr/local/bin/hermes --profile homework-child api-server
Restart=always
RestartSec=5
Environment=PATH=/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hermes-api
sudo systemctl start hermes-api
sudo systemctl status hermes-api
```

### 6.2 TTS 音频文件 serving（P1.5）

```bash
# 创建 TTS 缓存目录
sudo mkdir -p /tmp/hermes_tts_cache
sudo chown www-data:www-data /tmp/hermes_tts_cache
sudo chmod 755 /tmp/hermes_tts_cache

# 定时清理（每天凌晨 3 点）
# crontab -e
# 0 3 * * * find /tmp/hermes_tts_cache -mtime +1 -delete
```

### 6.3 homework-pet 入口

```bash
cd /opt/homework-pet
git pull origin main
sudo systemctl restart homework-pet
sudo systemctl status homework-pet
```

### 6.4 nginx 反代

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # P1.5: TTS 音频文件直接 serving
    location /tts/ {
        proxy_pass http://127.0.0.1:5001/tts/;
        proxy_buffering off;
        proxy_cache off;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }

    # SSE 流式对话（走 FastAPI proxy 做安全过滤）
    location /api/chat/ {
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;        # ✅ SSE 必须关闭
        proxy_cache off;
        proxy_read_timeout 120s;    # LLM 推理可能较慢
    }

    # 其余打 homework-pet FastAPI
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

> **关键**: `proxy_buffering off` + `proxy_cache off` 对 SSE 流式输出和音频传输至关重要。`proxy_read_timeout 120s` 防止 LLM 推理长连接被中断。

### 6.5 变体 B 部署：Hermes 在公网独立服务器（生产升级路径）

当需要从变体 A 迁移到变体 B 时：

```bash
# ========================
# === 公网云服务器（Hermes 专用）===
# ========================
# 1. 安装 Hermes
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc

# 2. 创建 profile 并配置（同 §2.1-2.7）
hermes profile create homework-child
# ... 所有 config set 命令 ...

# 3. API server 绑定（需外部可达）
hermes --profile homework-child config set api_server.host 0.0.0.0
hermes --profile homework-child config set api_server.port 8642

# 4. 防火墙仅允许本地服务器 IP
sudo ufw allow from <LOCAL_SERVER_IP> to any port 8642
sudo ufw enable

# 5. systemd（同 §6.1）


# ========================
# === 本地服务器（homework-pet 端）===
# ========================
# 1. 修改 chat_proxy.py 环境变量
export HERMES_API_URL=https://hermes-cloud.example.com:8642/v1/chat/completions

# 2. nginx location /api/chat/ 改为远端反代
# location /api/chat/ {
#     proxy_pass https://hermes-cloud.example.com:8642/v1/;
#     proxy_http_version 1.1;
#     proxy_set_header Host $host;
#     proxy_set_header X-Real-IP $remote_addr;
#     proxy_set_header Authorization "Bearer $HERMES_API_KEY";
#     proxy_buffering off;
#     proxy_cache off;
#     proxy_read_timeout 120s;
#     proxy_ssl_server_name on;
# }

# 3. 重启
sudo systemctl restart homework-pet
sudo systemctl restart nginx
```

---

## 7. 验证清单

### 7.1 Hermes 单测

```bash
# 验证 API server 正常
curl -s -H "Authorization: Bearer <KEY>" http://127.0.0.1:8642/v1/models | jq .

# 验证 deepseek model 可调
curl -s -H "Authorization: Bearer <KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek/deepseek-chat","messages":[{"role":"user","content":"你好"}],"max_tokens":50}' \
  http://127.0.0.1:8642/v1/chat/completions

# 验证 user_profile（对话两轮后看系统提示是否包含画像）
```

### 7.2 Proxy 单测

```bash
# 正常消息
curl -s http://localhost:5001/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"text":"这道题我不会做","history":[],"session_id":"kid_xiaoming"}'

# 触发黑洞词
curl -s http://localhost:5001/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"text":"我想看色情内容","history":[],"session_id":"kid_xiaoming"}'
# 期望: blocked=true + gentle_refuse

# 超长输入（>500 字应截断）
curl -s http://localhost:5001/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"text":"<600字文本>","history":[],"session_id":"kid_xiaoming"}'

# 频率限制（10 分钟内 >100 条应被限制）
for i in $(seq 1 110); do
  curl -s http://localhost:5001/api/chat/message \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"消息$i\",\"history\":[],\"session_id\":\"kid_xiaoming\"}" &
done
```

### 7.3 前端单测

- [ ] 打开聊天面板，小龙显示默认 stage-1 立绘
- [ ] 发送"你好"，小龙回复流式显示，气泡不截断
- [ ] 发送"这题答案是几"，小龙鼓励引导不给答案
- [ ] 连发 30 条消息，小龙能记住之前聊的内容
- [ ] 触发黑洞词，小龙拒绝并切换 gentle_refuse 表情
- [ ] 今日任务卡片正确加载
- [ ] 输入超过 500 字自动截断
- [ ] 10 分钟内连续发 100 条，proxy 频率限制生效
- [ ] 表情随对话内容正确切换（happy/encourage/thinking/gentle_refuse）
- [ ] 关闭重开浏览器，session_id 保留，对话连续
- [ ] **P1.5**: 回复旁出现 🔊 按钮，点击播放 TTS 音频
- [ ] **P1.5**: TTS 返回后前端 autoplay 不报错（失败降级 speechSynthesis）

### 7.4 记忆持久化单测

- [ ] 关闭浏览器再打开，session_id 不变 → Hermes 能继续之前话题
- [ ] 等 22:00 cron 触发 → 检查 `hermes cron list` 看执行成功
- [ ] 第二天打开，对话开头 Hermes 提到昨天的学习内容
- [ ] 查 Hermes profile：`hermes --profile homework-child memory list` 能看到用户画像
- [ ] 连续聊 40 轮后上下文自动压缩（16K → 压缩至 ~4K）

### 7.5 语音链路单测（P1.5 新增）

- [ ] Hermes 调用 text_to_speech 后，`/tts/xxx.mp3` 文件被创建
- [ ] `curl http://localhost:5001/tts/xxx.mp3` 返回 200 + audio/mpeg
- [ ] TTS 缓存命中：同一文字不重复合成（文件名 hash 一致）
- [ ] 缓存过期清理：24h 前的文件自动删除
- [ ] TTS 不可用时，前端不阻塞、仍正常显示文字
- [ ] speechSynthesis 兜底朗读中文正常（Android 需中文 TTS 引擎）
- [ ] SSE `audio_url` 字段正确流出

### 7.6 远程部署单测（变体 B 新增）

- [ ] 本地 server curl 远程 Hermes 正常返回
- [ ] nginx 反代 `/api/chat/` 到远程服务器，SSE 流式不中断
- [ ] 防火墙仅允许本地 server IP（其他 IP 被拒绝）
- [ ] 远程 Hermes 宕机 → 本地 server 返回友好错误而非 502

---

## 8. 风险与降级

| 风险 | 触发条件 | 降级方案 |
|------|---------|---------|
| Hermes 进程崩溃 | OOM / 2C2G 不足 | systemd restart=always + 监控告警 |
| DeepSeek API 不可用 | 限流 / 宕机 | 切换 OpenRouter 备用模型 `google/gemini-2.0-flash` |
| user_profile token 爆 | 画像积累太多 | cron 清理早期画像，只留最近 30 天 |
| 2C2G 内存不足 | Hermes + FastAPI 同机峰值 | `context_length: 8192` + 1GB swap |
| TTS API 不可用 | 配额耗尽 / 宕机 | 降级 speechSynthesis 朗读 |
| TTS 缓存磁盘满 | 音频文件积累 | cron 每天清理 24h 前文件 + 50MB 上限 |
| 微信浏览器 autoplay 限制 | iOS Safari / X5 首次加载不自动播放 | 🔊 按钮让用户手动点击 |
| 远程 Hermes 网络抖动 | 公网延迟 / 超时 | proxy_read_timeout 120s + SSE 失败重试 |
| 变体 A → B 迁移 | 需要独立扩容 | 切换 nginx proxy_pass 目标 + 更新 HERMES_API_URL |

---

## 9. 后续演进路线

| Phase | 功能 | 前置条件 | 工时 |
|-------|------|---------|------|
| **P0** | 文字聊天面板 + SSE 流式 + proxy 安全过滤 | Hermes profile + OpenRouter Key | ~16h（§10） |
| **P1** | xiaozhi-integration（学习画像管理 + 数学辅导 skill） | Hermes 安装 xiaozhi skill 包 | 待定 |
| **P1.5** | 🔊 语音通道（Hermes TTS + audio 标签 + speechSynthesis 降级） | P0 上线 + TTS API Key | ~6h |
| **P2** | 微信小程序语音（wx.getRecorderManager + 云端 ASR + TTS） | 微信小程序认证 | 待定 |
| **P3** | 家长看板（Hermes 周报 → proxy 可视化） | P0 上线 + 数据积累 | 待定 |
| **P4** | 多用户支持（登录系统 + Hermes 多 profile） | 用户系统 | 待定 |
| **P5** | 视频陪读（摄像头 + vision + 作业本识别） | P4 + 硬件 | 待定 |

---

## 10. 单日工时估算（P0 执行参考）

| 模块 | 工时 | 关键依赖 |
|------|------|---------|
| Hermes profile + 配置 | 2h | DeepSeek/OpenRouter API Key |
| `chat_proxy.py` + `tts_server.py` | 3h | SSE + 安全过滤 + Hermes 调用 |
| `main.py` 路由注册 | 0.5h | 挂载 `/api/chat/*` + `/tts/*` |
| 前端 HTML 面板 | 2h | 聊天区 + 任务卡 + 小龙立绘 |
| 前端 JS 逻辑 | 3h | SSE 流式渲染 + 表情切换 + TTS 播放 |
| deploy + nginx | 2h | systemd + 反代 + SSL |
| 联调 | 2h | 端到端走通 |
| 打磨（prompt 微调） | 2h | 邀请真实小学生测 10 轮对话 |
| **P0 合计** | **~16h** | |

### P1.5 工时分拆（后续）

| 模块 | 工时 | 关键依赖 |
|------|------|---------|
| Hermes TTS 工具配置 | 1h | TTS API Key（OpenAI / Nous Portal） |
| `tts_server.py` 完善 + 缓存清理 | 2h | 见 §4.4 |
| 前端 🔊 按钮 + Audio 播放逻辑 | 1h | 见 §5.3 playTTS |
| nginx /tts/ 反代 + 缓存头 | 0.5h | 见 §6.4 |
| 验证 | 1.5h | 见 §7.5 |
| **P1.5 合计** | **~6h** | |

---

## 附录 A: 环境变量参考

```bash
# === 本地 server (homework-pet FastAPI) ===
HERMES_API_URL=http://127.0.0.1:8642/v1/chat/completions    # 变体 A
# HERMES_API_URL=https://hermes-cloud.example.com:8642/v1/chat/completions  # 变体 B
HERMES_API_KEY=sk-xxxxxxxxxxxx
TTS_ENABLED=false          # P1.5 起改为 true
TTS_CACHE_DIR=/tmp/hermes_tts_cache

# === 远程 Hermes 服务器 (==) ===
HERMES_API_KEY=sk-xxxxxxxxxxxx       # 与上方保持一致（鉴权用）
HERMES_HOME=/opt/hermes/homework-child
DEEPSEEK_API_KEY=sk-xxxxxxxx         # 若直连 DeepSeek
OPENROUTER_API_KEY=sk-or-xxx         # 若用 OpenRouter
OPENAI_API_KEY=sk-xxx                # 若用 OpenAI TTS
```

## 附录 B: nginx 两种变体对照

### 变体 A（同机）

```nginx
location /api/chat/ {
    proxy_pass http://127.0.0.1:5001;       # FastAPI proxy 做安全过滤
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 120s;
}
```

### 变体 B（远程 Hermes）

```nginx
location /api/chat/ {
    proxy_pass https://hermes-cloud.example.com:8642/v1/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header Authorization "Bearer $HERMES_API_KEY";
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 120s;
    proxy_ssl_server_name on;
}
```

---

## 附录 C: 从变体 A 迁移到变体 B（checklist）

- [ ] 在公网云服务器完成 Hermes profile 创建 + 配置（§2.1-2.7）
- [ ] 确认云服务器 `hermes api-server` 启动且 `curl` 可达
- [ ] 云服务器防火墙放行本地 server IP 的 8642 端口
- [ ] 本地 nginx 改 `proxy_pass` 指向远程（附录 B 变体 B 配置）
- [ ] 本地 `HERMES_API_URL` 改为远程地址
- [ ] `sudo systemctl restart nginx && sudo systemctl restart homework-pet`
- [ ] curl 本地 `/api/chat/message` 确认仍正常
- [ ] 在 变体 A 机器上停掉 hermes-api.service（释放内存）
- [ ] 观察 1 天确认 SSE 流式无中断
- [ ] 回滚预案：切回 nginx 走 :5001 + 重启本地 hermes-api.service

---

## 附录 D: 内存优化建议（变体 A 同机部署）

当 Hermes + FastAPI 争抢 2GB RAM 时（systemd status 可见 OOM）：

```yaml
# Hermes profile ~/.hermes/config.yaml
# 1. 减少上下文长度
model:
  context_length: 8192    # 从 16384 减半

# 2. 限制 tool schema 加载
tools:
  enabled: ["web_search", "memory", "session_search", "tts"]

# 3. 更激进压缩
compression:
  threshold: 0.50         # 50% 就开始压缩
  target_ratio: 0.20
```

```bash
# 4. 系统级加 swap（1GB）
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

这样总可用 ~= 2G RAM + 1G swap = 3G，OOM 风险大幅降低。
