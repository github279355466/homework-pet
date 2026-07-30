## Task: 闯关模块（Challenge Mode）(Phase: challenge-mode)

**时间**: 2026-07-29 ~ 2026-07-30
**Commit**: (待 commit)
**变更**:
- 修改文件: app/database.py, app/main.py, app/templates/index.html
- 新增文件: scripts/convert_textbooks_fast.py, scripts/convert_textbooks.py, scripts/generate_seed_questions.py, scripts/generate_question_bank.py
- 新增文档: .trellis/tasks/2026-07/challenge-mode/PRD.md, .trellis/tasks/2026-07/challenge-mode/tasks-index.json
- 新增数据: docs/教材/markdown/ (80 个 MD 文件, 5.1 MB), docs/教材/knowledge_graph.json

**验证结果**:
- [OK] 数据库 6 张新表创建成功
- [OK] 知识图谱 7139 个知识点生成，3490 个入库（去重后）
- [OK] 基础题库 6010 题入库（本地种子 + API 模板）
- [OK] 6 个 API 端点全部测试通过
- [OK] 前端闯关 UI 完整（学科卡片、答题界面、通关动画、宝箱系统）
- [OK] 端到端测试通过（开始→答题→结算→状态更新）

**遇到的问题**:
- markitdown 转换 293 个 PDF 太慢（5 分钟只完成 8 个），改用 PyMuPDF 并行处理（56 秒完成全部）
- 部分 PDF 是图片型，无法提取文本（0 字节），但不影响系统运行（有降级题库）
- AI 出题在本地测试环境因 Hermes API 未配置而降级到预设题库，生产环境会正常调用

**下一步**: 推送到 main 分支触发 Railway 部署，生产环境执行 generate_question_bank.py 生成 API 题库
