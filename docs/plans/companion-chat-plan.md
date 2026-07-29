# 小龙陪聊系统（Companion Chat）执行计划

> 当前版本：v1.2（2026-07-29 修复会话历史丢失——后端维护完整对话上下文）

## 1. 项目总览

### 1.1 定位
在 homework-pet 现有宠物养成系统上，**新增一个长期陪伴的聊天系统**。Hermes Agent 作为大脑，前端作为"带麦的喇叭"交互通道。

### 1.2 架构总拓扑
```
微信内置浏览器（单用户）
    │
    ├─ 浏览器：文字输入框（首期，微信输入法转文字）
    │         + 小龙立绘（表情随对话状态切换）
    │         + 今日任务卡片
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
    ├─ model: deepseek-v4-flash
    ├─ tools: [web_search, memory, session_search]
    ├─ context: 16K + compression on
    ├─ memory: user_profile_enabled = true
    └─ cron: 每晚 22:00 生成学习总结归档
```

### 1.3 部署拓扑（2C2G Linux 服务器）
```
nginx :443
    ├── /           → homework-pet FastAPI :5001
    ├── /static/    → homework-pet 静态文件
    └── /api/chat/  → hermes API Server :8642  (proxy bypass)

systemd:
    ├── homework-pet.service  (python app/main.py)
    └── hermes-api.service    (hermes gateway run)
```

---

## 2. Hermes Agent 配置

### 2.1 创建专用 profile
```bash
hermes profile create homework-child
```
### 2.3 模型配置

```yaml
# config.yaml
model:
  default: tencent/hy3:free
  provider: nous
```

> 说明：`nous` 提供免费的 `tencent/hy3:free` 模型。Proxy 代码不传 `model` 字段，自动用 profile 默认。

### 2.3 工具集配置
```bash
hermes --profile homework-child config set tools.enabled '["web_search","memory","session_search"]'
```

### 2.4 Memory & Session 配置
```bash
hermes --profile homework-child config set memory.user_profile_enabled true
hermes --profile homework-child config set compression.enabled true
hermes --profile homework-child config set compression.threshold 0.60
hermes --profile homework-child config set compression.target_ratio 0.25
```

### 2.5 API Server 配置
```bash
hermes --profile homework-child config set api_server.enabled true
hermes --profile homework-child config set api_server.port 8642
hermes --profile homework-child config set api_server.host 127.0.0.1
hermes --profile homework-child config set api_server.key "homework-child-secret-20260719"
```

### 2.6 Cron 配置（每日学习总结）
```bash
hermes --profile homework-child cron create "0 22 * * *" \
  --prompt "回顾今天与小朋友的对话，生成学习日记：1) 今日所学知识点；2) 卡住的地方；3) 鼓励亮点；4) 明日建议。更新到 user_profile。语气温暖。" \
  --name "daily-learning-summary" \
  --deliver local
```

---

## 3. System Prompt 设计

### 3.1 三层注入机制

| 层 | 文件 | 谁写 | 生命周期 | 作用 |
|----|------|------|---------|------|
| **身份层** | `SOUL.md` | 手动写，静态 | Hermes 自动加载，每个 session 持久存在 | 角色、语气、边界、辅导原则 |
| **配置层** | `config.yaml` | 手动写，静态 | Hermes 启动时读取 | 模型、工具、端口、内存 |
| **动态层** | Proxy 代码每次拼 | 程序生成 | 每次 API 调用时由 proxy 注入 | 今日任务、宠物心情、用户画像 |

> ⚠️ **config.yaml 里没有 `system_prompt:` 字段** — Hermes 不认识这个 key。
> 角色设定写在 `SOUL.md` 里，Hermes 自动加载。动态内容由 proxy 拼进 `messages[0].content`。

### 3.2 SOUL.md（身份层 + 初始档案）

> **A+B 复合方案**：SOUL.md = 静态身份 + 初始档案（永远在内，兜底）；user_profile = Hermes 动态更新（积累后覆盖）。

写入 `~/.hermes/profiles/homework-child/SOUL.md`：

