# 作业小龙 — Agent 项目指南

> 当前版本：v3.3.0（多宠物系统；2026-07-09 全 Phase 完成并 push 至 main；Railway 已部署上线）

## 项目状态

- **生产环境**：Railway（连 GitHub `github279355466/homework-pet` 自动构建）
- **生产地址**：`https://homepet.up.railway.app/`（2026-07-09 重建服务，旧域名 `web-production-a9e82.up.railway.app` 已废弃）
- **数据库**：SQLite。`app/homework_pet.db` 是**仓库内种子库**（已含紫宝等生产数据，随 git 提交）；生产实时库落在 **Railway Volume**（经 `HOMEWORK_PET_DB_PATH` 或 `RAILWAY_VOLUME_MOUNT_PATH` 指定），首次挂载由 `_ensure_persistent_db()` 从种子库迁移过去，重部署不丢数据
- **本地开发**：`cd app && python run_local.py`（端口 5001）

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
- 前端单页面 `app/templates/index.html`（Jinja2 模板，~3760 行）
- 后端单文件 `app/main.py`（FastAPI，~2609 行）+ `app/multi_pet.py`（多宠物迁移+兼容层）
- 静态图片已压缩：皮肤 PNG 256×256，物种立绘 PNG 256×256（35 张，由 1024² 压缩，37MB→2.4MB）
- `app/static/dragon-skins/pic/` 目录是参考图素材，不在前端引用

## 项目结构

```
app/
├── main.py               # 后端主程序（~2609 行）
├── multi_pet.py          # 多宠物迁移 + 兼容层（v3.3 新增）
├── database.py           # 数据库初始化（16 张表）
├── run_local.py          # 本地开发启动
├── templates/index.html  # 前端单页
├── static/               # 静态资源（含 species/ 35 张立绘）
└── homework_pet.db       # 生产数据库
Procfile                  # Railway 启动命令
railway.json              # Railway 构建配置
requirements.txt          # Python 依赖
```

## 已知历史决策

- **秒悟平台改造已评估并放弃**：秒悟只支持 React/Vue SPA + Deno Edge Functions，不支持 Python 后端。沙箱代码已推送但未走 CDN 部署。`.env` 里残留的 `MEOO_PROJECT_URL_ID` 是历史遗留，可清理。
- **静态图片压缩**：原 2048×2048 PNG 已压缩到 256×256（5MB → 1.5MB），避免 Railway 上传超限
- **金币上限已放开**：v3.2.1 移除了手动发布任务的 100 金币上限（HTML `max="100"` + JS 验证双重移除）
- **数学题定时器修复**：v3.2.1 修复"再来一题"自动关闭 bug，根因是 `closeMathQuiz()` 内 `location.reload()` 与 setTimeout 冲突
