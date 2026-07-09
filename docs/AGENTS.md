# AGENTS.md — 作业小龙 (homework-pet) 项目上下文

> 本文件供 **AI agent（多 agent 协作）** 快速建立项目心智模型而写。人类可在此目录下查看 `docs/项目地图.html`（可视化版）。
> 修改本仓库任何代码前，请先读完本文件，特别是「已知技术坑」一节。

## 0. 一句话定位
面向 1–6 年级小学生的 **作业激励 Web App**：完成作业赚「经验（进化）」+「龙币（消费）」，配宠物养成、专注打卡、家长监督。单进程 FastAPI 服务，无外部服务依赖。

## 1. 技术栈
- **后端**：Python 3.12+ / FastAPI 0.109 / uvicorn 0.27
- **模板**：Jinja2 3.1（**注意坑**：用 `jinja2.Environment` 直接渲染返回 `HTMLResponse`，不用 `Jinja2Templates`，规避 3.1.x 缓存 bug）
- **数据库**：SQLite（原生 `sqlite3` 模块，**无 ORM**）—— `WAL` 模式 + `busy_timeout=5000` + `connect(timeout=10)`
- **前端**：单页 `index.html`（3293 行），Bootstrap5 + 原生 JS，靠 `?role=kid|parent` 切换双视图
- **部署**：Windows 云服务器，OpenResty 反代 → `127.0.0.1:5000`

## 2. 文件清单（按角色标记）

### 运行时 (RUNTIME — 改这些才影响线上)
| 路径 | 行数 | 角色 |
|------|------|------|
| `app/main.py` | 2141 | FastAPI 应用主体，**全部 45 个路由 + 业务逻辑** |
| `app/database.py` | 365 | 建库/建表、WAL 连接、默认数据初始化；`import` 时自动 `init_db()` |
| `app/run_local.py` | — | 本地启动器（等同 `uvicorn main:app --port 5000`） |
| `app/__init__.py` | — | 包标记 |
| `app/templates/index.html` | 3293 | 前端单页（孩子/家长双视图） |
| `app/static/` | — | 图片/JS/CSS/皮肤资源（`dragon-skins/`、`dragon-references/`） |

### 开发 & 测试历史 (DEV-ONLY — 不参与运行时，见 `scripts/README.md`)
| 路径 | 角色 |
|------|------|
| `scripts/main_new.py` | 废弃重构稿，已合入 main.py |
| `scripts/implement_features.py` | v3.1 功能实现草稿 |
| `scripts/fix_main.py` | 历史临时修复脚本 |
| `scripts/test_comprehensive.py` | 端到端集成测试（requests 打 5000） |
| `scripts/test_data_chain.py` | 数据链测试 |
| `scripts/test_safe_regression.py` | 回归测试（TestClient） |
> ⚠️ 重跑需 `PYTHONPATH=app`，详见 `scripts/README.md`。

### 文档 & 部署 (DOCS/DEPLOY)
- `README.md` — 项目总览
- `prd.md` — 产品需求文档（39+ API 端点）
- `DEPLOY.md` — Windows + OpenResty 部署指南
- `docs/周学习计划指导.md` — 给家长的周计划配置文档
- `docs/项目地图.html` — 可视化项目地图（人类版）
- `Procfile` / `railway.json` — Railway 部署
- `start_server.bat` — Windows 启动脚本

## 3. API 端点全景（45 个，按域分组）

### 页面 & 宠物
- `GET  /` — 渲染主页面（Jinja2）
- `GET  /api/pet` — 宠物完整状态
- `POST /api/pet/feed` — 喂食（消耗龙币、改 hunger）
- `POST /api/pet/interact` — 互动（摸头/挠痒/逗玩，改 mood/bond）
- `POST /api/pet/rename` — 改名
- `GET  /api/pet/mood` — 状态反馈轮询（每 60s，前端用）
- `GET  /api/pet/skins` — 皮肤列表
- `POST /api/pet/skin/select` — 选皮肤
- `POST /api/pet/skin/unlock` — 解锁皮肤
- `POST /api/pet/math-quiz` — 生成数学挑战题
- `POST /api/pet/math-quiz/answer` — 作答（每天首题 +20 龙币）