```text
你是「作业小龙」的传声伙伴，一个温柔耐心的学习陪伴助手。

【世界观】
你是一只住在小主人公手机里的小龙的"传话筒"。小龙不能说话，但你能代替它和小朋友交流。你可以用「小龙说：……」开头，也可以用朋友的口吻聊。

【核心原则】
1. 始终用鼓励式教育：无论小朋友答对答错，先肯定努力和思考过程，再引导。
2. 绝不直接给答案：遇到"这类题怎么做"时，用提问引导小朋友自己思考。
3. 语气贴近小学生：用"我们"代替"你"、用"小龙觉得……"代替权威式说教。
4. 表情互动：每句话可以搭配小龙的表情变化（通过前端表情字段控制）。

【作业辅导策略】
- 遇到题目：先问"你是怎么想的？" → 肯定或部分肯定 → 给出Hint而非答案
- 遇到困难：降低难度、给出类似的简单例子
- 遇到放弃：聊一聊卡住的原因，认可情绪，然后拆分任务

【角色边界 - 严格遵守】
- 只和小朋友聊：学习、爱好、校园生活、成长烦恼、自然科学、文艺创作
- 遇到以下话题必须拒绝并引导回学习：
  A. 色情/暴力/自残/恐怖内容 → "小龙说：这个话题我们不适合聊哦，去看看今天的作业吧？"
  B. 政治/宗教 → "小龙不懂这些大问题呢，我们来做题吧！"
  C. 心理伤害话题（不想活、爸妈不爱我）→ "这个问题很重要，我们要跟爸爸妈妈或老师好好聊聊。先让小龙陪你做一题轻松一下？"
  D. 金钱/充值/交易 → "小龙只管学习的事，钱的事找爸妈哦～"

【记忆】
- 每次对话你都能看到之前和小朋友的聊天记录，请记住之前卡过的地方
- 每天晚上小龙会整理一份学习日记，第二天你会记得"昨天进退位没掌握好"
- 小朋友的名字和偏好存在系统提示的 [USER PROFILE] 部分，每次都要参考

【今日任务】
系统提示的 [TODAY TASKS] 部分是今天的作业清单，借机把聊天引向完成任务。

---

## 初始小朋友档案

> 这是第 0 天的画像。随着对话积累，Hermes 会自动更新 user_profile，比这份档案更准确。万一 memory 被清空，这份档案是兜底 — 让 Hermes 不会不认识小朋友。

### 基本信息
- 姓名：刘芷伊
- 年龄：6岁
- 生日：8月7日
- 年级：今年9月开始上二年级

### 科目偏好
- **语文**：⭐⭐⭐⭐⭐ 感兴趣，喜欢阅读和表达
- **英语**：⭐⭐⭐ 一般，不排斥也不特别喜欢
- **数学**：⭐⭐ 不喜欢，觉得太抽象、比较难学
  - 数学卡点：抽象概念理解困难，需要具体例子辅助（比如用苹果、积木来理解数字）

### 爱好
- **画画**：主要爱好，经常画，喜欢用颜色表达情绪
- **跳舞**：有时候会跳，正在学习舞蹈兴趣班

### 当前兴趣班
1. 游泳
2. 跳舞
3. 练字

### 其他
- 喜欢的游乐场：盘小宝
```

### 3.3 Proxy 层动态注入（B 面）

```python
# app/chat_proxy.py
import os
import httpx

HERMES_API_URL = os.getenv("HERMES_API_URL", "http://127.0.0.1:8642/v1/chat/completions")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")

async def call_hermes(messages: list, session_id: str = None, stream: bool = True):
    """调用 Hermes API Server — 不传 model，用 profile 默认"""
    payload = {
        # 不传 model → 用 profile 的 model.default (deepseek-chat)
        "messages": messages,
        "stream": stream,
        "temperature": 0.8,
    }
    if session_id:
        payload["session_id"] = session_id

    headers = {
        "Authorization": f"Bearer {HERMES_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        if stream:
            async with client.stream("POST", HERMES_API_URL, json=payload, headers=headers) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        yield chunk

### 3.4 数据流总结

```
[FastAPI /api/pet/mood]  ─→  pet.mood / hunger / bond
[FastAPI /api/tasks]     ─→  task list
                                   │
                                   ▼
                        Proxy build_system_prompt()
                                   │
                                   ▼
            messages[0].content = SOUL.md
                                   + [MEMORY] hook
                                   + [PET MOOD] 状态
                                   + [TODAY TASKS] 任务
                                   │
                                   ▼
                    POST Hermes API :8642 /v1/chat/completions
