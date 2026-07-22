"""app/speech/base.py - 抽象接口 + 百度 access_token 缓存 + Mock 降级

所有厂商在概念上 I/O 一致：
  ASR = 音频字节 -> 文本
  TTS = 文本 -> 音频字节
差异（鉴权/格式/协议/解析）封装进各自适配器内部，路由层不感知。
"""
import os
import time
import asyncio
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("homework-pet.speech")


# ---------- 抽象接口 ----------
class ASRProvider(ABC):
    @abstractmethod
    async def recognize(self, audio: bytes, fmt: str = "wav", rate: int = 16000) -> dict:
        """音频字节 -> {'text': str, 'confidence': float|None}"""


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, **opts) -> bytes:
        """文本 -> 音频字节 (mp3)"""


# ---------- 百度 access_token 缓存 ----------
# token 有效期 30 天；缓存在内存，提前 5 天过期重取（Railway ephemeral，冷启动重取无害）
_TOKEN_CACHE = {"token": None, "expire_at": 0.0}
_TOKEN_LOCK = asyncio.Lock()


async def get_baidu_token(api_key: str, secret_key: str) -> str:
    """获取百度 access_token（带内存缓存，避免每次请求都申请）"""
    now = time.time()
    if _TOKEN_CACHE["token"] and _TOKEN_CACHE["expire_at"] > now:
        return _TOKEN_CACHE["token"]
    async with _TOKEN_LOCK:
        if _TOKEN_CACHE["token"] and _TOKEN_CACHE["expire_at"] > now:
            return _TOKEN_CACHE["token"]
        import httpx

        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        }
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        if "access_token" not in data:
            raise RuntimeError(f"百度 token 获取失败: {data}")
        _TOKEN_CACHE["token"] = data["access_token"]
        expires_in = data.get("expires_in", 2592000)
        _TOKEN_CACHE["expire_at"] = now + expires_in - 5 * 86400
        logger.info("百度 access_token 已刷新，有效期 %s 秒", expires_in)
        return _TOKEN_CACHE["token"]


# ---------- Mock 降级（无密钥/未配置时） ----------
class MockASR(ASRProvider):
    async def recognize(self, audio, fmt="wav", rate=16000):
        return {"text": "[mock-asr] 你好小龙，这是模拟识别结果", "confidence": 0.99}


class MockTTS(TTSProvider):
    async def synthesize(self, text, **opts):
        # 用 ID3(mp3) 头冒充，方便前端/测试识别类型
        return b"ID3\x03\x00\x00\x00\x00\x00\x00MOCK_TTS:" + text.encode("utf-8")[:24]
