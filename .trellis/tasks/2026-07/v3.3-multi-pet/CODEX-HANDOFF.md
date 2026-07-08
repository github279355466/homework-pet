# Codex 交接 Prompt - v3.3 多宠物系统实施

> **使用方法**: 在 Codex CLI 启动后，复制以下内容作为初始 prompt

---

## 角色与任务

你是 homework-pet (作业小龙) 项目的实施者，接手 Hermes 设计的 v3.3 多宠物系统改造任务。

**你的角色**: Codex (实施者)
**项目路径**: `D:/AIProject/workbuddy/homework-pet`
**分支**: `feature/multi-pet-v3.3`
**任务总数**: 69 个 Task (8 个阶段，预估 13 天)

## 启动步骤

请按以下顺序执行:

### 1. 加载 Trellis 上下文

读取以下文件了解项目状态:
- `.trellis/ONBOARDING.md` - 项目导航
- `.trellis/project-status.json` - 项目状态 JSON
- `.trellis/tasks/2026-07/v3.3-multi-pet/PRD.md` - 任务需求文档
- `.trellis/tasks/2026-07/v3.3-multi-pet/tasks/tasks-index.json` - 69 个 Task 总览

### 2. 阅读详细实施计划

- `docs/plans/2026-07-08-multi-pet-v3.3-plan.md` - 完整 Task 详情 (87KB)
- `docs/multi-pet-design.md` - 设计方案 (27KB)

### 3. 阅读操作规范

- `.agents/skills/trellis-start/SKILL.md` - 会话启动
- `.agents/skills/trellis-before-dev/SKILL.md` - 开发前检查
- `.agents/skills/trellis-finish-work/SKILL.md` - 完成收尾

### 4. 阅读 Journal

- `.trellis/workspace/liucb/journal-1.md` - Hermes 设计会话日志

## 执行原则

1. **严格按 Task ID 顺序执行**: 0.1 → 0.2 → ... → 7.6
2. **每个 Task 完整 TDD 循环**: 写测试 → 验证失败 → 实现 → 验证通过 → commit
3. **真实验证**: 必须运行验证命令，禁止假设通过
4. **DB 隔离**: 测试必须用 `HOMEWORK_PET_DB_PATH=backups/test_v33.db`
5. **单 Task 单 commit**: 一个 Task 一个 commit，commit message 见计划
6. **完成标记**: 每个 Task 完成后更新 `task-{ID}.json` 的 `status=done`

## 禁止行为

- ❌ 直接修改 `app/homework_pet.db` 生产数据库
- ❌ 跳过测试，直接假设通过
- ❌ 一次提交多个 Task
- ❌ 修改 `requirements.txt` 添加新依赖
- ❌ 修改 `main.py` 末尾 PORT 读取逻辑
- ❌ 在 main 分支直接开发 (必须用 feature/multi-pet-v3.3 分支)

## 关键约束 (来自 CLAUDE.md)

- 生产 DB `app/homework_pet.db` 是真实数据，禁止直接修改
- 测试必须用环境变量: `HOMEWORK_PET_DB_PATH=backups/test_xxx.db`
- 推送 `main` 分支即触发 Railway 自动部署
- `main.py` 末尾 `port=int(os.environ.get("PORT", 5000))` 必须保留
- 前端单页 `app/templates/index.html` (~3243 行)
- 后端单文件 `app/main.py` (~2141 行)
- 静态图片压缩到 256×256 PNG

## 第一个 Task

**Task 0.1: 备份生产数据库**

```bash
cd D:/AIProject/workbuddy/homework-pet
TS=$(date +%Y%m%d_%H%M%S)
cp app/homework_pet.db "backups/homework_pet_pre_v33_${TS}.db"
ls -la backups/homework_pet_pre_v33_*.db

# 创建测试 DB
cp app/homework_pet.db backups/test_v33.db
export HOMEWORK_PET_DB_PATH="D:/AIProject/workbuddy/homework-pet/backups/test_v33.db"
```

完成后:
1. 更新 `.trellis/tasks/2026-07/v3.3-multi-pet/tasks/task-0-1.json` 的 status=done
2. 在 `.trellis/workspace/liucb/journal-2.md` 记录会话日志
3. 继续 Task 0.2

## 卡住时

- 测试失败: 先看错误信息，必要时搜索
- 设计有疑问: 在 `journal-N.md` 写下问题，标记 `❓ PENDING QUESTION`，继续下一个 Task
- 验证命令报错: 检查 `HOMEWORK_PET_DB_PATH` 是否设置

## 预期产出

完成全部 69 个 Task 后:
- ✅ 代码: feature/multi-pet-v3.3 分支，所有 Task 已 commit
- ✅ 测试: 所有验证命令通过
- ✅ 文档: Trellis 任务状态全部 done，journal 完整
- ✅ 合并: feature 分支合并到 main 并推送
- ✅ 部署: Railway 自动部署成功，生产环境验证通过

---

## 给 Codex 的初始 prompt (复制以下)

```
我要在 homework-pet 项目实施 v3.3 多宠物系统改造任务。

请按以下顺序加载上下文:
1. 读 .trellis/ONBOARDING.md
2. 读 .trellis/project-status.json
3. 读 .trellis/tasks/2026-07/v3.3-multi-pet/PRD.md
4. 读 docs/plans/2026-07-08-multi-pet-v3.3-plan.md (详细 Task 计划)
5. 读 .agents/skills/trellis-start/SKILL.md
6. 读 .trellis/workspace/liucb/journal-1.md (Hermes 设计会话)

然后从 Task 0.1 开始按顺序执行。

每个 Task 必须遵循 TDD 循环:
- 写测试 → 验证失败 → 实现 → 验证通过 → commit

严格遵守:
- 测试必须用 HOMEWORK_PET_DB_PATH=backups/test_v33.db 隔离
- 禁止修改 app/homework_pet.db 生产数据库
- 单 Task 单 commit
- 完成后更新 .trellis/tasks/2026-07/v3.3-multi-pet/tasks/task-{ID}.json 的 status=done

开始执行 Task 0.1: 备份生产数据库。
```
