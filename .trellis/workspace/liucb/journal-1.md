# 会话日志 - liucb

> **索引文件**: `.trellis/workspace/liucb/index.md`
> **开发者**: liucb (Hermes 设计 + Codex 实施)
> **项目**: homework-pet (作业小龙)

---

## Journal-1: v3.3 多宠物系统设计 + 交接 (2026-07-08)

### 会话概要
- **角色**: Hermes (架构师)
- **时段**: 2026-07-08
- **产出**: v3.3 多宠物系统完整设计方案 + 69 个 Task 详细实施计划 + Trellis 上下文
- **交接对象**: Codex (实施者)

### 完成工作

#### 1. 现状分析
- 探索 homework-pet 项目代码结构
- `app/main.py` 2141 行单文件后端，47 个 API 端点
- 50+ 处 `WHERE id=1` 硬编码引用单宠物
- `app/templates/index.html` 3243 行单页前端
- v3.2 皮肤系统: 5 套配色 (CSS 滤镜换色)

#### 2. 需求确认 (与用户多轮对话)
通过 `clarify` 工具确认了 7 个核心决策:
- **属性归属**: C 混合模式 (金币/成就共享 + 饱腹/心情/经验独立)
- **物种**: 不同物种 (7 种: 龙/猫/兔/狐/独角兽/凤凰/熊猫)
- **获取方式**: 多种组合 (商店 + 扭蛋 + 成就自动发放)
- **未激活**: 冻结 (不衰减不喂食)
- **属性差异**: 纯收集观赏，无加成
- **切换 UI**: 卡片列表轮播

二次确认 7 个开工前问题:
- 同物种不可重复领养
- 扭蛋已领养的不参与
- 第一版完整 7 种
- AI 生图 (FLUX 2 Klein 9B)
- 无领养上限
- 不做放生
- 成就解锁自动发放

#### 3. 设计方案产出
- 文档: `docs/multi-pet-design.md` (27KB)
- 包含: 架构图 / DDL / API 设计 / 迁移策略 / UI 草图 / 风险对策

#### 4. 实施计划产出
- 文档: `docs/plans/2026-07-08-multi-pet-v3.3-plan.md` (87KB)
- 69 个 Task，每个 Task 包含: 文件路径 / 完整代码 / 验证命令 / commit message
- 8 个阶段，预估 13 天

#### 5. Trellis 上下文初始化
为支持 Codex 接手开发，初始化了完整的 Trellis 项目结构:

```
.trellis/
├── ONBOARDING.md              # 项目导航
├── project-status.json         # 项目状态 (JSON)
├── tasks/2026-07/v3.3-multi-pet/
│   ├── PRD.md                  # 任务需求文档
│   └── tasks/
│       ├── tasks-index.json    # 69 个 Task 总览
│       └── task-0-1.json ... task-7-6.json  # 单 Task 元数据
├── workspace/liucb/
│   ├── index.md                # 个人会话索引
│   └── journal-1.md            # 本日志
├── spec/backend/               # 后端规范
└── spec/frontend/              # 前端规范

.agents/skills/
├── trellis-start/SKILL.md      # 会话启动流程
├── trellis-before-dev/SKILL.md # 开发前检查
└── trellis-finish-work/SKILL.md # 完成收尾流程
```

### 关键设计决策

#### 决策 1: 使用 `sync_active_pet_mirror()` 兼容层
- **原因**: 50+ 处 `WHERE id=1` 全部重写风险高、回归测试量大
- **方案**: 兼容层把激活宠物的属性同步到 `pet` 表镜像字段
- **效果**: 旧代码读 `pet.exp` 仍能拿到激活宠物的 exp，无需立刻重写
- **代价**: 每次写操作多一次 UPDATE (性能可忽略，单用户场景)

#### 决策 2: `skin_id` 从 `parent_settings` 迁移到 `pet_collection`
- **原因**: 旧设计所有龙共享一个皮肤 (全局 current_skin)
- **新设计**: 每只宠物独立选皮 (龙用 fire，猫用 default)
- **迁移**: 把 `parent_settings.current_skin` 写入 `pet_collection.skin_id` (仅第一只龙)

#### 决策 3: 同物种不可重复领养
- **原因**: 用户决策，避免收集爆炸
- **效果**: 物种 ID 可作为宠物身份标识
- **扭蛋**: 已领养的物种不参与抽选，避免重复

#### 决策 4: 冻结式切换 (不继续衰减)
- **原因**: 用户决策，简单且切回时恢复原样
- **实现**: `is_frozen=1` 的宠物调度器不处理
- **效果**: 切换后旧宠物属性完全保留

### 给 Codex 的交接说明

#### 启动指令
1. 读取 `.trellis/ONBOARDING.md`
2. 读取 `.trellis/project-status.json`
3. 读取 `.trellis/tasks/2026-07/v3.3-multi-pet/PRD.md`
4. 读取 `docs/plans/2026-07-08-multi-pet-v3.3-plan.md`
5. 从 Task 0.1 开始按顺序执行

#### 执行原则
- **TDD 循环**: 写测试 → 验证失败 → 实现 → 验证通过 → commit
- **真实验证**: 必须运行测试命令，禁止假设通过
- **DB 隔离**: 必须用 `HOMEWORK_PET_DB_PATH` 切换测试 DB
- **单 Task 提交**: 一个 Task 一个 commit，commit message 见计划
- **完成标记**: 每个 Task 完成后更新对应 `task-{ID}.json` 的 status=done

#### 关键文件位置
- 实施计划: `docs/plans/2026-07-08-multi-pet-v3.3-plan.md`
- 设计方案: `docs/multi-pet-design.md`
- 任务总览: `.trellis/tasks/2026-07/v3.3-multi-pet/tasks/tasks-index.json`
- 操作指南: `.agents/skills/trellis-{start,before-dev,finish-work}/SKILL.md`

#### 禁止行为
- ❌ 直接修改 `app/homework_pet.db` 生产数据库
- ❌ 跳过测试，直接假设通过
- ❌ 一次提交多个 Task
- ❌ 修改 `requirements.txt`
- ❌ 修改 `main.py` 末尾 PORT 读取逻辑

### 下一步

🟡 **等待 Codex 开始实施 Phase 0 Task 0.1**

第一个 Task: 备份生产数据库到 `backups/homework_pet_pre_v33_$(date).db`

---

*Journal 结束。Codex 接手后请在此文件继续追加 Journal-2, Journal-3...*


## Task CC-7: 聊天会话历史修复 (Companion Chat)

**时间**: 2026-07-29
**Commit**: (pending)
**变更**:
- 修改文件: app/main.py
- 新增: _chat_session_histories 内存缓存字典
- 新增: _MAX_HISTORY_MESSAGES = 50 限制
- 修改: chat_message 路由——加载历史、发送完整上下文给 Hermes、保存响应、自动修剪
- 修改: /api/chat/new-session 端点——新增服务端历史清除

**根因**: 每次调用 Hermes API 只发送 [system, current_user]，不发送完整对话历史。chatHistory 前端变量声明但未使用。

**验证结果**:
- [OK] Python AST 语法解析通过
- [OK] 11 项关键代码路径检查全部通过
- [OK] 前端 localStorage 持久化 session_id → 后端加载历史 → 发送完整上下文 数据流完整

**遇到的问题**: 无

**下一步**: 生产环境冒烟测试（Railway 部署后验证多轮对话记忆）
