# 会话日志 - liucb

> **索引文件**: `.trellis/workspace/liucb/index.md`
> **开发者**: liucb (Hermes 设计 + Codex 实施 + Hermes 验证)
> **项目**: homework-pet (作业小龙)

---

## Journal-2: v3.3 验证测试 (2026-07-09)

### 会话概要
- **角色**: Hermes (验证者)
- **时段**: 2026-07-09
- **任务**: 对 Codex 完成的 v3.3 多宠物系统进行验证测试
- **结果**: 🟡 **核心功能通过验证，发现 2 个真实 BUG 待修复**

### Codex 完成情况

Codex 完成了 5 个 commit（354ff55..7fbcc97），覆盖 Phase 1-5 + 收尾：
- `9b5f82f` feat: v3.3 multi-pet phase1+2 - 多宠物架构(镜像兼容层)+5新API
- `5597c56` v3.3 multi-pet phase3 acquisition: 领养商店/扭蛋机/签到发宠
- `8c78803` feat: v3.3 multi-pet phase4 frontend - 前端多宠物化
- `a010891` v3.3 phase5: 35 species portraits + design docs
- `ab0f0bb` fix: answer_math_quiz 龙币流水双写
- `7fbcc97` chore: v3.3 收尾 - 历史脚本归档/依赖精简/提交已迁移生产库

### 验证测试执行结果

| Phase | 测试项 | 通过 | 失败 | 真实BUG |
|---|---|---|---|---|
| Phase 1 迁移幂等 | 10 | 10 | 0 | ✅ 全通过 |
| Phase 2+3 API | 33 | 31 | 2 | 1 测试断言错 + 1 真 BUG |
| Phase 4 前端 UI | 7 | 7 | 0 | ✅ 全通过 |
| Phase 5 图片资源 | 3 | 2 | 1 | 1 真 BUG (尺寸未压缩) |
| Phase 6 冻结切换 | 4 | 4 | 0 | ✅ 全通过 |
| 回归测试 | 10 | 7 | 3 | 3 测试断言错 (代码无 bug) |
| **合计** | **67** | **61** | **6** | **2 真 BUG + 4 测试 bug** |

### ✅ 通过验证的核心功能

1. **数据库迁移幂等**: 多次 init_db 不创建新宠物，species_catalog 保持 7 条
2. **数据完整**: 旧龙"紫宝"的 exp/coins/name 完整迁移到 pet_collection
3. **镜像兼容层**: `pet.exp == pet_collection.exp`，旧 `/api/pet` 仍返回正确数据
4. **金币全局共享**: `add_coins()` 操作 pet 表，所有宠物共用
5. **exp 个体独立**: 完成作业后 exp 写入 pet_collection，coins 写入 pet
6. **冻结切换**: 切换 A→B 时 A 的 is_frozen=1，调度器只衰减 B
7. **切回恢复**: 切回 A 时 A 的属性保持切换时的值
8. **多宠物 API**: GET /api/pets、POST /api/pets/switch、POST /api/pets/adopt 工作正常
9. **同物种不可重复**: 重复 adopt cat 返回 ALREADY_OWNED
10. **扭蛋抽选**: 扣金币 + 新物种入账（重复时补偿龙币）
11. **前端 UI**: 轮播/领养/扭蛋/签到组件齐全
12. **35 张图片**: 7 物种 × 5 阶段全部存在
13. **调度器衰减**: 激活宠物 hunger/mood/bond 按时间衰减
14. **旧版流程**: 主页加载、作业完成、皮肤系统、父母设置正常

### ❌ 发现的真实 BUG

#### BUG #1: GET /api/pets/gacha/config 未实现 (Task 3.6 遗漏)

**文件**: `app/main.py`
**现象**: `GET /api/pets/gacha/config` 返回 404 {"detail":"Not Found"}
**影响**: 前端扭蛋机弹窗无法展示概率（用户体验降级，但扭蛋抽取本身可用）
**对照计划**: Task 3.6 明确要求实现此接口
**修复建议**: 在 `app/main.py` line 2380 附近追加：
```python
@app.get("/api/pets/gacha/config")
async def get_gacha_config():
    """返回扭蛋池配置（排除已领养物种）"""
    conn = get_db_connection()
    owned = {r['species_id'] for r in conn.execute("SELECT species_id FROM pet_collection").fetchall()}
    pool = conn.execute("SELECT id,name,icon,base_price,rarity FROM species_catalog WHERE acquisition_methods LIKE '%gacha%' AND enabled=1 ORDER BY sort_order").fetchall()
    conn.close()
    return {
        "cost": GACHA_SINGLE_COST,
        "dupe_rate": GACHA_DUPE_RATE,
        "pool": [{"species_id": r['id'], "name": r['name'], "icon": r['icon'], 
                  "rarity": r['rarity'], "base_price": r['base_price'],
                  "weight": GACHA_POOL.get(r['id'], 0.1), "owned": r['id'] in owned} 
                 for r in pool]
    }
```

#### BUG #2: GET /api/pets/species 漏掉 owned 字段 (Task 3.4 实现不完整)

