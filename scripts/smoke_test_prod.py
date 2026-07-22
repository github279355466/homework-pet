#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产环境语音后端冒烟测试 (B 阶段: 部署后基础设施排雷)

不依赖前端: 直接对生产 URL 发 HTTP 请求, 验证:
  1) /api/chat/tts  -> 百度 TTS 真实返回音频 (非 Mock)
  2) /api/chat/voice -> 把 TTS 产出的音频回灌 ASR, 验证整链路通

用法:
  python scripts/smoke_test_prod.py
  RAILWAY_URL=https://xxx.railway.app python scripts/smoke_test_prod.py
"""
import json
import os
import sys
import urllib.request
import urllib.error

PROD_URL = os.getenv("RAILWAY_URL", "https://homepet.up.railway.app").rstrip("/")

# Mock 标记 (来自 app/speech/base.py 的 MockTTS / MockASR)
MOCK_TTS_MARKER = b"mock-audio"
MOCK_ASR_MARKER = "这是一段模拟识别文本"


def _post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, resp.headers, resp.read()


def _post_multipart_file(url, field_name, filename, raw_bytes, ctype):
    boundary = "----smokeboundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode("utf-8") + raw_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, resp.headers, resp.read()


def check(name, ok, detail=""):
    mark = "✅" if ok else "❌"
    print(f"{mark} {name}" + (f"  -> {detail}" if detail else ""))
    return ok


def main():
    print(f"== 生产冒烟测试 @ {PROD_URL} ==\n")
    all_ok = True

    # ---- 1. TTS ----
    print("[1/2] TTS: POST /api/chat/tts")
    try:
        status, headers, body = _post_json(
            f"{PROD_URL}/api/chat/tts",
            {"text": "你好小龙，今天我们一起写作业吧", "per": 4},
        )
        ct = headers.get("Content-Type", "")
        size = len(body)
        is_mock = body == MOCK_TTS_MARKER
        ok = check(
            "TTS 返回 200 + 音频",
            status == 200 and ct.startswith("audio") and size > 1000 and not is_mock,
            f"status={status} content-type={ct} bytes={size}" + (" [MOCK!密钥未配]" if is_mock else ""),
        )
        all_ok = all_ok and ok
        if ok and not is_mock:
            with open("/tmp/smoke_tts.mp3", "wb") as f:
                f.write(body)
            print("     已保存 /tmp/smoke_tts.mp3 供下一步回灌 ASR")
    except urllib.error.HTTPError as e:
        all_ok = False
        check("TTS HTTP 错误", False, f"{e.code} {e.read().decode('utf-8', 'replace')[:200]}")
    except Exception as e:
        all_ok = False
        check("TTS 异常", False, repr(e))

    # ---- 2. Voice (round-trip) ----
    print("\n[2/2] Voice: POST /api/chat/voice (回灌 TTS 音频)")
    mp3_path = "/tmp/smoke_tts.mp3"
    if not os.path.exists(mp3_path):
        # 退化: 用极小静音 wav 验证管线可达 (不验证识别率)
        print("     (无 TTS 产出, 跳过回灌)")
    else:
        try:
            with open(mp3_path, "rb") as f:
                mp3 = f.read()
            status, headers, body = _post_multipart_file(
                f"{PROD_URL}/api/chat/voice", "file", "smoke.mp3", mp3, "audio/mpeg"
            )
            try:
                resp = json.loads(body.decode("utf-8"))
            except Exception:
                resp = {"raw": body.decode("utf-8", "replace")[:200]}
            text = resp.get("text", "")
            is_mock = text.strip() == MOCK_ASR_MARKER
            ok = check(
                "Voice 返回 200 + JSON",
                status == 200 and "text" in resp and not is_mock,
                f"status={status} text={text!r}" + (" [MOCK!密钥未配]" if is_mock else ""),
            )
            all_ok = all_ok and ok
        except urllib.error.HTTPError as e:
            all_ok = False
            check("Voice HTTP 错误", False, f"{e.code} {e.read().decode('utf-8', 'replace')[:200]}")
        except Exception as e:
            all_ok = False
            check("Voice 异常", False, repr(e))

    print("\n== 结果 ==")
    if all_ok:
        print("✅ 生产语音后端基础设施 OK (ffmpeg / nixpacks / 百度密钥 均生效)")
        return 0
    print("❌ 存在失败项, 见上。需排查生产日志。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
