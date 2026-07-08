# 作业小龙 - 多宠物系统设计方案 v1.0

> 修改记录
> - 2026-07-08 初版创建。混合模式（金币/成就共享 + 饱腹/心情/经验独立），不同物种，多种获取途径，冻结式切换，纯收集无属性差异，卡片轮播 UI。

---

## 一、需求确认

| 决策项 | 选择 | 说明 |
|---|---|---|
| 属性归属 | **C 混合模式** | 金币/成就/连续打卡共享；饱腹/心情/经验/亲密度独立 |
| 物种类型 | 不同物种 | 龙/猫/兔/独角兽/狐狸等，需要新图片资源 |
| 获取方式 | 多种组合 | 金币购买 + 成就解锁 + 扭蛋随机 + 签到奖励 |
| 未激活宠物 | **冻结** | 切回时恢复原样，不衰减不喂食 |
| 属性差异 | 纯收集观赏 | 无加成无能力差异 |
| 切换 UI | 卡片列表轮播 | 横向滑动卡片，点击切换 |

---

## 二、当前架构分析

### 2.1 现状

- `pet` 表硬编码 `id=1`，全局唯一一只宠物
- `main.py` 中 **50+ 处 `WHERE id = 1`** 引用
- 皮肤系统（v3.2）：5 套配色，CSS 滤镜换色，本质是同种龙的着色
- 关键全局状态：`coins`（龙币）、`streak`（连续打卡）、`math_streak`、成就解锁

### 2.2 改造痛点

1. 50+ 处 `WHERE id=1` 不能简单改成 `WHERE id=?`，需区分"全局属性"vs"个体属性"
2. 调度器 `/api/scheduler/run` 当前对唯一宠物做衰减，多宠物后只对**激活宠物**衰减
3. 皮肤系统是按"龙"的物种设计的，新物种（猫/兔）需要独立图片资源
4. `add_coins()` 是全局函数，必须保持；`exp/hunger/mood/bond` 必须改为按个体

---

## 三、目标架构

### 3.1 双表拆分（核心）

```
┌─────────────────────────────────────┐
│  pet_profile (全局档案表)            │
│  id=1 固定，存共享属性                │
│  - coins (龙币)                      │
│  - streak (连续打卡)                 │
│  - math_streak                       │
│  - last_streak_date                  │
│  - last_math_date                    │
│  - math_challenge_today              │
│  - active_pet_id (当前激活宠物) ⭐    │
│  - last_decay_date (衰减基准)         │
└─────────────────────────────────────┘
                │
                │ 1:N
                ▼
┌─────────────────────────────────────┐
│  pet_collection (宠物个体表)         │
│  - id (主键，每只宠物一行)            │
│  - species_id (物种：dragon/cat/...) │
│  - skin_id (该物种下的皮肤)           │
│  - name (昵称)                       │
│  - exp (经验，独立) ⭐                │
│  - hunger (饱腹，独立) ⭐             │
│  - mood (心情，独立) ⭐               │
│  - bond (亲密度，独立) ⭐             │
│  - status (happy/sad/sleeping/...)   │
│  - runaway_until                     │
│  - acquired_at (获取时间)             │
│  - acquisition (shop/achievement/    │
│                 gacha/signin)        │
│  - is_frozen (冻结标记，默认 1)       │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  species_catalog (物种目录表)        │
│  - id (dragon/cat/rabbit/...)        │
│  - name (中文：龙/猫/兔子)           │
│  - icon (emoji)                      │
│  - desc                              │
│  - base_price (基础售价)             │
│  - rarity (common/rare/epic/legend) │
│  - acquisition_methods (json)        │
│  - stage_image_root                  │
└─────────────────────────────────────┘
```

### 3.2 属性归属对照表

| 属性 | 归属 | 表 | 说明 |
|---|---|---|---|
| coins 龙币 | 全局共享 | pet_profile | 钱包唯一 |
| streak 连续打卡 | 全局共享 | pet_profile | 行为奖励 |
| math_streak 数学连续 | 全局共享 | pet_profile | 同上 |
| achievements 成就 | 全局共享 | achievements 表 | 不变 |
| exp 经验 | 个体独立 | pet_collection | 切换不影响 |
| hunger 饱腹 | 个体独立 | pet_collection | 冻结不衰减 |
| mood 心情 | 个体独立 | pet_collection | 冻结不衰减 |
| bond 亲密度 | 个体独立 | pet_collection | 冻结不衰减 |
| status 状态 | 个体独立 | pet_collection | sleeping/happy |
| name 昵称 | 个体独立 | pet_collection | 每只可独立命名 |
| skin_id 皮肤 | 个体独立 | pet_collection | 每只独立选皮 |