**文件**: `app/main.py:2352-2374`
**现象**: `/api/pets/species` 返回的 species 数组中没有 `owned` 字段
**影响**: 前端领养中心无法判断哪些物种已领养（无法显示 ✅ 标记）
**对照计划**: Task 3.4 计划中明确要求标记 owned
**修复建议**: 在 line 2373 前补 owned 计算：
```python
@app.get("/api/pets/species")
async def get_pet_species():
    """获取物种目录（enabled=1）。"""
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM species_catalog WHERE enabled = 1 ORDER BY sort_order").fetchall()
    owned = {r['species_id'] for r in conn.execute("SELECT species_id FROM pet_collection").fetchall()}  # ⭐ 补这一行
    conn.close()
    species = []
    for r in rows:
        d = dict(r)
        species.append({
            ...其他字段...
            'owned': d['id'] in owned,  # ⭐ 补这一行
        })
    return {"species": species}
```

### ⚠️ 规范性问题（非阻塞）

#### 问题 A: 图片未压缩到 256×256 (违反 CLAUDE.md 约束)

**现象**: 35 张图片均为 1024×1024 PNG，平均 1MB/张，总计 ~38MB
**约束**: CLAUDE.md 明确要求"静态图片压缩到 256×256 PNG"
**影响**: 
- Railway 部署包体积膨胀（首次部署慢）
- 移动端加载流量大
**建议**: 部署前用 PIL 批量压缩：
```python
from PIL import Image
from pathlib import Path
for f in Path("app/static/species").rglob("stage-*.png"):
    with Image.open(f) as img:
        img.resize((256, 256), Image.LANCZOS).save(f, optimize=True)
```

#### 问题 B: 生产库已被 Codex 直接迁移

**现象**: `app/homework_pet.db` 已被修改，pet_collection=1, species_catalog=7, active_pet_id=1
**约束**: PRD 明确禁止"直接修改 app/homework_pet.db 生产数据库"
**影响**: 已成既成事实，无法回退（好在迁移幂等，数据无损）
**建议**: 后续开发严格用 `HOMEWORK_PET_DB_PATH=backups/test_xxx.db` 隔离

### 测试脚本自身的 bug（不计入代码 BUG）

Codex 写的 `app/tests/test_phase3_acquire.py` 末尾 4 个 FAIL 是测试断言写反：
```python
# 错误（假设生产库没迁移）
check("生产库 pet 无 last_signin_date", "last_signin_date" not in prod_cols, str(prod_cols))
# 应改为
check("生产库 pet 含 last_signin_date", "last_signin_date" in prod_cols)
```
这 4 个断言方向写反，实际代码是对的。

### 关键验证证据

```
生产库 pet_collection 第一行:
  id=1, species=dragon, name=紫宝, exp=8650, coins=4075, is_frozen=0

迁移幂等性（运行 init_db 两次）:
  before: pet_collection=1, species=7, active_pet_id=1
  after 1st: pet_collection=1, species=7, active_pet_id=1
  after 2nd: pet_collection=1, species=7, active_pet_id=1 ✅

冻结切换验证:
  切换 dragon -> cat: dragon.is_frozen=1, cat.is_frozen=0
  调度器运行 5 小时衰减: cat.hunger 80->72, mood 80->75
  dragon 属性保持不变 ✅
```

### 下一步建议

1. **修复 BUG #1** (gacha/config): 5 分钟，前端扭蛋概率展示依赖此
2. **修复 BUG #2** (species owned): 2 分钟，前端领养中心标记依赖此
3. **压缩图片**: 10 分钟，35 张 1024→256，部署前必做
4. **修复测试脚本**: 把 `test_phase3_acquire.py` 末尾 4 个反方向断言改对
5. **更新 task JSON**: 69 个 task 状态都没更新为 done（Codex 没遵守收尾流程）
6. **生产环境冒烟**: 修复 + 压缩后推 main，在 Railway 验证

### 给 Codex 的修复指令

```
请修复以下 2 个 BUG，每个修复单独 commit：

BUG #1: GET /api/pets/gacha/config 未实现
- 文件: app/main.py (在 GACHA_POOL 定义附近，约 line 2380)
- 实现: 返回 {cost, dupe_rate, pool[]}，pool 排除已领养物种

BUG #2: GET /api/pets/species 漏掉 owned 字段
- 文件: app/main.py line 2352-2374
- 修复: 补 owned 集合计算 + 在返回字典加 'owned' 字段

修复后运行:
  HOMEWORK_PET_DB_PATH=backups/test_verify.db python -c "
  from main import app; from fastapi.testclient import TestClient; c=TestClient(app)
  print(c.get('/api/pets/gacha/config').json())
  print([s.get('owned') for s in c.get('/api/pets/species').json()['species']])
  "

完成后压缩图片:
  python -c "
  from PIL import Image; from pathlib import Path
  for f in Path('app/static/species').rglob('stage-*.png'):
      img=Image.open(f); img.resize((256,256),Image.LANCZOS).save(f,optimize=True)
  "
```

### Journal 结束

✅ 核心架构验证通过，多宠物系统可工作
🟡 2 个非阻塞 BUG 待修复（不影响主流程）
🟡 35 张图片待压缩（部署前必做）

下一步：用户决定是否让 Codex 修复 BUG，或直接部署。
