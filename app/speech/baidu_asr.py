"""app/speech/baidu_asr.py - 百度短语音识别(REST, 标准版)

官方文档：https://cloud.baidu.com/doc/SPEECH/s/Jlbxdezuf
端点：http(s)://vop.baidu.com/server_api   （注意：不是 aip.baidubce.com/rpc/...）
音频要求：16kHz 单声道；服务端用 ffmpeg 统一转码为 16k 单声道（推荐 pcm，wav 亦可）。
免费额度：中文普通话 5万次 / 永久（来自「语音技术」控制台，个人实名自动发放）。
"""
import os
import base64
import logging
import httpx
from .base import ASRProvider, get_baidu_token

logger = logging.getLogger("homework-pet.speech.baidu_asr")

# 标准版普通话输入法模型（带标点）。极速版用 80001，端点改为 pro_api。
DEV_PID = 1537


class BaiduASR(ASRProvider):
    def __init__(self):
        self.app_id = os.getenv("BAIDU_APPID", "")
        self.api_key = os.getenv("BAIDU_API_KEY", "")
        self.secret_key = os.getenv("BAIDU_SECRET_KEY", "")
        # 官方文档给出的标准版地址。https 在公网更安全（Railway 出站支持）。
        self.endpoint = "https://vop.baidu.com/server_api"

    async def recognize(self, audio: bytes, fmt: str = "wav", rate: int = 16000) -> dict:
        token = await get_baidu_token(self.api_key, self.secret_key)
        # cuid：用于 UV 统计的唯一标识（≤60字符）。优先用 AppID，否则固定串。
        cuid = (self.app_id or "homework-pet")[:60]
        payload = {
            "format": fmt,
            "rate": rate,
            "channel": 1,
            "cuid": cuid,
            "token": token,
            "dev_pid": DEV_PID,
            "speech": base64.b64encode(audio).decode("ascii"),
            "len": len(audio),  # 原始字节数，非 base64 之后的长度
        }
        async with httpx.AsyncClient(timeout=30) as c:
            # 官方示例把 token 放在 body 里；query 也支持，二选一即可。
            r = await c.post(self.endpoint, json=payload)
            r.raise_for_status()
            data = r.json()
        if data.get("err_no", -1) != 0:
            raise RuntimeError(
                f"百度ASR错误 err_no={data.get('err_no')} msg={data.get('err_msg')} sn={data.get('sn')}"
            )
        result = data.get("result") or [""]
        text = (result[0] or "").strip()
        logger.info("百度ASR识别结果: %r", text)
        return {"text": text, "confidence": None}
