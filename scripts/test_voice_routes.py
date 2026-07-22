"""路由级 mock 验证：/api/chat/voice 与 /api/chat/tts。

不依赖真实百度密钥：本机未设 BAIDU_* 时 factory 自动走 MockASR/MockTTS。
仅验证「HTTP 接线 + ffmpeg 转码 + 适配器返回」链路正确。
"""
import os
import sys
import subprocess
import tempfile

# 安全：避免任何可能的 DB 触碰落到生产文件
os.environ.setdefault("HOMEWORK_PET_DB_PATH", os.path.join(tempfile.gettempdir(), "test_voice_routes.db"))

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, os.path.abspath(APP_DIR))
os.chdir(os.path.abspath(APP_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("✅" if cond else "❌") + f" {name}" + (f" -> {detail}" if detail else ""))


def make_silent_wav(path, seconds=0.5):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono",
         "-t", str(seconds), "-ar", "16000", "-ac", "1", "-f", "wav", path],
        capture_output=True, check=True,
    )


def main():
    client = TestClient(app)

    # 1) /api/chat/tts：文本 -> 音频字节（mock 返回 ID3 头占位）
    r = client.post("/api/chat/tts", json={"text": "你好小龙"})
    check("TTS 路由返回 200", r.status_code == 200, f"status={r.status_code}")
    check("TTS 返回 audio/mpeg", r.headers.get("content-type", "").startswith("audio/mpeg"),
          r.headers.get("content-type"))
    check("TTS 返回非空音频字节", len(r.content) > 0, f"{len(r.content)} bytes")
    check("TTS mock 含 ID3 标记", r.content[:3] == b"ID3", r.content[:8])

    # 2) /api/chat/tts：空文本 -> 400
    r2 = client.post("/api/chat/tts", json={"text": ""})
    check("TTS 空文本返回 400", r2.status_code == 400, f"status={r2.status_code}")

    # 3) /api/chat/voice：上传 wav -> 经 ffmpeg 转码 -> MockASR 返回文本
    wav_path = os.path.join(tempfile.gettempdir(), "silent_test.wav")
    make_silent_wav(wav_path)
    with open(wav_path, "rb") as f:
        rv = client.post("/api/chat/voice", files={"file": ("rec.wav", f, "audio/wav")})
    check("Voice 路由返回 200", rv.status_code == 200, f"status={rv.status_code}")
    if rv.status_code == 200:
        body = rv.json()
        check("Voice 返回 text 字段", "text" in body, str(body)[:80])
        check("Voice 走 Mock 识别", "[mock-asr]" in body.get("text", ""), body.get("text"))

    # 4) /api/chat/voice：缺音频 -> 400
    r4 = client.post("/api/chat/voice")
    check("Voice 缺音频返回 400", r4.status_code == 400, f"status={r4.status_code}")

    print(f"\n通过 {len(PASS)} / 失败 {len(FAIL)}")
    if FAIL:
        print("失败项:", FAIL)
        sys.exit(1)


if __name__ == "__main__":
    main()
