"""Phase 4 前端多宠物化 — 冒烟测试（仅测试库，生产库只读不碰）。

运行方式（必须使用项目 venv，且 DB 环境变量指向测试库）：
    .venv-phase3/Scripts/python app/tests/test_phase4_frontend_smoke.py

铁律：
- 生产库 app/homework_pet.db 只读，绝不写。
- 测试库 = 生产库只读快照（shutil.copy2），所有写操作只落测试库。
- 不依赖 /static/species 图片存在（前端 emoji 兜底）。
"""
import os
import sys
import shutil

# ===== 项目根 & 路径 =====
HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(HERE)                       # .../app
PROJECT_ROOT = os.path.dirname(APP_DIR)               # .../homework-pet
PROD_DB = os.path.join(APP_DIR, "homework_pet.db")
TEST_DB = os.path.join(PROJECT_ROOT, "backups", "test_homework_pet.db")

# ===== 环境：强制指向测试库 + 允许 gacha 测试钩子 =====
os.environ["HOMEWORK_PET_DB_PATH"] = TEST_DB
os.environ["MULTI_PET_TEST"] = "1"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


def copy_production_to_test():
    """生产库只读 → 测试库（物理快照，绝不写生产）。"""
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


RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f"  -- {detail}" if (detail and not cond) else ""))


def main():
    print("=== Phase 4 前端多宠物化冒烟测试 ===")
    copy_production_to_test()

    # import database / main（import 时 init_db 跑在测试库，并迁移）
    import database
    import main
    from fastapi.testclient import TestClient
    client = TestClient(main.app)

    # 1) GET / 返回 200 且含新增入口元素
    print("\n[1] 首页渲染 + 入口元素")
    resp = client.get("/", params={"role": "kid"})
    html = resp.text
    check("GET / 返回 200", resp.status_code == 200, f"status={resp.status_code}")
    for token in ["我的宠物", "领养中心", "扭蛋机", "签到", "mpCarousel",
                  "showAdoptShop", "showGachaPanel", "showSwitchModal", "doSignin",
                  "mp-toolbar", "species-emoji-fallback"]:
        check(f"HTML 含『{token}』", token in html)

    # 2) 给测试宠物充足龙币（直接写测试库，便于验证 adopt/gacha 成功路径）
    print("\n[2] 准备测试数据（仅测试库）")
    conn = database.get_db_connection()
    conn.execute("UPDATE pet SET coins = 99999 WHERE id=1")
    # 确保迁移已建表
    has_pc = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pet_collection'"
    ).fetchone()
    conn.commit()
    conn.close()
    check("测试库已迁移（pet_collection 存在）", has_pc is not None)

    # 3) 领养 adopt（成功 + 重复）
    print("\n[3] 领养中心 API")
    r = client.post("/api/pets/adopt", data={"species_id": "cat"})
    d = r.json()
    check("领养 cat 成功", d.get("success") is True, str(d))
    check("领养返回 icon", bool(d.get("icon")), str(d.get("icon")))
    r2 = client.post("/api/pets/adopt", data={"species_id": "cat"})
    d2 = r2.json()
    check("重复领养返回 ALREADY_OWNED", d2.get("code") == "ALREADY_OWNED", str(d2))
    # 龙币不足路径
    conn = database.get_db_connection()
    conn.execute("UPDATE pet SET coins = 0 WHERE id=1")
    conn.commit(); conn.close()
    r3 = client.post("/api/pets/adopt", data={"species_id": "panda"})
    d3 = r3.json()
    check("龙币不足返回 NO_COINS", d3.get("code") == "NO_COINS", str(d3))
    # 恢复龙币
    conn = database.get_db_connection()
    conn.execute("UPDATE pet SET coins = 99999 WHERE id=1")
    conn.commit(); conn.close()

    # 4) 扭蛋 gacha（force_species 钩子，新物种 + 重复补偿）
    print("\n[4] 扭蛋机 API")
    r = client.post("/api/pets/gacha", data={"force_species": "fox"})
    d = r.json()
    check("扭蛋 fox 成功", d.get("success") is True, str(d))
    if d.get("success"):
        if d.get("duplicated"):
            check("重复扭蛋返回补偿", "compensation" in d and d["compensation"] > 0, str(d))
        else:
            check("新物种扭蛋返回 pet_id", "pet_id" in d, str(d))
    # 重复抽已拥有的 fox → 补偿
    r2 = client.post("/api/pets/gacha", data={"force_species": "fox"})
    d2 = r2.json()
    check("重复抽 fox 走补偿分支", d2.get("duplicated") is True and d2.get("compensation", 0) > 0, str(d2))

    # 5) 签到 signin（首次成功 + 幂等）
    print("\n[5] 签到 API")
    r = client.post("/api/pets/signin")
    d = r.json()
    check("签到首次成功", d.get("success") is True and d.get("already_signed") is False, str(d))
    r2 = client.post("/api/pets/signin")
    d2 = r2.json()
    check("签到幂等（同日再次返回 ALREADY_SIGNED）",
          d2.get("code") == "ALREADY_SIGNED" or d2.get("already_signed") is True, str(d2))

    # 6) 切换 switch
    print("\n[6] 切换宠物 API")
    conn = database.get_db_connection()
    pets = conn.execute("SELECT id, species_id, name FROM pet_collection ORDER BY id").fetchall()
    conn.close()
    check("测试库至少 2 只宠物（龙 + 领养/扭蛋所得）", len(pets) >= 2, f"count={len(pets)}")
    if len(pets) >= 2:
        target = pets[1]  # 非激活的那只
        r = client.post("/api/pets/switch", data={"pet_id": target["id"]})
        d = r.json()
        check("切换成功", d.get("success") is True, str(d))
        conn = database.get_db_connection()
        active = conn.execute("SELECT active_pet_id FROM pet WHERE id=1").fetchone()[0]
        conn.close()
        check("切换后 active_pet_id 已更新", active == target["id"], f"active={active}")

    # 7) 汇总
    print("\n=== 结果汇总 ===")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"PASS {passed}/{total}")
    fails = [n for n, ok, _ in RESULTS if not ok]
    if fails:
        print("FAIL 项:", fails)
        sys.exit(1)
    print("✅ Phase 4 前端冒烟全部通过（仅测试库，生产库未触碰）")


if __name__ == "__main__":
    main()