---

## 四、数据库迁移方案

### 4.1 新表 DDL

```sql
-- 物种目录（静态数据，代码维护）
CREATE TABLE IF NOT EXISTS species_catalog (
    id TEXT PRIMARY KEY,                  -- 'dragon','cat','rabbit','unicorn','fox'
    name TEXT NOT NULL,                   -- '龙','猫','兔子','独角兽','狐狸'
    icon TEXT NOT NULL,                   -- '🐲','🐱','🐰','🦄','🦊'
    desc TEXT,
    base_price INTEGER DEFAULT 100,
    rarity TEXT DEFAULT 'common',         -- common/rare/epic/legend
    acquisition_methods TEXT,             -- 'shop,gacha,achievement' 逗号分隔
    stage_image_root TEXT,                -- /static/species/dragon
    sort_order INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1
);

-- 宠物个体表
CREATE TABLE IF NOT EXISTS pet_collection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_id TEXT NOT NULL,
    skin_id TEXT DEFAULT 'default',
    name TEXT NOT NULL,
    exp INTEGER DEFAULT 0,
    hunger INTEGER DEFAULT 80,
    mood INTEGER DEFAULT 80,
    bond INTEGER DEFAULT 50,
    status TEXT DEFAULT 'happy',
    runaway_until DATETIME,
    acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    acquisition TEXT DEFAULT 'shop',      -- shop/achievement/gacha/signin
    is_frozen INTEGER DEFAULT 1,          -- 1=冻结,0=激活
    last_decay_date DATETIME,
    created_at DAT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (species_id) REFERENCES species_catalog(id)
);
CREATE INDEX IF NOT EXISTS idx_pet_collection_species ON pet_collection(species_id);

-- 全局档案表（从原 pet 表演化）
-- 不新建表，沿用 pet 表 id=1，但移除个体字段含义
-- 兼容期保留 exp/hunger/mood/bond 字段（指向激活宠物的镜像值，便于旧 API 不崩）
```

### 4.2 迁移策略（无痛迁移）

**核心原则：不破坏现有 API，逐步迁移**

**Phase 1 - 数据搬迁（一次性脚本）**

```python
def migrate_single_to_multi_pet():
    """把单宠物数据迁移到多宠物结构"""
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. 确保 species_catalog 有 'dragon'
    cur.execute("INSERT OR IGNORE INTO species_catalog(id,name,icon,desc,base_price,rarity,acquisition_methods,stage_image_root) VALUES ('dragon','作业小龙','🐲','经典陪伴小龙',0,'common','shop','/static/dragon-skins')")

    # 2. 读取旧 pet 表数据
    old = conn.execute("SELECT * FROM pet WHERE id=1").fetchone()
    if not old:
        return
    old_dict = dict(old)

    # 3. 创建第一只宠物（继承旧数据）
    # 检查是否已迁移
    existing = cur.execute("SELECT COUNT(*) FROM pet_collection").fetchone()[0]
    if existing == 0:
        # 读取旧皮肤设置
        skin_id = 'default'
        cs = conn.execute("SELECT value FROM parent_settings WHERE key='current_skin'").fetchone()
        if cs: skin_id = cs['value']

        cur.execute("""
            INSERT INTO pet_collection
                (species_id, skin_id, name, exp, hunger, mood, bond, status, runaway_until,
                 acquired_at, acquisition, is_frozen, last_decay_date)
            VALUES ('dragon', ?, '作业小龙', ?, ?, ?, ?, ?, ?, ?, 'initial', 0, ?)
        """, (skin_id, old_dict['exp'], old_dict['hunger'], old_dict['mood'],
              old_dict.get('bond', 50), old_dict['status'],
              old_dict.get('runaway_until'),
              old_dict.get('created_at'),
              old_dict.get('last_decay_date')))

        new_pet_id = cur.lastrowid

        # 4. 在 pet 表增加 active_pet_id 字段（如未有）
        try:
            cur.execute("ALTER TABLE pet ADD COLUMN active_pet_id INTEGER")
        except: pass

        cur.execute("UPDATE pet SET active_pet_id = ? WHERE id = 1", (new_pet_id,))

    conn.commit()
    conn.close()
```

