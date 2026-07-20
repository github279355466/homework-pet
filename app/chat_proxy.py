"""
app/chat_proxy.py - Hermes Bridge (HTTP 模式)
全部配置通过环境变量读取，适合 Railway 远程部署。

环境变量:
  HERMES_API_URL     (必填) Hermes API 地址, 如 https://xxx:8642/v1/chat/completions
  HERMES_API_KEY     (必填) Bearer <REDACTED>
  HERMES_TIMEOUT     (可选) 超时秒数, 默认 60
  HERMES_MODEL       (可选) 模型名, 默认 deepseek-chat
  MAX_INPUT_LENGTH   (可选) 单条消息最大长度, 默认 500
"""

import os
import re
import time
import logging

logger = logging.getLogger("homework-pet.chat_proxy")

HERMES_API_URL = os.getenv("HERMES_API_URL", "")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
HERMES_TIMEOUT = int(os.getenv("HERMES_TIMEOUT", "60"))
HERMES_MODEL = os.getenv("HERMES_MODEL", "deepseek-chat")
MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", "500"))
_RATE_LOG = []


def check_rate_limit():
    """频率限制: 100次/10分钟"""
    now = time.time()
    global _RATE_LOG
    _RATE_LOG = [t for t in _RATE_LOG if now - t < 600]
    if len(_RATE_LOG) >= 100:
        return False
    _RATE_LOG.append(now)
    return True


def filter_input(text):
    """安全过滤"""
    if re.search(r"做爱|强奸|激情|裸体|色情|自杀|割腕|跳楼|杀人|血腥", text, re.IGNORECASE):
        return "", True
    return text[:MAX_INPUT_LENGTH], False


def build_system_prompt(pet_mood, today_tasks):
    """注入宠物状态和今日任务"""
    parts = []
    if pet_mood:
        parts.append(
            "[PET MOOD]\n"
            f"小龙当前状态：心情{pet_mood.get('mood', 50)}"
            f"、饱腹{pet_mood.get('hunger', 50)}"
            f"、亲密度{pet_mood.get('bond', 50)}。"
        )
    if today_tasks:
        task_str = "\n".join(f"- {t.get('name', t.get('subject', '任务'))}" for t in today_tasks)
        parts.append(f"[TODAY TASKS]\n{task_str}")
    return "\n\n".join(parts)


def detect_mood_from_text(text):
    """心情检测"""
    if any(w in text for w in ["太棒了", "真厉害", "做得很好", "好棒"]):
        return "happy"
    if any(w in text for w in ["没关系", "下次一定", "慢慢来", "加油"]):
        return "encourage"
    if any(w in text for w in ["想一想", "试试看", "换个角度"]):
        return "thinking"
    if any(w in text for w in ["不适合聊", "这个话题"]):
        return "gentle_refuse"
    return "normal"


def call_hermes(message, session_id=None, system_context=None):
    """调用远程 Hermes API"""
    if not HERMES_API_URL:
        return {"text": "未配置 HERMES_API_URL", "session_id": None, "mood": "error"}

    try:
        import httpx
    except ImportError:
        return {"text": "缺少 httpx 依赖", "session_id": None, "mood": "error"}

    headers = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {HERMES_API_KEY}"

    msgs = []
    if system_context:
        msgs.append({"role": "system", "content": system_context})
    msgs.append({"role": "user", "content": message})

    payload = {
        "model": HERMES_MODEL,
        "messages": msgs,
        "stream": False,
        "max_tokens": 200,
    }
    if session_id:
        payload["session_id"] = session_id

    try:
        with httpx.Client(timeout=float(HERMES_TIMEOUT)) as client:
            resp = client.post(HERMES_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return {
                "text": text,
                "session_id": data.get("session_id", session_id),
                "mood": detect_mood_from_text(text),
            }
    except httpx.TimeoutException:
        return {
            "text": f"思考超时（>{HERMES_TIMEOUT}s），请稍后重试",
            "session_id": session_id,
            "mood": "overwhelmed",
        }
    except Exception as e:
        return {
            "text": f"连接 Hermes 失败: {str(e)[:60]}",
            "session_id": session_id,
            "mood": "error",
        }


def chat(message, session_id=None, pet_mood=None, today_tasks=None):
    """主入口"""
    if not check_rate_limit():
        return {"text": "说太快啦，让小龙头休息一下", "session_id": session_id, "mood": "overwhelmed", "blocked": True}

    clean_text, blocked = filter_input(message)
    if blocked:
        return {"text": "这个话题不适合聊哦", "session_id": session_id, "mood": "gentle_refuse", "blocked": True}

    ctx = ""
    if pet_mood or today_tasks:
        ctx = build_system_prompt(pet_mood or {}, today_tasks or [])

    result = call_hermes(clean_text, session_id, ctx)
    result["blocked"] = False
    return result
