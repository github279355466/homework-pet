"""scripts/test_speech_baidu_requests.py
对照百度官方文档逐项校验 app/speech 适配器请求构造与响应解析（mock 注入，无需真实密钥）。

校验点：
  ASR  : 端点必须为 vop.baidu.com/server_api；body 含 token/dev_pid=1537/speech(base64)/len
  TTS  : 必须用 POST 表单(data=) 而非 GET(params=)；tex/tok/per=4/aue=3；成功返回音频、失败抛 err_no
  TTS流: WebSocket 帧协议 system.start -> text -> system.finish；接收 binary 音频帧 -> system.finished
  Factory: 未配置密钥回退 Mock；SPEECH_TTS_MODE=stream/short 切换适配器
"""
import asyncio
import sys
import json
import types
import os

import app.speech.base as base
import app.speech.baidu_asr as ba
import app.speech.baidu_tts as bt
import app.speech.baidu_tts_stream as bts
from app.speech import factory

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'OK' if cond else 'XX'}] {name}" + (f"  -> {detail}" if (detail and not cond) else ""))


async def fake_token(*a, **k):
    return "FAKE_TOKEN"


base.get_baidu_token = fake_token
ba.get_baidu_token = fake_token
bt.get_baidu_token = fake_token
bts.get_baidu_token = fake_token


# ---------- Fake httpx.AsyncClient ----------
class FakeResp:
    def __init__(self, *, json_data=None, content=b"", headers=None, status_code=200):
        self._json = json_data
        self.content = content
        self.headers = headers or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


class FakeAsyncClient:
    CAP = {}
    MODE = "audio"  # audio | err

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, *, json=None, data=None, params=None):
        FakeAsyncClient.CAP.update(method="POST", url=url, json=json, data=data, params=params)
        if "vop.baidu.com" in url:
            return FakeResp(json_data={"err_no": 0, "err_msg": "success.", "result": ["北京天气"]})
        if "tsn.baidu.com" in url:
            if FakeAsyncClient.MODE == "audio":
                return FakeResp(content=b"\xff\xfb\x90audio", headers={"Content-Type": "audio/mp3"})
            return FakeResp(json_data={"err_no": 500, "err_msg": "notsupport."},
                            headers={"Content-Type": "application/json"})
        return FakeResp(json_data={"err_no": 0, "result": ["x"]})


ba.httpx.AsyncClient = FakeAsyncClient
bt.httpx.AsyncClient = FakeAsyncClient


# ---------- Fake websockets ----------
class FakeWS:
    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def send(self, data):
        self.sent.append(json.loads(data))

    async def recv(self):
        if not self.frames:
            return json.dumps({"type": "system.finished", "code": 0})
        return self.frames.pop(0)


class FakeWebsockets:
    def __init__(self, frames):
        self._frames = frames
        self.last_ws = None

    def connect(self, *a, **k):
        self.last_ws = FakeWS(self._frames)
        return self.last_ws


def install_fake_websockets(frames):
    fw = FakeWebsockets(frames)
    mod = types.ModuleType("websockets")
    mod.connect = fw.connect
    sys.modules["websockets"] = mod
    return fw


# ---------- 1) ASR ----------
async def test_asr():
    print("\n[ASR] 短语音识别 REST")
    FakeAsyncClient.CAP.clear()
    res = await ba.BaiduASR().recognize(b"PCMDATA" * 10, fmt="wav", rate=16000)
    cap = FakeAsyncClient.CAP
    check("ASR 端点=vop.baidu.com/server_api", "vop.baidu.com/server_api" in cap.get("url", ""), cap.get("url"))
    check("ASR 用 POST", cap.get("method") == "POST")
    j = cap.get("json") or {}
    check("ASR body 含 token", j.get("token") == "FAKE_TOKEN")
    check("ASR body 含 dev_pid=1537", j.get("dev_pid") == 1537)
    check("ASR body 含 speech(base64)", bool(j.get("speech")) and j.get("speech") != "PCMDATA")
    check("ASR body 含 len(原始字节数)", j.get("len") == len(b"PCMDATA" * 10))
    check("ASR 返回文本正确", res["text"] == "北京天气", res)


