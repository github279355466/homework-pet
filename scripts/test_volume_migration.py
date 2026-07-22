"""验证 Volume 持久化迁移逻辑（无需真实 Railway，本地模拟）。

覆盖：
  1) 首启种子迁移：HOMEWORK_PET_DB_PATH 指向空目标时，_ensure_persistent_db 把 bundled 库拷贝过去且数据可读
  2) 幂等：目标已存在则跳过
  3) 退出 checkpoint 注册无异常
  4) get_database_url 优先级：显式 > RAILWAY_VOLUME_MOUNT_PATH > 默认
  5) /api/admin/db-export 接口：错误密码 403、正确密码返回文件
"""
import os
import sys
import tempfile
import sqlite3

PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("✅" if cond else "❌") + f" {name}" + (f"  ({extra})" if extra else ""))

tmpdir = tempfile.mkdtemp()
target = os.path.join(tmpdir, "homework_pet.db")
os.environ["HOMEWORK_PET_DB_PATH"] = target

# 必须在 import database 之前设好 env（模块级 init_db 在 import 时运行）
import database

# 1) 种子迁移：target 由 bundled 库拷贝而来，应有数据
ok_target = os.path.exists(target)
n_pet = n_ach = -1
if ok_target:
    c = sqlite3.connect(target)
    n_pet = c.execute("SELECT COUNT(*) FROM pet").fetchone()[0]
    n_ach = c.execute("SELECT COUNT(*) FROM achievements").fetchone()[0]
    c.close()
check("种子迁移生成目标库", ok_target)
check("种子迁移拷贝 pet 数据", n_pet >= 1, f"pet={n_pet}")
check("种子迁移拷贝 achievements 数据", n_ach >= 1, f"ach={n_ach}")

# 2) 幂等：再次调用不应报错、数据仍在
try:
    database._ensure_persistent_db()
    c = sqlite3.connect(target)
    n2 = c.execute("SELECT COUNT(*) FROM pet").fetchone()[0]
    c.close()
    check("幂等：重复调用安全且数据保持", n2 == n_pet, f"pet={n2}")
except Exception as e:
    check("幂等：重复调用安全且数据保持", False, str(e))

# 3) 退出 checkpoint 注册
try:
    database.register_shutdown_dump()
    check("register_shutdown_dump 无异常", True)
except Exception as e:
    check("register_shutdown_dump 无异常", False, str(e))

# 4) 路径优先级
check("get_database_url 返回显式路径", database.get_database_url() == target)
del os.environ["HOMEWORK_PET_DB_PATH"]
os.environ["RAILWAY_VOLUME_MOUNT_PATH"] = "/data"
import posixpath
check("RAILWAY_VOLUME_MOUNT_PATH 回退",
      database.get_database_url().replace("\\", "/") == "/data/homework_pet.db",
      database.get_database_url())
del os.environ["RAILWAY_VOLUME_MOUNT_PATH"]

# 5) db-export 接口（TestClient）
try:
    from fastapi.testclient import TestClient
    import main
    client = TestClient(main.app)
    r = client.get("/api/admin/db-export?pwd=wrong")
    check("db-export 错误密码返回 403", r.status_code == 403, f"code={r.status_code}")
    r = client.get("/api/admin/db-export?pwd=1234")
    ok_file = (r.status_code == 200 and len(r.content) > 0)
    check("db-export 正确密码返回文件", ok_file, f"code={r.status_code} bytes={len(r.content)}")
except Exception as e:
    check("db-export 接口测试", False, str(e))

print(f"\n结果: {len(PASS)} 通过 / {len(FAIL)} 失败")
if FAIL:
    print("失败项:", FAIL)
    sys.exit(1)
print("全部通过 ✅")