**Phase 2 - 兼容层**

`pet` 表 `id=1` 的 `exp/hunger/mood/bond` 字段保留，但每次写操作时**同步镜像**到激活宠物：

```python
def sync_active_pet_mirror(conn):
    """把激活宠物的属性同步到 pet 表镜像字段（兼容旧代码）"""
    active_id = conn.execute("SELECT active_pet_id FROM pet WHERE id=1").fetchone()['active_pet_id']
    if not active_id:
        return
    active = conn.execute("SELECT exp,hunger,mood,bond,status,runaway_until FROM pet_collection WHERE id=?", (active_id,)).fetchone()
    if active:
        conn.execute("""
            UPDATE pet SET exp=?,hunger=?,mood=?,bond=?,status=?,runaway_until=?
            WHERE id=1
        """, (active['exp'], active['hunger'], active['mood'], active['bond'],
              active['status'], active['runaway_until']))
```

这样所有 `SELECT * FROM pet WHERE id=1` 的旧代码继续工作，不需要立刻重写 50+ 处。

---

## 五、API 设计

### 5.1 新增 API

```
GET    /api/pets                     获取所有宠物列表（卡片轮播用）
GET    /api/pets/active              获取当前激活宠物（替代旧 /api/pet）
POST   /api/pets/switch              切换激活宠物 {pet_id}
GET    /api/pets/species             获取可领养的物种目录
POST   /api/pets/adopt               领养新宠物 {species_id, method}
POST   /api/pets/gacha               扭蛋抽取（消耗龙币随机）
GET    /api/pets/gacha/config        扭蛋配置（奖池+概率）
POST   /api/pets/{pet_id}/rename     重命名个体
POST   /api/pets/{pet_id}/release    放生（可选，防止误删先用软删除）
```

### 5.2 改造的旧 API（关键路径）

#### `/api/task/complete` - 完成作业

```python
# 旧：直接 UPDATE pet SET exp=exp+?
# 新：取 active_pet_id，更新 pet_collection，再 sync 镜像
def complete_task(...):
    active_id = get_active_pet_id(conn)
    # exp/mood/bond 给个体
    conn.execute("""
        UPDATE pet_collection
        SET exp=exp+?, mood=min(100,mood+?), bond=min(100,bond+?), hunger=min(100,hunger+?)
        WHERE id=?
    """, (exp_reward, mood_reward, bond_reward, hunger_reward, active_id))

    # coins 给全局
    add_coins(conn, coins_reward, 'task', f'完成{subject}')

    # streak/math_streak 给全局
    update_global_streak(conn, subject)

    # 同步镜像
    sync_active_pet_mirror(conn)
```

#### `/api/scheduler/run` - 定时调度

```python
# 旧：对 pet id=1 衰减
# 新：只对激活宠物衰减，冻结宠物不动
def scheduler():
    active_id = get_active_pet_id(conn)
    active = conn.execute("SELECT * FROM pet_collection WHERE id=? AND is_frozen=0", (active_id,)).fetchone()

    if not active:
        return

    # 睡眠检查（仅激活宠物）
    if active['status'] == 'sleeping' and active['runaway_until']:
        if sleep_end < current_time:
            conn.execute("UPDATE pet_collection SET status='normal', runaway_until=NULL, mood=40, hunger=40 WHERE id=?", (active_id,))

    # 衰减（仅激活宠物）
    if active['status'] != 'sleeping':
        decayed = calculate_realtime_decay(...)
        conn.execute("UPDATE pet_collection SET hunger=?,mood=?,bond=?,last_decay_date=? WHERE id=?",
                     (decayed['hunger'], decayed['mood'], decayed['bond'], now, active_id))

    # 21点睡眠检查（仅激活宠物）
    if today_tasks_cnt == 0 and current_time.hour >= 21 and active['status'] != 'sleeping':
        conn.execute("UPDATE pet_collection SET status='sleeping', runaway_until=? WHERE id=?",
                     (sleep_until, active_id))

    # 同步镜像
    sync_active_pet_mirror(conn)
```

