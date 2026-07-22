"""app/speech/baidu_tts.py - 百度短文本在线合成(REST, POST 表单, 返回 mp3)

官方文档：https://cloud.baidu.com/doc/SPEECH/s/mlbxh7xie
端点：http(s)://tsn.baidu.com/text2audio
鉴权：tok = access_token（由 base.get_baidu_token 获取并缓存）
说明：文档推荐 POST 表单方式（tex 走表单编码，避免 GET 拼接 tex 二次 urlencode 的 +/&/= 丢字坑）。
      单次 tex ≤ 1024 GBK 字节（约 340 汉字）；超出按计费次数累加，这里做安全截断。
      如需「边合成边播放」（首句优先），见 baidu_tts_stream.py（WebSocket 流式）。
"""
import os
import logging
import httpx
from .base import TTSProvider, get_baidu_token

logger = logging.getLogger("homework-pet.speech.baidu_tts")

# 发音人参考（基础音库）：0=度小美(普通女) 1=度小宇(普通男) 3=度逍遥(情感男) 4=度丫丫(情感女/可爱)
# 对孩子场景默认度丫丫(4)；若开通精品/臻品音库可换童声 110(度小童)。可用 BAIDU_TTS_PER 覆盖。
DEFAULT_PER = 4


class BaiduTTS(TTSProvider):
    def __init__(self):
        self.app_id = os.getenv("BAIDU_APPID", "")
        self.api_key = os.getenv("BAIDU_API_KEY", "")
        self.secret_key = os.getenv("BAIDU_SECRET_KEY", "")
        self.endpoint = "https://tsn.baidu.com/text2audio"
        self.per = int(os.getenv("BAIDU_TTS_PER", str(DEFAULT_PER)))
        self.spd = int(os.getenv("BAIDU_TTS_SPD", "5"))   # 语速 0-15
        self.pit = int(os.getenv("BAIDU_TTS_PIT", "5"))   # 音调 0-15
        self.vol = int(os.getenv("BAIDU_TTS_VOL", "5"))   # 音量 0-9(基础)/0-15(精品)
        self.aue = int(os.getenv("BAIDU_TTS_AUE", "3"))   # 3=mp3(默认) 4=pcm 6=wav

    @staticmethod
    def _clip_to_limit(text: str, max_gbk_bytes: int = 1024) -> str:
        """按 GBK 字节截断到 ≤1024（百度短文本上限），且不切断中文字。

        注：中文在 GBK 占 2 字节、UTF-8 占 3 字节，故 UTF-8 ≤1024 字节必然 ≤1024 GBK 字节，
        这里直接用 UTF-8 长度做保守截断同样安全；但为精确仍按 GBK 估算（GBK 不兼容字符回退 UTF-8）。
        """
        try:
            raw = text.encode("gbk")
        except UnicodeEncodeError:
            raw = text.encode("utf-8")
        if len(raw) <= max_gbk_bytes:
            return text
        logger.warning("TTS文本超长(%d字节GBK)，截断至%d且不切断中文", len(raw), max_gbk_bytes)
        # 逐字符累加，到上限前停止，避免切断一个汉字
        out, total = [], 0
        for ch in text:
            try:
                b = len(ch.encode("gbk"))
            except UnicodeEncodeError:
                b = len(ch.encode("utf-8"))
            if total + b > max_gbk_bytes:
                break
            out.append(ch)
            total += b
        return "".join(out)

    async def synthesize(self, text: str, **opts) -> bytes:
        text = self._clip_to_limit(text)
        token = await get_baidu_token(self.api_key, self.secret_key)
        # POST 表单字段（官方推荐）。表单编码自动处理 tex 的特殊字符，无需手动 urlencode。
        form = {
            "tex": text,
            "tok": token,
            "cuid": (self.app_id or "homework-pet")[:60],
            "ctp": 1,
            "lan": "zh",
            "spd": opts.get("spd", self.spd),
            "pit": opts.get("pit", self.pit),
            "vol": opts.get("vol", self.vol),
            "per": opts.get("per", self.per),
            "aue": self.aue,
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(self.endpoint, data=form)
        ct = r.headers.get("Content-Type", "")
        body = r.content
        # 成功：Content-Type 以 audio 开头（audio/mp3, audio/wav, audio/basic...）
        # 二进制前缀兜底：mp3=ID3/0xFFFB, wav=RIFF
        if ct.startswith("audio") or body[:3] == b"ID3" or body[:2] == b"\xff\xfb" or body[:4] == b"RIFF":
            logger.info("百度TTS合成成功 %d字节 (ct=%s)", len(body), ct)
            return body
        # 失败：返回 JSON 错误体（Content-Type: application/json），含 err_no/err_msg
        try:
            err = r.json()
            err_no = err.get("err_no")
            err_msg = err.get("err_msg")
        except Exception:
            err_no, err_msg = None, None
        raise RuntimeError(f"百度TTS错误 err_no={err_no} msg={err_msg} status={r.status_code} ct={ct}")
