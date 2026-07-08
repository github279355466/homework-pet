# PRD: v3.3 多宠物系统改造

> **任务 ID**: v3.3-multi-pet
> **创建日期**: 2026-07-08
> **负责人**: Codex
> **分支**: feature/multi-pet-v3.3
> **状态**: planning-complete (待实施)

---

## 1. 背景与目标

### 1.1 现状
作业小龙 v3.2 是单宠物系统:
- `pet` 表硬编码 `id=1`，全局唯一一只宠物
- `main.py` 中 50+ 处 `WHERE id = 1` 引用
- v3.2 皮肤系统: 5 套配色 (CSS 滤镜换色)，本质是同种龙的着色

### 1.2 目标
在保留现有功能的前提下，增加多宠物领养/切换功能:
- 玩家可拥有多只不同物种的宠物
- 可在宠物间切换激活
- 每只宠物独立成长（exp/hunger/mood/bond 独立）
- 金币/成就全局共享

## 2. 用户确认的需求决策

| 决策项 | 选择 | 说明 |
|---|---|---|
| 属性归属 | **C 混合模式** | 金币/成就/连续打卡共享；饱腹/心情/经验/亲密度独立 |
| 物种类型 | 不同物种 | 龙/猫/兔/狐/独角兽/凤凰/熊猫 共 7 种 |
| 获取方式 | 多种组合 | 商店购买 + 扭蛋 + 成就自动发放 |
| 未激活宠物 | **冻结** | 切回时恢复原样，不衰减不喂食 |
| 属性差异 | 纯收集观赏 | 无加成无能力差异 |
| 切换 UI | 卡片列表轮播 | 横向滑动卡片，点击切换 |
| 同物种领养 | **不可重复** | 每物种限 1 只 |
| 扭蛋重复抽中 | **已领养的不参与** | 抽选前过滤已拥有物种 |
| 第一版物种数 | **完整 7 种** | 龙/猫/兔/狐/独角兽/凤凰/熊猫 |
| 图片资源 | **AI 生图** | FLUX 2 Klein 9B，统一风格 PNG |
| 领养上限 | **无上限** | (但同物种已限 1 只，自然 7 只封顶) |
| 放生功能 | **不做** | 第一版不实现 |
| 成就解锁宠物 | **自动发放** | 触发成就时自动入账 |

## 3. 架构设计

### 3.1 双表拆分（核心）

```
┌─────────────────────────────────────┐
│  pet 表 (id=1 全局档案，保留)         │
│  - coins (龙币，全局共享)             │
│  - streak (连续打卡，全局)            │
│  - math_streak (数学连续，全局)       │
│  - active_pet_id (当前激活宠物) ⭐    │
│  - exp/hunger/mood/bond (镜像字段)    │
│    └─ 通过 sync_active_pet_mirror()  │
│       同步自 pet_collection，兼容旧代码 │
└─────────────────────────────────────┘
                │ 1:N
                ▼
┌─────────────────────────────────────┐
│  pet_collection (个体宠物表，新增)    │
│  - id (主键，每只一行)                │
│  - species_id (物种: dragon/cat/...) │
│  - skin_id (皮肤，个体独立)           │
│  - name, exp, hunger, mood, bond      │
│  - status, runaway_until              │
│  - is_frozen (1=冻结,0=激活)          │
│  - acquisition (shop/gacha/achievement/initial) │
│  - acquired_at, last_decay_date       │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  species_catalog (物种目录，新增)     │
│  - id (dragon/cat/rabbit/fox/...)   │
│  - name, icon, desc                  │
│  - base_price, rarity                │
│  - acquisition_methods (csv)         │
│  - stage_image_root                  │
└─────────────────────────────────────┘
```

### 3.2 属性归属表

| 属性 | 归属 | 存储位置 |
|---|---|---|
| coins 龙币 | 全局 | pet.coins |
| streak 连续打卡 | 全局 | pet.streak |
| math_streak | 全局 | pet.math_streak |
| achievements 成就 | 全局 | achievements 表 |
| exp 经验 | 个体 | pet_collection.exp |
| hunger 饱腹 | 个体 | pet_collection.hunger |
| mood 心情 | 个体 | pet_collection.mood |
| bond 亲密度 | 个体 | pet_collection.bond |
| status 状态 | 个体 | pet_collection.status |
| name 昵称 | 个体 | pet_collection.name |
| skin_id 皮肤 | 个体 | pet_collection.skin_id |