#### `add_coins()` - 龙币（**完全不变**）

金币是全局共享，`UPDATE pet SET coins=?` 保留不动。

#### `/api/pet/feed` 喂食 `/api/pet/interact` 互动

改为操作 `pet_collection` 中激活宠物的 `hunger/mood/bond`，再 sync 镜像。

#### `/api/pet/skins` 皮肤系统

皮肤改为**个体属性**，每只宠物独立选皮。`skin_id` 字段从 `parent_settings` 迁移到 `pet_collection.skin_id`。

```python
# 旧：parent_settings.current_skin
# 新：pet_collection.skin_id (where id=active_pet_id)
```

### 5.3 切换宠物 API 详解

```python
@app.post("/api/pets/switch")
async def switch_pet(pet_id: int = Form(...)):
    """切换激活宠物（冻结式）"""
    conn = get_db_connection()
    # 1. 校验归属
    target = conn.execute("SELECT * FROM pet_collection WHERE id=?", (pet_id,)).fetchone()
    if not target:
        conn.close()
        return {"success": False, "message": "宠物不存在"}

    # 2. 冻结旧激活宠物（保留当前所有状态，不再衰减）
    old_active = conn.execute("SELECT active_pet_id FROM pet WHERE id=1").fetchone()['active_pet_id']
    if old_active:
        conn.execute("UPDATE pet_collection SET is_frozen=1 WHERE id=?", (old_active,))

    # 3. 激活新宠物
    conn.execute("UPDATE pet_collection SET is_frozen=0, last_decay_date=? WHERE id=?",
                (get_current_time().isoformat(), pet_id))
    conn.execute("UPDATE pet SET active_pet_id=? WHERE id=1", (pet_id,))

    # 4. 同步镜像到 pet 表
    sync_active_pet_mirror(conn)
    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": f"已切换为{target['name']}！",
        "pet_id": pet_id
    }
```

---

## 六、获取方式设计

### 6.1 物种目录初始数据

```python
SPECIES_CATALOG = [
    {'id':'dragon',  'name':'龙',     'icon':'🐲', 'rarity':'common', 'price':0,    'methods':'initial'},
    {'id':'cat',      'name':'魔法猫', 'icon':'🐱', 'rarity':'common', 'price':80,   'methods':'shop'},
    {'id':'rabbit',   'name':'月光兔', 'icon':'🐰', 'rarity':'rare',   'price':150,  'methods':'shop,gacha'},
    {'id':'fox',      'name':'九尾狐', 'icon':'🦊', 'rarity':'epic',   'price':300,  'methods':'gacha,achievement'},
    {'id':'unicorn',  'name':'独角兽', 'icon':'🦄', 'rarity':'legend', 'price':500,  'methods':'achievement,gacha'},
    {'id':'phoenix',  'name':'凤凰',   'icon':'🔥', 'rarity':'legend', 'price':0,    'methods':'achievement'},
    {'id':'panda',    'name':'熊猫',   'icon':'🐼', 'rarity':'rare',   'price':120,  'methods':'shop,signin'},
]
```

### 6.2 商店购买

```python
@app.post("/api/pets/adopt")
async def adopt_pet(species_id: str = Form(...), method: str = Form("shop")):
    conn = get_db_connection()
    species = conn.execute("SELECT * FROM species_catalog WHERE id=? AND enabled=1", (species_id,)).fetchone()
    if not species:
        return {"success": False, "message": "物种不存在"}

    # 检查是否已拥有（同物种可重复？设计决策见 6.5）
    # 默认：同物种可重复领养（每只可独立命名、独立成长）

    price = species['base_price']
    pet_coins = conn.execute("SELECT coins FROM pet WHERE id=1").fetchone()['coins']
    if pet_coins < price:
        return {"success": False, "message": f"龙币不够，需要{price}"}

    # 扣金币
    add_coins(conn, -price, 'adopt', f'领养{species["name"]}')

    # 创建个体
    new_name = species['name'] + str(random.randint(100,999))
    cur = conn.execute("""
        INSERT INTO pet_collection
            (species_id, skin_id, name, exp, hunger, mood, bond, status, acquisition, is_frozen)
        VALUES (?, 'default', ?, 0, 80, 80, 50, 'happy', 'shop', 1)
    """, (species_id, new_name))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"success": True, "pet_id": new_id, "message": f"成功领养{species['name']}！"}
```

