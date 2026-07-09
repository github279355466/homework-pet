# 🚂 作业小龙 - Railway 重新部署备忘（v3.3 多宠物）

> **当前状态（2026-07-09 更新）**: ✅ 已成功部署到 `https://homepet.up.railway.app/`。
> 旧域名 `web-production-a9e82.up.railway.app` 已废弃（Railway 服务重建后子域名变更）。
> 本备忘保留作为后续如需再次重建 Railway 服务的参考手册。

---

## 0. 当前状态

| 项 | 状态 |
|----|------|
| 本地 commit | ✅ 全部已在 `origin/main` |
| GitHub 远端 | ✅ 代码 + 已迁移生产库 + 35 张立绘均已推送 |
| 生产 URL `https://homepet.up.railway.app/` | ✅ 200 OK，v3.3 多宠物系统已上线 |
| 旧 URL `https://web-production-a9e82.up.railway.app/` | ❌ 已废弃（Railway 服务重建，子域名变更） |

`Application not found` 是 Railway **平台网关**的报错（带 `request_id`），不是我们 app 自己的 404。
含义：该子域名对应的服务**已被删除 / 重命名 / 从未成功构建**，不是代码问题。

👉 **第一步永远是去 Railway 面板确认项目是否还在**（见 §2），而不是重新 push 代码。

---

## 1. 部署前必须知道的两个事实

### 事实 A：我们的生产库已经"自带多宠物数据"
仓库里提交的 `app/homework_pet.db` **已经是迁移过的状态**：
- `pet_collection` = `[紫宝 / dragon / 激活]`
- `pet[1]` = 紫宝 / coins=4075 / level=5
- 已含 v3.3 新表（`species_catalog` / `pet_collection` / `active_pet_id` 列）

所以**如果 Railway 直接用它（默认不挂 Volume），多宠物开箱即用，无需触发迁移**。

### 事实 B：迁移触发条件（见 `app/database.py:444`）
```python
if db_url != DEFAULT_DATABASE_URL or os.environ.get("MULTI_PET_MIGRATE_PROD") == "1":
    migrate_single_to_multi_pet(allow_production=(os.environ.get("MULTI_PET_MIGRATE_PROD") == "1"))
else:
    # 生产路径：跳过自动迁移
```
- 默认 Railway 部署用仓库里的 `homework_pet.db` = `DEFAULT_DATABASE_URL`，且没设 `MULTI_PET_MIGRATE_PROD` → **迁移跳过**（没问题，因为库已迁移过）。
- **只有当你让 Railway 用"另一份库"（挂 Volume、或换了空库）时，才需要 `MULTI_PET_MIGRATE_PROD=1` 来跑迁移。**

---

## 2. 重连 / 重建 Railway 服务（解决 "Application not found"）

1. 打开 https://railway.app → 用 GitHub 登录。
2. 在 Dashboard 看项目列表：
   - **项目还在** → 进入项目，看 Deployments 是否红/卡住；点 **Redeploy** 或重新连接仓库。
   - **项目没了 / 想新建** → `New Project` → `Deploy from GitHub repo` → 选 `github279355466/homework-pet`。
3. Railway 按 `requirements.txt`（已精简，仅 fastapi/uvicorn/jinja2/python-multipart/pytz）安装依赖。
4. 按 `Procfile` 启动 `python app/main.py`；`main.py` 末尾读 `PORT` 环境变量（`uvicorn.run(..., port=int(os.environ.get("PORT", 5000)))`）。
5. 部署完成后获得新域名 `https://<service-name>.up.railway.app`（若重建，子域名前缀会变，旧 `web-production-a9e82` 失效）。

---

## 3. 环境变量配置（核心）

在 Railway 项目 → **Variables** 中添加：

| 变量名 | 值 | 何时需要 | 说明 |
|--------|-----|----------|------|
| `PORT` | （不设） | 自动 | Railway 自动注入，无需手动设 |
| `MULTI_PET_MIGRATE_PROD` | `1` | **挂 Volume / 用非提交库时必设** | 让 `init_db` 对生产库执行多宠物迁移（幂等：已迁移则跳过） |
| `HOMEWORK_PET_DB_PATH` | `/app/data/homework_pet.db`（示例） | 挂 Volume 持久化时必设 | 指定 DB 落到 Volume 挂载路径，避免重部署丢数据 |
| `GACHA_COST` | `50` | 可选 | 单次扭蛋龙币价 |
| `SIGNIN_DAILY_COIN` | `5` | 可选 | 每日签到基础龙币 |
| `SIGNIN_PANDA_INTERVAL` | `7` | 可选 | 每 N 次签到发熊猫 |
| `SIGNIN_DUP_COIN` | `30` | 可选 | 熊猫已拥有时的补偿龙币 |
| `MULTI_PET_TEST` | （**切勿设**） | ❌ 生产禁用 | `1` 仅测试用，允许 `force_species` 指定扭蛋结果 |

