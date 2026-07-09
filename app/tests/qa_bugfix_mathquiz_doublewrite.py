"""独立回归验证：answer_math_quiz 龙币流水双写 Bug（修复后）。

铁律：
- 仅操作测试库副本，绝不读写 app/homework_pet.db（生产库只读不碰）。
- 通过 HOMEWORK_PET_DB_PATH 指向副本隔离。
- 跑完删除临时库。

验证点：
  ① 答对一次：source='math_quiz' AND type='earn' 本次新增恰好 1 条(amount=10)，pet.coins +10。
  ② 答错一次：本次新增 source='math_quiz' earn 行 0 条，pet.coins 不变。
  ③ 账本对账：本会话 coin_transactions 流水连续可对账，末笔 balance_after == pet.coins。
"""
import os
import sys
import shutil
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(HERE)                       # .../app
PROJECT_ROOT = os.path.dirname(APP_DIR)               # .../homework-pet
PROD_DB = os.path.join(APP_DIR, "homework_pet.db")
TEST_DB = os.path.join(APP_DIR, "tests", "_qa_bugfix.db")

# ===== 环境：强制指向测试库 =====
os.environ["HOMEWORK_PET_DB_PATH"] = TEST_DB
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


def copy_production_to_test():
    """物理拷贝生产库（含 -wal/-shm）到测试库，仅读生产字节，不写生产。"""
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


def cleanup():
    for suffix in ("", "-wal", "-shm", "-journal"):
        f = TEST_DB + suffix
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f"  -- {detail}" if detail else ""))


def main():
    print("=== QA 独立回归：math_quiz 龙币双写修复 ===")
    copy_production_to_test()

    import database
    import main
    from fastapi.testclient import TestClient
    client = TestClient(main.app)

    def get_coins():
        c = database.get_db_connection()
        v = c.execute("SELECT coins FROM pet WHERE id=1").fetchone()["coins"]
        c.close()
        return v

    def set_happy():
        c = database.get_db_connection()
        c.execute("UPDATE pet SET status='happy' WHERE id=1")
        c.commit()
        c.close()

    def count_math_quiz_earn(since_id):
        c = database.get_db_connection()
        rows = c.execute(
            "SELECT amount FROM coin_transactions WHERE id > ? "
            "AND source='math_quiz' AND type='earn' ORDER BY id",
            (since_id,)).fetchall()
        c.close()
        return [r["amount"] for r in rows]

    # 记录隔离基线（隔离历史 167 条旧流水）
    c = database.get_db_connection()
    row = c.execute("SELECT MAX(id) AS m FROM coin_transactions").fetchone()
    start_id = row["m"] or 0
    c.close()
    print(f"  隔离基线 start_id={start_id}")

    baseline_coins = get_coins()
    set_happy()

    # ---------- ① 答对一次 ----------
    print("\n-- ① 答对一次 --")
    r1 = client.post("/api/pet/math-quiz/answer",
                     data={"answer": 42, "correct_answer": 42})
    j1 = r1.json()
    check("答对接口 success=True", j1.get("success") is True, str(j1))
    check("答对接口 correct=True", j1.get("correct") is True)
    amounts1 = count_math_quiz_earn(start_id)
    check("答对新增 math_quiz earn 恰好 1 条", len(amounts1) == 1, f"实际条数={len(amounts1)} 金额={amounts1}")
    check("答对新增流水 amount=10", amounts1 == [10], f"金额={amounts1}")
    check("答对后 new_coins 返回 baseline+10", j1.get("new_coins") == baseline_coins + 10,
          f"new_coins={j1.get('new_coins')} 期望={baseline_coins + 10}")
    after_correct_coins = get_coins()
    check("pet.coins 余额恰好 +10", after_correct_coins == baseline_coins + 10,
          f"余额={after_correct_coins} 期望={baseline_coins + 10}")

    # ---------- ② 答错一次 ----------
    print("\n-- ② 答错一次 --")
    # 答错前再记一次基线，用于隔离"答对"产生的那 1 条
    c = database.get_db_connection()
    row = c.execute("SELECT MAX(id) AS m FROM coin_transactions").fetchone()
    before_wrong_id = row["m"] or 0
    c.close()
    coins_before_wrong = get_coins()
    set_happy()
    r2 = client.post("/api/pet/math-quiz/answer",
                     data={"answer": 1, "correct_answer": 2})
    j2 = r2.json()
    check("答错接口 success=True", j2.get("success") is True, str(j2))
    check("答错接口 correct=False", j2.get("correct") is False)
    amounts2 = count_math_quiz_earn(before_wrong_id)
    check("答错新增 math_quiz earn 行 0 条", len(amounts2) == 0, f"实际条数={len(amounts2)} 金额={amounts2}")
    coins_after_wrong = get_coins()
    check("答错后余额不变", coins_after_wrong == coins_before_wrong,
          f"前={coins_before_wrong} 后={coins_after_wrong}")

    # ---------- ③ 账本对账 ----------
    print("\n-- ③ 账本对账 --")
    c = database.get_db_connection()
    prev_row = c.execute(
        "SELECT balance_after FROM coin_transactions WHERE id=?", (start_id,)).fetchone()
    prev = prev_row["balance_after"] if prev_row else None
    rows = c.execute(
        "SELECT amount, balance_after FROM coin_transactions WHERE id > ? ORDER BY id",
        (start_id,)).fetchall()
    ok = True
    for row in rows:
        if prev is not None and row["balance_after"] != prev + row["amount"]:
            ok = False
            print(f"    对账断点: {prev} + {row['amount']} != {row['balance_after']}")
        prev = row["balance_after"]
    final = c.execute("SELECT coins FROM pet WHERE id=1").fetchone()[0]
    c.close()
    check("本会话 coin_transactions 流水连续可对账", ok)
    check("末笔 balance_after == pet.coins", prev == final, f"{prev} vs {final}")

    # ---------- 汇总 ----------
    print("\n=== 汇总 ===")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    for name, ok, detail in RESULTS:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n结果: {passed}/{total} 通过")

    cleanup()
    if os.path.exists(TEST_DB):
        print("警告：临时库未清理:", TEST_DB)
    else:
        print("临时测试库已清理 ✅")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
