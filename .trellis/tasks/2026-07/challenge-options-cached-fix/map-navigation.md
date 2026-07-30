# 地图导航：闯关选项空白回归（challenge-options-cached-fix）

> 生成日期：2026-07-30 ｜ 状态：done ｜ commit：7aa9b9c（待部署）

## 1. 项目地图（本次涉及）
- 后端：`app/main.py`
  - `_generate_questions_for_level`（~L3046）：缓存读路径（L3054-3059）直接返回 DB 行；非缓存读路径对 question_bank 调 `json.loads(q['options'])`（L3076）
  - `INSERT INTO challenge_questions`（~L3095）：用 `json.dumps(q['options'])` 写库
  - `/api/challenge/start`（~L3349）：透传 `q['options']` 到 safe_questions
- 前端：`app/templates/index.html`
  - `renderChallengeQuestion`（~L4490）：`q.options.forEach(...)` 渲染按钮；`opt.replace(/^[A-D]\.\s*/, '')` 处理文本
  - `startChallenge`（~L4458）：调用 `/api/challenge/start` 获取 questions

## 2. 任务执行状况
| 任务 | 状态 | 改动点 |
|------|------|--------|
| 根因定位 | done | 缓存读路径未解码 options → 前端 .forEach 抛 TypeError |
| 后端修复 | pending | `app/main.py` 缓存读路径加 `json.loads(d['options'])` |
| 回归测试 | pending | 隔离库调用 `_generate_questions_for_level`，断言每题 options 是 list[4] |

## 3. 当前进度
- 进度：50%（根因已定位，实现+测试待做）
- 下一步：改 `app/main.py` → 隔离库回归测试 → 提交 → 部署前与用户确认。

## 4. 硬性约束与教训
- **类型对称是底线**：JSON 写入数据库的字段，读取时必须同步解码。`_generate_questions_for_level` 把 question_bank（明文 JSON 字段）跟 challenge_questions（自管）混用，必须保证两条读路径返回类型一致。
- **回归 bug 的"潜伏期"**：缓存表原本存满 ≥10 行才触发该分支，意味着功能首次上线时通常不会立即暴露。生产/测试环境应在 lint/冒烟里加入"返回类型断言"或 E2E，避免久放置后突然故障。
- **不引入前端兜底**：不修改前端对字符串 options 的兼容，避免掩盖后端类型 bug（用户明确要求"避免引入新的副作用"）。
- 提交时排除 `app/homework_pet.db`（WAL 残留）、`nul`（Windows 设备名）、未跟踪的 `xiaozhi-skills-package/` 等非相关目录。
