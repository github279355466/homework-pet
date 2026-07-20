# Hermes homework-child — Linux 云端部署配置文档

> 适用：2C2G Linux 服务器（Debian/Ubuntu）
> 目标：homework-child profile 跑 API Server :8642，供 homework-pet proxy 调用

---

## 2.1 服务器初始化

```bash
# 安装 Python 3.11+ 和 Node.js 18+
sudo apt update && sudo apt install -y python3.11 python3.11-venv nodejs npm git

# 安装 Hermes Agent
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 验证
hermes --version
```

## 2.2 创建 homework-child Profile

```bash
hermes profile create homework-child
hermes profile use homework-child
```

## 2.3 config.yaml（完整生产版）

写入 `~/.hermes/profiles/homework-child/config.yaml`：

```yaml
model:
  default: deepseek-v4-flash
  provider: deepseek-direct
  context_length: 16384
providers:
  deepseek-direct:
    base_url: https://api.deepseek.com/v1
    api_key: sk-xxxxxxxxxxxxxxxx  # ← 替换为你的 DeepSeek Key
    api_mode: chat_completions
    models:
      deepseek-chat:
        name: deepseek-chat
      deepseek-v4-flash:
        name: deepseek-v4-flash
toolsets:
- hermes-cli
- memory
- session_search
- web
agent:
  max_turns: 50
  environment_probe: false
terminal:
  backend: local
  timeout: 60
api_server:
  enabled: true
  port: 8642
  host: 127.0.0.1
  key: homework-child-secret-20260719   # ← 跟 proxy 端一致
memory:
  user_profile_enabled: true
streaming:
  enabled: true
compression:
  enabled: true
  threshold: 0.60
  target_ratio: 0.25
logging:
  level: INFO
code_execution:
  mode: off
```

## 2.4 .env（密钥文件）

写入 `~/.hermes/profiles/homework-child/.env`：

```ini
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
API_SERVER_ENABLED=true
API_SERVER_KEY=homework-child-secret-20260719
API_SERVER_PORT=8642
API_SERVER_HOST=127.0.0.1
```

## 2.5 Cron 配置（每晚学习总结）

```bash
hermes --profile homework-child cron create "0 22 * * *" \
  --prompt "回顾今天与小朋友的对话，生成学习日记：1) 今日所学知识点；2) 卡住的地方；3) 鼓励亮点；4) 明日建议。更新到 user_profile。语气温暖。" \
  --name "daily-learning-summary"
```

## 2.6 systemd

> ⚠️ **重要**：不要用 `hermes serve`（那是桌面 WebUI 后端，port 9119）。
> API Server 是 gateway 的 platform adapter，必须用 `hermes gateway run`。

```bash
sudo tee /etc/systemd/system/hermes-api.service > /dev/null << 'EOF'
[Unit]
Description=Hermes API Server (homework-child)
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/homework-child
ExecStart=/usr/local/bin/hermes --profile homework-child gateway run
Restart=always
RestartSec=5
Environment=PATH=/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hermes-api
sudo systemctl start hermes-api
sudo systemctl status hermes-api
```

## 2.7 nginx 反代（可选，对外统一域名）

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location /api/chat/ {
        proxy_pass http://127.0.0.1:8642/v1/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization "Bearer homework-child-secret-20260719";
        proxy_buffering off;
        proxy_cache off;
    }

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 2.8 验证清单

```bash
# 1. API 可用
curl -s -H "Authorization: Bearer homework-child-secret-20260719" \
  http://127.0.0.1:8642/v1/models | jq .

# 2. 对话可用
curl -s -X POST \
  -H "Authorization: Bearer homework-child-secret-20260719" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"你好"}],"max_tokens":20}' \
  http://127.0.0.1:8642/v1/chat/completions

# 3. cron 已注册
hermes --profile homework-child cron list

# 4. 服务自启
sudo systemctl is-active hermes-api
```

## 2.9 迁移注意

- 本机 Windows 的 homework-child profile 仅用于开发测试
- 生产环境 Linux 上**重新创建 profile**，不要直接复制 Windows 目录（路径格式不兼容）
- DeepSeek API Key 在 api.deepseek.com → 账户管理 → API Keys 获取
- 2C2G 服务器上 Hermes + homework-pet 同时跑，context_length 不超过 16K

## 2.10 常见误区

| 错误做法 | 正确做法 | 原因 |
|---------|---------|------|
| `hermes serve --port 9119` | `hermes gateway run` | `serve` 是桌面 WebUI 后端，不是 API Server |
| 直接调 9119 端口 | 调 8642 端口 | API Server 默认监听 8642 |
| 手动 `nohup ... &` | 用 systemd | systemd 崩溃自启、日志完整 |
| 复制 Windows profile 目录 | `hermes profile create` 重建 | 路径格式不兼容 |
