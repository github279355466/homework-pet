# 🐉 作业小龙 v3.4.1（多宠物系统 + 语音陪伴聊天）

> 用电子宠物养成 + 代币经济激励孩子完成作业，养成良好学习习惯和行为规范。

作业小龙是一款面向 **6-8 岁小学生** 的学习激励电子宠物应用。孩子在 iPad 或手机浏览器中打开网页，完成作业、专注打卡、积极行为评价来喂养和陪伴宠物成长。家长通过密码进入家长端，布置额外任务、评价行为、审批零花钱兑换。

**一句话**：做作业养宠物赚龙币，专注打卡兑换零花钱。

---

## ✨ 功能概览

### 🥚 进化系统
5 阶段可视化形态变化（龙蛋 → 幼龙 → 少年龙 → 青年龙 → 神龙），经验驱动进化，全屏闪光动画。

### 🤗 互动系统
摸头、挠痒、逗玩、喂食和算术题挑战，亲密度属性，瑞星小狮子风格动画 + 语音气泡 + 粒子特效。

### ✅ 任务打卡
- **日常作业**：语文/数学/英语/课外阅读/体育锻炼，数学双倍经验
- **家长额外任务**：12 个预设模板 + 自定义，支持截止时间
- **行为评价**：30 条预设规则（学习/行为/健康/其他）+ 手动输入自定义评价，即时打分

### 🪙 龙币经济（双轨制）
- **经验值**：决定宠物进化阶段
- **龙币**：商店消费 + 零花钱兑换
- 专注打卡（10/20/30 分钟）获得龙币，连续 7 天额外奖励

### 🏪 商店 & 钱包
6 种零食购买即喂食，装饰商品，钱包弹窗查看交易记录与零花钱统计。

### 🏆 成就徽章墙
11 个成就（破壳而出、成长之龙、龙之力量、神龙降临、最佳拍档、专注达人、小富翁、喂养达人、互动高手、暖心天使、挑战勇士），3 列网格布局，新解锁金色闪光。

### 📅 限时活动（v3.1）
- 周末自动双倍龙币奖励
- 数学挑战赛：每天首道数学作业额外 +20 龙币

### 💤 宠物状态（v3.1 → v3.2 升级）
- **实时衰减**：按真实经过时间连续计算；饱腹高于 30 时衰减较快，低于 30 后自动放慢，避免直接归零
- **丰富情绪**：新增生气😤、委屈😢、骄傲😎 3 种中间情绪状态
- **状态反馈**：低饱腹撒娇、低亲密度躲起来（CSS 滤镜 + 动画联动）
- **随机惊喜**：每天首次打开 20% 概率获得礼物（龙币/经验/亲密度/称号）

### 🎮 趣味互动（v3.2 新增）
- **算术题挑战**：100 以内加减法，4 个选项，答对获得龙币并提升亲密度
- **宠物改名**：小朋友可以给自己宠物取喜欢的名字
- **宠物换肤**：5 款皮肤（经典/火焰/冰雪/黄金/森林），每款 5 个阶段真实 PNG 图片，龙币购买解锁
- **提前完成奖励**：放学1小时内完成作业额外龙币加成

### 📊 学习周报
过去 7 天柱状图（作业/龙币/专注可切换），Canvas 绘制无第三方依赖。

### 📱 双角色
- **孩子端**：查看宠物、完成任务、互动、商店、成就
- **家长端**：布置任务、行为评价、零花钱审批、系统设置（需密码）

---

## 🏗️ 技术架构

| 层 | 技术 |
|----|------|
| 后端 | Python 3.8+ / FastAPI / Uvicorn |
| 数据库 | SQLite（WAL 模式，支持并发读写） |
| 前端 | HTML + Bootstrap 5.3 + 原生 JavaScript + CSS3 动画 |
| 模板 | Jinja2 Environment + HTMLResponse |
| 动画 | CSS Keyframes + Canvas + 内联 SVG |

---

## 📁 目录结构

