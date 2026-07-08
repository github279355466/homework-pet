---
name: trellis-finish-work
description: Task 完成后的收尾工作 - 更新任务状态、写 Journal、commit
version: 1.0.0
applies_to: [codex, claude-code, cursor, hermes]
---

# Task 完成收尾

## 收尾 6 步流程

### Step 1: 验证测试真实通过

```bash
# 必须实际运行，不能假设
HOMEWORK_PET_DB_PATH=backups/test_v33.db python scripts/test_xxx.py
# 输出必须包含 [OK] 或 PASS，不能是 FAIL
```

### Step 2: 更新 Task JSON

修改 `.trellis/tasks/2026-07/v3.3-multi-pet/tasks/task-{ID}.json`:

```json
{
  "id": "X.Y",
  "status": "done",
  "started_at": "2026-07-08T10:00:00",
  "completed_at": "2026-07-08T10:30:00",
  "commit_sha": "abc1234",
  "verification_output": "[OK] xxx test passed",
  "notes": "若有特殊情况写这里"
}
```

### Step 3: Commit 代码

```bash
git add <修改的文件>
git commit -m "<type>: <message>"
# type: feat / refactor / test / docs / chore / fix
```

### Step 4: 更新 tasks-index.json

修改 `.trellis/tasks/2026-07/v3.3-multi-pet/tasks/tasks-index.json`:
- 找到对应 task，把 `status` 从 `"pending"` 改为 `"done"`

### Step 5: 更新 Journal

在 `.trellis/workspace/liucb/journal-N.md` 末尾追加：

```markdown
## Task X.Y: <标题> (Phase N)

**时间**: 2026-07-08 10:00-10:30
**Commit**: abc1234
**变更**:
- 修改文件: app/main.py, app/database.py
- 新增文件: app/pet_helpers.py

**验证结果**:
- [OK] xxx 测试通过
- [OK] yyy 验证通过

**遇到的问题**:
- (若有) 描述问题和解决方式

**下一步**: Task X.Z
```

### Step 6: 更新 project-status.json

修改 `.trellis/project-status.json` 的 `current_task.completed_tasks` 字段 +1。

## 中断/暂停处理

如果 Task 未完成但需要中断:

```json
{
  "status": "in-progress",
  "notes": "已完成 Step 1-3，剩余 Step 4-5。下次从 Step 4 继续。"
}
```

## 紧急情况

### 测试 DB 损坏

```bash
# 从生产备份重新复制
cp backups/homework_pet_pre_v33_*.db backups/test_v33.db
# 重新运行所有已完成的 Task 的迁移
HOMEWORK_PET_DB_PATH=backups/test_v33.db python -c "from database import init_db; init_db()"
```

### 误改了生产 DB

```bash
# 立即从备份恢复
cp backups/homework_pet_pre_v33_*.db app/homework_pet.db
# 通知用户
```

### 提交了错误代码

```bash
# 回滚最后一次 commit (保留改动)
git reset HEAD~1
# 或彻底丢弃
git reset --hard HEAD~1
```

## 完成所有 Task 后

执行 Phase 7 收尾:
1. 合并 `feature/multi-pet-v3.3` 到 `main`
2. 推送 main 触发 Railway 部署
3. 生产环境冒烟测试
4. 标记 `tasks-index.json` 全部 done
5. 写最终 journal 总结
