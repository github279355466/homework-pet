import os, sys, json, random, logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("phase3")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "app"))
from database import get_db_connection

HARD_MATH_TEMPLATES = {
    3: [
        lambda: (f"小明有{random.randint(10,50)}个苹果，给了小红{random.randint(1,10)}个，又给了小华{random.randint(1,5)}个，小明还剩几个苹果？", 
                 "B", [f"A.{random.randint(5,20)}", f"B.{random.randint(10,50)-random.randint(1,10)-random.randint(1,5)}", f"C.{random.randint(20,30)}", f"D.{random.randint(30,40)}"], "减法应用题"),
        lambda: (f"一本书{random.randint(20,100)}页，小明每天看{random.randint(2,10)}页，看了{random.randint(2,5)}天，还剩多少页？",
                 "B", [f"A.{random.randint(10,30)}", f"B.{random.randint(20,100)-random.randint(2,10)*random.randint(2,5)}", f"C.{random.randint(30,50)}", f"D.{random.randint(50,70)}"], "乘减应用题"),
    ],
    4: [
        lambda: (f"学校操场长{random.randint(50,100)}米，宽{random.randint(20,50)}米，小明跑了{random.randint(2,5)}圈，一共跑了多少米？",
                 "B", [f"A.{random.randint(100,200)}", f"B.{(random.randint(50,100)+random.randint(20,50))*2*random.randint(2,5)}", f"C.{random.randint(200,400)}", f"D.{random.randint(400,600)}"], "周长应用题"),
    ],
    5: [
        lambda: (f"一桶油有{random.randint(5,10)}升，用去了{random.randint(1,3)}/{random.randint(2,5)}，还剩多少升？",
                 "B", [f"A.{random.randint(2,5)}", f"B.{int(random.randint(5,10)*(1-random.randint(1,3)/random.randint(2,5)))}", f"C.{random.randint(3,6)}", f"D.{random.randint(6,8)}"], "分数应用题"),
    ],
    6: [
        lambda: (f"地图上{random.randint(1,5)}厘米代表实际{random.randint(10,50)}千米，{random.randint(5,15)}厘米代表实际多少千米？",
                 "B", [f"A.{random.randint(50,100)}", f"B.{random.randint(5,15)*random.randint(10,50)//random.randint(1,5)}", f"C.{random.randint(100,200)}", f"D.{random.randint(200,300)}"], "比例尺应用题"),
    ],
}

HARD_CHINESE_TEMPLATES = {
    3: [
        lambda: ("读了\"春天来了，花儿开了，小鸟在树上唱歌\"，下面哪个说法正确？",
                 "B", ["A.花儿在冬天开", "B.小鸟在树上唱歌", "C.春天很冷", "D.花儿不开"], "阅读理解"),
    ],
    4: [
        lambda: ("\"井底之蛙\"这个故事告诉我们什么道理？",
                 "B", ["A.井里很舒服", "B.眼界要开阔", "C.青蛙很聪明", "D.井很深"], "成语故事理解"),
    ],
    5: [
        lambda: ("读了\"小明是个爱学习的孩子，每天都认真完成作业\"，下面哪个说法不正确？",
                 "C", ["A.小明爱学习", "B.小明认真完成作业", "C.小明不爱学习", "D.小明每天写作业"], "阅读理解"),
    ],
    6: [
        lambda: ("\"完璧归赵\"这个成语的主人公是谁？",
                 "B", ["A.廉颇", "B.蔺相如", "C.赵王", "D.秦王"], "成语典故"),
    ],
}

HARD_ENGLISH_TEMPLATES = {
    3: [
        lambda: ("I ___ a student. He ___ a student, too. 填什么？",
                 "B", ["A.am, am", "B.am, is", "C.is, am", "D.is, is"], "be动词"),
    ],
    4: [
        lambda: ("There ___ a book and two pens on the desk. 填什么？",
                 "B", ["A.am", "B.is", "C.are", "D.be"], "there be句型"),
    ],
    5: [
        lambda: ("She ___ to school yesterday. 填什么？",
                 "B", ["A.go", "B.went", "C.goes", "D.going"], "一般过去时"),
    ],
    6: [
        lambda: ("If it ___ tomorrow, we will stay at home. 填什么？",
                 "B", ["A.rain", "B.rains", "C.rained", "D.will rain"], "条件句"),
    ],
}

def main():
    conn = get_db_connection()
    total_added = 0
    
    # 数学高难度
    for grade, templates in HARD_MATH_TEMPLATES.items():
        kps = conn.execute("SELECT * FROM knowledge_points WHERE subject='math' AND grade=?", (grade,)).fetchall()
        for i, kp in enumerate(kps[:50]):
            try:
                qt, correct, opts, exp = random.choice(templates)()
                conn.execute("INSERT INTO question_bank (kp_id, subject, grade, chapter, difficulty, question_text, options, correct_answer, explanation, source) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (kp["id"], "math", grade, kp["chapter"], 3, qt, json.dumps(opts, ensure_ascii=False), correct, exp, "hard_v1"))
                total_added += 1
            except Exception as e:
                log.debug(f"FAIL math G{grade}: {e}")
    
    # 语文高难度
    for grade, templates in HARD_CHINESE_TEMPLATES.items():
        kps = conn.execute("SELECT * FROM knowledge_points WHERE subject='chinese' AND grade=?", (grade,)).fetchall()
        for i, kp in enumerate(kps[:30]):
            try:
                qt, correct, opts, exp = random.choice(templates)()
                conn.execute("INSERT INTO question_bank (kp_id, subject, grade, chapter, difficulty, question_text, options, correct_answer, explanation, source) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (kp["id"], "chinese", grade, kp["chapter"], 3, qt, json.dumps(opts, ensure_ascii=False), correct, exp, "hard_v1"))
                total_added += 1
            except Exception as e:
                log.debug(f"FAIL chinese G{grade}: {e}")
    
    # 英语高难度
    for grade, templates in HARD_ENGLISH_TEMPLATES.items():
        kps = conn.execute("SELECT * FROM knowledge_points WHERE subject='english' AND grade=?", (grade,)).fetchall()
        for i, kp in enumerate(kps[:30]):
            try:
                qt, correct, opts, exp = random.choice(templates)()
                conn.execute("INSERT INTO question_bank (kp_id, subject, grade, chapter, difficulty, question_text, options, correct_answer, explanation, source) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (kp["id"], "english", grade, kp["chapter"], 3, qt, json.dumps(opts, ensure_ascii=False), correct, exp, "hard_v1"))
                total_added += 1
            except Exception as e:
                log.debug(f"FAIL english G{grade}: {e}")
    
    conn.commit()
    conn.close()
    log.info(f"Phase 3 done: added {total_added} hard questions")

if __name__ == "__main__":
    main()