## 4. 功能需求

### 4.1 数据库变更
- 新增 `species_catalog` 表（7 条静态数据）
- 新增 `pet_collection` 表
- `pet` 表增加 `active_pet_id` 字段
- 迁移函数: 把旧 pet (id=1) 数据迁移到 pet_collection 第一行

### 4.2 后端 API 改造
- 50+ 处 `WHERE id=1` 通过 `sync_active_pet_mirror()` 兼容层兜底
- 金币 `add_coins()` 不变（全局）
- exp/hunger/mood/bond 通过 `update_active_pet()` 写入 pet_collection
- 调度器只对激活宠物衰减，冻结宠物不动
- 皮肤 `skin_id` 从 `parent_settings` 迁移到 `pet_collection`

### 4.3 新增 API
- `GET /api/pets` - 宠物列表（卡片轮播用）
- `GET /api/pets/active` - 激活宠物详情
- `POST /api/pets/switch` - 切换激活宠物（冻结式）
- `GET /api/pets/species` - 物种目录（已领养标记 owned=true）
- `POST /api/pets/adopt` - 商店领养（同物种不可重复）
- `GET /api/pets/gacha/config` - 扭蛋池配置（排除已领养）
- `POST /api/pets/gacha` - 扭蛋抽取（已领养不参与）
- `POST /api/pets/{pet_id}/rename` - 个体重命名

### 4.4 成就解锁自动发放
- `龙之守护者` (达到神龙阶段) → 自动发放凤凰
- `学霸` (完成100次作业) → 自动发放独角兽
- `专注达人` (累计专注10小时) → 自动发放九尾狐

### 4.5 前端 UI
- 宠物卡片轮播组件（顶部，横向滑动）
- 切换弹窗（二次确认）
- 领养中心弹窗（7 种物种展示）
- 扭蛋机弹窗（动画 + 概率展示）
- 27 处 `/api/pet` 调用适配（部分改为 `/api/pets/active`）

### 4.6 AI 图片资源
- 7 物种 × 5 阶段 = 35 张图
- 风格: 可爱卡通，Q版，透明背景 PNG
- 尺寸: 1024×1024 生成，压缩到 256×256
- 路径: `app/static/species/{species_id}/stage-{0-4}.png`
- 龙沿用现有 `/static/dragon-skins/` 路径

## 5. 实施计划

**详细 Task 清单**: 见 `docs/plans/2026-07-08-multi-pet-v3.3-plan.md`
**Trellis 任务卡**: 见 `.trellis/tasks/2026-07/v3.3-multi-pet/tasks/`

### 阶段总览

| 阶段 | 任务数 | 工时 | 内容 |
|---|---|---|---|
| Phase 0 | 4 | 0.5天 | 环境准备 |
| Phase 1 | 8 | 1.5天 | 数据库+迁移 |
| Phase 2 | 13 | 2天 | 后端旧API重构 |
| Phase 3 | 11 | 2天 | 新增多宠物API |
| Phase 4 | 7 | 3天 | 前端UI |
| Phase 5 | 10 | 2天 | AI图片资源 |
| Phase 6 | 10 | 1.5天 | 端到端测试 |
| Phase 7 | 6 | 0.5天 | 部署上线 |
| **总计** | **69** | **13天** | |

## 6. 验收标准

### 6.1 功能验收
- [ ] 数据迁移后，旧龙的所有属性（exp/hunger/mood/bond/coins/streak）与迁移前一致
- [ ] 完成作业: 金币进全局钱包，exp/饱腹进当前激活宠物个体
- [ ] 切换宠物 A→B: A 冻结不衰减，B 开始衰减
- [ ] 切换回 A: A 的属性与切换时一致（无丢失）
- [ ] 喂食/互动只影响激活宠物，不影响冻结宠物
- [ ] 调度器只对激活宠物衰减
- [ ] 皮肤选择按个体生效，切换宠物后皮肤跟随个体
- [ ] 扭蛋扣金币正确，已领养物种不参与抽选
- [ ] 成就解锁自动发放宠物，且只发一次
- [ ] 前端卡片轮播可正常切换，激活宠物高亮
- [ ] 旧版前端（未改造的 API 调用）仍能正常显示（镜像兼容层有效）

