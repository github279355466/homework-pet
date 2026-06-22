# PRD - 作业小龙 v3.2（学习激励电子宠物）

---

## 1. 产品概述

### 1.1 产品名称
**作业小龙 v3.0**

### 1.2 产品定位
- **目标用户**：6-8岁 小学一年级学生（主要）+ 家长（辅助）
- **核心价值**：用电子宠物养成+代币经济激励孩子完成作业，养成良好学习习惯和行为规范
- **使用方式**：iPad/手机浏览器打开网页，不需要安装 App
- **一句话**：做作业养宠物赚龙币，专注打卡兑换零花钱

### 1.3 v3.0 新增痛点解决（参考 GitHub 开源方案）
| 痛点 | v2.0 方案 | v3.0 方案 | 参考 |
|------|-----------|-----------|------|
| 只有作业激励 | 完成作业获得经验 | 行为评价系统：日常行为快速打分（+好习惯/-坏习惯） | 班级宠物园 |
| 缺乏长期目标感 | 经验值→等级 | 进化系统：5阶段可视化形态变化（蛋→幼龙→少年龙→青年龙→神龙） | 班级宠物园 |
| 互动单一 | 点击宠物说一句话 | 4种互动方式（摸头/挠痒/逗玩/喂食），亲密度属性 | PetStudy |
| 没有经济激励 | 无 | 龙币经济系统（双轨制），专注换龙币，龙币兑换零花钱 | TamoStudy |
| 缺乏专注训练 | 无 | 专注打卡（10/20/30分钟），小龙陪读 | TamoStudy |
| 家长只能鼓励 | 发送文字消息 | 布置额外任务 + 行为评价 + 零花钱审批 + 系统设置 | 班级宠物园 |

---

## 2. 用户角色

### 2.1 孩子端 (kid)
- 查看 CSS/SVG 宠物（5阶段进化形态，带浮动动画）
- 4种宠物互动（摸头/挠痒/逗玩/喂食），获得亲密度和语音气泡
- 完成作业打卡（日常 + 额外 + 家长布置的额外任务）
- 专注打卡（10/20/30分钟，获得龙币）
- 商店购物（零食/装饰）+ 零花钱兑换
- 查看成就进度
- 查看家长鼓励消息

### 2.2 家长端 (parent)
- 发送鼓励消息
- **布置额外任务**（12个预设模板 + 截止时间选择）
- **行为评价**（30条预设规则，4大分类，点击即评价）
- **零花钱审批**（批准/拒绝孩子的兑换请求）
- **系统设置**（汇率、每周上限、零花钱开关）

---

## 3. 功能需求

### 3.1 进化系统（v3.0 核心升级）

#### 3.1.1 进化阶段（前快后慢递进曲线）
- 阈值数组：`EVOLUTION_THRESHOLDS = [0, 800, 2000, 4000, 8000]`
- 设计理念：前2-3天破壳建立成就感，后期递增保持长期吸引力

| 阶段 | 名称 | 经验阈值 | 形态 | 颜色 | 预计达成 |
|------|------|----------|------|------|----------|
| Stage 0 | 龙蛋 | 0-799 | 圆形龙蛋，有裂纹动画 | 淡紫 #B388FF | 初始 |
| Stage 1 | 幼龙 | 800-1999 | 圆胖小龙，大眼睛，小翅膀 | 嫩绿 #69F0AE | 2-3天 |
| Stage 2 | 少年龙 | 2000-3999 | 修长龙形，有角，较大翅膀 | 天蓝 #40C4FF | ~1周 |
| Stage 3 | 青年龙 | 4000-7999 | 壮实龙形，双翼展开 | 金红 #FF8A65 | ~2周 |
| Stage 4 | 神龙 | 8000+ | 飘逸长龙，光环+粒子 | 金色 #FFD740 | 长期目标 |

#### 3.1.2 进化动画
- 阶段升级时：全屏闪光 → 新形态展示 → "进化了！XXX形态！"
- CSS keyframes 实现

### 3.2 互动系统（v3.0 新增）

| 互动 | 亲密度 | 心情 | 语音气泡 | 粒子效果 |
|------|--------|------|----------|----------|
| 🤚 摸头 | +2 | +1 | 好舒服～/再摸摸～ | 💕❤️💖 |
| 🤗 挠痒 | +3 | +2 | 哈哈哈好痒！/别挠了～ | 😆😂✨ |
| 🎾 逗玩 | +2 | -2饥饿 | 太好玩了！/再来再来！ | ⭐🌟✨ |
| 🍖 喂食 | +1 | +10 | 喂食成功 | - |

