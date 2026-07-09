# scripts/ — 开发 & 测试历史脚本（不参与运行时）

> ⚠️ **本目录下的文件都不是运行时的一部分。** 应用实际只加载 `app/main.py` + `app/database.py`。
> 这些脚本是项目迭代过程中（v2.0 → v3.1）留下来的**一次性开发/验证产物**，仅作历史参考，请勿在生产中依赖。

## 文件清单与用途

| 文件 | 性质 | 用途 |
|------|------|------|
| `main_new.py` | 开发稿（已废弃） | 某次重构尝试的完整副本，最终逻辑已合入 `app/main.py`，与现版本不同步，**不要再改它** |
| `implement_features.py` | 功能实现片段 | v3.1 部分功能的实现草稿，已被 `app/main.py` 吸收 |
| `fix_main.py` | 修复脚本 | 历史上临时修补 `main.py` 的脚本，修补已落盘，本文件仅留痕 |
| `test_comprehensive.py` | 集成测试 | 通过 `requests` 打本地 5000 端口做端到端校验 |
| `test_data_chain.py` | 数据链测试 | 校验「作业→经验→龙币→进化→成就」全链路 |
| `test_safe_regression.py` | 回归测试 | 用 `fastapi.testclient.TestClient` 直接 import `main.app` 做安全/回归校验 |

## 如果要重新运行这些脚本

它们用的是**相对于 `app/` 目录的裸导入**（`from database import ...` / `from main import ...`），
移出 `app/` 后直接运行会 `ModuleNotFoundError`。重跑前需把 `app/` 加入路径，例如：

```bash
cd /d/AIProject/workbuddy/homework-pet
PYTHONPATH=app python scripts/test_safe_regression.py
# 或 Windows PowerShell：
$env:PYTHONPATH = "app"; python scripts/test_safe_regression.py
```

- 测试类脚本默认假设后端已在 `http://127.0.0.1:5000` 运行（除 `test_safe_regression.py` 用 TestClient 自起）。
- 这些脚本依赖当时数据库结构，跨版本可能失效，运行失败属正常，不代表线上有 bug。

## 清理建议

确定不再需要历史参考时，可直接删除整个 `scripts/` 目录，不影响任何线上功能。
