"""Phase 3 获取系统自测（仅测试库，生产库只读不碰）。

运行方式（必须使用 Python 3.12 的 venv，且 HOOK 环境变量指向测试库）：
    source .venv-phase3/Scripts/activate
    export HOMEWORK_PET_DB_PATH="$(pwd)/backups/test_homework_pet.db"
    python app/tests/test_phase3_acquire.py

铁律：
- 生产库 app/homework_pet.db 只读，绝不写。
- 测试库 = 生产库只读快照（sqlite3.backup），结构变更增量幂等。
"""
import os
import sys
import sqlite3
import shutil

# ===== 项目根 & 路径 =====
HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(HERE)                       # .../app
PROJECT_ROOT = os.path.dirname(APP_DIR)               # .../homework-pet
PROD_DB = os.path.join(APP_DIR, "homework_pet.db")
# 每轮用唯一文件名，规避沙箱对 os.remove 的拦截与上一轮遗留 -wal 导致的脏数据
TEST_DB = os.path.join(PROJECT_ROOT, "backups", f"test_homework_pet_{os.getpid()}.db")

# ===== 环境：强制指向测试库 + 允许 gacha 测试钩子 =====
os.environ["HOMEWORK_PET_DB_PATH"] = TEST_DB
os.environ["MULTI_PET_TEST"] = "1"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# ===== 1) 生产库只读 → 测试库（物理快照，绝不写生产）=====
def copy_production_to_test():
    # 沙箱下 os.remove 被 safe-delete 拦截；sqlite3.backup 在 WAL 只读源上会尝试写源而失败。
    # 改用 shutil.copy2 物理拷贝（仅读生产文件字节，写仅落测试库），并连带拷贝 -wal/-shm 保持一致。
    # 使用每轮唯一文件名，规避上一轮遗留 -wal 造成的脏数据，也无需删除操作。
    for suffix in ("", "-wal", "-shm", "-journal"):
        src_f = PROD_DB + suffix
        dst_f = TEST_DB + suffix
        if os.path.exists(src_f):
            shutil.copy2(src_f, dst_f)
        elif os.path.exists(dst_f):
            try:
                os.remove(dst_f)
            except Exception:
                pass
    print("[setup] 已物理拷贝生产库 → 测试库（仅读生产，不写生产）")


def read_counts(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tables = ["pet", "tasks", "coin_transactions", "achievements", "behavior_rules",
              "pet_accessories", "parent_settings", "encourage", "treasure_log",
              "custom_tasks", "behavior_records", "focus_sessions", "random_surprises",
              "pocket_money_records"]
    out = {}
    for t in tables:
        try:
            out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            out[t] = -1
    conn.close()
    return out


# ===== 测试运行器 =====
RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f"  -- {detail}" if detail and not cond else ""))


