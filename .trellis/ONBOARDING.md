# Trellis 项目导航 - homework-pet (作业小龙)

> **版本**: v3.3.0 (已上线)
> **更新**: 2026-07-23
> **当前主线**: v3.3 多宠物系统已部署 (https://homepet.up.railway.app) + Railway 卷持久化已修复

---

## 项目概览

**作业小龙** 是一个面向小学生的作业打卡 + 宠物养成 Web 应用。
- **技术栈**: FastAPI 0.109 + SQLite + Jinja2 单页前端
- **生产环境**: Railway (https://homepet.up.railway.app/)
- **数据库**: `app/homework_pet.db` 是仓库**种子库**（含真实数据）；生产实时库在 Railway Volume（卷持久化，重部署不丢）
- **启动命令**: `python app/main.py` (端口由 PORT 环境变量决定)

## 项目结构

```
homework-pet/
├── app/
│   ├── main.py               # FastAPI 后端主程序 (~2141 行)
│   ├── database.py           # 数据库初始化 (14 张表)
│   ├── templates/index.html  # 前端单页 (~3243 行)
│   ├── static/               # 静态资源 (PNG 图片)
│   └── homework_pet.db       # 生产数据库 ⚠️ 不可直接修改
├── backups/                  # DB 备份 + 测试 DB
├── docs/                     # 设计文档 + 计划
│   ├── multi-pet-design.md   # v3.3 多宠物系统设计方案
│   └── plans/
│       └── 2026-07-08-multi-pet-v3.3-plan.md  # 详细实施计划
├── scripts/                  # 测试脚本
├── Procfile                  # Railway 启动: web: python app/main.py
├── railway.json
├── requirements.txt          # fastapi/uvicorn/jinja2/python-multipart/pytz
├── CLAUDE.md                 # Agent 项目指南
├── DEPLOY.md                 # 部署文档
├── README.md
└── .trellis/                 # Trellis 多 agent 协作上下文
```

## 关键约束 (来自 CLAUDE.md)

1. **生产 DB 不可直接修改**: 仓库内 `app/homework_pet.db` 是种子库；生产实时库在 Railway Volume，经 `HOMEWORK_PET_DB_PATH` 指定
   - 写操作测试必须用环境变量: `HOMEWORK_PET_DB_PATH=backups/test_xxx.db`
2. **部署机制**: 推送 `main` 分支即触发 Railway 自动构建
3. **端口动态读取**: `main.py` 末尾必须保留 `port=int(os.environ.get("PORT", 5000))`
4. **单文件后端**: `main.py` 当前 ~2141 行，所有 API 集中此文件
5. **单页前端**: `templates/index.html` ~3243 行，所有 UI 在一个文件
6. **静态图片压缩**: PNG 256×256，避免 Railway 上传超限

## 当前任务状态

### v3.3 多宠物系统 (2026-07-08 启动)

**分支**: 已合并到 `main` (feature/multi-pet-v3.3 分支已删除)

**目标**: 增加多宠物领养/切换功能
- 混合模式: 金币/成就共享，饱腹/心情/经验/亲密度独立
- 7 种物种: 龙/猫/兔/狐/独角兽/凤凰/熊猫
- 获取途径: 商店购买 + 扭蛋 + 成就自动发放
- 冻结式切换: 未激活宠物不衰减
- 同物种不可重复领养
- 卡片轮播 UI

**详细文档**:
- 设计方案: `docs/multi-pet-design.md`
- 实施计划: `docs/plans/2026-07-08-multi-pet-v3.3-plan.md` (69 个 Task)
- Trellis 任务卡: `.trellis/tasks/2026-07/v3.3-multi-pet/`

**进度**: ✅ 全部完成，已部署到 https://homepet.up.railway.app

## 多 Agent 协作约定

本项目的多宠物改造计划由 Hermes 设计，**实施工作交接给 Codex** 执行。

| Agent | 角色 | 工作内容 |
|---|---|---|
| Hermes | 架构师 + 计划设计 | 设计方案、编写计划、Trellis 上下文维护 |
| Codex | 实施者 | 按 Task 顺序编码 + 测试 + 提交 |

### Codex 工作流程

1. **会话启动**: 读取本文件 + `.trellis/project-status.json` + 当前任务 PRD
2. **任务执行**: 从 `.trellis/tasks/2026-07/v3.3-multi-pet/tasks/` 按 ID 顺序取 Task
3. **每个 Task**: TDD 循环 (写测试 -> 验证失败 -> 实现 -> 验证通过 -> commit)
4. **完成标记**: 在 task.json 写入 status=done + commit SHA
5. **会话结束**: 更新 `.trellis/workspace/liucb/journal-N.md`

## 下一动作

✅ **v3.3 多宠物系统已上线** https://homepet.up.railway.app

下一步待定（可选方向）：
- 用户反馈收集 + 缺陷修复
- 新物种/新皮肤扩展
- ✅ 数据持久化：Railway Volume 持久化已实现并修复（重部署不再清库；紫宝经种子库自动恢复）
- 性能监控接入
