# 地图导航：修复闯关状态误判（challenge-state-fix）

> 生成日期：2026-07-30 ｜ 状态：done ｜ commit：待补

## 1. 项目地图（本次涉及）
- 后端：`app/main.py`
  - `GET /api/challenge/status`（~L3280）：返回各科目今日闯关状态 `today_done`
  - `POST /api/challenge/start`（~L3349）：插入 `challenge_daily_progress` 行（completed=0）
  - `POST /api/challenge/complete`（~L3452）：通关后把该行 `completed` 更新为 1
  - `_check_daily_challenge`（~L2970）：正确判断 `completed==1`（守卫基准）
- 前端：`app/templates/index.html`
  - `loadChallengeStatus()`（~L4332）：拉取状态，按 `today_done` 给科目卡片加 `done` 类
  - `startChallenge()`（~L4364）：检查卡片 `done` 类来拦截重复进入
  - `closeChallengeModal()`（~L4520）：关闭答题弹窗

## 2. 任务执行状况
| 任务 | 状态 | 改动点 |
|------|------|--------|
| 修复 today_done 误判 | done | `app/main.py` L3307：`today_done = daily is not None and daily['completed'] == 1` |
| 关闭弹窗即时刷新 | done | `app/templates/index.html` `closeChallengeModal()` 调用 `loadChallengeStatus()` |
| QA 回归验证 | done | 隔离测试库端到端：开局→false，完成→true；div 平衡 |

## 3. 当前进度
- 进度：100%（修复 + 验证 + trellis 落盘完成）
- 下一步：提交并推送 main 触发 Railway 部署；生产环境验证"未完成关闭可再次闯关"。

## 4. 硬性约束与教训
- 状态判定必须以"数据值"为准（completed==1），不能仅以"记录是否存在"为准——存在≠完成。
- 后端 start 守卫 `_check_daily_challenge` 与 status 接口的 today_done 必须保持同一判定口径，否则出现"能进但不能进"的不一致。
- 前端"进行中"态（completed=0 但已有记录）应允许重新进入，仅"已完成"(completed=1)才禁用。
- 提交时排除 `app/homework_pet.db`（验证起服务产生的 WAL 残留）与 `nul`（Windows 设备名垃圾文件）。
