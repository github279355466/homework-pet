# 地图导航：家长模式闯关重置（challenge-parent-reset）

> 生成日期：2026-07-30 ｜ 状态：done ｜ commit：e95d2ba（已部署 Railway）

## 1. 项目地图（本次涉及）
- 后端：`app/main.py`
  - `POST /api/parent/reset-data`（~L1470）：既有家长密码守卫基准（读 `parent_settings.parent_password`，默认 '1234'）
  - **新增** `POST /api/parent/reset-challenge`（计划插在 reset-data 之后）：复刻密码守卫；`UPDATE challenge_daily_progress SET completed=0 WHERE challenge_date=today AND completed=1`
  - `GET /api/challenge/status`（~L3280）：返回 `today_done` / `today_completed`，前端重置后用它刷新
  - `GET /api/challenge/history`（~L3548）：返回已完成关卡 + `wrong_stats`，只读
  - `GET /api/challenge/wrong-questions`（~L3575）：返回错题列表，只读
- 前端：`app/templates/index.html`（家长面板 `{% if role == 'parent' %}`，~L1949）
  - 新增两个 `.parent-section`：「🏆 闯关记录」(`#parentChallengeStatus` + `#parentChallengeHistory`) 与「🎮 闯关重置」按钮
  - 新增 JS：`resetTodayChallenge()` / `loadParentChallengeStatus()` / `loadParentChallengeHistory()`
  - 触发：DOMContentLoaded 中 `if (currentRole === 'parent')` 调两个 load 函数

## 2. 任务执行状况
| 任务 | 状态 | 改动点 |
|------|------|--------|
| 后端 reset-challenge 端点 | pending | `app/main.py` 新增 `POST /api/parent/reset-challenge` |
| 前端家长面板：闯关记录 | pending | `#parentChallengeHistory` + `loadParentChallengeHistory()` |
| 前端家长面板：闯关重置按钮 | pending | `resetTodayChallenge()` + `loadParentChallengeStatus()` |
| QA 回归验证 | pending | 隔离测试库：完成→reset→completed 翻 0、历史/错题不变；div 平衡 |

## 3. 当前进度
- 进度：100%（实现 + 验证 + 部署完成）
- 已部署：push main（`3f4cbe8..2d95abe`）触发 Railway 自动构建；生产探测 `POST /api/parent/reset-challenge`（错误密码）→ 200 `{"success":false,"message":"密码错误"}` 确认新端点已上线。
- 数据安全已在隔离测试库端到端验证：重置仅翻转 `challenge_daily_progress.completed`，关卡/错题行数不变。

## 4. 硬性约束与教训
- 重置**只动** `challenge_daily_progress.completed`，严禁 touching `challenge_levels` / `challenge_wrong_questions` / `challenge_questions`（需求 #3 数据安全红线）。
- 复用既有家长密码守卫（`parent_settings.parent_password`，默认 '1234'），与 `reset-data`/`change-password` 口径一致。
- 前端触达：家长面板为服务端按 `role=='parent'` 渲染，进入靠 `verifyParentPassword()` → `location.href='/?role=parent'` 整页刷新；因此加载钩子放在 `DOMContentLoaded` 的 `currentRole==='parent'` 分支即可，无需新增路由。
- 提交时排除 `app/homework_pet.db`（WAL 残留）与 `nul`（Windows 设备名垃圾文件）。
- 部署：push main 触发 Railway 自动部署；生产发布前必须再次与用户确认（影响真实用户）。
