## Task: 闯关模块（Challenge Mode）(Phase: challenge-mode)

**时间**: 2026-07-29 ~ 2026-07-30
**Commit**: f591648
**变更**:
- 修改文件: app/database.py, app/main.py, app/templates/index.html
- 新增文件: scripts/generate_seed_questions_v22.py, scripts/generate_hard_questions.py
- 新增数据: docs/教材/markdown/ (80 MD files, 5.1MB), docs/教材/knowledge_graph.json
- 新增文档: .trellis/tasks/2026-07/challenge-mode/PRD.md

**验证结果**:
- [OK] 数据库 6 张新表创建成功
- [OK] 知识图谱 3492 个知识点生成并入库
- [OK] 基础题库 3492 题（seed_v22，全覆盖）
- [OK] 高难度题 350 题（hard_v1）
- [OK] 所有知识点都有题目覆盖（0 缺失）
- [OK] 6 个 API 端点全部测试通过
- [OK] 前端闯关 UI 完整
- [OK] 推送 main 触发 Railway 部署

**最终数据**:
- 知识点: 3492
- 题库: 3844 题（基础 3492 + 高难 350 + 教材 2）
- 语文: 1148 题（1-6年级全覆盖）
- 数学: 2598 题（1-6年级全覆盖）
- 英语: 98 题（1、3年级，其他年级无教材）

**遇到的问题**:
- markitdown 转换太慢，改用 PyMuPDF（56秒完成293个PDF）
- 部分PDF是图片型无法提取文本
- 模板格式化 bug（{a*b*10} 不是合法占位符），改用 lambda 函数
- 种子库和测试库混淆，需显式设置 HOMEWORK_PET_DB_PATH

**下一步**: 生产环境验证、英语高年级教材补充
