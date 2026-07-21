
## Phase: 小龙陪聊系统（Companion Chat） — 2026-07-18 ~ 2026-07-21

### 目标
在现有宠物养成系统上，新增 AI 长期陪伴聊天能力。Hermes Agent 作为大脑，前端作为"带麦的喇叭"交互通道。

### 架构
- 浏览器 → FastAPI (Railway) → Hermes API Server (Linux 47.242.10.160:8642) → DeepSeek
- 全部配置通过环境变量控制，不写死 model
- 前端微信输入法转文字（STT），浏览器 speechSynthesis 朗读（TTS）

### 核心代码
- pp/chat_proxy.py — Hermes Bridge (HTTP async, env-controlled)
- pp/main.py +2608-2669 — /api/chat/message + /api/chat/status 路由
- pp/main.py pet_interact — Hermes 动态生成互动反馈
- 	emplates/index.html — 聊天面板 CSS/JS, 事件委托（CSP 兼容）

### 环境变量
| 变量 | 值 |
|------|-----|
| CHAT_PROXY_MODE | http |
| HERMES_API_URL | http://47.242.10.160:8642/v1/chat/completions |
| HERMES_API_KEY | homework-child-secret-20260719 |
| HERMES_TIMEOUT | 60 |

### 测试结果
| 测试项 | 结果 |
|--------|------|
| 聊天 (不传 model, 走 profile 默认) | ✅ 8.4s 返回 |
| 语音朗读 (speechSynthesis) | ✅ 事件委托 + 中文语音 |
| 宠物互动 (pat/tickle/play) | ✅ 10.6s Hermes 动态反馈 |
| 算术题自动连续 | ✅ 1.5s/2s 自动下一题 |
| Railway CSP 兼容 | ✅ addEventListener 替代 inline onclick |

### Commits
- 24bea85: §2+§4 Hermes 陪聊代理模块
- 34fc23c: §4+§5 核心模块 - 前端
- dcc331e: 切 HTTP 模式 + 全环境变量
- ffb9186: async call_hermes, streaming
- b580c20: pet_interact bond_delta 修复
- fa7c7fd: 全链路测试通过
- f3e8026: chat_status hermes_found 修复
- 48fb537: 4 issues 修复
- c45bf04: CSP 事件委托 - a7c1360: 按钮 pointer-events

### 下一步 (P2+)
- 微信小程序语音通道 (wx.getRecorderManager + 云端 ASR)
- 家长看板（Hermes 周报 → 可视化）
- 多用户支持（登录系统 + Hermes 多 profile）