### 6.3 扭蛋系统

```python
GACHA_POOLS = {
    'normal': {  # 100 龙币/次
        'cat': 0.40, 'rabbit': 0.30, 'panda': 0.20, 'fox': 0.08, 'unicorn': 0.02
    },
    'premium': {  # 300 龙币/次
        'rabbit': 0.35, 'panda': 0.25, 'fox': 0.25, 'unicorn': 0.10, 'phoenix': 0.05
    }
}

@app.post("/api/pets/gacha")
async def gacha(pool: str = Form("normal")):
    price = 100 if pool == 'normal' else 300
    # 扣金币
    # 按概率抽
    # 重复抽中已拥有的可改为：转化为龙币补偿（deja vu 模式）
```

### 6.4 成就解锁

在 `check_achievements()` 函数末尾增加：

```python
# 成就解锁奖励宠物
ACHIEVEMENT_PET_REWARDS = {
    '龙之守护者': 'phoenix',   # 达到神龙阶段 → 解锁凤凰
    '学霸': 'unicorn',          # 完成100次作业 → 解锁独角兽
    '专注达人': 'fox',          # 累计专注10小时 → 解锁九尾狐
}
for ach_name, species_id in ACHIEVEMENT_PET_REWARDS.items():
    if newly_unlocked_name == ach_name:
        # 检查是否已通过此成就领过
        # 未领过则自动发放一只 pet_collection
```

### 6.5 设计决策（需确认）

| 问题 | 推荐方案 | 备选 |
|---|---|---|
| 同物种可否重复领养 | ✅ 可重复（每只独立成长） | ❌ 每物种限 1 只 |
| 扭蛋重复抽中 | 转为龙币补偿（30%-50%） | 直接拒绝、强制保留 |
| 放生功能 | 第一版不做 | 提供软删除 |
| 领养上限 | 10 只（避免无限积累） | 无上限 |

---

## 七、前端 UI 设计

### 7.1 卡片轮播切换器

```html
<!-- 顶部宠物展示区下方 -->
<div class="pet-carousel" id="petCarousel">
  <!-- 卡片动态生成 -->
  <div class="pet-card" data-pet-id="1">
    <img src="dragon-stage-2.png" class="pet-avatar">
    <div class="pet-name">作业小龙 Lv.3</div>
    <div class="pet-status">😊 开心</div>
  </div>
  <div class="pet-card locked" data-pet-id="2">
    <div class="lock-icon">🔒</div>
    <div>魔法猫</div>
  </div>
  <!-- 左右滑动 -->
  <button class="carousel-prev">‹</button>
  <button class="carousel-next">›</button>
</div>

<!-- 底部入口 -->
<div class="pet-actions">
  <button onclick="showAdoptShop()">🛒 领养中心</button>
  <button onclick="showGachaPanel()">🎰 扭蛋机</button>
  <button onclick="switchCurrentPet()">🔄 切换</button>
</div>
```

### 7.2 切换交互流程

```
点击"切换" → 弹出卡片轮播 → 横滑选择目标卡片 →
  ├─ 已拥有：点击卡片 → 二次确认 → POST /api/pets/switch → 刷新页面
  └─ 未拥有：显示获取途径（商店/扭蛋/成就条件）
```

### 7.3 领养中心弹窗

```
┌──────────────────────────────────┐
│ 🛒 领养中心                  ✕  │
├──────────────────────────────────┤
│ [🐱 魔法猫]   [🐰 月光兔]        │
│  80龙币       150龙币           │
│  common       rare              │
│  [领养]       [领养]            │
│                                  │
│ [🦊 九尾狐]  [🦄 独角兽]        │
│  扭蛋/成就    成就/扭蛋         │
│  [去扭蛋]     [查看条件]        │
└──────────────────────────────────┘
```

### 7.4 扭蛋机弹窗

```
┌──────────────────────────────────┐
│ 🎰 扭蛋机                   ✕  │
├──────────────────────────────────┤
│       ┌──────────┐              │
│       │   🎁     │              │
│       │  ??     │              │
│       └──────────┘              │
│                                  │
│   [普通扭蛋 100🪙] [高级 300🪙]│
│                                  │
│ 当前龙币：520                    │
│ 上次抽中：🐰 月光兔              │
└──────────────────────────────────┘
```

