"""
app/chat_proxy.py - Hermes Bridge (异步流式)
不传 model，用 Hermes profile 默认模型。
"""

import os
import re
import time
import json
import logging
import httpx

logger = logging.getLogger("homework-pet.chat_proxy")

HERMES_API_URL = os.getenv("HERMES_API_URL", "")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
HERMES_TIMEOUT = int(os.getenv("HERMES_TIMEOUT", "60"))
_RATE_LOG = []


def check_rate_limit():
    now = time.time()
    global _RATE_LOG
    _RATE_LOG = [t for t in _RATE_LOG if now - t < 600]
    if len(_RATE_LOG) >= 100:
        return False
    _RATE_LOG.append(now)
    return True


def filter_input(text):
    """安全过滤 + 长度截断"""
    blacklist = re.compile(
        "|".join([
            r"做爱|强奸|激情|裸体|色情",
            r"自杀|割腕|跳楼|杀人|血腥",
        ]),
        re.IGNORECASE,
    )
    if blacklist.search(text):
        return "", True
    return text[:500], False


def detect_mood_from_text(text):
    """根据回复检测心情"""
    if any(w in text for w in ["太棒了", "真厉害", "做得很好", "好棒"]):
        return "happy"
    if any(w in text for w in ["没关系", "下次一定", "慢慢来", "加油"]):
        return "encourage"
    if any(w in text for w in ["想一想", "试试看", "换个角度"]):
        return "thinking"
    if any(w in text for w in ["不适合聊", "这个话题"]):
        return "gentle_refuse"
    return "normal"


def build_context(pet_mood, today_tasks):
    """注入宠物状态和今日任务"""
    parts = []
    if pet_mood:
        m = (
            f"小龙当前状态：心情{pet_mood.get('mood', 50)}"
            f"、饱腹{pet_mood.get('hunger', 50)}"
            f"、亲密度{pet_mood.get('bond', 50)}。"
        )
        parts.append("[PET MOOD]\n" + m)
    if today_tasks:
        lines = [f"- {t.get('name', t.get('subject', '任务'))}" for t in today_tasks]
        parts.append("[TODAY TASKS]\n" + "\n".join(lines))
    return "\n\n".join(parts)


async def call_hermes(messages, session_id=None):
    """调用 Hermes API Server — 不传 model，用 profile 默认"""
    headers = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {HERMES_API_KEY}"

    payload = {
        "messages": messages,
        "stream": False,
        "temperature": 0.8,
    }
    if session_id:
        payload["session_id"] = session_id

    async with httpx.AsyncClient(timeout=float(HERMES_TIMEOUT)) as client:
        resp = await client.post(HERMES_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def chat(message, session_id=None, pet_mood=None, today_tasks=None):
    """主入口"""
    if not check_rate_limit():
        return {"text": "说太快啦，让小龙头休息一下", "session_id": session_id, "mood": "overwhelmed", "blocked": True}

    clean_text, blocked = filter_input(message)
    if blocked:
        return {"text": "这个话题不适合聊哦", "session_id": session_id, "mood": "gentle_refuse", "blocked": True}

    msgs = []
    if pet_mood or today_tasks:
        ctx = build_context(pet_mood, today_tasks)
        msgs.append({"role": "system", "content": ctx})
    msgs.append({"role": "user", "content": clean_text})

    try:
        full_text = await call_hermes(msgs, session_id=session_id)
    except httpx.TimeoutException:
        full_text = "小龙思考中，请稍后重试～"
    except Exception as e:
        full_text = "小龙正在休息，请稍后重试～"

    return {
        "text": full_text,
        "session_id": session_id,
        "mood": detect_mood_from_text(full_text),
        "blocked": False,
    }


async def call_hermes_stream(messages, session_id=None):
    """流式调用 Hermes（stream:True），逐块 yield 文本片段。

    解析 Hermes 的 OpenAI 兼容 SSE：每行 `data: {...}`，其中
    choices[0].delta.content 为增量文本；结束行为 `data: [DONE]`。
    若 Hermes 不支持流式或连接失败，抛出原异常，由路由层降级处理。
    """
    headers = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {HERMES_API_KEY}"

    payload = {
        "messages": messages,
        "stream": True,
        "temperature": 0.8,
    }
    if session_id:
        payload["session_id"] = session_id

    async with httpx.AsyncClient(timeout=float(HERMES_TIMEOUT)) as client:
        async with client.stream("POST", HERMES_API_URL, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = (line or "").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                except Exception:
                    continue
                choices = data.get("choices") or [{}]
                delta = (choices[0] or {}).get("delta") or {}
                content = delta.get("content") or ""
                if content:
                    yield content