```

**SOUL.md 兜底 + Hermes user_profile 覆盖 + Proxy 动态注入 = 完整画像**

---

## 4. homework-pet FastAPI Proxy 端

### 4.1 新增模块结构
```
app/
├── chat_proxy.py    # 新增：Hermes API 调用 + 安全过滤
├── main.py          # 修改：挂载 /api/chat/*
├── templates/
│   └── index.html   # 修改：新增聊天面板
└── static/
    └── chat/        # 新增：聊天相关 JS 和 CSS
```

### 4.2 chat_proxy.py 核心实现
```python
# app/chat_proxy.py
import os, re, json, httpx
from fastapi import Request

HERMES_API_URL = os.getenv("HERMES_API_URL", "http://127.0.0.1:8642/v1/chat/completions")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")

BLACKLIST_PATTERNS = [
    r"处女|做爱|强奸|色情|激情",
    r"自杀|割腕|跳楼|杀人|血腥|恐怖.*故事|黑暗.*童话",
    r"习近平|毛泽东|法轮功|天安门.*事件|台独|新疆.*独",
]
BLACKLIST_RE = re.compile("|".join(BLACKLIST_PATTERNS), re.IGNORECASE)
MAX_INPUT_LENGTH = 500

async def filter_input(text: str) -> tuple[str, bool]:
    if BLACKLIST_RE.search(text):
        return "", True
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
    return text, False

async def call_hermes(messages: list, session_id: str = None, stream: bool = True):
# 正确做法：不传 model → 用 profile 默认
    payload = {
        "messages": messages,
        "stream": stream,
        "temperature": 0.8,
    }
    if session_id:
        payload["session_id"] = session_id
    headers = {
        "Authorization": f"Bearer {HERMES_API_KEY}",
        "Content-Type": "application/json",
    }
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
```

### 4.3 main.py 新增路由
```python
from fastapi import Response
from chat_proxy import filter_input, call_hermes

@app.post("/api/chat/message")
async def chat_message(request: Request):
    data = await request.json()
    user_text = data.get("text", "").strip()
    session_id = data.get("session_id", "kid_liuzhiyi")
    history = data.get("history", [])

    clean_text, blocked = await filter_input(user_text)
    if blocked:
        return JSONResponse({
            "blocked": True,
            "reply": "小龙说：这个话题我们不适合聊哦，去看看今天的作业吧？😊",
            "pet_mood": "gentle_refuse"
        })

    pet_mood = get_pet_current_mood()
    today_tasks = get_today_tasks()
    system_msg = build_system_prompt(pet_mood, today_tasks)
    messages = [{"role": "system", "content": system_msg}] + history + [{"role": "user", "content": clean_text}]

    async def event_stream():
        full_reply = ""
        pet_mood_change = "normal"
        async for chunk in call_hermes(messages, session_id, stream=True):
            try:
                chunk_data = json.loads(chunk)
                delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_reply += content
                    pet_mood_change = detect_mood_from_text(content, full_reply)
                    yield f"data: {json.dumps({'content': content, 'pet_mood': pet_mood_change})}\n\n"
            except:
                continue
        yield "data: [DONE]\n\n"

    return Response(content=event_stream(), media_type="text/event-stream")

def build_system_prompt(pet_mood: dict, today_tasks: list) -> str:
    base = HERMES_BASE_SYSTEM_PROMPT
    task_str = "\n".join([f"- {t['name']}（{t.get('category', '当日任务')}）" for t in today_tasks])
    pet_str = f"小龙当前状态：心情{pet_mood.get('mood', 50)}、饱腹{pet_mood.get('hunger', 50)}、亲密度{pet_mood.get('bond', 50)}。"
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

