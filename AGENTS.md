# 作业小龙 — Agent 项目指南

> 当前版本：v3.5.0（闯关模块 Challenge Mode；2026-07-30 教材AI出题系统）

## 项目状态

- **生产环境**：Railway（连 GitHub `github279355466/homework-pet` 自动构建）
- **生产地址**：`https://homepet.up.railway.app/`（2026-07-09 重建服务，旧域名 `web-production-a9e82.up.railway.app` 已废弃）
- **数据库**：SQLite。`app/homework_pet.db` 是**仓库内种子库**（已含紫宝等生产数据，随 git 提交）；生产实时库落在 **Railway Volume**（经 `HOMEWORK_PET_DB_PATH` 或 `RAILWAY_VOLUME_MOUNT_PATH` 指定），首次挂载由 `_ensure_persistent_db()` 从种子库迁移过去，重部署不丢数据
- **本地开发**：`cd app && python run_local.py`（端口 5001）
- **陪聊 API Server**：Linux 服务器 `47.242.10.160:8642`（Hermes homework-child profile，儿童作业陪伴聊天大脑）

## 重要约束

### 数据库
- 仓库内 `app/homework_pet.db` 是**种子库**（提交到 git），不是实时生产库；不要把它当生产数据直接改
- 生产运行库在 Railway Volume：设 `HOMEWORK_PET_DB_PATH=${RAILWAY_VOLUME_MOUNT_PATH}/homework_pet.db`（Railway 会在注入前展开 `${VAR}`）；`database.py` 信任该路径并自动从种子库 seed，重部署持久化
- 写操作测试用环境变量切换：`HOMEWORK_PET_DB_PATH=backups/test_homework_pet.db`
- 测试脚本 `app/test_safe_regression.py` 拒绝连接真实数据库路径

### 部署
- 推送 `main` 分支即触发 Railway 自动部署
- 启动命令：`python app/main.py`（见 `Procfile`）
- `main.py` 末尾 `port=int(os.environ.get("PORT", 5000))` — 必须保留动态端口读取
- `requirements.txt` 每个依赖独占一行（真实换行符，不能用字面 `\n`）

### 代码规范
- 前端单页面 `app/templates/index.html`（Jinja2 模板，~4500 行）
- 后端单文件 `app/main.py`（FastAPI，~3600 行）+ `app/multi_pet.py`（多宠物迁移+兼容层）
- 静态图片已压缩：皮肤 PNG 256×256，物种立绘 PNG 256×256（35 张，由 1024² 压缩，37MB→2.4MB）
- `app/static/dragon-skins/pic/` 目录是参考图素材，不在前端引用

## 项目结构

```
app/
├── main.py               # 后端主程序（~2780 行，含聊天会话历史管理）
├── multi_pet.py          # 多宠物迁移 + 兼容层（v3.3 新增）
├── chat_proxy.py         # Hermes API 桥接（聊天代理 + 安全过滤）
├── database.py           # 数据库初始化（22 张表，含闯关6张）
├── run_local.py          # 本地开发启动
├── templates/index.html  # 前端单页
├── static/               # 静态资源（含 species/ 35 张立绘）
└── homework_pet.db       # 仓库内种子库（随 git 提交）
Procfile                  # Railway 启动命令
railway.json              # Railway 构建配置
requirements.txt          # Python 依赖
```

## 已知历史决策

- **秒悟平台改造已评估并放弃**：秒悟只支持 React/Vue SPA + Deno Edge Functions，不支持 Python 后端。沙箱代码已推送但未走 CDN 部署。`.env` 里残留的 `MEOO_PROJECT_URL_ID` 是历史遗留，可清理。
- **静态图片压缩**：原 2048×2048 PNG 已压缩到 256×256（5MB → 1.5MB），避免 Railway 上传超限
- **金币上限已放开**：v3.2.1 移除了手动发布任务的 100 金币上限（HTML `max="100"` + JS 验证双重移除）
- **数学题定时器修复**：v3.2.1 修复"再来一题"自动关闭 bug，根因是 `closeMathQuiz()` 内 `location.reload()` 与 setTimeout 冲突
- **小龙陪聊系统（Companion Chat）**：2026-07-18 启动，Hermes Agent 作为大脑（带长期记忆的用户画像），前端作为交互通道；2026-07-22 完成语音聊天 T3–T7（ASR/TTS 全用百度）；2026-07-29 修复会话历史丢失 bug——后端新增 `_chat_session_histories` 内存缓存，每次调用 Hermes 发送完整对话上下文，详见 `docs/plans/companion-chat-plan.md`


## 闯关模块（v3.5 新增）

### 功能概述
- **学科**：语文、数学、英语
- **年级**：1-5 年级（家长端设置）
- **关卡**：每天每科 1 关，每关 10 题（50% 基础题库 + 50% AI 动态生成）
- **奖励**：龙币 + 经验 + 宝箱（普通/黄金/传奇）
- **星级**：1-5 星评价，≥60% 通关

### 教材处理流程
1. `scripts/convert_textbooks_fast.py` — PDF→Markdown（PyMuPDF，本地离线）
2. `scripts/convert_textbooks.py kg` — 从 Markdown 提取知识图谱
3. `scripts/convert_textbooks.py import` — 知识图谱入库
4. `scripts/generate_seed_questions.py` — 本地种子题库（模板生成，无需 API）
5. `scripts/generate_question_bank.py` — API 题库（需 Hermes，生产环境执行）

### 新增数据库表
- `knowledge_points` — 知识图谱（学科→年级→章节→知识点）
- `question_bank` — 基础题库（约 6000 题）
- `challenge_levels` — 关卡表
- `challenge_questions` — 题目缓存
- `challenge_daily_progress` — 每日进度
- `challenge_wrong_questions` — 错题记录

### 新增 API（6 个）
- `GET /api/challenge/status` — 闯关状态
- `GET /api/challenge/subjects` — 学科配置
- `POST /api/challenge/start` — 开始闯关
- `POST /api/challenge/answer` — 提交答案
- `POST /api/challenge/complete` — 通关结算
- `GET /api/challenge/history` — 闯关历史

### AI 出题机制
- **System Prompt**：含防幻觉规则，严格控制知识范围
- **质量校验**：格式检查 → 数学答案验证 → 难度检测
- **降级策略**：API 失败时使用预设题库
- **教材参考**：实时出题时传入对应章节 Markdown 片段

