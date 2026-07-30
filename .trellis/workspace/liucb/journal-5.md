## Task: 闯关模块（Challenge Mode）(Phase: challenge-mode)

**时间**: 2026-07-29 ~ 2026-07-30
**Commit**: f591648, bc46071, 48ed96b
**变更**:
- 修改文件: app/database.py, app/main.py, app/templates/index.html, AGENTS.md, README.md, DEPLOY.md
- 新增文件: scripts/generate_seed_questions_v22.py, scripts/generate_hard_questions.py, scripts/generate_english_questions.py
- 新增数据: docs/教材/markdown/ (80 MD files, 5.1MB), docs/教材/knowledge_graph.json
- 新增文档: .trellis/tasks/2026-07/challenge-mode/PRD.md, docs/小学生AI闯关学习系统/ (5篇参考文档)

**Phase 1: 知识点体系完善**:
- 3,492 个知识点入库（语文/数学/英语 × 1-6年级）

**Phase 2: 程序化模板全覆盖**:
- generate_seed_questions_v22.py: 3,492 道基础题（lambda 函数修复 format bug）
- generate_hard_questions.py: 350 道高难度题

**Phase 3: 英语全覆盖**:
- generate_english_questions.py: 基于课程标准的英语出题
- 英语从 98 题（仅 G1/G3）-> 868 题（G1-G6 全覆盖）

**验证结果**:
- [OK] 数据库 6 张新表创建成功
- [OK] 知识图谱 3,492 个知识点生成并入库
- [OK] 基础题库 3,492 题（seed_v22，全覆盖）
- [OK] 高难度题 350 题（hard_v1）
- [OK] 英语题库 868 题（english_gen）
- [OK] 所有知识点都有题目覆盖（0 缺失）
- [OK] 6 个 API 端点全部测试通过
- [OK] 前端闯关 UI 完整
- [OK] 推送 main 触发 Railway 部署

**最终数据**:
- 知识点: 3,492
- 题库: 4,614 题（基础 3,492 + 高难 350 + 英语 868 + 教材 2 + 其他 2）
- 语文: 1,148 题（1-6年级全覆盖）
- 数学: 2,598 题（1-6年级全覆盖）
- 英语: 868 题（1-6年级全覆盖）
- 难度分布: diff1=1,779, diff2=1,715, diff3=350

**遇到的问题**:
- markitdown 转换太慢，改用 PyMuPDF（56秒完成293个PDF）
- 部分PDF是图片型无法提取文本
- 模板格式化 bug（{a*b*10} 不是合法占位符），改用 lambda 函数
- 种子库和测试库混淆，需显式设置 HOMEWORK_PET_DB_PATH
- 英语高年级无教材知识点，改用课程标准直接生成

**下一步**: 生产环境验证
