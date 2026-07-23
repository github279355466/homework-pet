# 会话日志 - liucb

> **索引文件**: `.trellis/workspace/liucb/index.md`
> **开发者**: liucb（协调）/ workbuddy（执行本次修复）
> **项目**: homework-pet (作业小龙)

---

## Journal-4: Railway 数据库持久化修复收尾 (2026-07-23)

### 会话概要
- **角色**: workbuddy 按 neat-freak 同步文档 + trellis-finish-work 收尾
- **时段**: 2026-07-23
- **任务**: 修复生产重部署清库（no such table: pet / 表重建），并同步项目知识库 + 更新 Trellis 任务状态
- **结果**: ✅ 代码修复已推送（e6c4474/6a562c8/4ad7446）；文档与 Trellis 上下文已同步

### 根因与修复
| 项 | 内容 |
|----|------|
| 现象 | 重部署后所有表内容丢失、重建为默认 作业小龙；此前有 no such table: pet 的 500 |
| 根因 | `database.py` 写探针 `_is_writable_dir` 在 Railway 只读根+挂载时序下误判卷不可写→静默回退容器临时盘 `/app/app/homework_pet.db`→自愈重建空库 |
| 修复 | 信任 `RAILWAY_VOLUME_MOUNT_PATH`（os.path.isdir 兜底，不主动 makedirs）；`HOMEWORK_PET_DB_PATH` 显式优先；提交紫宝种子库；加 `${` 未展开模板守卫 |
| 关键认知 | Railway 支持 `${VAR}` 引用展开（用户实测 `${RAILWAY_VOLUME_MOUNT_PATH}/homework_pet.db` 可用）；守卫仅在该引用未解析时触发 |

### 提交
- e6c4474：卷信任 + 紫宝种子库提交
- 6a562c8：${VAR} 未展开模板守卫
- 4ad7446：注释修正（Railway 支持 ${VAR}）

### 文档同步（neat-freak）
- `CLAUDE.md`：数据库段改为「仓库种子库 + Railway Volume 实时库」准确表述
- `DEPLOY.md`：修正 builder NIXPACKS→DOCKERFILE（2 处硬错误）；A.6 持久化改为「已实现」说明
- `.trellis/ONBOARDING.md`：更新日期 + 标记卷持久化已修复
- `.trellis/project-status.json`：last_updated→2026-07-23；current_task→railway-db-persistence(done)；新增 recent_completed

### 待你拍板（规范审计发现）
1. **AGENTS.md 与 CLAUDE.md 同源约束**：根 `AGENTS.md`(3121B) 非 `CLAUDE.md` 软链且内容分叉（含过时的 Companion Chat「当前进行中」段）。建议以 CLAUDE.md 为权威、合并有效差异后改为软链；Windows 软链需确认可行性。
2. **版本号冲突**：`project-status.json` 标 `v3.4.1`，而 `CLAUDE.md`/`README`/`MEMORY.md` 均 `v3.3.0`。需确认哪个为权威版本号（companion-chat 是否算 v3.4）。

### Trellis 任务状态
- 新建 `.trellis/tasks/2026-07/railway-persistence-fix/task.json`：status=done，commits=[e6c4474,6a562c8,4ad7446]
- 新建 `map-navigation.md`：项目地图 + 执行状况 + 进度 + 硬性约束
- `project-status.json.current_task` 已切换至本任务

### 下一步
1. 用户贴新部署日志，确认 `[db] ✅ 持久化已启用` + 紫宝首屏
2. 决策 AGENTS.md 同源 与 版本号冲突（待用户拍板）
3. （可选）沉淀「Railway + SQLite 卷持久化」为可复用 skill
