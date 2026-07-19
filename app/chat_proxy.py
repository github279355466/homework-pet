"""
app/chat_proxy.py - Hermes Bridge for homework-child profile.
通过环境变量控制调用模式:
  CHAT_PROXY_MODE=http|subprocess  (默认 http，用于远程部署)
  HERMES_API_URL=http://...:8642/v1/chat/completions
  HERMES_API_KEY=xxx (Bearer <REDACTED>)
  HERMES_TIMEOUT=60 (超时秒数)
"""

import os
import re
import time
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("homework-pet.chat_proxy")

# ===== 配置 (全部通过环境变量控制) =====
HERMES_PROFILE = os.getenv("HERMES_PROFILE", "homework-child")
HERMES_EXEC = os.getenv("HERMES_EXEC", "")
HERMES_API_URL = os.getenv("HERMES_API_URL", "")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
CHAT_PROXY_MODE = os.getenv("CHAT_PROXY_MODE", "http" if HERMES_API_URL else "subprocess")
HERMES_TIMEOUT = int(os.getenv("HERMES_TIMEOUT", "60"))
MAX_INPUT_LENGTH = 500
_RATE_LOG = []


def check_rate_limit():
    """频率限制: 100次/10分钟滑动窗口"""
    _RATE_MAX = 100
    _RATE_WINDOW = 600
    now = time.time()
    global _RATE_LOG
    _RATE_LOG = [t for t in _RATE_LOG if now - t < _RATE_WINDOW]
    if len(_RATE_LOG) >= _RATE_MAX:
        return False
    _RATE_LOG.append(now)
    return True


def filter_input(text):
    """安全过滤 + 长度截断"""
    BLACKLIST_RE = re.compile(
        "|".join([
            r"做爱|强奸|激情|裸体|色情",
            r"自杀|割腕|跳楼|杀人|血腥",
        ]),
        re.IGNORECASE,
    )
    if BLACKLIST_RE.search(text):
        return "", True
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
    return text, False


def build_system_prompt(pet_mood, today_tasks):
    """注入宠物状态和今日任务到 prompt"""
    parts = []
    if pet_mood:
        m = (
            f"小龙当前状态：心情{pet_mood.get('mood', 50)}"
            f"、饱腹{pet_mood.get('hunger', 50)}"
            f"、亲密度{pet_mood.get('bond', 50)}。"
        )
        parts.append("[PET MOOD]\n" + m)
    if today_tasks:
        lines = [f"- {x.get('name', x.get('subject', '任务'))}" for x in today_tasks]
        parts.append("[TODAY TASKS]\n" + "\n".join(lines))
    return "\n\n".join(parts)


def detect_mood_from_text(text):
    """根据回复内容检测心情"""
    if any(w in text for w in ["太棒了", "真厉害", "做得很好", "好棒"]):
        return "happy"
    if any(w in text for w in ["没关系", "下次一定", "慢慢来", "加油"]):
        return "encourage"
    if any(w in text for w in ["想一想", "试试看", "换个角度"]):
        return "thinking"
    if any(w in text for w in ["不适合聊", "这个话题"]):
        return "gentle_refuse"
    return "normal"


# ═══════════════════════════════════════════════
# HTTP 模式 (远程 Hermes)
# ═══════════════════════════════════════════════
def call_hermes_http(message, session_id=None, system_context=None):
    """HTTP 模式: 调用远程 Hermes API Server"""
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
        "model": "deepseek-chat",
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
            "text": f"小龙思考超时（>{HERMES_TIMEOUT}s），请稍后重试",
            "session_id": session_id,
            "mood": "overwhelmed",
        }
    except Exception as e:
        return {
            "text": f"连接 Hermes 失败: {str(e)[:60]}",
            "session_id": session_id,
            "mood": "error",
        }


# ═══════════════════════════════════════════════
# Subprocess 模式 (本地 Hermes)
# ═══════════════════════════════════════════════
BOX_TOP = "╭─"
BOX_BOT = "╰─"


def _strip_ansi(text):
    return re.sub(chr(0x1B) + r'\[[0-9;]*m', '', text)


def call_hermes_subprocess(message, session_id=None, system_context=None):
    """Subprocess 模式: 本地调用 hermes CLI"""
    hermes_exec = HERMES_EXEC or "hermes"
    cmd = [hermes_exec, "--profile", HERMES_PROFILE, "chat"]
    if session_id:
        cmd.extend(["--continue", session_id])
    cmd.extend(["--query", message])

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["TERM"] = "dumb"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=HERMES_TIMEOUT,
            env=env,
        )
        # 解析输出
        output = result.stdout
        # 简单提取回复: 找第一个非空行且不是 Reasoning/Query/Session
        lines = _strip_ansi(output).split("\n")
        response_lines = []
        capture = False
        for line in lines:
            s = line.strip()
            if not s:
                continue
            if "Hermes" in s and ("─" in s or "⚕" in s):
                capture = True
                continue
            if capture and "─" in s and len(s) > 20:
                break
            if capture and s and not any(k in s for k in ["Query:", "Session:", "Duration:", "Reasoning", "Resume"]):
                response_lines.append(s)

        text = "\n".join(response_lines).strip()
        if not text:
            # 降级: 把所有非空非系统行拼起来
            text = "\n".join(
                l.strip() for l in lines
                if l.strip() and not any(
                    k in l for k in ["Query:", "Session:", "Duration:", "Reasoning", "Resume", "Messages:", "──", "hermes"]
                )
            ).strip()

        return {
            "text": text or "小龙没有回复内容",
            "session_id": session_id,
            "mood": detect_mood_from_text(text),
        }

    except subprocess.TimeoutExpired:
        return {
            "text": f"小龙思考超时（>{HERMES_TIMEOUT}s）",
            "session_id": session_id,
            "mood": "overwhelmed",
        }
    except Exception as e:
        return {
            "text": f"调用本地 Hermes 失败: {str(e)[:60]}",
            "session_id": session_id,
            "mood": "error",
        }


# ═══════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════
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

    if CHAT_PROXY_MODE == "http":
        result = call_hermes_http(clean_text, session_id, ctx)
    else:
        result = call_hermes_subprocess(clean_text, session_id, ctx)

    result["blocked"] = False
    return result