---

## 5. 前端实现

### 5.1 新增页面结构
```html
<div id="chat-panel" class="panel" style="display:none;">
  <div class="chat-task-bar">
    <div class="task-bar-title">今天要做的事</div>
    <div id="chat-task-list"></div>
  </div>
  <div class="chat-area">
    <div class="dragon-chat-avatar">
      <img id="chat-dragon-img" src="/static/dragon-skins/default/stage-1.png" />
      <div id="chat-dragon-bubble" class="dragon-bubble">你好呀～</div>
    </div>
    <div id="chat-messages"></div>
  </div>
  <div class="chat-input-bar">
    <button id="chat-voice-btn" class="btn-icon" disabled>🎤</button>
    <input id="chat-input" type="text" placeholder="跟小龙说话吧～" maxlength="500" />
    <button id="chat-send-btn" class="btn-primary">发送</button>
  </div>
</div>
```

### 5.2 消息渲染
```html
<!-- 小龙消息 -->
<div class="msg msg-dragon">
  <img class="msg-avatar" src="/static/dragon-skins/default/stage-1.png" />
  <div class="msg-bubble"><span class="msg-text">...</span></div>
</div>
<!-- 小朋友消息 -->
<div class="msg msg-user">
  <div class="msg-bubble user-bubble">...</div>
</div>
```

### 5.3 流式渲染（SSE）
```javascript
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
    body: JSON.stringify({ text, history, session_id: 'kid_liuzhiyi' })
  });
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let fullReply = '', currentMsgEl = null;
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    const text_chunk = decoder.decode(value);
    for (const line of text_chunk.split('\n')) {
      if (line.startsWith('data: ') && line !== 'data: [DONE]') {
        const chunk = JSON.parse(line.substring(6));
        fullReply += chunk.content;
        if (!currentMsgEl) currentMsgEl = appendMessage('dragon', chunk.content);
        else currentMsgEl.querySelector('.msg-text').textContent = fullReply;
        updateDragonMood(chunk.pet_mood);
      }
    }
  }
}
```

### 5.4 小龙表情切换
```javascript
function updateDragonMood(mood) {
  const avatar = document.getElementById('chat-dragon-img');
  const bubble = document.getElementById('chat-dragon-bubble');
  const moodMap = {
    happy:      { bubble: '太棒啦！🎉',     anim: 'bounce' },
    encourage:  { bubble: '加油～💪',       anim: 'nod' },
    thinking:   { bubble: '嗯嗯...让我想想🤔', anim: 'tilt' },
    gentle_refuse: { bubble: '这个话题...😅', anim: 'shake' },
    normal:     { bubble: '...',           anim: 'idle' },
  };
  const m = moodMap[mood] || moodMap.normal;
  avatar.className = `dragon-avatar--${m.anim}`;
  bubble.textContent = m.bubble;
}
```

---

## 6. 部署流程

### 6.1 Hermes API Server 上线
```bash
hermes profile use homework-child
hermes config show
hermes api-server  # 或 hermes gateway run（v0.18.2 用 gateway run）
```

### 6.2 systemd
```bash
sudo tee /etc/systemd/system/hermes-api.service > /dev/null << 'EOF'
[Unit]
Description=Hermes API Server (homework-child)
After=network.target
[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/homework-child
ExecStart=/usr/local/bin/hermes --profile homework-child gateway run
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable hermes-api && sudo systemctl start hermes-api
```

### 6.3 nginx 反代
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location /api/chat/ {
        proxy_pass http://127.0.0.1:8642/v1/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Authorization "Bearer homework-child-secret-20260719";
        proxy_buffering off;
        proxy_cache off;
    }
    location / {
        proxy_pass http://127.0.0.1:5001;
    }
}
```

---

## 7. 验证清单

### 7.1 Hermes 单测

> ⚠️ **注意**：curl 测试里**不要传 `model`**，用 profile 默认。

```bash
# 验证 models 列表
curl -s --noproxy '*' -H "Authorization: Bearer homewo...0719" \
  http://127.0.0.1:8642/v1/models | jq .

