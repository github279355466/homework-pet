"""app/speech/factory.py - 按环境变量选择适配器

切换厂商仅改 SPEECH_ASR_PROVIDER / SPEECH_TTS_PROVIDER，路由/前端零改动。
若 provider=baidu 但未完整配置 BAIDU_* 密钥，自动回退 Mock（避免部署前误调用失败）。
"""
import os
import logging
from .base import ASRProvider, TTSProvider, MockASR, MockTTS
from .baidu_asr import BaiduASR
from .baidu_tts import BaiduTTS

logger = logging.getLogger("homework-pet.speech.factory")


def _baidu_configured() -> bool:
    return bool(
        os.getenv("BAIDU_API_KEY")
        and os.getenv("BAIDU_SECRET_KEY")
        and os.getenv("BAIDU_APPID")
    )


def get_asr_provider() -> ASRProvider:
    prov = os.getenv("SPEECH_ASR_PROVIDER", "baidu").lower()
    if prov == "baidu":
        if _baidu_configured():
            return BaiduASR()
        logger.warning("BAIDU_* 未完整配置，ASR 回退 Mock")
        return MockASR()
    logger.warning("未知 SPEECH_ASR_PROVIDER=%s，回退 Mock", prov)
    return MockASR()


def get_tts_provider() -> TTSProvider:
    prov = os.getenv("SPEECH_TTS_PROVIDER", "baidu").lower()
    if prov == "baidu":
        if not _baidu_configured():
            logger.warning("BAIDU_* 未完整配置，TTS 回退 Mock")
            return MockTTS()
        # SPEECH_TTS_MODE=stream 走 WebSocket 流式（首句优先，需 T3 SSE + T5 前端配合）；
        # 默认 short 走 REST 短文本（整句合成，前端按句切分队列播放）。
        mode = os.getenv("SPEECH_TTS_MODE", "short").lower()
        if mode == "stream":
            from .baidu_tts_stream import BaiduStreamTTS
            return BaiduStreamTTS()
        return BaiduTTS()
    logger.warning("未知 SPEECH_TTS_PROVIDER=%s，回退 Mock", prov)
    return MockTTS()