- 亲密度范围：0-100
- 每种互动2秒冷却
- 亲密度 > 70 时回应更热情
- 亲密度 < 30 时显示"不想玩"气泡

### 3.3 双轨制经济系统（v3.0 核心新增）

#### 3.3.1 经验值（EXP）
- 作用：决定宠物进化阶段
- 获取：完成作业（数学+100/其他+50）、完成额外任务（按设定）、专注打卡（经验加成卡+20）

#### 3.3.2 龙币（Coins）
- 作用：商店消费 + 兑换零花钱
- 获取途径：
  - 完成日常作业（数学+10/其他+5）
  - 完成额外任务（按设定的龙币值）
  - 行为评价加分（按规则设定的龙币值）
  - 专注打卡（10分钟=15/20分钟=30/30分钟=50）
  - 连续7天打卡额外+30

#### 3.3.3 龙币用途
- 🍖 小龙零食（5-10龙币，恢复饥饿值）
- 🎨 装饰/帽子/背景（20-50龙币）
- 💰 兑换零花钱（家长定义汇率，需审批）

### 3.4 专注打卡（v3.0 新增，参考 TamoStudy）
- 可选时长：10/20/30分钟
- 圆环倒计时 + 小龙陪读动画（表情变化：😴→😐→😊）
- 完成后庆祝动画 + 龙币到账
- 每日最多3次
- 页面不可见时暂停计时

### 3.5 家长额外任务系统（v3.0 新增）

#### 3.5.1 预设模板（12个）
| 分类 | 任务 | 经验 | 龙币 |
|------|------|------|------|
| 数学 | 口算练习20题 | 80 | 8 |
| 数学 | 数学练习册2页 | 100 | 10 |
| 数学 | 背诵乘法口诀 | 80 | 8 |
| 语文 | 读一篇课文 | 50 | 5 |
| 语文 | 抄写生字10个 | 60 | 6 |
| 语文 | 背诵古诗 | 70 | 7 |
| 英语 | 英语单词听写10个 | 60 | 6 |
| 英语 | 读英语绘本 | 50 | 5 |
| 其他 | 练字15分钟 | 40 | 4 |
| 其他 | 跳绳100个 | 30 | 3 |
| 其他 | 整理书包 | 20 | 2 |
| 其他 | 阅读课外书20分钟 | 40 | 4 |

#### 3.5.2 截止时间
- 快捷选项：今天/明天/本周五/下周一
- 过期自动标记为 expired

### 3.6 行为评价系统（v3.0 新增，参考班级宠物园）

#### 3.6.1 定位
独立于额外任务，用于日常行为的即时快速打分

#### 3.6.1.1 自定义评价（v3.2 修订）
- 保留固定预设规则。
- 家长端新增「自定义评价」输入区，支持临时填写评价名称、类型和龙币变化。
- 类型分为「奖励行为」和「需要改进」。
- 龙币变化范围限制为 -20 到 +20，避免误操作。
- 自定义评价写入 `behavior_records` 和 `coin_transactions`，同时影响心情和亲密度，纳入周报统计。

#### 3.6.2 预设规则（30条）
| 分类 | 规则 | 龙币 |
|------|------|------|
| 📚 学习 | 主动阅读 | +10 |
| 📚 学习 | 认真完成作业 | +15 |
| 📚 学习 | 作业工整 | +10 |
| 📚 学习 | 提前预习 | +15 |
| 📚 学习 | 考试进步 | +20 |
| 📚 学习 | 错题订正 | +10 |
| 📚 学习 | 朗读课文 | +10 |
| 📚 学习 | 迟到交作业 | -5 |
| 🎯 行为 | 帮助家人 | +10 |
| 🎯 行为 | 礼貌问好 | +5 |
| 🎯 行为 | 收拾玩具 | +10 |
| 🎯 行为 | 诚实守信 | +15 |
| 🎯 行为 | 自己穿衣 | +5 |
| 🎯 行为 | 主动洗碗 | +10 |
| 🎯 行为 | 说脏话 | -10 |
| 🎯 行为 | 发脾气 | -5 |
| 🎯 行为 | 打架 | -15 |
| 🎯 行为 | 顶嘴 | -5 |
| 💪 健康 | 跳绳运动 | +10 |
| 💪 健康 | 早睡早起 | +10 |
| 💪 健康 | 做眼保健操 | +5 |
| 💪 健康 | 按时吃饭 | +5 |
| 💪 健康 | 少吃零食 | +5 |
| 💪 健康 | 久坐提醒 | -5 |
| 📝 其他 | 获得老师表扬 | +20 |
| 📝 其他 | 完成小目标 | +10 |
| 📝 其他 | 坚持打卡 | +5 |
| 📝 其他 | 浪费食物 | -5 |
| 📝 其他 | 乱丢垃圾 | -5 |
| 📝 其他 | 电子产品超时 | -10 |

