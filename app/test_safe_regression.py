"""
安全回归测试：默认只操作测试 DB，不连接真实 app/homework_pet.db。

运行示例：
    $env:HOMEWORK_PET_DB_PATH="D:\\AIProject\\workbuddy\\homework-pet\\backups\\test_homework_pet_YYYYMMDD_HHMMSS.db"
    python app/test_safe_regression.py
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
DEFAULT_REAL_DB = APP_DIR / "homework_pet.db"

db_path = Path(os.environ.get("HOMEWORK_PET_DB_PATH", ""))
if not db_path:
    raise SystemExit("请先设置 HOMEWORK_PET_DB_PATH 指向测试 DB，禁止直接跑真实 DB。")
if db_path.resolve() == DEFAULT_REAL_DB.resolve():
    raise SystemExit("HOMEWORK_PET_DB_PATH 指向真实 DB，已拒绝运行。")
if not db_path.exists():
    raise SystemExit(f"测试 DB 不存在：{db_path}")

sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)
passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"[OK] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name} {detail}")


def conn():
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def set_pet(**fields):
    c = conn()
    pairs = ", ".join(f"{k}=?" for k in fields)
    c.execute(f"UPDATE pet SET {pairs} WHERE id=1", tuple(fields.values()))
    c.commit()
    c.close()


def latest_custom_task():
    c = conn()
    row = c.execute("SELECT * FROM custom_tasks ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    return dict(row) if row else None


def main():
    print(f"TEST_DB={db_path}")

    # 1. 睡觉状态下，页面仍应允许打开完成作业弹窗，接口完成后应唤醒。
    set_pet(status="sleeping", runaway_until=(datetime.now() + timedelta(hours=8)).isoformat(), hunger=50, mood=50)
    html = client.get("/?role=kid").text
    btn_start = html.find('class="btn-complete')
    btn_end = html.find('</button>', btn_start)
    complete_btn_html = html[btn_start:btn_end]
    check("睡觉状态完成作业按钮不应 disabled", btn_start >= 0 and " disabled " not in complete_btn_html, complete_btn_html)
    r = client.post("/api/task/complete", data={"task_type": "daily", "subject": "英语", "completed_by": "kid"}).json()
    check("睡觉状态完成作业可唤醒", r.get("success") and r.get("woke_up"), str(r))
    c = conn()
    pet = dict(c.execute("SELECT status, runaway_until FROM pet WHERE id=1").fetchone())
    c.close()
    check("完成作业后宠物状态恢复 happy", pet["status"] == "happy" and pet["runaway_until"] is None, str(pet))

    # 2. 家长模板接口应能准确创建所选任务，防止“整理书包”变成“背诵乘法口诀”。
    r = client.post("/api/custom-tasks/create", data={
        "subject": "整理书包",
        "category": "other",
        "exp_reward": 20,
        "coins_reward": 2,
        "deadline": datetime.now().strftime("%Y-%m-%d"),
    }).json()
    task = latest_custom_task()
    check("额外任务创建成功", r.get("success"), str(r))
    check("额外任务标题保持选择值", task and task["subject"] == "整理书包", str(task))
    check("额外任务奖励保持选择值", task and task["exp_reward"] == 20 and task["coins_reward"] == 2, str(task))

    # 3. 实时衰减：48 小时后饱腹低于 30，但不直接归零；心情和亲密度也衰减。
    old_time = (datetime.now() - timedelta(hours=48)).isoformat()
    set_pet(status="happy", hunger=100, mood=100, bond=100, last_decay_date=old_time)
    r = client.post("/api/scheduler/run").json()
    c = conn()
    pet = dict(c.execute("SELECT hunger, mood, bond FROM pet WHERE id=1").fetchone())
    c.close()
    check("调度执行成功", r.get("success"), str(r))
    check("48小时饱腹低于30且大于0", 0 < pet["hunger"] < 30, str(pet))
    check("48小时心情衰减", pet["mood"] < 100, str(pet))
    check("48小时亲密度衰减", pet["bond"] < 100, str(pet))

    # 4. 自定义行为评价：记录行为、龙币流水、心情亲密度变化，且限制 -20~20。
    set_pet(status="happy", mood=50, bond=50, coins=100)
    r = client.post("/api/behavior/evaluate/custom", data={
        "name": "主动整理书桌",
        "behavior_type": "positive",
        "coins": 5,
    }).json()
    check("自定义行为评价成功", r.get("success") and r.get("new_balance") == 105, str(r))
    check("自定义行为提升心情亲密度", r.get("mood", 0) > 50 and r.get("bond", 0) > 50, str(r))
    r = client.post("/api/behavior/evaluate/custom", data={
        "name": "超限测试",
        "behavior_type": "improve",
        "coins": -30,
    }).json()
    check("自定义行为限制龙币范围", not r.get("success"), str(r))

    # 5. 皮肤接口返回当前阶段图片路径。
    r = client.get("/api/pet/skins").json()
    check("皮肤接口返回列表", bool(r.get("skins")), str(r))
    check("皮肤含图片路径", all("image" in s and "/static/dragon-skins/" in s["image"] for s in r.get("skins", [])), str(r))
    skin_files_ok = True
    for skin in ["default", "fire", "ice", "gold", "nature"]:
        for stage in range(5):
            skin_files_ok = skin_files_ok and (ROOT / "app" / "static" / "dragon-skins" / skin / f"stage-{stage}.png").exists()
    check("5套皮肤25张阶段图存在", skin_files_ok)

    print(f"PASS={passed} FAIL={failed}")
    raise SystemExit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
