# 地图导航 — Railway 数据库持久化修复

> 任务 ID: railway-persistence-fix
> 状态: ✅ done (2026-07-23)
> 分支: main | 负责人: workbuddy
> 关联提交: e6c4474, 6a562c8, 4ad7446（完整链: 2c58a20→28adcca→4652c25→e6c4474→6a562c8→4ad7446）

---

## 1. 任务执行状况

| 项 | 状态 | 说明 |
|----|------|------|
| 路径缓存（一次解析） | done | 2c58a20 — 消除「导入时/请求时卷可写性不一致」 |
| 写探针重试 + 父目录确保 | done | 28adcca |
| 自愈守卫 + WAL 清洗 | done | 4652c25 — no such table: pet 的 500 消失 |
| 卷信任 + 紫宝种子库提交 | done | e6c4474 — 根因修复 + 数据可恢复 |
| ${VAR} 未展开模板守卫 | done | 6a562c8 — 防误填模板清库 |
| 注释修正（Railway 支持 ${VAR}） | done | 4ad7446 |

结论：生产 500（no such table: pet）已消除；重部署清库根因已修复；紫宝经种子库在卷首挂载时自动恢复。

## 2. 项目地图（数据库持久化相关）

```
app/database.py
├── get_database_url()       # 进程内一次性解析+缓存，优先级 HOMEWORK_PET_DB_PATH > RAILWAY_VOLUME_MOUNT_PATH > 镜像种子库
├── _resolve_database_url()  # 信任卷挂载点（os.path.isdir 兜底，不主动 makedirs）；检测 ${ 未展开模板→报警回退
├── _ensure_persistent_db()  # 卷库不存在/空壳→从 bundled 种子库拷贝（紫宝数据迁移）
├── ensure_db_ready()        # 请求入口自检 pet 表，缺失则 init_db() 重建
└── init_db()                # 16 张表 schema

app/homework_pet.db          # 仓库种子库（含紫宝 level5/exp8650/coins4080，115 tasks，13 achievements）
railway.json                 # builder: DOCKERFILE
```

## 3. 当前进度

- 代码修复：100%（已推送 main，Railway 自动重建）
- 数据恢复：紫宝已随种子库提交，待卷启用部署后自动恢复（用户已设 HOMEWORK_PET_DB_PATH=${RAILWAY_VOLUME_MOUNT_PATH}/homework_pet.db）
- 验证：待用户贴新部署日志确认 `[db] ✅ 持久化已启用` + 紫宝首屏

## 4. 硬性约束 / 教训（避免重复踩坑）

1. **禁止写探针判断卷可写性**：Railway 只读根 + 挂载时序会让 `_is_writable_dir` 误判→静默回退临时盘→清库。改信任 `RAILWAY_VOLUME_MOUNT_PATH`（`os.path.isdir` 兜底）。
2. **Railway 支持 `${VAR}` 变量引用**：`HOMEWORK_PET_DB_PATH=${RAILWAY_VOLUME_MOUNT_PATH}/homework_pet.db` 是官方推荐写法，Railway 注入前展开。仅当引用未解析（卷未就绪）才原样保留字面串——此时 `${ 守卫触发报警，不要静默写入坏路径。
3. **SQLite 持久化必须落 Volume**：默认 `DEFAULT_DATABASE_URL=/app/app/homework_pet.db` 是容器临时盘，重部署即重置。
4. **种子库提交**：运行时数据（紫宝）不会自动进仓库/卷，需显式 `wal_checkpoint` 后提交 `app/homework_pet.db` 作为镜像种子。
5. **路径解析只做一次并缓存**：避免「导入时」与「请求时」解析到不同库文件。