- 家长可自定义规则
- 扣分时影响宠物心情（减半）
- 龙币最低不低于0

### 3.7 零花钱兑换（v3.0 新增）
- 流程：孩子申请 → 家长审批 → 批准后到账 / 拒绝后退还龙币
- 汇率可配置（默认100龙币=1元）
- 每周兑换上限可配置（默认200龙币）
- 可整体关闭零花钱功能

### 3.8 成就系统（v3.0 更新）
保留 v2.0 所有成就，新增：
| 成就 | 条件 | 图标 |
|------|------|------|
| 🥚 破壳而出 | 进化到幼龙(Stage 1) | 🥚 |
| 🐲 成长之龙 | 进化到少年龙(Stage 2) | 🐲 |
| 💪 龙之力量 | 进化到青年龙(Stage 3) | 💪 |
| ✨ 神龙降临 | 进化到神龙(Stage 4) | ✨ |
| 💕 最佳拍档 | 亲密度达到100 | 💕 |
| 🧘 专注达人 | 累计专注10小时 | 🧘 |
| 💰 小富翁 | 累计获得1000龙币 | 💰 |

---

## 4. 数据结构

### 4.1 宠物表 (pet) - v3.0 新增字段
```sql
CREATE TABLE pet (
  id INTEGER PRIMARY KEY,
  name TEXT DEFAULT '作业小龙',
  level INTEGER DEFAULT 1,
  exp INTEGER DEFAULT 0,
  hunger INTEGER DEFAULT 80,
  mood INTEGER DEFAULT 80,
  streak INTEGER DEFAULT 0,
  status TEXT DEFAULT 'happy',
  runaway_until DATETIME,
  last_streak_date DATE,
  math_streak INTEGER DEFAULT 0,
  last_math_date DATE,
  bond INTEGER DEFAULT 50,          -- v3.0 新增：亲密度 0-100
  coins INTEGER DEFAULT 0,          -- v3.0 新增：龙币余额
  created_at DATETIME,
  updated_at DATETIME
);
```

### 4.2 家长额外任务表 (custom_tasks) - v3.0 新增
```sql
CREATE TABLE custom_tasks (
  id INTEGER PRIMARY KEY,
  subject TEXT NOT NULL,
  category TEXT DEFAULT 'other',
  exp_reward INTEGER DEFAULT 30,
  coins_reward INTEGER DEFAULT 3,
  deadline DATE,
  status TEXT DEFAULT 'pending',    -- pending/completed/expired
  assigned_by TEXT DEFAULT 'parent',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME
);
```

### 4.3 行为评价规则表 (behavior_rules) - v3.0 新增
```sql
CREATE TABLE behavior_rules (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  coins INTEGER NOT NULL,
  category TEXT NOT NULL,            -- study/behavior/health/other
  icon TEXT,
  is_custom INTEGER DEFAULT 0
);
```