---

## 八、资源需求

### 8.1 图片资源（最大工作量）

每个物种 × 5 个进化阶段 = 5 张图。初版 7 个物种 = **35 张图**。

| 物种 | 阶段1（蛋） | 阶段2（幼） | 阶段3（少年） | 阶段4（青年） | 阶段5（神） |
|---|---|---|---|---|---|
| 龙 🐲 | 已有 | 已有 | 已有 | 已有 | 已有 |
| 猫 🐱 | 待做 | 待做 | 待做 | 待做 | 待做 |
| 兔 🐰 | 待做 | 待做 | 待做 | 待做 | 待做 |
| 狐 🦊 | 待做 | 待做 | 待做 | 待做 | 待做 |
| 独角兽 🦄 | 待做 | 待做 | 待做 | 待做 | 待做 |
| 凤凰 | 待做 | 待做 | 待做 | 待做 | 待做 |
| 熊猫 🐼 | 待做 | 待做 | 待做 | 待做 | 待做 |

**资源方案**：
- 方案 A：用 AI 生图（FLUX/DALL-E）批量生成，统一风格 PNG 透明背景
- 方案 B：用 emoji + CSS 配色（快速上线，丑但能用）
- 方案 C：用 SVG 矢量图（可染色，但工作量大）

**推荐方案 B 上线 MVP**，后续用方案 A 补图。

### 8.2 目录结构

```
app/static/
├── dragon-skins/      # 现有
│   ├── default/
│   ├── fire/
│   └── ...
├── species/           # 新增
│   ├── cat/
│   │   ├── stage-0.png
│   │   ├── stage-1.png
│   │   └── ...
│   ├── rabbit/
│   └── ...
```

---

## 九、分阶段实施计划

### Phase 1：后端架构改造（2-3 天）

- [ ] 数据库 DDL：新增 `species_catalog`、`pet_collection` 表
- [ ] `pet` 表增加 `active_pet_id` 字段
- [ ] 编写迁移函数 `migrate_single_to_multi_pet()`
- [ ] 实现 `sync_active_pet_mirror()` 兼容层
- [ ] 改造 `add_coins()` 保持不变
- [ ] 改造 `/api/task/complete`（exp→个体，coins→全局）
- [ ] 改造 `/api/pet/feed`、`/api/pet/interact`（操作个体）
- [ ] 改造 `/api/scheduler/run`（仅衰减激活宠物）
- [ ] 改造皮肤系统（skin_id 从 settings 迁移到个体）

### Phase 2：多宠物核心 API（1-2 天）

- [ ] `GET /api/pets` - 宠物列表
- [ ] `GET /api/pets/active` - 激活宠物详情
- [ ] `POST /api/pets/switch` - 切换
- [ ] `POST /api/pets/{id}/rename` - 重命名
- [ ] 物种目录初始化数据

### Phase 3：获取系统（2-3 天）

- [ ] `GET /api/pets/species` - 物种目录
- [ ] `POST /api/pets/adopt` - 商店领养
- [ ] `POST /api/pets/gacha` - 扭蛋
- [ ] 成就解锁宠物逻辑
- [ ] 签到奖励宠物逻辑

### Phase 4：前端 UI（3-4 天）

- [ ] 卡片轮播组件
- [ ] 切换弹窗
- [ ] 领养中心页面
- [ ] 扭蛋机动画
- [ ] 旧 `index.html` 中 50+ 处 `/api/pet` 调用适配
- [ ] 皮肤选择 UI 改为按个体

### Phase 5：资源 + 测试（2-3 天）

- [ ] 批量生成 7 物种 × 5 阶段图片（或先用 emoji 占位）
- [ ] 端到端测试：领养→切换→冻结→切回→衰减验证
- [ ] 数据迁移脚本测试
- [ ] 旧 API 兼容性测试

**总工期：10-15 天**

---

## 十、风险与对策

| 风险 | 对策 |
|---|---|
| 50+ 处 `WHERE id=1` 改造遗漏 | 用 `sync_active_pet_mirror()` 兼容层兜底，旧 API 不重写也能跑 |
| 数据迁移中途失败 | 迁移前备份 `homework_pet.db`，迁移幂等可重跑 |
| 皮肤系统与新物种冲突 | 新物种暂时只支持 `default` 皮肤，旧皮肤系统仅作用于龙 |
| 前端调用量大 | 优先改 5 个核心接口（task/complete、pet/feed、pet/interact、scheduler、pet），其余按需 |
| 扭蛋概率争议 | 概率明示在 UI，重复抽中给龙币补偿 |
| 同物种重复导致管理混乱 | 加宠物上限 10 只，超出需先放生 |