```
homework-pet/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI 后端，所有路由和业务逻辑（~2609 行）
│   ├── multi_pet.py          # 多宠物迁移 + 兼容层（v3.3 新增）
│   ├── database.py           # SQLite 数据库初始化（16 张表）
│   ├── run_local.py          # 本地开发启动脚本（端口 5001）
│   ├── static/               # 静态资源
│   │   ├── dragon-references/ # 进化阶段参考图（JPEG，已压缩）
│   │   ├── dragon-skins/     # 5 套皮肤 × 5 阶段透明 PNG（256×256，已压缩）
│   │   └── species/          # 7 物种 × 5 阶段立绘（256×256，已压缩）
│   ├── templates/
│   │   └── index.html        # 前端单页面（Jinja2 模板）
│   └── homework_pet.db       # 仓库内种子库（已入库，随 git 提交）
├── docs/
│   ├── 项目地图.html
│   ├── RAILWAY_REDEPLOY_MEMO.md  # v3.3 Railway 重新部署备忘
│   └── 周学习计划指导.md      # 每周配置参考与龙币经济指南
├── prd.md                    # 产品需求文档（v3.0 + v3.1 + v3.2 + v3.3）
├── DEPLOY.md                 # 部署指南（Railway + Windows 两种方案）
├── Procfile                  # Railway 部署启动命令
├── railway.json              # Railway 构建配置
├── requirements.txt          # Python 依赖
├── start_server.bat          # Windows 本地启动脚本
└── README.md                 # 本文件
```

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装

```bash
# 克隆项目
git clone https://github.com/your-repo/homework-pet.git
cd homework-pet

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate      # Linux/Mac
# 或 venv\Scripts\activate    # Windows

# 安装依赖
pip install -r requirements.txt
```

### 启动

```bash
# 进入 app 目录
cd app

# 开发模式（端口 5001，本地访问）
python run_local.py

# 生产模式（端口 5000，公网访问）
python -m uvicorn main:app --host 0.0.0.0 --port 5000
```

> **云端部署**：当前生产环境用 Railway，详见 [DEPLOY.md](DEPLOY.md) 方式 A。推送代码到 GitHub 即自动部署，地址：`https://<service-name>.up.railway.app`。

### 安全测试数据库

默认数据库仍是 `app/homework_pet.db`。如需在不污染真实数据的情况下测试，可复制数据库后通过环境变量切换：

```powershell
$env:HOMEWORK_PET_DB_PATH="D:\AIProject\workbuddy\homework-pet\backups\test_homework_pet.db"
python app\test_safe_regression.py
```

`test_safe_regression.py` 会拒绝连接真实数据库路径，避免误写真实数据。

启动后浏览器访问：
- 孩子端：`http://localhost:5001/?role=kid`
- 家长端：`http://localhost:5001/?role=parent`

> 📖 **云端部署**：详见 [DEPLOY.md](DEPLOY.md)

---

## 📡 API 概览

共 **57 个 API 端点**（含 v3.3 新增 10 个多宠物 `/api/pets*` 端点），完整列表见 [prd.md](prd.md) 第 6 章及 [docs/AGENTS.md](docs/AGENTS.md)。

| 分类 | 端点数 | 说明 |
|------|--------|------|
| 页面 | 1 | 主页路由 |
| 宠物 | 7 | 状态、喂食、互动、心情反馈、改名、算术题、皮肤 |
| 任务 | 2 | 完成作业、获取任务 |
| 家长额外任务 | 4 | 模板、布置、完成、删除 |
| 行为评价 | 4 | 规则、评价、自定义、今日记录 |
| 龙币经济 | 3 | 交易记录、统计、兑换零花钱 |
| 零花钱审批 | 2 | 批准、拒绝 |
| 专注打卡 | 2 | 完成、今日统计 |
| 商店 | 3 | 商品、购买、装备 |
| 家长设置 | 4 | 设置读写、密码验证/修改 |
| 其他 | 5 | 鼓励、成就、钱包、周报、定时任务 |
| 活动系统 | 3 | 心情轮询、随机惊喜、活动状态 |
| 多宠物系统 | 10 | 宠物列表/激活/切换/改名、物种目录、商店目录、领养、扭蛋(含 config)、签到 |

---

## 📜 版本历史

### v3.2.1（2026-06-22，Railway 上线）
- **部署迁移到 Railway**（连 GitHub 自动构建，公网 24/7 访问）
- 新增 `Procfile` / `railway.json` 部署配置
- `main.py` 末尾读取 `PORT` 环境变量，适配 Railway 动态端口
- `requirements.txt` 修复字面 `\n` 问题，移除未使用的 `sqlalchemy` / `aiosqlite`
- `homework_pet.db` 入库（含生产数据，部署后直接使用）
- 静态资源压缩：皮肤 PNG 2048×2048 → 256×256，参考图 JPEG 质量优化
- **Bug 修复**：数学题"再来一题"自动关闭（答对后 `closeMathQuiz()` 内 `location.reload()` 与 2.5 秒 setTimeout 冲突 → 用 `mathQuizAutoCloseTimer` 变量保存定时器 ID，每次 `startMathQuiz()` 先 `clearTimeout`）
- **Bug 修复**：手动发布任务金币上限 100（移除 HTML `max="100"` 和 JS `coinsReward > 100` 双重限制）
- 秒悟平台改造评估：不支持 Python 后端，沙箱代码已保留但未走 CDN 部署