### 4.4 行为评价记录表 (behavior_records) - v3.0 新增
```sql
CREATE TABLE behavior_records (
  id INTEGER PRIMARY KEY,
  rule_id INTEGER,
  rule_name TEXT,
  coins INTEGER NOT NULL,
  category TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.5 龙币交易记录表 (coin_transactions) - v3.0 新增
```sql
CREATE TABLE coin_transactions (
  id INTEGER PRIMARY KEY,
  type TEXT NOT NULL,                -- earn/spend
  source TEXT NOT NULL,              -- homework/custom_task/behavior/focus/shop/pocket_money
  amount INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  description TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.6 零花钱记录表 (pocket_money_records) - v3.0 新增
```sql
CREATE TABLE pocket_money_records (
  id INTEGER PRIMARY KEY,
  coins_spent INTEGER NOT NULL,
  amount_yuan REAL NOT NULL,
  status TEXT DEFAULT 'pending',     -- pending/approved/rejected
  requested_at DATETIME,
  approved_at DATETIME
);
```

### 4.7 专注打卡记录表 (focus_sessions) - v3.0 新增
```sql
CREATE TABLE focus_sessions (
  id INTEGER PRIMARY KEY,
  duration_minutes INTEGER NOT NULL,
  coins_earned INTEGER NOT NULL,
  completed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.8 宠物装饰表 (pet_accessories) - v3.0 新增
```sql
CREATE TABLE pet_accessories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,                -- hat/background/trail
  price INTEGER NOT NULL,
  owned INTEGER DEFAULT 0,
  equipped INTEGER DEFAULT 0
);
```

### 4.9 家长设置表 (parent_settings) - v3.0 新增
```sql
CREATE TABLE parent_settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
-- 预设：exchange_rate=100, weekly_coin_limit=200, pocket_money_enabled=1
```

---

## 5. 页面设计（v3.0）

### 5.1 顶部宠物展示区（毛玻璃卡片）
- 黄金时段倒计时条
- 环形进度条（左）+ CSS/SVG 龙（中）+ 互动按钮行（4个圆形按钮）
- 进化阶段标签 + 进化进度条（接近100%时闪烁）
- 五格属性条（经验/连续/饱腹/亲密度/龙币余额）

### 5.2 主内容卡片
- 三个 Tab：📝 作业 / 🏪 商店 / 🏆 成就
- 作业 Tab：完成作业 + 喂食 + 专注打卡入口 + 日常任务列表 + 家长额外任务 + 额外任务
- 商店 Tab：龙币余额 + 零花钱兑换 + 零食商品 + 钱包入口
- 成就 Tab：全部成就列表

### 5.3 家长面板
- 鼓励消息
- 布置额外任务（模板分类选择 + 截止时间 + 已布置列表）
- 行为评价（四大分类标签 + 规则按钮 + 今日记录）
- 零花钱审批（待审批列表 + 批准/拒绝按钮）
- 设置（汇率 + 每周上限 + 零花钱开关）

### 5.4 弹窗系统
- 完成作业弹窗（科目选择）
- 进化动画覆盖层（全屏闪光 + 新形态）
- 专注打卡覆盖层（时长选择 → 倒计时 → 完成）
- 确认弹窗（通用）
- 宝箱弹窗
- 鼓励消息弹窗
- 宠物睡眠蒙层

---

## 6. API 设计（v3.2，45 个端点）

### 6.1 页面
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | / | 主页（role=kid/parent） |

### 6.2 宠物
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/pet | 获取宠物状态 |
| POST | /api/pet/feed | 喂食 |
| POST | /api/pet/interact | 互动（pat/tickle/play） |

### 6.3 任务
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/task/complete | 完成日常作业 |
| GET | /api/tasks | 获取今日任务 |

### 6.4 家长额外任务
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/custom-tasks/templates | 预设模板列表 |
| POST | /api/custom-tasks/create | 布置任务 |
| POST | /api/custom-tasks/{id}/complete | 孩子完成任务 |
| DELETE | /api/custom-tasks/{id} | 删除任务 |

### 6.5 行为评价
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/behavior/rules | 规则列表 |
| POST | /api/behavior/evaluate | 执行预设评价 |
| POST | /api/behavior/evaluate/custom | 执行自定义评价 |
| POST | /api/behavior/rules/create | 自定义规则 |
| DELETE | /api/behavior/rules/{id} | 删除规则 |

### 6.6 龙币经济
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/coins/transactions | 交易记录 |
| GET | /api/coins/stats | 龙币统计 |
| POST | /api/coins/exchange-pocket-money | 兑换零花钱 |

### 6.7 零花钱审批
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/pocket-money/{id}/approve | 批准 |
| POST | /api/pocket-money/{id}/reject | 拒绝 |

### 6.8 专注打卡
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/focus/complete | 完成专注 |
| GET | /api/focus/today | 今日专注统计 |

### 6.9 商店
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/shop/accessories | 商品列表 |
| POST | /api/shop/buy/{id} | 购买 |
| POST | /api/shop/equip/{id} | 装备/卸下 |

### 6.10 其他
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/achievements | 成就列表 |
| GET | /api/parent/settings | 家长设置 |
| POST | /api/parent/settings | 保存设置 |
| POST | /api/parent/verify | 家长密码验证 |
| POST | /api/parent/change-password | 修改家长密码 |
| POST | /api/encourage | 发送鼓励 |
| GET | /api/encourage | 获取鼓励 |
| POST | /api/scheduler/run | 定时检查 |
| POST | /api/shop/buy-feed | 商店购买零食并喂食 |
| GET | /api/behavior/today | 今日行为记录（孩子端） |
| GET | /api/wallet/detail | 钱包详情（交易记录+统计） |
| GET | /api/weekly-report | 学习周报（7天数据） |

### 6.11 活动系统（v3.1 新增）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/pet/mood | 获取宠物心情状态（60秒轮询） |
| GET | /api/random-surprise | 触发/查询随机惊喜（每天20%概率） |
| GET | /api/event/status | 获取活动状态（周末/挑战赛） |

### 6.12 v3.2 新增端点
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/pet/rename | 宠物改名 |
| POST | /api/pet/math-quiz | 生成算术题 |
| POST | /api/pet/math-quiz/answer | 提交算术题答案 |
| GET | /api/pet/skins | 获取皮肤列表和当前选择 |
| POST | /api/pet/skin/select | 选择皮肤 |
| POST | /api/pet/skin/unlock | 购买解锁皮肤 |
| POST | /api/behavior/evaluate/custom | 执行自定义行为评价 |

---

## 7. 技术架构

### 7.1 技术栈
- 后端：Python FastAPI + SQLite（延续）
- 前端：HTML + Bootstrap 5.3 + 原生 JavaScript + CSS3 动画 + 内联 SVG
- 模板：Jinja2 Environment + HTMLResponse（延续 v2.0 兼容方案）

### 7.2 启动方式
```bash
cd app
python -m uvicorn main:app --host 0.0.0.0 --port 5000
```

---

## 8. 开源方案参考映射

| 功能 | 参考项目 | 借鉴要点 |
|------|----------|----------|
| 行为评价系统 | 班级宠物园 | 83条规则→精简为30条家庭版，四大分类，正负分平衡 |
| 龙币经济系统 | TamoStudy | 专注=代币、商店消耗、状态衰减闭环 |
| 进化阶段系统 | 班级宠物园 | 8级→5阶段，形态变化 |
| CSS/SVG龙设计 | AI生成参考图 | 5阶段Q版可爱龙，内联SVG实现 |

---

## 9. v3.1 新增功能（2026-04-24）

### 9.1 互动衰减机制

#### 9.1.1 设计目的
解决"孩子只要上线互动一次就能维持满状态"的问题，引入时间维度的衰减压力。

#### 9.1.2 衰减规则
| 属性 | 每日衰减 | 说明 |
|------|----------|------|
| 饱腹度 (hunger) | -8 | 约 5 天从 80 降到 0 |
| 心情 (mood) | -5 | 约 7 天从 80 降到 0 |
| 亲密度 (bond) | -6 | 约 8 天从 50 降到 0 |

- **触发频率**：每天最多衰减一次（通过 `last_decay_date` 字段控制，与服务端调度器联动）
- **睡眠豁免**：宠物处于 `sleeping` 状态时不衰减
- **最低值**：所有属性不低于 0
- **体验设计**：约一周不玩 bond 从 50 降到约 8（不归零，保留恢复空间）

### 9.2 宠物状态反馈系统

#### 9.2.1 心情轮询
- 前端每 60 秒调用 `GET /api/pet/mood` 获取宠物当前状态
- 返回数据：`hunger`、`mood`、`bond`、`status`、`bubble`（气泡文案）、`bubble_type`

#### 9.2.2 状态阈值与表现
| 条件 | 表现 | CSS 效果 |
|------|------|----------|
| 饱腹 < 30 | 撒娇讨食 | 宠物轻微抖动 + 气泡"好饿呀～" |
| 亲密度 < 20 | 躲起来 | 灰度滤镜 + 缩小 + 气泡"不想理你" |
| 心情 > 70 | 开心 | 明亮色彩 + 轻微浮动 |
| 所有属性 > 50 | 正常 | 默认状态 |

#### 9.2.3 气泡文案池
```python
MOOD_BUBBLES = {
    'begging': ["好饿呀，喂喂我～", "肚子咕咕叫了", "想吃东西..."],
    'hiding': ["不想理你...", "哼，都不陪我", "你都不来看我"],
    'happy': ["今天真开心！", "有你真好～", "嘿嘿嘿"],
    'normal': ["来做作业吧！", "一起加油！", "我在等你哦～"],
}
```

### 9.3 限时活动系统

#### 9.3.1 周末双倍龙币
- **触发条件**：周六、周日（`weekday() >= 5`）
- **效果**：完成作业获得的龙币自动 ×2
- **实现**：`add_coins()` 函数新增 `double_weekend` 参数
- **标识**：交易记录中带 `[周末双倍🎉]` 标记

#### 9.3.2 数学挑战赛
- **规则**：每天第一道数学作业额外获得 +20 龙币
- **标识**：宠物状态中显示挑战赛横幅
- **限制**：每天仅一次，通过 `pet.math_challenge_today` 字段控制
- **目的**：针对孩子对数学不感兴趣的专项激励

#### 9.3.3 活动横幅
- 顶部显示当前活动信息（周末双倍 / 数学挑战赛）
- 蓝色渐变（周末）或 橙红渐变（挑战赛）背景
- `GET /api/event/status` 返回活动状态供前端判断

### 9.4 成就徽章墙

#### 9.4.1 v3.1 新增成就（4 个）
| 成就 | 条件 | 图标 | 类别 |
|------|------|------|------|
| 🍖 喂养达人 | 累计喂食 50 次 | 🍖 | 互动 |
| 🤗 互动高手 | 累计互动 100 次（摸头/挠痒/逗玩） | 🤗 | 互动 |
| 💖 暖心天使 | 亲密度连续 7 天 ≥ 80 | 💖 | 情感 |
| ⚔️ 挑战勇士 | 完成 10 次数学挑战赛 | ⚔️ | 挑战 |

#### 9.4.2 徽章墙布局
- 3 列等宽网格布局（`grid-template-columns: repeat(3, 1fr)`）
- 已解锁：彩色图标 + 金色边框
- 未解锁：灰色图标 + 锁标记
- 新解锁动画：金色闪光 + 弹跳缩放（`@keyframes unlock-shine`）

### 9.5 随机惊喜系统

#### 9.5.1 触发规则
- **概率**：每天首次打开页面时 20% 概率触发
- **限制**：每天最多一次（数据库记录 `random_surprises` 表）
- **前端**：页面加载时调用 `GET /api/random-surprise`

#### 9.5.2 奖励池（9 种）
| 奖励类型 | 奖励值 | 描述 |
|----------|--------|------|
| 龙币小红包 | +10~30 龙币 | 意外之财！ |
| 经验加倍卡 | +30~80 经验 | 经验飞升！ |
| 亲密度提升 | +5~15 亲密度 | 小龙更爱你了 |
| 限时称号 | 称号文字 | "数学小天才"等 |
| 超级零食 | +20 饱腹 | 超级大餐！ |
| 双倍龙币券 | 标记 | 下次作业双倍龙币 |
| 心情大振 | +15 心情 | 开心一整天！ |
| 金龙祝福 | +50 经验 | 金龙显灵！ |
| 神秘礼物 | 随机 | 惊喜盲盒！ |

#### 9.5.3 展示效果
- 全屏半透明遮罩 + 弹跳动画卡片
- 奖励图标旋转 + 粒子庆祝特效
- 2 秒后自动消失或点击关闭

### 9.6 v3.1 新增数据结构

#### 9.6.1 随机惊喜表 (random_surprises)
```sql
CREATE TABLE IF NOT EXISTS random_surprises (
    id INTEGER PRIMARY KEY,
    surprise_type TEXT NOT NULL,        -- 奖励类型
    reward_value INTEGER,               -- 奖励值
    description TEXT,                   -- 描述文案
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 9.6.2 pet 表新增字段
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `last_decay_date` | DATE/TEXT | NULL | v3.2 起存储 ISO 时间戳，用于按真实经过时间结算衰减 |
| `math_challenge_today` | INTEGER | 0 | 今天是否已完成数学挑战赛 |

### 9.7 v3.1 新增 API 端点（3 个）

| 方法 | 路径 | 说明 | 返回字段 |
|------|------|------|----------|
| GET | /api/pet/mood | 获取宠物心情状态 | hunger, mood, bond, status, bubble, bubble_type |
| GET | /api/random-surprise | 触发/查询随机惊喜 | triggered, surprise_type, reward_value, description |
| GET | /api/event/status | 获取活动状态 | is_weekend, events[], math_challenge_done |

---

## 10. v3.2 新增功能（2026-04-27）

### 10.1 宠物改名

- **端点**：`POST /api/pet/rename`
- **规则**：名字长度 1-20 字符，不能为空
- **UI**：点击宠物名字旁的 ✏️ 图标弹窗输入新名字
- **设计意图**：小朋友喜欢给自己养的宠物取名字，增加归属感

### 10.2 算术题互动游戏

- **端点**：`POST /api/pet/math-quiz`、`POST /api/pet/math-quiz/answer`
- **规则**：随机生成 100 以内加减法，提供 4 个选项
- **奖励**：答对奖励 +10 龙币、心情 +5、亲密度 +2；答错也给予轻微鼓励
- **UI**：算术题弹窗，孩子选择答案，答对/答错展示不同反馈
- **设计意图**：保留 TaskTails 小游戏的即时反馈，同时把互动改成更适合一年级的数学练习

### 10.3 实时属性衰减

- **旧机制**：每日衰减一次（饱腹-8/心情-5/亲密度-6），通过 `last_decay_date` 存储日期控制
- **新机制**：按真实经过时间连续计算，通过 `last_decay_date` 存储 ISO 时间戳控制
- **饱腹衰减**：饱腹高于 30 时约每小时 -1.5，48 小时从 100 降到 30 以下；低于 30 后约每 6 小时 -1，避免直接归零
- **心情/亲密度**：心情约每小时 -1，亲密度约每小时 -0.75
- **触发**：定时调度器 `/api/scheduler/run` 每次检查，距上次衰减超过约 6 分钟即按真实时间结算
- **睡眠豁免**：宠物处于 `sleeping` 状态时不衰减
- **设计意图**：每日衰减间隔太长，实时衰减让孩子更频繁关注宠物状态

### 10.4 丰富情绪系统

- **旧机制**：仅区分 sleep/beg/pout/hide/shy/happy/normal
- **新机制**：新增中间情绪状态

| 状态 | 触发条件 | CSS 特效 | 气泡文案 |
|------|----------|----------|----------|
| 😤 生气 | hunger < 10 或 mood < 5 | 抖动 + 红色滤镜 | "超级生气！😤" |
| 😢 委屈 | mood < 15 | 缩小 + 灰色滤镜 | "好委屈..." |
| 😎 骄傲 | hunger > 90 且 mood > 90 且 bond > 90 | 金色光环 + 放大 | "我太棒了！" |

- 情绪通过 `GET /api/pet/mood` 返回 `bubble_type` 控制前端 CSS 动画类

### 10.5 提前完成奖励（Early Bird Bonus）

- **规则**：在家长设置的放学时间（默认 16:00）后 1 小时内完成作业，额外获得等额龙币奖励
- **设置**：家长面板可配置 `school_end_time`（存储在 `parent_settings` 表）
- **返回**：`POST /api/task/complete` 响应中新增 `early_bird_bonus` 字段
- **设计意图**：参考 TaskTails 按 deadline 提前完成给更多 Token 的机制

### 10.6 宠物换肤系统

- **5 款皮肤**：

| 皮肤 ID | 名称 | 图标 | 价格 |
|---------|------|------|------|
| default | 经典小龙 | 🐲 | 免费 |
| fire | 火焰小龙 | 🔥 | 50 龙币 |
| ice | 冰雪小龙 | ❄️ | 50 龙币 |
| gold | 黄金小龙 | 👑 | 50 龙币 |
| nature | 森林小龙 | 🌿 | 50 龙币 |

- **端点**：
  - `GET /api/pet/skins` — 获取所有皮肤和当前选择
  - `POST /api/pet/skin/select` — 选择皮肤
  - `POST /api/pet/skin/unlock` — 解锁新皮肤（消耗龙币）
- **存储**：`parent_settings` 表中 `current_skin` 和 `unlocked_skins` 键值
- **图片资源**：`app/static/dragon-skins/{skin_id}/stage-{0-4}.png`，共 5 套皮肤 × 5 个进化阶段 = 25 张 1024×1024 透明 PNG
- **UI**：皮肤面板和商店皮肤区均展示当前阶段图片，已解锁/未解锁状态区分
- **设计意图**：TaskTails 支持多存档/多宠物，通过换肤实现宠物多样化

### 10.7 学习平台联动

该功能已移除。真实接入学而思、作业帮等平台需要官方 API、鉴权方式和数据授权说明；在没有稳定接口前不保留模拟入口，避免用户误以为已经接入真实平台。

### 10.8 v3.2 新增 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/pet/rename | 宠物改名 |
| POST | /api/pet/math-quiz | 生成算术题 |
| POST | /api/pet/math-quiz/answer | 提交算术题答案 |
| GET | /api/pet/skins | 获取皮肤列表 |
| POST | /api/pet/skin/select | 选择皮肤 |
| POST | /api/pet/skin/unlock | 解锁皮肤 |
| POST | /api/behavior/evaluate/custom | 执行自定义行为评价 |

### 10.9 v3.2 数据结构变更

#### pet 表无新增字段（衰减改用时间戳格式存储现有字段）
- `last_decay_date`：从 DATE 改为存储 ISO 时间戳字符串

#### parent_settings 表新增键值
| key | value | 说明 |
|-----|-------|------|
| `school_end_time` | `16:00` | 放学时间，用于提前完成奖励 |
| `current_skin` | `default` | 当前皮肤 ID |
| `unlocked_skins` | `default` | 已解锁皮肤 ID 列表（逗号分隔） |
| `skins_enabled` | `1` | 皮肤系统开关 |

---

## 11. 待实现（V3.3+）
- [ ] 装饰商店完善（装备展示在龙身上、更多装饰类型）
- [ ] 微信通知推送
- [ ] 多孩子账号
- [ ] 学习周报统计图表优化（增加行为趋势、对比上周）
- [ ] 真实学习平台 API 对接（学而思/作业帮真实 OAuth）
- [ ] 商店商品扩展（更多零食/装饰/特效）

---

done! v3.2 — 2026-04-27 实现完成
- ✅ 宠物改名（POST /api/pet/rename + 前端改名弹窗）
- ✅ 算术题互动游戏（100 以内加减法，答对 +10 龙币并提升亲密度）
- ✅ 实时属性衰减（按真实经过时间连续计算，低饱腹阶段自动放慢）
- ✅ 丰富情绪系统（新增生气/委屈/骄傲 3 种中间状态）
- ✅ 提前完成奖励（放学1小时内完成作业额外龙币加成）
- ✅ 宠物换肤系统（5 款皮肤 × 5 阶段透明 PNG）
- ✅ 行为评价支持手动输入自定义评价
- ✅ 学习平台联动模拟入口已移除，保留真实 API 对接为 V3.3+ 事项
- ✅ 安全回归测试脚本（测试 DB 隔离，拒绝连接真实 DB）

done! v3.1 — 2026-04-24 实现完成
- ✅ 互动衰减机制（每日一次，last_decay_date 控制）
- ✅ 宠物状态反馈（60 秒轮询，低饱腹/低亲密度视觉反馈）
- ✅ 限时活动（周末双倍龙币、数学挑战赛 +20 龙币）
- ✅ 成就徽章墙（新增 4 个成就，网格布局）
- ✅ 随机惊喜（每天 20% 概率触发礼物）
- ✅ 3 个新 API 端点（/api/pet/mood, /api/random-surprise, /api/event/status）

done! v3.0 — 2026-04-24 实现完成
- ✅ CSS/SVG 5阶段进化系统 + 前快后慢递进曲线
- ✅ 4种互动系统 + 亲密度属性
- ✅ 家长额外任务（12模板 + 截止时间）
- ✅ 行为评价（30条预设规则 + 自定义）
- ✅ 龙币经济（双轨制 + 31个API端点）
- ✅ 专注打卡（圆环倒计时 + 小龙陪读）
- ✅ 商店系统（6种零食 + 装饰商品）
- ✅ 零花钱兑换（申请→审批→退还）
- ✅ 钱包弹窗（交易记录 + 零花钱统计）
- ✅ 学习周报（Canvas柱状图，作业/龙币/专注可切换）
- ✅ 家长密码验证 + 修改密码
- ✅ 进化全屏动画特效