### 6.2 资源验收
- [ ] 7 物种 × 5 阶段 = 35 张图片全部存在
- [ ] 图片尺寸 256×256 PNG 透明背景
- [ ] 图片风格统一（可爱卡通 Q 版）

### 6.3 部署验收
- [ ] Railway 自动部署成功
- [ ] 生产环境主页加载正常
- [ ] 生产环境核心功能验证（完成作业、领养、切换、扭蛋）

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| 50+ 处 `WHERE id=1` 改造遗漏 | `sync_active_pet_mirror()` 兼容层兜底 |
| 数据迁移中途失败 | 备份在 `backups/homework_pet_pre_v33_*.db`，可回滚 |
| 皮肤系统与新物种冲突 | 新物种第一版仅支持 `default` 皮肤 |
| 前端调用量大 | 优先改 5 个核心接口，其余按需 |
| 扭蛋概率争议 | 概率明示在 UI，已领养的不参与 |
| AI 生图风格不一致 | Prompt 统一风格模板，人工筛选 |
| Railway 部署失败 | `requirements.txt` 不变，无新依赖 |

## 8. 交接给 Codex 的说明

### 8.1 启动指令
Codex 会话启动时:
1. 读取 `.trellis/ONBOARDING.md`
2. 读取 `.trellis/project-status.json`
3. 读取本 PRD 文件
4. 读取 `docs/plans/2026-07-08-multi-pet-v3.3-plan.md` 获取详细 Task
5. 从 Phase 0 Task 0.1 开始按顺序执行

### 8.2 每个 Task 的执行流程
1. 从 `tasks/` 目录读取对应 `task-XX.md`
2. 按 TDD 循环: 写测试 → 验证失败 → 实现 → 验证通过
3. 运行验证命令（必须真实执行，不能假设通过）
4. git add + git commit（commit message 见每个 Task 的 Step）
5. 在 `task-XX.md` 末尾追加 `## 完成记录` 区块，写入: status / commit_sha / 验证输出
6. 更新 `.trellis/workspace/liucb/journal-N.md`

### 8.3 禁止行为
- ❌ 假设测试通过而不实际运行
- ❌ 修改 `app/homework_pet.db` 生产数据库
- ❌ 跳过 Task 或合并多个 Task 一次性提交
- ❌ 修改 `requirements.txt` 添加新依赖（本项目不需要）
- ❌ 修改 `main.py` 末尾的 PORT 读取逻辑

### 8.4 卡住时的处理
- 测试失败: 先看错误信息，必要时 google/搜索
- 设计有疑问: 在 `journal-N.md` 写下问题，标记 `❓ PENDING QUESTION`，继续下一个 Task
- 验证命令报错: 检查 HOMEWORK_PET_DB_PATH 是否设置

## 9. 关键设计决策记录

### 为什么用 `sync_active_pet_mirror()` 兼容层？
- 50+ 处 `WHERE id=1` 全部重写风险高、回归测试量大
- 兼容层让旧代码读 `pet.exp` 仍能拿到激活宠物的 exp（镜像同步）
- 新代码直接操作 `pet_collection`，写完后调用 `sync_active_pet_mirror()`
- 缺点: 每次写操作多一次 UPDATE（性能可忽略，单用户场景）

### 为什么 `skin_id` 从 `parent_settings` 迁移到 `pet_collection`？
- 旧设计: 所有龙共享一个皮肤（全局 current_skin）
- 新设计: 每只宠物独立选皮（龙用 fire，猫用 default）
- 迁移: 把 `parent_settings.current_skin` 写入 `pet_collection.skin_id`（仅第一只龙）

### 为什么同物种不可重复领养？
- 用户决策: 避免收集爆炸，每物种唯一
- 简化数据: 物种 ID 即可作为宠物身份标识
- 扭蛋: 已领养的物种不参与抽选，避免重复