### 作业 & 任务
- `POST /api/task/complete` — 完成日常作业（经验+龙币，数学双倍）
- `GET  /api/tasks` — 今日任务汇总（日常 5 科 + 额外任务）
- `GET  /api/custom-tasks/templates` — 家长额外任务模板
- `POST /api/custom-tasks/create` — 家长布置任务
- `POST /api/custom-tasks/{task_id}/complete` — 孩子完成任务
- `DELETE /api/custom-tasks/{task_id}` — 删除额外任务

### 成就 & 鼓励
- `GET  /api/achievements` — 成就徽章墙
- `POST /api/encourage` — 家长发鼓励
- `GET  /api/encourage` — 取未过期鼓励

### 行为评价
- `GET  /api/behavior/rules` — 规则列表
- `POST /api/behavior/evaluate` — 评价（按规则 ±龙币）
- `POST /api/behavior/evaluate/custom` — 自定义评价
- `POST /api/behavior/rules/create` — 新增规则
- `DELETE /api/behavior/rules/{rule_id}` — 删规则
- `GET  /api/behavior/today` — 今日评价记录

### 龙币经济
- `GET  /api/coins/transactions` — 交易记录
- `GET  /api/coins/stats` — 龙币统计
- `POST /api/coins/exchange-pocket-money` — 申请零花钱
- `POST /api/pocket-money/{record_id}/approve` — 家长审批通过
- `POST /api/pocket-money/{record_id}/reject` — 家长驳回
- `GET  /api/wallet/detail` — 钱包明细（交易+本周/本月/累计）

### 专注 & 商店
- `POST /api/focus/complete` — 专注打卡完成（10/20/30 分钟，每日≤3）
- `GET  /api/focus/today` — 今日专注次数
- `GET  /api/shop/accessories` — 装饰商店
- `POST /api/shop/buy/{item_id}` — 买装饰
- `POST /api/shop/equip/{item_id}` — 装备装饰
- `POST /api/shop/buy-feed` — 买零食即喂食

### 家长设置
- `GET  /api/parent/settings` — 读设置
- `POST /api/parent/settings` — 改设置
- `POST /api/parent/verify` — 验证家长密码
- `POST /api/parent/change-password` — 改密码
- `POST /api/parent/reset-data` — 重置数据

### 报表 & 活动
- `GET  /api/weekly-report` — 学习周报（7 天柱状图数据）
- `GET  /api/random-surprise` — 每日随机惊喜（20% 概率）
- `GET  /api/event/status` — 限时活动状态

### 系统
- `POST /api/scheduler/run` — 手动触发衰减/活动调度（正常由内部 scheduler 每日跑）

## 4. 数据库 Schema（14 张表，SQLite）

> 连接：经 `get_db_connection()`（WAL）。DB 路径 `app/homework_pet.db`（可用 `HOMEWORK_PET_DB_PATH` 覆盖做测试隔离）。
> `pet` 表在 `init_db()` 里用 `ALTER TABLE` 向前兼容加字段（`last_decay_date`、`math_challenge_today` 等）。

