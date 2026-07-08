---
name: trellis-start
description: 启动 Trellis 会话 - 加载项目上下文，确定下一个待执行 Task
version: 1.0.0
applies_to: [codex, claude-code, cursor, hermes]
---

# Trellis 会话启动

## 启动流程

每次会话开始时，按以下顺序加载上下文：

### Step 1: 读取项目核心文件

```bash
# 必读文件（按顺序）
1. .trellis/ONBOARDING.md              # 项目导航
2. .trellis/project-status.json         # 项目状态 (JSON)
3. CLAUDE.md                            # 项目约束
```

### Step 2: 读取当前任务 PRD

```bash
# 当前任务目录
.trellis/tasks/2026-07/v3.3-multi-pet/PRD.md
```

### Step 3: 读取任务清单

```bash
# 任务总览
.trellis/tasks/2026-07/v3.3-multi-pet/tasks/tasks-index.json
```

### Step 4: 读取详细实施计划

```bash
# 完整 Task 详情
docs/plans/2026-07-08-multi-pet-v3.3-plan.md
```

### Step 5: 读取最新 Journal

```bash
# 最新会话日志
.trellis/workspace/liucb/journal-N.md (N 为最大编号)
```

## 确定下一个 Task

1. 打开 `tasks-index.json`
2. 从 `tasks[]` 数组中找第一个 `status == "pending"` 的任务
3. 检查其 `depends_on` 列表，所有依赖必须 `status == "done"`
4. 该任务即为本次会话的执行目标

## 启动检查清单

- [ ] 当前分支: `feature/multi-pet-v3.3` (用 `git branch` 确认)
- [ ] 测试 DB 路径已设置: `HOMEWORK_PET_DB_PATH=backups/test_v33.db`
- [ ] 生产 DB 未被修改: `app/homework_pet.db` mtime 未变
- [ ] 依赖 Task 全部 done

## 启动后

读取 `.agents/skills/trellis-before-dev/SKILL.md` 开始开发。
