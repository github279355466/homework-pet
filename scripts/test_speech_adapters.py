"""本地验证 app/speech 适配器管线。

运行：
  python scripts/test_speech_adapters.py

行为：
  - 无 BAIDU_* 环境变量 -> factory 自动回退 Mock，验证管线结构正确。
  - 有 BAIDU_API_KEY/SECRET_KEY/APPID -> 走真实百度，额外落盘 scripts/_tts_sample.mp3 供人工听测。
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from speech.factory import get_asr_provider, get_tts_provider


async def main():
    print("=== 适配器选择 ===")
    asr = get_asr_provider()
    tts = get_tts_provider()
    print(f"ASR provider: {type(asr).__name__}")
    print(f"TTS provider: {type(tts).__name__}")

    print("\n=== ASR 调用 ===")
    res = await asr.recognize(b"fake-audio-bytes", fmt="wav", rate=16000)
    print("ASR result:", res)
    assert isinstance(res, dict) and "text" in res, "ASR 返回格式错误"

    print("\n=== TTS 调用 ===")
    text = "你好，我是小龙，今天我们一起写作业吧！"
    audio = await tts.synthesize(text)
    print(f"TTS returned {len(audio)} bytes; head={audio[:8]!r}")
    assert isinstance(audio, bytes) and len(audio) > 0, "TTS 返回音频为空"

    if os.getenv("BAIDU_API_KEY"):
        out = os.path.join(os.path.dirname(__file__), "_tts_sample.mp3")
        with open(out, "wb") as f:
            f.write(audio)
        print(f"\n真实百度 TTS 音频已保存: {out}")

    print("\n✅ 适配器管线验证通过")


if __name__ == "__main__":
    asyncio.run(main())