### v3.4.1（2026-07-23，语音陪伴聊天 + 数据持久化修复）
- **小龙陪聊系统（Companion Chat）**：2026-07-18 启动、2026-07-22 完成语音聊天 T3–T7（ASR/TTS 全用百度），Hermes Agent 作为大脑（带长期记忆的用户画像），前端🎤文字/语音切换、按住说话、SSE 逐字渲染、服务端 TTS 播放
- **数据持久化修复**：Railway Volume 挂载信任 + 种子库迁移（`_ensure_persistent_db()`），重部署不再清库；`HOMEWORK_PET_DB_PATH=${RAILWAY_VOLUME_MOUNT_PATH}/homework_pet.db`（Railway 注入前展开 `${VAR}`）
- 当前版本号统一为 v3.4.1（Companion Chat 计为 v3.4）

### v3.3.0（2026-07-09，多宠物系统上线，Railway 部署成功）
- **多宠物系统**：单宠物 → 多宠物（龙/猫/兔/狐/独角兽/凤凰/熊猫），金币/成就/连续打卡全局共享，饱腹/心情/经验/亲密度按个体
- 新增 `species_catalog` / `pet_collection` 两表 + `pet.active_pet_id`；`multi_pet.py` 镜像兼容层保证旧 `WHERE id=1` 不崩
- 领养商店 / 扭蛋机（重复转 50% 龙币补偿）/ 签到发宠（每 7 次发熊猫）；`spend_coins()` 全局扣费
- 前端多宠物化（轮播/切换/领养中心/扭蛋机/签到 + emoji 回退）
- 35 张 AI 物种立绘（7×5），压缩至 256×256（37MB→2.4MB）
- **Bug 修复**：math_quiz 龙币流水双写（ab0f0bb）；新增 `GET /api/pets/gacha/config`、补全 `GET /api/pets/species` 的 `owned` 字段（34a32d1）
- 生产库已增量迁移（紫宝=激活宠物），全部 commit 已 push 至 GitHub main
- ✅ v3.3 多宠物已上线：`https://homepet.up.railway.app/`（旧域名 `web-production-a9e82.up.railway.app` 已废弃， Railway 服务已重建）。多宠物数据已随提交的 `app/homework_pet.db` 迁移好，开箱即用。

### v3.2（2026-04-27）
- 宠物改名功能（点击 ✏️ 输入新名字）
- 算术题互动游戏（100 以内加减法，答对赢龙币并提升亲密度）
- 实时属性衰减（按真实经过时间连续计算，低饱腹阶段放慢）
- 丰富情绪系统（新增生气/委屈/骄傲 3 种状态）
- 提前完成奖励（放学1小时内完成作业额外龙币）
- 宠物换肤系统（5 款皮肤 + 25 张阶段透明 PNG + 购买解锁机制）
- 行为评价支持手动输入自定义评价，记录行为流水和龙币流水
- 安全回归测试脚本支持测试 DB 隔离
- 12 个新 API 端点
- 2 项测试套件通过（数据链 83/83，综合 248/248）

### v3.1（2026-04-24）
- 互动衰减机制（每日一次，last_decay_date 控制）
- 宠物状态反馈（60 秒轮询，低饱腹/低亲密度视觉反馈）
- 限时活动（周末双倍龙币、数学挑战赛 +20 龙币）
- 成就徽章墙（新增 4 个成就，网格布局）
- 随机惊喜（每天 20% 概率触发礼物）
- 3 个新 API 端点

### v3.0（2026-04-24）
- CSS/SVG 5 阶段进化系统
- 4 种互动 + 亲密度属性
- 双轨制经济（经验 + 龙币）
- 家长额外任务 + 行为评价
- 专注打卡 + 商店 + 零花钱兑换
- 学习周报（Canvas 柱状图）
- 家长密码验证 + 系统设置

### v2.0
- 数学双倍经验 + 宝箱系统
- 全屏庆祝动画
- 宠物睡眠机制
- 数学勇士成就

---

## 📋 待实现（v3.5+）

- [ ] 微信通知推送
- [ ] 装饰商店完善（帽子/背景/拖尾效果）
- [ ] 多孩子账号
- [ ] 学习周报趋势对比
- [ ] 真实学习平台 API 对接（学而思/作业帮真实 OAuth）

---

## 📄 文档

| 文档 | 说明 |
|------|------|
| [README.md](README.md) | 项目概览（本文件） |
| [prd.md](prd.md) | 产品需求文档 |
| [DEPLOY.md](DEPLOY.md) | 云端部署指南 |
| [docs/周学习计划指导.md](docs/周学习计划指导.md) | 每周配置参考与行为评价标准 |

---

Made with ❤️ for kids and parents
