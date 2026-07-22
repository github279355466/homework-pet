"""SSE 聊天接口单测：验证 /api/chat/message 流式帧格式 + 降级。

不依赖真实 Hermes：monkeypatch call_hermes_stream 注入增量。
用 FastAPI TestClient 收集完整 SSE 文本后按 \n\n 分帧解析。
"""
import os
import sys
import json

os.environ.setdefault("HOMEWORK_PET_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "backups", "test_homework_pet.db"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import chat_proxy
from fastapi.testclient import TestClient
import main

# 注入可控的流式片段
async def _fake_stream(messages, session_id=None):
    for piece in ["你好", "小朋友", "！今天作业写完了吗？"]:
        yield piece

chat_proxy.call_hermes_stream = _fake_stream


def parse_frames(text):
    frames = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        line = next((l for l in block.split("\n") if l.startswith("data:")), None)
        if not line:
            continue
        frames.append(json.loads(line[len("data:"):].strip()))
    return frames


def test_sse_normal():
    client = TestClient(main.app)
    resp = client.post("/api/chat/message", json={"text": "小龙你好", "session_id": "s1", "mode": "text"})
    assert resp.status_code == 200, resp.status_code
    assert resp.headers.get("content-type", "").startswith("text/event-stream"), resp.headers
    frames = parse_frames(resp.text)
    types = [f["type"] for f in frames]
    assert types[0] == "token"
    assert types[-1] == "done"
    # 聚合 token 应等于 done 的文本
    joined = "".join(f["text"] for f in frames if f["type"] == "token")
    done = [f for f in frames if f["type"] == "done"][0]
    assert joined == done["text"], (joined, done["text"])
    assert done["text"] == "你好小朋友！今天作业写完了吗？"
    assert done["session_id"] == "s1"
    print("✅ test_sse_normal 通过，帧数:", len(frames))


def test_sse_empty_message():
    client = TestClient(main.app)
    resp = client.post("/api/chat/message", json={"text": "   ", "session_id": "s2"})
    assert resp.status_code == 400
    print("✅ test_sse_empty_message 通过（400）")


def test_sse_hermes_failure_degrade():
    async def _boom(messages, session_id=None):
        raise RuntimeError("hermes down")
        yield  # 使其成为 async generator（不可达）
    chat_proxy.call_hermes_stream = _boom
    client = TestClient(main.app)
    resp = client.post("/api/chat/message", json={"text": "小龙", "session_id": "s3"})
    frames = parse_frames(resp.text)
    assert frames[-1]["type"] == "done"
    assert "小龙正在休息" in frames[-1]["text"], frames[-1]["text"]
    print("✅ test_sse_hermes_failure_degrade 通过")
    # 还原
    chat_proxy.call_hermes_stream = _fake_stream


if __name__ == "__main__":
    test_sse_normal()
    test_sse_empty_message()
    test_sse_hermes_failure_degrade()
    print("\n全部 SSE 测试通过 ✅")
