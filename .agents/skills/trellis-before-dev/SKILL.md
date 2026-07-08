---
name: trellis-before-dev
description: Task 开发前的准备工作 - TDD 设置、DB 隔离、分支确认
version: 1.0.0
applies_to: [codex, claude-code, cursor, hermes]
---

# Task 开发前准备

## 开发前 5 步检查

### Step 1: 确认分支

```bash
git branch --show-current
# 必须: feature/multi-pet-v3.3
# 如果不是: git checkout feature/multi-pet-v3.3
```

### Step 2: 确认测试 DB 路径

```bash
echo $HOMEWORK_PET_DB_PATH
# 必须: D:/AIProject/workbuddy/homework-pet/backups/test_v33.db
# 如果未设置:
export HOMEWORK_PET_DB_PATH="D:/AIProject/workbuddy/homework-pet/backups/test_v33.db"

# 如果测试 DB 不存在，从备份复制:
cp backups/homework_pet_pre_v33_*.db backups/test_v33.db
```

### Step 3: 确认生产 DB 未被修改

```bash
# 生产 DB mtime 应早于今天
ls -la app/homework_pet.db
# 如果 mtime 是今天: ❌ 危险! 检查是否误操作
```

### Step 4: 读取当前 Task 详情

```bash
# 读取 task JSON
cat .trellis/tasks/2026-07/v3.3-multi-pet/tasks/task-{ID}.json

# 读取实施计划中对应 Task 章节
grep -n "Task {ID}" docs/plans/2026-07-08-multi-pet-v3.3-plan.md
```

### Step 5: 确认依赖已完成

```bash
# 读取所有 depends_on 的 task JSON，确认 status == "done"
for dep in $(cat .trellis/tasks/2026-07/v3.3-multi-pet/tasks/task-{ID}.json | jq -r '.depends_on[]'); do
  echo "Dependency: $dep"
  cat .trellis/tasks/2026-07/v3.3-multi-pet/tasks/task-${dep//./-}.json | jq -r '.status'
done
```

## TDD 开发循环

每个 Task 遵循以下循环：

```
1. 写测试 (test script)
2. 运行测试 → 验证失败 (red)
3. 实现/修改代码
4. 运行测试 → 验证通过 (green)
5. git add + git commit
6. 更新 task JSON (status=done, commit_sha)
7. 更新 journal
```

## 禁止行为

- ❌ 直接修改 `app/homework_pet.db`
- ❌ 跳过测试，直接假设通过
- ❌ 一次提交多个 Task
- ❌ 修改 `requirements.txt`
- ❌ 修改 `main.py` 末尾 PORT 读取逻辑
- ❌ 在 main 分支直接开发

## 完成后

读取 `.agents/skills/trellis-finish-work/SKILL.md` 完成收尾。