---

## 十一、待确认问题（开工前需回答）

### Q1：同物种可否重复领养？
- **A**：可重复（每只独立成长、独立命名）— 推荐，玩家有收集感
- **B**：每物种限 1 只 — 简化数据，但失去收集乐趣

### Q2：扭蛋重复抽中怎么处理？
- **A**：转为龙币补偿（50% 价值）— 推荐
- **B**：拒绝抽取，提示已拥有
- **C**：仍发放但同名加序号

### Q3：第一版上线哪些物种？
- **最小集（3 种）**：龙（初始）+ 猫 + 兔 — 1 周可上线
- **标准集（5 种）**：龙 + 猫 + 兔 + 狐 + 独角兽 — 2 周
- **完整集（7 种）**：上述 + 凤凰 + 熊猫 — 3 周

### Q4：图片资源方案？
- **A**：AI 生图（推荐，美观但耗时）
- **B**：emoji 占位（快速上线，后续替换）
- **C**：现有龙的图复用 + 不同 CSS 滤镜（最省事但混淆物种）

### Q5：领养上限？
- **5 / 10 / 20 / 无限**（推荐 10）

### Q6：放生功能是否需要？
- **A**：不需要（第一版不做）
- **B**：软删除（保留数据可恢复）
- **C**：硬删除（释放槽位）

### Q7：成就解锁的宠物，是直接发放还是需要领取？
- **A**：自动发放到宠物列表 — 推荐
- **B**：弹窗提示后用户手动领取

---

## 十二、验证清单（上线前必过）

- [ ] 数据迁移后，旧龙（id=1）的所有属性（exp/hunger/mood/bond/coins/streak）与迁移前一致
- [ ] 完成作业：金币进全局钱包，exp/饱腹进当前激活宠物个体
- [ ] 切换宠物 A→B：A 冻结不衰减，B 开始衰减
- [ ] 切换回 A：A 的属性与切换时一致（无丢失）
- [ ] 喂食/互动只影响激活宠物，不影响冻结宠物
- [ ] 调度器只衰减激活宠物
- [ ] 皮肤选择按个体生效，切换宠物后皮肤跟随个体
- [ ] 扭蛋扣金币正确，概率符合配置
- [ ] 成就解锁自动发放宠物，且只发一次
- [ ] 宠物上限达到后无法继续领养/扭蛋
- [ ] 前端卡片轮播可正常切换，激活宠物高亮
- [ ] 旧版前端（未改造的 API 调用）仍能正常显示（镜像兼容层有效）

---

## 附录 A：核心代码改造对照表

| 旧代码 | 新代码 | 说明 |
|---|---|---|
| `SELECT * FROM pet WHERE id=1` | `SELECT * FROM pet_collection WHERE id=(SELECT active_pet_id FROM pet WHERE id=1)` | 取激活宠物 |
| `UPDATE pet SET exp=exp+? WHERE id=1` | `UPDATE pet_collection SET exp=exp+? WHERE id=?` | 更新个体 |
| `UPDATE pet SET coins=? WHERE id=1` | 保持不变 | 金币全局 |
| `parent_settings.current_skin` | `pet_collection.skin_id` | 皮肤个体化 |
| `parent_settings.unlocked_skins` | 弃用或改为 `pet_collection` 全局聚合查询 | 不再全局 |
| `/api/pet/skins` 返回全局皮肤列表 | 改为 `/api/pets/{id}/skins` 按个体 | 个体皮肤 |

---

## 附录 B：建议保存的技能

完成本方案后，建议将"多宠物系统改造"流程保存为 Hermes skill，覆盖：
1. 单宠物 → 多宠物数据迁移模式
2. 兼容层设计（镜像同步）
3. 扭蛋/商店/成就多途径获取的设计模板
4. 卡片轮播 UI 模式

---

**方案版本**：v1.0
**创建日期**：2026-07-08
**项目**：作业小龙 v3.3（拟）
**预估工期**：10-15 天