# ---------- 2) TTS 短文本 ----------
async def test_tts():
    print("\n[TTS] 短文本在线合成 POST 表单")
    FakeAsyncClient.MODE = "audio"
    FakeAsyncClient.CAP.clear()
    audio = await bt.BaiduTTS().synthesize("你好小龙")
    cap = FakeAsyncClient.CAP
    check("TTS 端点=tsn.baidu.com/text2audio", "tsn.baidu.com/text2audio" in cap.get("url", ""), cap.get("url"))
    check("TTS 用 POST(data=表单)", cap.get("method") == "POST" and cap.get("data") is not None and cap.get("params") is None)
    d = cap.get("data") or {}
    check("TTS form 含 tex", d.get("tex") == "你好小龙")
    check("TTS form 含 tok", d.get("tok") == "FAKE_TOKEN")
    check("TTS form 含 per=4(度丫丫)", d.get("per") == 4)
    check("TTS form 含 aue=3(mp3)", d.get("aue") == 3)
    check("TTS 成功返回音频字节", audio[:2] == b"\xff\xfb", audio[:4])
    # 错误分支
    FakeAsyncClient.MODE = "err"
    raised = False
    try:
        await bt.BaiduTTS().synthesize("x")
    except RuntimeError as e:
        raised = True
        check("TTS 错误抛 err_no=500", "500" in str(e), str(e))
    check("TTS 错误确实抛出", raised)
    FakeAsyncClient.MODE = "audio"


# ---------- 3) TTS 流式 ----------
async def test_tts_stream():
    print("\n[TTS流] 流式文本在线合成 WebSocket 帧协议")
    frames = [
        json.dumps({"type": "system.started", "code": 0, "message": "success"}),
        b"\x11\x22\x33",
        b"\x44\x55\x66",
        json.dumps({"type": "system.finished", "code": 0}),
    ]
    fw = install_fake_websockets(frames)
    stts = bts.BaiduStreamTTS()
    chunks = [c async for c in stts.synthesize_stream("今天天气真好")]
    check("流式逐帧产出音频", chunks == [b"\x11\x22\x33", b"\x44\x55\x66"], chunks)
    joined = await stts.synthesize("今天天气真好")
    check("缓冲 synthesize 合并音频", joined == b"\x11\x22\x33\x44\x55\x66")
    sent_types = [s.get("type") for s in fw.last_ws.sent]
    check("发送帧顺序 system.start->text->system.finish",
          sent_types == ["system.start", "text", "system.finish"], sent_types)
    check("流式默认童声音色 per=110", stts.per == 110, stts.per)


# ---------- 4) Factory ----------
def test_factory():
    print("\n[Factory] 厂商选择与降级")
    for k in ("BAIDU_API_KEY", "BAIDU_SECRET_KEY", "BAIDU_APPID", "SPEECH_TTS_MODE"):
        os.environ.pop(k, None)
    check("未配置密钥 ASR 回退 Mock", factory.get_asr_provider().__class__.__name__ == "MockASR")
    check("未配置密钥 TTS 回退 Mock", factory.get_tts_provider().__class__.__name__ == "MockTTS")

    os.environ.update({"BAIDU_API_KEY": "k", "BAIDU_SECRET_KEY": "s", "BAIDU_APPID": "app"})
    os.environ["SPEECH_TTS_MODE"] = "stream"
    check("SPEECH_TTS_MODE=stream 选流式TTS",
          factory.get_tts_provider().__class__.__name__ == "BaiduStreamTTS")
    os.environ["SPEECH_TTS_MODE"] = "short"
    check("默认 short 选短文本TTS",
          factory.get_tts_provider().__class__.__name__ == "BaiduTTS")


async def main():
    await test_asr()
    await test_tts()
    await test_tts_stream()
    test_factory()
    print(f"\n==== 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 ====")
    if FAIL:
        print("失败项：", FAIL)
        sys.exit(1)
    print("全部通过 ✅")


if __name__ == "__main__":
    asyncio.run(main())