| 表 | 关键字段 | 用途 |
|----|----------|------|
| `pet` | id, name, level, exp, hunger, mood, streak, status, bond, coins, last_streak_date, math_streak, last_math_date, last_decay_date, math_challenge_today | 宠物唯一主记录 |
| `tasks` | id, task_type(daily), subject, completed, exp_reward, created_date | 日常 5 科作业（语文/数学/英语/课外阅读/体育锻炼） |
| `achievements` | id, name, description, icon, unlocked, unlocked_at | 17 个成就（含 v3.1 新增 4 个） |
| `encourage` | id, message, expires_at | 家长鼓励消息 |
| `treasure_log` | id, reward_type, reward_name, reward_icon | 宝箱记录（数学触发） |
| `random_surprises` | id, surprise_type, reward_value, description | v3.1 随机惊喜 |
| `custom_tasks` | id, subject, category, exp_reward, coins_reward, deadline, status(pending/done) | 家长额外任务 |
| `behavior_rules` | id, name, coins, category(study/behavior/health/other), is_custom | 行为评价规则（30 条默认） |
| `behavior_records` | id, rule_id, rule_name, coins, category | 评价历史 |
| `coin_transactions` | id, type, source, amount, balance_after | 龙币流水（含余额快照） |
| `pocket_money_records` | id, coins_spent, amount_yuan, status(pending/approved/rejected) | 零花钱兑换申请 |
| `focus_sessions` | id, duration_minutes, coins_earned | 专注打卡 |
| `pet_accessories` | id, name, type(hat/background), price, owned, equipped | 装饰商品 |
| `parent_settings` | key(PK), value | 汇率/周上限/家长密码/开关 |

**关键业务常量（在 `app/main.py` 顶部定义，改前务必确认）**
- `EVOLUTION_THRESHOLDS = [0, 800, 2000, 4000, 8000]`（5 阶段：蛋→幼龙→少年龙→青年龙→神龙，前快后慢）
- 数学作业经验 **+100**（普通 +50）；数学宝箱触发率 60%
- 日常 5 科常量在 `DEFAULT_TASKS` / `get_today_tasks_summary()` / `SUBJECT_REWARDS` 三处必须一致
- `calculate_level(exp) = calculate_evolution_stage(exp) + 1`（向后兼容函数，**保留**）

## 5. 核心数据流（一次「完成作业」全链路）
```
孩子点完成数学作业
  → POST /api/task/complete {subject:'数学'}
  → 经验 +100（普通+50）、数学 streak+1
  → exp 跨阈值? → level 升阶 → 触发进化动画 + 成就(破壳/成长/神龙/数学勇士)
  → 龙币 +N（写入 coin_transactions 带 balance_after）
  → 60% 概率宝箱 (treasure_log) → 称号/道具/经验卡
  → 返回更新后的 pet 状态 → 前端刷新 + 全屏粒子庆祝
```
衰减（v3.1）：内部 scheduler 每日一次 `hunger-8 / mood-5 / bond-6`，`last_decay_date` 控制「每天只减一次」，sleeping 状态豁免。一周不玩 bond 从 50 降到约 8。

## 6. 双角色模型
- **孩子视图**：`?role=kid` — 做作业、养宠物、互动、专注、商店、看成就/周报
- **家长视图**：`?role=parent` — 布置额外任务、行为评价、零花钱审批、改设置（需密码，默认 `1234`）、重置数据
- 共享同一宠物与数据库，无多账号（多孩子账号在待办 V3.2+）

## 7. 部署架构
```
公网用户 → OpenResty(:80, server_name _) → proxy_pass 127.0.0.1:5000
                                         → /static alias app/static (缓存7天)
后端: uvicorn main:app --host 127.0.0.1 --port 5000 (NSSM 托管为 Windows 服务)
DB:   app/homework_pet.db (WAL)
```
- 无域名场景：`server_name _;` 通配公网 IP，直接 `http://公网IP/?role=kid` 访问
- 详细步骤见 `DEPLOY.md`

