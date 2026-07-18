"""
app/chat_proxy.py - Hermes Bridge for homework-child profile.
"""

import os
import re
import time
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("homework-pet.chat_proxy")

HERMES_PROFILE = os.getenv("HERMES_PROFILE", "homework-child")
HERMES_EXEC = os.getenv("HERMES_EXEC", "")
HERMES_HOME = os.getenv("HERMES_HOME", "")
CHAT_PROXY_MODE = os.getenv("CHAT_PROXY_MODE", "subprocess")
HERMES_API_URL = os.getenv("HERMES_API_URL", "http://127.0.0.1:8642/v1/chat/completions")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")

BLACKLIST_PATTERNS = [
    r"处女|做爱|强奸|色情|激情|裸体",
    r"自杀|割腕|跳楼|杀人|血腥|恐怖.*故事|黑暗.*童话",
    r"习近平|毛泽东|法轮功|天安门.*事件|台独|新疆.*独",
]
BLACKLIST_RE = re.compile("|".join(BLACKLIST_PATTERNS), re.IGNORECASE)

_RATE_LOG = []
_RATE_MAX = 100
_RATE_WINDOW = 600
MAX_INPUT_LENGTH = 500


def _find_hermes_exec():
    if HERMES_EXEC and Path(HERMES_EXEC).exists():
        return HERMES_EXEC
    for c in [
        Path.home() / ".local/bin/hermes",
        Path.home() / ".local/bin/hermes.cmd",
        Path(os.getenv("LOCALAPPDATA", "")) / "hermes/hermes-agent/venv/Scripts/hermes.exe",
    ]:
        if c.exists():
            return str(c)
    return "hermes"


def check_rate_limit():
    now = time.time()
    global _RATE_LOG
    _RATE_LOG = [t for t in _RATE_LOG if now - t < _RATE_WINDOW]
    if len(_RATE_LOG) >= _RATE_MAX:
        return False
    _RATE_LOG.append(now)
    return True


def filter_input(text):
    if BLACKLIST_RE.search(text):
        return "", True
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
    return text, False


def build_system_prompt(pet_mood, today_tasks):
    parts = []
    if pet_mood:
        m = ("小龙当前状态：心情" + str(pet_mood.get("mood", 50)) +
             "、饱腹" + str(pet_mood.get("hunger", 50)) +
             "、亲密度" + str(pet_mood.get("bond", 50)) + "。")
        parts.append("[PET MOOD]\n" + m)
    if today_tasks:
        lines = []
        for x in today_tasks:
            lines.append("- " + x.get("name", x.get("subject", "任务")))
        parts.append("[TODAY TASKS]\n" + "\n".join(lines))
    return "\n\n".join(parts)


def detect_mood_from_text(text):
    if any(w in text for w in ["太棒了", "真厉害", "做得很好", "好棒"]):
        return "happy"
    if any(w in text for w in ["没关系", "下次一定", "慢慢来", "加油"]):
        return "encourage"
    if any(w in text for w in ["想一想", "试试看", "换个角度"]):
        return "thinking"
    if any(w in text for w in ["不适合聊", "这个话题"]):
        return "gentle_refuse"
    return "normal"


BOX_TOP = "╭" + "─"
BOX_BOT = "╰" + "─"


def _parse_hermes_output(output):
    lines = output.split("\n")
    response_lines = []
    in_resp = False
    for line in lines:
        if line.startswith(BOX_TOP):
            in_resp = True
            continue
        if line.startswith(BOX_BOT):
            in_resp = False
            continue
        if in_resp:
            if line.startswith("    "):
                line = line[4:]
            response_lines.append(line.rstrip())
    text = "\n".join(response_lines).strip()
    sid = None
    for line in lines:
        m = re.match(r"Session:\s*(\S+)", line)
        if m:
            sid = m.group(1)
    return {"text": text, "session_id": sid}


def call_hermes_subprocess(message, session_id=None, system_context=None):
    hermes_exec = _find_hermes_exec()
    cmd = [hermes_exec, "--profile", HERMES_PROFILE, "chat"]
    if system_context:
        full_msg = system_context + "\n\n---\n\n小朋友说：" + message
    else:
        full_msg = message
    if session_id:
        cmd.extend(["--continue", session_id])
    cmd.extend(["--query", full_msg])
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["TERM"] = "dumb"
    if HERMES_HOME:
        env["HERMES_HOME"] = HERMES_HOME
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=60, env=env, cwd=str(Path.home()))
        output = result.stdout + result.stderr
        parsed = _parse_hermes_output(output)
        mood = detect_mood_from_text(parsed["text"])
        return {"text": parsed["text"],
                "session_id": parsed.get("session_id", session_id),
                "mood": mood}
    except subprocess.TimeoutExpired:
        return {"text": "小龙好久没回应，可能正在休息～",
                "session_id": session_id, "mood": "overwhelmed"}
    except Exception as e:
        return {"text": "小龙暂时无法回应：" + str(e)[:50],
                "session_id": session_id, "mood": "error"}


def chat(message, session_id=None, pet_mood=None, today_tasks=None):
    """Main entry: process one chat message, returns dict with text/session_id/mood/blocked."""
    if not check_rate_limit():
        return {"text": "小龙说：你说得太快啦，让小龙头休息一下～",
                "session_id": session_id, "mood": "overwhelmed", "blocked": True}
    clean_text, blocked = filter_input(message)
    if blocked:
        return {"text": "小龙说：这个话题我们不适合聊哦，去看看今天的作业吧？",
                "session_id": session_id, "mood": "gentle_refuse", "blocked": True}
    ctx = ""
    if pet_mood or today_tasks:
        ctx = build_system_prompt(pet_mood or {}, today_tasks or [])
    if CHAT_PROXY_MODE == "http" and HERMES_API_URL:
        result = _call_hermes_http(clean_text, session_id, ctx)
    else:
        result = call_hermes_subprocess(clean_text, session_id, ctx)
    result["blocked"] = False
    return result


def _call_hermes_http(message, session_id=None, system_context=None):
    """HTTP mode for production (Linux)."""
    try:
        import httpx
    except ImportError:
        return call_hermes_subprocess(message, session_id, system_context)
    headers = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        headers["Authorization"] = "Bearer " + HERMES_API_KEY
    msgs = []
    if system_context:
        msgs.append({"role": "system", "content": system_context})
    msgs.append({"role": "user", "content": message})
    payload = {"model": "deepseek-chat", "messages": msgs,
               "stream": False, "max_tokens": 200}
    if session_id:
        payload["session_id"] = session_id
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(HERMES_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return {"text": text,
                    "session_id": session_id or data.get("session_id"),
                    "mood": detect_mood_from_text(text)}
    except Exception:
        return call_hermes_subprocess(message, session_id, system_context)
