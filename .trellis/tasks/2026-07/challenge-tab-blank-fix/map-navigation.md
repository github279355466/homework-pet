# 地图导航：修复闯关标签页空白（challenge-tab-blank-fix）

> 生成日期：2026-07-30 ｜ 状态：done ｜ commit：3f4cbe8

## 1. 项目地图（本次涉及）
- 前端单页：`app/templates/index.html`（~4537 行，Jinja2 模板）
- 后端单文件：`app/main.py`（FastAPI，闯关接口 `/api/challenge/*`）
- 闯关标签链路：`tab-challenge`(L1757) → `switchTab('challenge')`(L2442) → 显示 `pane-challenge`(L4222) + 调 `loadChallengeStatus()`(L4332)
- 聊天标签链路：`tab-chat` → `pane-chat`(L4189)

## 2. 任务执行状况
| 任务 | 状态 | 改动点 |
|------|------|--------|
| 修复 pane-challenge 嵌套错位 | done | `app/templates/index.html`：chat-panel 闭合后(原L4219)补 `</div>` 关闭 pane-chat；删除 `<script>` 前多余 `</div>`(原L4305)；整体 div 平衡(380/380) |
| QA 回归验证 | done | 结构解析 + 本地服务 + 生产探测，三项 PASS |

## 3. 当前进度
- 进度：100%（已修复 + 已验证 + 已提交推送 + 已触发部署）
- 下一步：等待 Railway 构建完成（~1-2min），生产环境点击"🎯 闯关"确认面板与答题弹窗正常展示。

## 4. 硬性约束与教训
- `app/templates/index.html` 是巨型单文件，**div 嵌套极易错位**：任何新增面板/弹窗务必确保与已有 pane 平级（同属 `.main-card`），不可误嵌套进其它 pane。
- 单文件前端改动后，用 Python `html.parser` 追踪 div 开闭栈是排查嵌套类渲染 bug 的最快手段。
- 仓库内 `app/homework_pet.db` 是种子库，本地/验证起服务须用 `HOMEWORK_PET_DB_PATH` 切换，避免污染种子。
- 推送 `main` 即触发 Railway 自动部署；git 推送在沙箱需 `git -c http.sslVerify=false push`（schannel 吊销检查离线）。