## 8. 已知技术坑（必读，避免重复踩）
1. **Jinja2 3.1.x 缓存 bug**：必须用 `jinja2.Environment` 渲染返回 `HTMLResponse`，不能用 `Jinja2Templates`。
2. **SQLite 不能调用 Python 函数**：SQL 里写 `level = calculate_level(?)` 会报 `no such function`。必须在 Python 端算好 `new_level` 再传参。
3. **`database is locked`**：靠 `WAL` + `busy_timeout=5000` + `connect(timeout=10)` 解决（已加）。
4. **`sqlite3.Row` 无 `.get()`**：用 `dict(pet).get('bond', 50)`，直接 `pet.get(...)` 报 `AttributeError`。
5. **科目三处必须对齐**：`DEFAULT_TASKS` / `get_today_tasks_summary()` / 前端弹窗按钮，现为 语文/数学/英语/课外阅读/体育锻炼。
6. **streak 只每天+1**：用 `last_streak_date` 控制，不能每次打卡都+1。
7. **前端 fetch 必须处理 catch**：至少 `console.error` + 用户提示，别静默吞错。
8. **依赖已精简**：`requirements.txt` 仅 fastapi/uvicorn/jinja2/python-multipart/pytz；**已移除未使用的 sqlalchemy/aiosqlite**（代码用原生 sqlite3）。
9. **历史脚本已移出 `app/`**：`scripts/` 下文件不参与运行，改线上功能别碰它们。

## 9. 本地运行 & 测试
```bash
cd app
python -m uvicorn main:app --host 127.0.0.1 --port 5000
# 或 python run_local.py
# 浏览器: http://127.0.0.1:5000/?role=kid
```
测试（需先起服务，或 `test_safe_regression.py` 用 TestClient 自起）：
```bash
PYTHONPATH=app python scripts/test_safe_regression.py
```

---
<!-- MACHINE-READABLE: 以下 JSON 供程序化解析，agent 可用 JSON parser 直接读取 -->
```json
{
  "project": "homework-pet",
  "version": "v3.1",
  "summary": "小学生作业激励 Web App：经验进化 + 龙币消费 + 宠物养成",
  "stack": {
    "backend": "FastAPI 0.109 + uvicorn 0.27",
    "db": "SQLite (native sqlite3, WAL mode)",
    "frontend": "single-page index.html (Bootstrap5 + vanilla JS), ?role=kid|parent",
    "templating": "jinja2.Environment directly (no Jinja2Templates)",
    "deploy": "Windows + OpenResty reverse proxy -> 127.0.0.1:5000"
  },
  "runtime_files": [
    "app/main.py", "app/database.py", "app/run_local.py", "app/__init__.py",
    "app/templates/index.html", "app/static/"
  ],
  "dev_only_files": [
    "scripts/main_new.py", "scripts/implement_features.py", "scripts/fix_main.py",
    "scripts/test_comprehensive.py", "scripts/test_data_chain.py", "scripts/test_safe_regression.py"
  ],
  "api_count": 45,
  "db_tables": [
    "pet","tasks","achievements","encourage","treasure_log","random_surprises",
    "custom_tasks","behavior_rules","behavior_records","coin_transactions",
    "pocket_money_records","focus_sessions","pet_accessories","parent_settings"
  ],
  "constants": {
    "EVOLUTION_THRESHOLDS": [0, 800, 2000, 4000, 8000],
    "math_exp": 100, "normal_exp": 50, "math_treasure_rate": 0.6,
    "default_subjects": ["语文","数学","英语","课外阅读","体育锻炼"],
    "parent_password_default": "1234"
  },
  "known_gotchas": [
    "use jinja2.Environment not Jinja2Templates (3.1.x cache bug)",
    "SQLite cannot call Python funcs in SQL; compute in Python first",
    "WAL + busy_timeout=5000 + connect(timeout=10) to avoid database is locked",
    "sqlite3.Row has no .get(); use dict(row).get()",
    "subjects must stay aligned in 3 places",
    "streak increments only once per day via last_streak_date",
    "sqlalchemy/aiosqlite removed from requirements.txt (unused)",
    "historical scripts moved to scripts/ (not runtime)"
  ],
  "run": "cd app && python -m uvicorn main:app --host 127.0.0.1 --port 5000",
  "docs": ["README.md","prd.md","DEPLOY.md","docs/周学习计划指导.md","docs/项目地图.html","docs/AGENTS.md"]
}
```
