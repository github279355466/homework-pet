"""app/speech - 语音适配层（ASR/TTS 多厂商可插拔）

当前实现（全百度，对照官方文档）：
  - ASR : 短语音识别标准版  POST https://vop.baidu.com/server_api
  - TTS : 短文本在线合成    POST https://tsn.baidu.com/text2audio  (整句，默认度丫丫 per=4)
          流式文本在线合成  WebSocket wss://aip.baidubce.com/ws/2.0/speech/publiccloudspeech/v1/tts
          （首句优先/边合成边播放，默认童声 per=110；SPEECH_TTS_MODE=stream 启用）
切换厂商仅改环境变量 SPEECH_ASR_PROVIDER / SPEECH_TTS_PROVIDER，路由/前端零改动。
"""
from .factory import get_asr_provider, get_tts_provider
from .base import ASRProvider, TTSProvider

__all__ = ["get_asr_provider", "get_tts_provider", "ASRProvider", "TTSProvider"]
