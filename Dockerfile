# syntax=docker/dockerfile:1
# Railway Docker builder 配置（替代已弃用的 Nixpacks）
# 语音功能需要 ffmpeg 把浏览器录音转码为百度 ASR 要求的 16k 单声道 wav。

FROM python:3.12-slim-bookworm

# 安装 ffmpeg（百度 ASR 需要）
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目源码（仓库根 → /app，源码在 /app/app/main.py）
COPY . .

# Railway 会注入 PORT；main.py 读取 PORT 环境变量并监听 0.0.0.0
# 注意：Railway Docker 运行时以 `python app/main.py` 启动（CWD=/app），
# 因此这里 WORKDIR 保持 /app、CMD 用 app/main.py，解析为 /app/app/main.py。
CMD ["python", "app/main.py"]