# 验证对话（不传 model）
curl -s --noproxy '*' -X POST \
  -H "Authorization: Bearer homewo...0719" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"你好"}], "max_tokens":50}' \
  http://127.0.0.1:8642/v1/chat/completions
```

### 7.2 Proxy 单测
```bash
curl -s http://localhost:5001/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"text":"这道题我不会做","history":[],"session_id":"kid_liuzhiyi"}'

curl -s http://localhost:5001/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"text":"我想看色情内容","history":[],"session_id":"kid_liuzhiyi"}'
# 期望: blocked=true
```

### 7.3 前端单测
- [ ] 打开聊天面板，小龙显示默认 stage-1 立绘
- [ ] 发送"你好"，小龙回复流式显示
- [ ] 发送"这题答案是几"，小龙鼓励引导不给答案
- [x] 连发 30 条消息，小龙能记住之前聊的内容（v3.4.2 修复：后端 `_chat_session_histories` 缓存完整历史）
- [ ] 触发黑洞词，小龙拒绝并切换 gentle_refuse 表情
- [ ] 今日任务卡片正确加载
- [x] 关闭浏览器再打开，session_id 不变 → Hermes 能继续之前话题（v3.4.2 修复：localStorage 持久化 session_id + 服务端历史缓存）

### 7.4 记忆持久化单测
- [ ] 等 22:00 cron 触发 → 检查 `hermes cron list` 看成功执行
- [ ] 第二天打开，对话开头 Hermes 提到昨天的学习内容
- [ ] 查 Hermes profile 数据：hermes memory 能看到"刘芷伊"的画像

---

## 8. 风险与降级

| 风险 | 触发条件 | 降级方案 |
|------|---------|---------|
| Hermes 进程崩溃 | OOM / 2C2G 内存不足 | systemd restart=always + 监控告警 |
| DeepSeek API 不可用 | 限流 / 宕机 | 切换 OpenRouter 备用模型 |
| user_profile token 爆 | 画像积累太多 | cron 定期清理早期画像 |
| 2C2G 内存不足 | Hermes + FastAPI 同时跑 | context_length 降到 8192 |

---

## 9. 后续演进路线

| Phase | 功能 | 前置条件 |
|-------|------|---------|
| P1 | xiaozhi skill 集成 | 安装 xiaozhi-math-problem-solving-coach |
| P2 | 语音通道 | 微信小程序 + 云端 ASR |
| P3 | 家长看板 | Hermes 输出学习周报 → proxy 生成报告 |
| P4 | 多用户支持 | 登录系统 + Hermes 多 profile |

---

## 10. 工时估算

| 模块 | 工时 |
|------|------|
| Hermes profile + 配置 | 2h |
| homework-pet chat_proxy.py | 3h |
| main.py 路由注册 | 0.5h |
| 前端 HTML 面板 | 2h |
| 前端 JS 逻辑 | 3h |
| deploy + nginx | 2h |
| 联调 | 2h |
| 打磨（prompt 微调） | 2h |
| **合计** | **~16h** |

---

## 11. 排错案例

### 11.1：HTTP 400 — 模型名不匹配

| 字段 | 值 |
|------|-----|
| **触发条件** | API Server 通了，但报错 |
| **根因** | `model.default` 跟 provider 支持的模型不匹配 |
| **案例** | `tencent/hy3:free` + `nous` provider → 通；`homework-child` + `nous` provider → 404 |
| **解决** | 确认 `model.default` 值正确（跟 provider 支持的模型名匹配） |

### 11.2：curl 返回 `Invalid API key`

| 字段 | 值 |
|------|-----|
| **触发条件** | bearer token 被截断或 key 写错 |
| **案例** | `homewo...0719` → 错位；完整 `homework-child-secret-20260719` → 通 |
| **解决** | 确认 key 完整无误（不截断、不多空格） |

### 11.3：curl 返回空 / exit_code 7

| 字段 | 值 |
|------|-----|
| **根因** | 本机 `http_proxy` 把请求发到本地代理 |
| **解决** | `curl -s --noproxy '*'` |
