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
MAX_INPUT_LENGTH = 500
_RATE_LOG = []


def check_rate_limit():
    """Rate limit: 100 requests per 10 minutes (sliding window)."""
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
    """Block blacklisted content and truncate long messages."""
    BLACKLIST_RE = re.compile(
        "|".join([
            r"\u5907\u5973|\u505a\u7231|\u5f3a\u5978|\u8272\u60c5|\u6fc0\u60c5|\u88f8\u4f53",
            r"\u81ea\u6740|\u5272\u8155|\u8df3\u697c|\u6740\u4eba|\u8840\u8165|\u6050\u6016.*\u6545\u4e8b|\u9ed1\u6697.*\u7ae5\u8bdd",
            r"\u4e60\u8fd1\u5e73|\u6bdb\u6cfd\u4e1c|\u6cd5\u8f6e\u529f|\u5929\u5b89\u95e8.*\u4e8b\u4ef6|\u53f0\u72ec|\u65b0\u7586.*\u72ec",
        ]),
        re.IGNORECASE,
    )
    if BLACKLIST_RE.search(text):
        return "", True
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
    return text, False


def build_system_prompt(pet_mood, today_tasks):
    """Inject pet state and daily tasks into system prompt."""
    parts = []
    if pet_mood:
        m = (
            f"LongCat-2.0: \u5fc3\u60c5{pet_mood.get('mood', 50)}"
            f"\u3001\u9971\u8179{pet_mood.get('hunger', 50)}"
            f"\u3001\u4eb2\u5bc6\u5ea6{pet_mood.get('bond', 50)}\u3002"
        )
        parts.append("[PET MOOD]\n" + m)
    if today_tasks:
        lines = [f"- {x.get('name', x.get('subject', '\u4efb\u52a1'))}" for x in today_tasks]
        parts.append("[TODAY TASKS]\n" + "\n".join(lines))
    return "\n\n".join(parts)


def detect_mood_from_text(text):
    """Pick a mood emoji based on response keywords."""
    if any(w in text for w in ["\u592a\u68d2\u4e86", "\u771f\u5389\u5bb3", "\u505a\u5f97\u5f88\u597d", "\u597d\u68d2"]):
        return "happy"
    if any(w in text for w in ["\u6ca1\u5173\u7cfb", "\u4e0b\u6b21\u4e00\u5b9a", "\u6162\u6162\u6765", "\u52a0\u6cb9"]):
        return "encourage"
    if any(w in text for w in ["\u60f3\u4e00\u60f3", "\u8bd5\u8bd5\u770b", "\u6362\u4e2a\u89d2\u5ea6"]):
        return "thinking"
    if any(w in text for w in ["\u4e0d\u9002\u5408\u804a", "\u8fd9\u4e2a\u8bdd\u9898"]):
        return "gentle_refuse"
    return "normal"


BOX_TOP = "\u256d\u2500"
BOX_BOT = "\u2570\u2500"


def _strip_ansi(text):
    """Remove ANSI escape sequences (ESC[ codes)."""
    return re.sub(chr(0x1B) + r'\[[0-9;]*m', '', text)



def _find_hermes_box(lines):
    """Find response box start/end indices. Handles both TTY and piped output."""
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if start_idx is None:
            if "Hermes" in line and (chr(0x2695) in line or chr(0x256d) in line or (chr(0x2500) in line and i > 0)):
                start_idx = i
        else:
            stripped = line.strip()
            if stripped and all(c == chr(0x2500) for c in stripped) and len(stripped) > 10:
                end_idx = i
                break
    return start_idx, end_idx
def _parse_hermes_output(output):
    """Parse Hermes output using flexible box detection."""
    output = _strip_ansi(output)
    lines = output.split("\n")
    result = _parse_and_extract(lines)
    return result

def _parse_and_extract(lines):
    start_idx, end_idx = _find_hermes_box(lines)
    if start_idx is None:
        return {"text": "", "session_id": None}
    end = end_idx if end_idx is not None else len(lines)
    content_lines = lines[start_idx + 1 : end]
    response_lines = []
    for line in content_lines:
        if line.startswith("     "): line = line[5:]
        elif line.startswith("    "): line = line[4:]
        elif line.startswith("  "): line = line[2:]
        s = line.strip()
        if s:
            response_lines.append(s)
    text = chr(10).join(response_lines).strip()
    sid = None
    for line in lines:
        m = re.match(r"Session:\s*(\S+)", line)
        if m:
            sid = m.group(1)
            break
    return {"text": text, "session_id": sid}


def _find_hermes_exec():
    """Locate hermes executable."""
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


def call_hermes_subprocess(message, session_id=None, system_context=None):
    """Call Hermes in subprocess mode."""
    hermes_exec = _find_hermes_exec()
    cmd = [hermes_exec, "--profile", HERMES_PROFILE, "chat"]
    if system_context:
        full_msg = system_context + "\n\n---\n\n\u5c0f\u670b\u53cb\u8bf4\uff1a" + message
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
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env=env,
            cwd=str(Path.home()),
        )
        output = result.stdout + result.stderr
        parsed = _parse_hermes_output(output)
        mood = detect_mood_from_text(parsed["text"])
        return {
            "text": parsed["text"],
            "session_id": parsed.get("session_id", session_id),
            "mood": mood,
        }
    except subprocess.TimeoutExpired:
        return {
            "text": "LongCat-2.0: \u5f88\u4e45\u6ca1\u56de\u5e94\uff0c\u53ef\u80fd\u5728\u4f11\u606f",
            "session_id": session_id,
            "mood": "overwhelmed",
        }
    except Exception as e:
        return {
            "text": "LongCat-2.0\u6682\u65f6\u65e0\u6cd5\u56de\u5e94\uff1a" + str(e)[:50],
            "session_id": session_id,
            "mood": "error",
        }


def call_hermes_http(message, session_id=None, system_context=None):
    """HTTP mode for production (Linux) ."""
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
    payload = {
        "model": "deepseek-chat",
        "messages": msgs,
        "stream": False,
        "max_tokens": 200,
    }
    if session_id:
        payload["session_id"] = session_id
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(HERMES_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return {
                "text": text,
                "session_id": session_id or data.get("session_id"),
                "mood": detect_mood_from_text(text),
            }
    except Exception:
        return call_hermes_subprocess(message, session_id, system_context)


def chat(message, session_id=None, pet_mood=None, today_tasks=None):
    """Main entry: process one chat message."""
    if not check_rate_limit():
        return {
            "text": "LongCat-2.0: \u8bf4\u5f97\u592a\u5feb\u5566",
            "session_id": session_id,
            "mood": "overwhelmed",
            "blocked": True,
        }
    clean_text, blocked = filter_input(message)
    if blocked:
        return {
            "text": "LongCat-2.0: \u8fd9\u4e2a\u8bdd\u9898\u6211\u4eec\u4e0d\u9002\u5408\u804a",
            "session_id": session_id,
            "mood": "gentle_refuse",
            "blocked": True,
        }
    ctx = ""
    if pet_mood or today_tasks:
        ctx = build_system_prompt(pet_mood or {}, today_tasks or [])
    if CHAT_PROXY_MODE == "http" and HERMES_API_URL:
        result = call_hermes_http(clean_text, session_id, ctx)
    else:
        result = call_hermes_subprocess(clean_text, session_id, ctx)
    result["blocked"] = False
    with open("C:/Users/Administrator/Desktop/chat_debug.json", "w", encoding="utf-8") as _dbg:
        import json as _j
        _j.dump(result, _dbg, ensure_ascii=False)
    return result




