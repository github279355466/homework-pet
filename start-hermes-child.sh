# ─── 脚本: start-hermes-child.sh ───
# 一次性完成: 停 Hermes → 起 homework-child gateway → 验证 8642
# 用法: bash D:/AIProject/workbuddy/homework-pet/start-hermes-child.sh

PROFILE_DIR="C:/Users/Administrator/AppData/Local/hermes/profiles/homework-child"
LOG_FILE="D:/AIProject/workbuddy/homework-pet/gateway.log"

# === Step 1: 停掉所有 Hermes 进程 ===
echo "⏹ Step 1: 停止所有 Hermes 进程..."
taskkill /F /IM pythonw.exe 2>/dev/null
taskkill /F /IM python.exe   2>/dev/null
taskkill /F /IM Hermes.exe   2>/dev/null
sleep 3
REMAINING=$(tasklist 2>/dev/null | grep -iE "hermes|python" | grep -v "grep" | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️  仍有 $REMAINING 个进程，再 kill 一次..."
    taskkill /F /IM pythonw.exe 2>/dev/null
    taskkill /F /IM python.exe   2>/dev/null
    taskkill /F /IM Hermes.exe   2>/dev/null
    sleep 2
fi
echo "✅ Hermes 进程已清理"

# === Step 2: 起 homework-child gateway ===
echo "▶️ Step 2: 启动 homework-child gateway..."
cd "$PROFILE_DIR"
> "$LOG_FILE"  # 清空旧日志
hermes gateway run --profile homework-child > "$LOG_FILE" 2>&1 &
GATEWAY_PID=$!
echo "gateway PID: $GATEWAY_PID"

# === Step 3: 等服务上线 ===
echo "⏳ Step 3: 等待 8642 端口就绪..."
for i in $(seq 1 30); do
    sleep 1
    if netstat -ano 2>/dev/null | grep -q ":8642.*LISTENING"; then
        echo "✅ 8642 端口已就绪 (等待 ${i}s)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ 30s 超时，8642 未上线，查看日志..."
        tail -20 "$LOG_FILE"
        tasklist | grep -i hermes
        exit 1
    fi
done

# === Step 4: 验证 API ===
echo "🧪 Step 4: 验证 API..."
sleep 2
RESP=$(curl -s -m 10 \
  -H "Authorization: Bearer homework-child-secret-20260719" \
  http://127.0.0.1:8642/v1/models 2>/dev/null)

if echo "$RESP" | grep -q "data"; then
    echo "✅ /v1/models 正常"
    echo "$RESP" | head -c 500
    echo ""
else
    echo "⚠️  /v1/models 返回异常，尝试 /v1/chat/completions 探测..."
    RESP2=$(curl -s -m 15 \
      -X POST \
      -H "Authorization: Bearer homework-child-secret-20260719" \
      -H "Content-Type: application/json" \
      -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"你好"}],"max_tokens":20}' \
      http://127.0.0.1:8642/v1/chat/completions 2>/dev/null)
    echo "chat/completions 返回: $(echo "$RESP2" | head -c 300)"
fi

echo ""
echo "🎉 完成！homework-child gateway 已跑在 http://127.0.0.1:8642"
echo "   接下来可以让 Codex 改 proxy 代码 + 前端"