### 两种典型部署的环境变量组合

**方案 A — 快速上线（用仓库提交的已迁移库，不挂 Volume）**
- 不挂 Volume、不设任何额外变量。
- ✅ 多宠物数据开箱即用（紫宝已在）。
- ⚠️ **每次 redeploy，容器文件系统回滚到提交快照**，新产生的数据（新领养的宠物、赚的龙币）会丢。
- 适合：先验证功能、临时演示。

**方案 B — 持久化（挂 Volume，推荐用于真实使用）**
- 在 Railway 添加 **Volume**，挂载到容器路径（如 `/app/data`）。
- 设 `HOMEWORK_PET_DB_PATH=/app/data/homework_pet.db` 和 `MULTI_PET_MIGRATE_PROD=1`。
- 首次启动：`init_db` 会对 Volume 里的库跑迁移。
  - 若 Volume 是**空库**：迁移读不到旧的 `pet` 表，会生成空 `pet_collection` → 需先把提交库拷进 Volume（见 §4）。
  - 若 Volume 里**已有迁移过的库**：迁移幂等跳过，正常。
- ✅ 重部署不丢数据。

---

## 4. 若用 Volume 且需保留真实数据（紫宝等）

Railway 无法直接读你本地提交的库作为 Volume。做法：
1. 本地先把已迁移库复制为可部署副本（仅一次）：
   ```bash
   cp app/homework_pet.db app/data/homework_pet.db   # 放进 Volume 挂载目录
   ```
2. 让 Railway 在构建/启动后该路径即为 Volume 持久层（Railway 的 Volume 是空挂载，需首次启动时从提交库 seed）：
   - 简单做法：保持**方案 A**先用着，把 `app/homework_pet.db` 当种子；后续再迁移到 Volume。
   - 或写启动脚本：若 `HOMEWORK_PET_DB_PATH` 指向的库不存在，则从仓库内备份 `cp` 一份再启动。

> 提示：`backups/pre_deploy_v331_20260709_143428.db` 是迁移前只读备份，万一需要回滚旧单宠物态可用。

---

## 5. 部署后验证（curl 自检）

部署成功后，用下列命令确认多宠物生效（替换成你的新域名）：

```bash
# 1. 首页健康检查（应 200）
curl -s -o /dev/null -w "%{http_code}\n" https://<你的新域名>.up.railway.app/

# 2. 多宠物 API（应返回 pet_collection，含紫宝）
curl -s https://<你的新域名>.up.railway.app/api/pets | head -c 400

# 3. 旧端点兼容（应 200）
curl -s -o /dev/null -w "%{http_code}\n" https://<你的新域名>.up.railway.app/api/pet/mood
```

- 若 `/api/pets` 返回空或 500 → 多半是 Volume 空库未 seed / 未设 `MULTI_PET_MIGRATE_PROD=1`，回看 §3。
- 若仍是 `Application not found` → 服务没起来，回看 §2。

---

## 6. 回滚

- 代码回滚：`git revert` 对应 commit 或 `git push` 旧 tag，Railway 自动重建。
- 数据回滚：把 `backups/pre_deploy_v331_20260709_143428.db` 覆盖回 `app/homework_pet.db` 并重新部署（会丢失 v3.3 后的新数据，谨慎）。

---

## 7. 一句话 checklist

- [ ] Railway 项目存在且已连接 `github279355466/homework-pet`
- [ ] 部署完成，新域名可访问（不再是 Application not found）
- [ ] `/api/pets` 返回含紫宝的 `pet_collection`
- [ ] 按持久化需求设好 `MULTI_PET_MIGRATE_PROD` / `HOMEWORK_PET_DB_PATH`
- [ ] **未**误设 `MULTI_PET_TEST=1`
- [ ] 家长端/孩子端分别可打开
