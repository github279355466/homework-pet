# 后端规范 - homework-pet v3.3

> **位置**: `app/main.py` (FastAPI 单文件)
> **数据库**: `app/database.py` (SQLite 初始化)
> **辅助模块**: `app/pet_helpers.py` (v3.3 新增)

## 文件结构

```
app/
├── main.py                # FastAPI 主程序，47 个 API 端点
├── database.py            # 数据库初始化，14 张表
├── pet_helpers.py         # v3.3 多宠物辅助函数 ⭐
├── migrations/
│   └── v3.3_multi_pet.py  # v3.3 迁移函数 ⭐
├── templates/index.html   # 前端单页
├── static/                # 静态资源
└── homework_pet.db        # 生产数据库 (禁改)
```

## 编码规范

### 1. 函数设计
- 所有写操作必须通过 `update_active_pet()` 或 `add_coins()` 等辅助函数
- 旧代码读 `pet` 表镜像字段，新代码直接读 `pet_collection`
- 写完 `pet_collection` 后必须调用 `sync_active_pet_mirror(conn)`

### 2. 数据库访问
```python
# 正确: 使用辅助函数
from pet_helpers import get_active_pet_row, update_active_pet, sync_active_pet_mirror

# 错误: 直接 WHERE id=1 (旧代码兼容可保留，新代码禁止)
pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()  # ❌ 新代码禁止
```

### 3. API 端点
- 路径: 全小写，连字符分隔 (如 `/api/pets/active`)
- 响应: 统一 JSON 格式 `{"success": bool, "message": str, ...}`
- 错误: 用 `{"success": False, "message": "错误描述"}`

### 4. 日志
```python
logger = logging.getLogger("homework-pet")
logger.info(f"[api-name] 操作描述: key={value}")
```

## v3.3 关键模块

### pet_helpers.py 核心 API

| 函数 | 用途 |
|---|---|
| `get_active_pet_id(conn)` | 获取激活宠物 ID |
| `get_active_pet_row(conn)` | 获取激活宠物完整行 |
| `sync_active_pet_mirror(conn)` | 同步镜像到 pet 表 |
| `update_active_pet(conn, exp_delta=, hunger_delta=, ...)` | 更新激活宠物属性 |

### 迁移模块

| 函数 | 用途 |
|---|---|
| `migrate_single_to_multi_pet(conn)` | 把旧 pet 表数据迁移到 pet_collection |

## 数据库表

### 全局表 (保留)
- `pet` (id=1): 全局档案 - coins/streak/math_streak/active_pet_id
- `tasks`: 作业完成记录
- `achievements`: 成就解锁
- `coin_transactions`: 龙币交易流水

### v3.3 新增表
- `species_catalog`: 7 个物种目录 (静态数据)
- `pet_collection`: 宠物个体表 (每只一行)

### 属性归属
| 属性 | 表 | 字段 |
|---|---|---|
| 金币 | pet | coins (全局) |
| 连续打卡 | pet | streak (全局) |
| 经验 | pet_collection | exp (个体) |
| 饱腹 | pet_collection | hunger (个体) |
| 心情 | pet_collection | mood (个体) |
| 亲密度 | pet_collection | bond (个体) |
| 皮肤 | pet_collection | skin_id (个体) |

## 测试约定

```bash
# 必须设置测试 DB 路径
export HOMEWORK_PET_DB_PATH="D:/AIProject/workbuddy/homework-pet/backups/test_v33.db"

# 运行测试
python scripts/test_xxx.py

# TestClient 模式
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)
```

## 部署

- 推送 `main` 分支 → Railway 自动构建
- 启动命令: `python app/main.py`
- 端口: `int(os.environ.get("PORT", 5000))` (必须保留)
- 依赖: `requirements.txt` (v3.3 不增加新依赖)