# ===== 主体 =====
def main():
    print("=== Phase 3 获取系统自测 ===")
    # 复制前基线（复制后、import 前，test db == 生产）
    copy_production_to_test()
    baseline = read_counts(TEST_DB)

    # import database / main（import 时 init_db 跑在测试库，并迁移）
    import database
    import main
    from fastapi.testclient import TestClient
    client = TestClient(main.app)

    # 记录测试会话起始交易 id（仅对账本会话内新增的交易做连续性校验；
    # 生产库历史 coin_transactions 存在已知的非连续记录，不在本次校验范围）
    _c = database.get_db_connection()
    _row = _c.execute("SELECT MAX(id) AS m FROM coin_transactions").fetchone()
    start_id = _row["m"] or 0
    _c.close()

    # 连接辅助
    def get_pet():
        conn = database.get_db_connection()
        p = dict(conn.execute("SELECT * FROM pet WHERE id=1").fetchone())
        conn.close()
        return p

    def set_pet(**fields):
        conn = database.get_db_connection()
        for k, v in fields.items():
            conn.execute(f"UPDATE pet SET {k}=? WHERE id=1", (v,))
        conn.commit()
        conn.close()

    def set_coins(n):
        # 经 add_coins 写入流水（double_weekend=False），保证 coin_transactions 与 pet.coins 连续可对账
        conn = database.get_db_connection()
        cur = conn.execute("SELECT coins FROM pet WHERE id=1").fetchone()["coins"]
        main.add_coins(conn, n - cur, "test_setup", "测试初始化余额", double_weekend=False)
        conn.commit()
        conn.close()

    def pc_has(species_id, frozen=None):
        conn = database.get_db_connection()
        if frozen is None:
            row = conn.execute("SELECT 1 FROM pet_collection WHERE species_id=?",
                               (species_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM pet_collection WHERE species_id=? AND is_frozen=?",
                (species_id, frozen)).fetchone()
        conn.close()
        return row is not None

    # ---------- P3-T1 结构断言 ----------
    print("\n-- P3-T1 schema --")
    conn = database.get_db_connection()
    pet_cols = [r[1] for r in conn.execute("PRAGMA table_info(pet)").fetchall()]
    check("pet 含 last_signin_date", "last_signin_date" in pet_cols)
    check("pet 含 signin_count", "signin_count" in pet_cols)
    sp_count = conn.execute("SELECT COUNT(*) FROM species_catalog").fetchone()[0]
    check("species_catalog 7 行", sp_count == 7, f"实际 {sp_count}")
    pc_rows = conn.execute("SELECT * FROM pet_collection").fetchall()
    check("pet_collection 1 行", len(pc_rows) == 1, f"实际 {len(pc_rows)}")
    if pc_rows:
        check("pet_collection 首行 dragon/紫宝",
              pc_rows[0]["species_id"] == "dragon" and pc_rows[0]["name"] == "紫宝",
              f"{pc_rows[0]['species_id']}/{pc_rows[0]['name']}")
    # 老表行数不变
    post = read_counts(TEST_DB)
    for t in baseline:
        check(f"老表 {t} 行数不变", baseline[t] == post[t],
              f"{baseline[t]} -> {post[t]}")
    conn.close()

    # ---------- P3-T2 商店 + 领养 ----------
    print("\n-- P3-T2 shop / adopt --")
    r = client.get("/api/pets/shop")
    check("GET /api/pets/shop 200", r.status_code == 200, r.text[:200])
    shop = r.json().get("shop", [])
    shop_ids = [i["id"] for i in shop]
    check("shop 含 cat/rabbit/panda",
          all(x in shop_ids for x in ("cat", "rabbit", "panda")), str(shop_ids))
    check("dragon 不在 shop（initial 非 shop）", "dragon" not in shop_ids)
    # 初始 shop 物种均未拥有
    check("初始 shop 物种 owned 均为 false",
          all(i["owned"] is False for i in shop), str([(i['id'], i['owned']) for i in shop]))

    set_coins(1000)
    r = client.post("/api/pets/adopt", data={"species_id": "cat"})
    j = r.json()
    check("adopt cat 成功", j.get("success") is True, r.text[:200])
    check("adopt cat 扣 80 龙币(1000->920)", j.get("coins") == 920, str(j.get("coins")))
    check("pet_collection 新增 cat(is_frozen=1)", pc_has("cat", frozen=1))

    r2 = client.post("/api/pets/adopt", data={"species_id": "cat"})
    check("重复领养 cat → ALREADY_OWNED", r2.json().get("code") == "ALREADY_OWNED", r2.text[:200])

    # owned 标记刷新
    r3 = client.get("/api/pets/shop").json()
    cat_item = [i for i in r3["shop"] if i["id"] == "cat"][0]
    check("shop 中 cat.owned=true", cat_item["owned"] is True)

    # 余额不足
    set_coins(10)
    r4 = client.post("/api/pets/adopt", data={"species_id": "panda"})  # panda shop 价 120
    check("低余额领养 panda → NO_COINS", r4.json().get("code") == "NO_COINS", r4.text[:200])
    check("NO_COINS 不插入 panda", not pc_has("panda"))
    check("NO_COINS 不扣龙币", get_pet()["coins"] == 10)

    # ---------- P3-T3 扭蛋机 ----------
    print("\n-- P3-T3 gacha --")
    set_coins(1000)
    r = client.post("/api/pets/gacha", data={"force_species": "rabbit"})
    j = r.json()
    check("gacha force rabbit 成功", j.get("success") is True, r.text[:200])
    check("gacha 新物种 duplicated=false", j.get("duplicated") is False)
    check("gacha 抽中 rabbit", j.get("species_id") == "rabbit")
    check("gacha 扣 50 龙币(1000->950)", get_pet()["coins"] == 950, str(get_pet()["coins"]))
    check("pet_collection 新增 rabbit(is_frozen=1)", pc_has("rabbit", frozen=1))
    rabbit_id = j.get("pet_id")

    r2 = client.post("/api/pets/gacha", data={"force_species": "rabbit"})
    j2 = r2.json()
    check("gacha 重复 rabbit → duplicated=true", j2.get("success") is True and j2.get("duplicated") is True,
          r2.text[:200])
    comp = j2.get("compensation")
    check("重复补偿 = floor(150*0.5)=75", comp == 75, str(comp))
    # 余额：950 -50 +75 = 975
    check("重复后余额 950-50+75=975", get_pet()["coins"] == 975, str(get_pet()["coins"]))
    check("重复不新增 rabbit", pc_has("rabbit") and rabbit_id is not None)

    # 余额不足
    set_coins(10)
    r3 = client.post("/api/pets/gacha", data={})
    check("低余额 gacha → NO_COINS", r3.json().get("code") == "NO_COINS", r3.text[:200])

    # ---------- 货币对账（移至签到之后，覆盖本会话全部交易）----------

    # ---------- 回归：旧接口 ----------

    # ---------- P3-T4 签到 ----------
    print("\n-- P3-T4 signin --")
    set_pet(last_signin_date=None, signin_count=0)
    set_coins(100)
    r = client.post("/api/pets/signin")
    j = r.json()
    check("首次签到成功", j.get("success") is True and j.get("already_signed") is False, r.text[:200])
    check("首次 signin_count=1", j.get("signin_count") == 1, str(j.get("signin_count")))
    check("首次 +5 龙币(100->105)", j.get("coins") == 105, str(j.get("coins")))

    r2 = client.post("/api/pets/signin")
    check("同日再签到 → ALREADY_SIGNED", r2.json().get("code") == "ALREADY_SIGNED", r2.text[:200])

    # 里程碑发熊猫（panda 未拥有）
    set_pet(last_signin_date="2000-01-01", signin_count=6)
    set_coins(100)
    r3 = client.post("/api/pets/signin")
    j3 = r3.json()
    check("里程碑 count=7", j3.get("signin_count") == 7, str(j3.get("signin_count")))
    check("里程碑发熊猫(type=pet)", j3.get("reward", {}).get("type") == "pet"
          and j3["reward"].get("species_id") == "panda", str(j3.get("reward")))
    check("pet_collection 新增 panda(is_frozen=1)", pc_has("panda", frozen=1))

    # 里程碑但 panda 已拥有 → +30 补偿
    set_pet(last_signin_date="2000-01-02", signin_count=6)
    set_coins(100)
    r4 = client.post("/api/pets/signin")
    j4 = r4.json()
    check("再次里程碑 count=7", j4.get("signin_count") == 7)
    check("已拥有 → 龙币补偿(type=coins)", j4.get("reward", {}).get("type") == "coins", str(j4.get("reward")))
    # 100 + 5(每日) + 30(补偿) = 135
    check("已拥有补偿后余额=135", j4.get("coins") == 135, str(j4.get("coins")))

    # ---------- 货币对账（仅本测试会话内的交易，start_id 之后）----------
    print("\n-- 龙币对账 --")
    conn = database.get_db_connection()
    prev_row = conn.execute(
        "SELECT balance_after FROM coin_transactions WHERE id=?", (start_id,)).fetchone()
    prev = prev_row["balance_after"] if prev_row else None
    rows = conn.execute(
        "SELECT amount, balance_after FROM coin_transactions WHERE id > ? ORDER BY id",
        (start_id,)).fetchall()
    ok = True
    for row in rows:
        if prev is not None and row["balance_after"] != prev + row["amount"]:
            ok = False
            print(f"    对账断点: {prev} + {row['amount']} != {row['balance_after']}")
        prev = row["balance_after"]
    final = conn.execute("SELECT coins FROM pet WHERE id=1").fetchone()[0]
    conn.close()
    check("本会话 coin_transactions 流水连续可对账", ok)
    check("末笔 balance_after == pet.coins", prev == final, f"{prev} vs {final}")

    # ---------- 回归：旧接口 ----------
    print("\n-- 回归：旧接口 --")
    r = client.get("/api/pet")
    check("GET /api/pet 正常", r.status_code == 200 and "pet" in r.json(), r.text[:120])
    r = client.post("/api/task/complete", data={"subject": "课外阅读", "task_type": "daily"})
    check("POST /api/task/complete 正常", r.status_code == 200 and "success" in r.json(), r.text[:120])
    r = client.post("/api/pet/feed")
    check("POST /api/pet/feed 正常", r.status_code == 200 and r.json().get("success") is True, r.text[:120])
    r = client.post("/api/pet/interact", data={"interaction_type": "pat"})
    check("POST /api/pet/interact 正常", r.status_code == 200 and r.json().get("success") is True, r.text[:120])
    lst = client.get("/api/pets").json()["pets"]
    others = [p for p in lst if not p["is_active"]]
    if others:
        tid = others[0]["id"]
        r = client.post("/api/pets/switch", data={"pet_id": tid})
        check("POST /api/pets/switch 正常", r.json().get("success") is True, r.text[:120])
        dragon = [p for p in client.get("/api/pets").json()["pets"] if p["species_id"] == "dragon"][0]
        client.post("/api/pets/switch", data={"pet_id": dragon["id"]})
    else:
        check("POST /api/pets/switch 正常", True, "无其它宠物可切换")

    # ---------- 生产库安全确认（只读）----------
    print("\n-- 生产库安全确认（只读）--")
    tmp = os.path.join(PROJECT_ROOT, "backups", f"prodcheck_{os.getpid()}.db")
    shutil.copy2(PROD_DB, tmp)   # 仅复制字节用于检查，绝不写生产库
    conn = sqlite3.connect(tmp)
    prod_cols = [r[1] for r in conn.execute("PRAGMA table_info(pet)").fetchall()]
    prod_tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    try:
        os.remove(tmp)
    except Exception:
        pass
    check("生产库 pet 无 last_signin_date", "last_signin_date" not in prod_cols, str(prod_cols))
    check("生产库 pet 无 signin_count", "signin_count" not in prod_cols)
    check("生产库 无 pet_collection", "pet_collection" not in prod_tables, str(prod_tables))
    check("生产库 无 species_catalog", "species_catalog" not in prod_tables)

    # ---------- 汇总 ----------
    print("\n=== 汇总 ===")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    for name, ok, _ in RESULTS:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n结果: {passed}/{total} 通过")
    if passed != total:
        print("存在失败项！")
        sys.exit(1)
    print("全部通过 ✅")


if __name__ == "__main__":
    main()
