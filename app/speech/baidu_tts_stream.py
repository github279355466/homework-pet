"""app/speech/baidu_tts_stream.py - 百度流式文本在线合成(WebSocket, 边合成边播放)

官方文档：https://cloud.baidu.com/doc/SPEECH/s/lm5xd63rn
连接：wss://aip.baidubce.com/ws/2.0/speech/publiccloudspeech/v1/tts?access_token=xxx&per=xxx
帧协议：
  客户端 -> 服务端：
    {"type":"system.start","payload":{"spd":5,"pit":5,"vol":5,"aue":3}}
    {"type":"text","payload":{"text":"..."}}
    {"type":"system.finish"}            # 通知服务端立即合成缓存文本
  服务端 -> 客户端：
    {"type":"system.started","code":0,...}   # 参数确认
    (binary 音频帧) ...                      # 边合成边吐
    {"type":"system.finished","code":0,...}  # 全部完成，随后断开
    {"type":"system.error","code":...,"message":"..."}

收益：配合后端 SSE(T3) + 前端流式播放(T5)，可实现「首句优先/边说边播」，端到端延迟最低。
依赖：websockets（仅 synthesize_stream 用到，惰性 import，不影响模块导入）。
"""
import os
import json
import logging
from typing import AsyncIterator
from .base import TTSProvider, get_baidu_token

logger = logging.getLogger("homework-pet.speech.baidu_tts_stream")

WS_URL = "wss://aip.baidubce.com/ws/2.0/speech/publiccloudspeech/v1/tts"
# 流式默认童声音色（度小童=110）；可用 BAIDU_TTS_PER 覆盖（与短文本共用旋钮）。
DEFAULT_PER = 110


class BaiduStreamTTS(TTSProvider):
    def __init__(self):
        self.app_id = os.getenv("BAIDU_APPID", "")
        self.api_key = os.getenv("BAIDU_API_KEY", "")
        self.secret_key = os.getenv("BAIDU_SECRET_KEY", "")
        self.per = int(os.getenv("BAIDU_TTS_PER", str(DEFAULT_PER)))
        self.spd = int(os.getenv("BAIDU_TTS_SPD", "5"))
        self.pit = int(os.getenv("BAIDU_TTS_PIT", "5"))
        self.vol = int(os.getenv("BAIDU_TTS_VOL", "5"))
        self.aue = int(os.getenv("BAIDU_TTS_AUE", "3"))

    async def synthesize_stream(self, text: str, **opts) -> AsyncIterator[bytes]:
        """逐帧产出音频字节（mp3/pcm/wav 取决于 aue）。异常在帧协议错误时抛出。"""
        token = await get_baidu_token(self.api_key, self.secret_key)
        url = f"{WS_URL}?access_token={token}&per={opts.get('per', self.per)}"
        import websockets  # 惰性 import：未装 websockets 时不影响模块导入/短文本路径
        async with websockets.connect(url, max_size=None, open_timeout=15, close_timeout=5) as ws:
            # 1) 开始帧
            await ws.send(json.dumps({
                "type": "system.start",
                "payload": {
                    "spd": opts.get("spd", self.spd),
                    "pit": opts.get("pit", self.pit),
                    "vol": opts.get("vol", self.vol),
                    "aue": self.aue,
                },
            }))
            # 2) 等待参数确认
            started = json.loads(await ws.recv())
            if started.get("type") == "system.started" and started.get("code", -1) != 0:
                raise RuntimeError(f"百度流式TTS参数错误 code={started.get('code')} msg={started.get('message')}")
            if started.get("type") == "system.error":
                raise RuntimeError(f"百度流式TTS错误 code={started.get('code')} msg={started.get('message')}")
            # 3) 发送文本
            await ws.send(json.dumps({"type": "text", "payload": {"text": text}}))
            # 4) 通知结束（强制刷新缓存文本）
            await ws.send(json.dumps({"type": "system.finish"}))
            # 5) 接收音频帧直到 finished
            while True:
                msg = await ws.recv()
                if isinstance(msg, (bytes, bytearray)):
                    yield bytes(msg)
                    continue
                frame = json.loads(msg)
                ftype = frame.get("type")
                if ftype == "system.finished":
                    break
                if ftype == "system.error":
                    raise RuntimeError(f"百度流式TTS错误 code={frame.get('code')} msg={frame.get('message')}")
                # 其他文本帧（如再次 system.started）忽略

    async def synthesize(self, text: str, **opts) -> bytes:
        """非流式兜底：缓冲全部音频帧返回（供还不支持流式播放的调用方使用）。"""
        chunks = [c async for c in self.synthesize_stream(text, **opts)]
        return b"".join(chunks)
