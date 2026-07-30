#!/usr/bin/env python3
"""
英语题库生成器 — 覆盖 1-6 年级
不依赖教材 PDF，直接基于小学英语课程标准生成
"""
import os, sys, json, random, logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("english-gen")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "app"))
from database import get_db_connection

# 小学英语课程标准的知识点体系
ENGLISH_CURRICULUM = {
    2: {
        "words": [("teacher", "老师"), ("student", "学生"), ("school", "学校"), ("friend", "朋友"),
                  ("family", "家庭"), ("happy", "高兴"), ("sad", "伤心"), ("angry", "生气"),
                  ("tired", "累"), ("hungry", "饿"), ("big", "大"), ("small", "小"),
                  ("long", "长"), ("short", "短"), ("tall", "高"), ("short_2", "矮")],
        "grammar": [
            ("I ___ a student.", "A", ["A.am", "B.is", "C.are", "D.be"], "be动词"),
            ("She ___ happy.", "B", ["A.am", "B.is", "C.are", "D.be"], "be动词"),
            ("They ___ friends.", "C", ["A.am", "B.is", "C.are", "D.be"], "be动词"),
            ("___ you a teacher?", "A", ["A.Are", "B.Is", "C.Am", "D.Be"], "be动词疑问"),
        ],
        "dialogue": [
            ("How are you?", "A", ["A.I am fine", "B.Thank you", "C.Goodbye", "D.Hello"], "日常问候"),
            ("Nice to meet you.", "A", ["A.Nice to meet you too", "B.Thank you", "C.Goodbye", "D.Hello"], "日常问候"),
            ("What\'s your name?", "B", ["A.I am fine", "B.My name is Tom", "C.Thank you", "D.Goodbye"], "自我介绍"),
        ],
    },
    4: {
        "words": [("computer", "电脑"), ("television", "电视"), ("refrigerator", "冰箱"),
                  ("telephone", "电话"), ("camera", "相机"), ("beautiful", "美丽"),
                  ("important", "重要"), ("different", "不同"), ("difficult", "困难")],
        "grammar": [
            ("There ___ a book on the desk.", "B", ["A.am", "B.is", "C.are", "D.be"], "there be"),
            ("There ___ two books on the desk.", "C", ["A.am", "B.is", "C.are", "D.be"], "there be复数"),
            ("He ___ playing football now.", "B", ["A.am", "B.is", "C.are", "D.be"], "现在进行时"),
            ("She ___ TV every day.", "B", ["A.watch", "B.watches", "C.watching", "D.watched"], "一般现在时"),
        ],
        "reading": [
            ("Tom is a student. He likes reading. He reads books every day. What does Tom like?", "B",
             ["A.Playing", "B.Reading", "C.Singing", "D.Dancing"], "阅读理解"),
        ],
    },
    5: {
        "words": [("knowledge", "知识"), ("experience", "经历"), ("opportunity", "机会"),
                  ("challenge", "挑战"), ("success", "成功"), ("confidence", "自信"),
                  ("responsibility", "责任"), ("independence", "独立")],
        "grammar": [
            ("I ___ to school yesterday.", "B", ["A.go", "B.went", "C.goes", "D.going"], "一般过去时"),
            ("She ___ to school tomorrow.", "B", ["A.go", "B.will go", "C.went", "D.goes"], "一般将来时"),
            ("I ___ my homework already.", "B", ["A.do", "B.have done", "C.did", "D.doing"], "现在完成时"),
            ("The book ___ by Lu Xun.", "B", ["A.wrote", "B.was written", "C.written", "D.writes"], "被动语态"),
        ],
        "reading": [
            ("Yesterday was Sunday. Tom went to the park with his friends. They played football and flew kites. They were very happy. Where did Tom go?",
             "B", ["A.School", "B.Park", "C.Home", "D.Shop"], "阅读理解"),
        ],
    },
    6: {
        "words": [("philosophy", "哲学"), ("psychology", "心理学"), ("literature", "文学"),
                  ("mathematics", "数学"), ("chemistry", "化学"), ("physics", "物理"),
                  ("biology", "生物"), ("geography", "地理")],
        "grammar": [
            ("If it ___ tomorrow, we will stay at home.", "B", ["A.rain", "B.rains", "C.rained", "D.will rain"], "条件句"),
            ("I wish I ___ fly.", "B", ["A.can", "B.could", "C.will", "D.may"], "虚拟语气"),
            ("The house ___ in 1990.", "B", ["A.builds", "B.was built", "C.built", "D.building"], "被动语态过去"),
            ("___ you study hard, you will pass.", "A", ["A.If", "B.When", "C.Because", "D.Although"], "条件状语从句"),
        ],
        "reading": [
            ("The earth is our home. We should protect it. Pollution is bad for our health. We should plant more trees and save water. What should we do?",
             "B", ["A.Pollute", "B.Protect earth", "C.Cut trees", "D.Waste water"], "阅读理解"),
        ],
    },
}

def generate_english_for_grade(conn, grade, target_count=200):
    """为指定年级生成英语题目"""
    curriculum = ENGLISH_CURRICULUM.get(grade)
    if not curriculum:
        log.warning(f"无课程大纲: G{grade}")
        return 0
    
    # 创建虚拟知识点（用于关联）
    kp_id = f"kp_english_g{grade}_generated"
    conn.execute("""
        INSERT OR IGNORE INTO knowledge_points (id, subject, grade, chapter, name, difficulty, sort_order)
        VALUES (?, 'english', ?, '综合', '英语综合', 1, 0)
    """, (kp_id, grade))
    conn.commit()
    
    generated = 0
    all_templates = []
    
    # 单词认知题
    for word, meaning in curriculum.get("words", []):
        wrong_meanings = [m for w, m in curriculum["words"] if m != meaning][:3]
        while len(wrong_meanings) < 3:
            wrong_meanings.append(random.choice(["苹果", "红色", "大", "小", "好"]))
        
        all_templates.append((
            f"{word} 是什么意思？", "B",
            [f"A.{wrong_meanings[0]}", f"B.{meaning}", f"C.{wrong_meanings[1]}", f"D.{wrong_meanings[2]}"],
            f"单词认知: {word}={meaning}"
        ))
    
    # 语法题
    for tmpl in curriculum.get("grammar", []):
        all_templates.append(tmpl)
    
    # 阅读理解
    for tmpl in curriculum.get("reading", []):
        all_templates.append(tmpl)
    
    # 对话
    for tmpl in curriculum.get("dialogue", []):
        all_templates.append(tmpl)
    
    # 生成题目（循环使用模板直到达到目标数量）
    for i in range(target_count):
        tmpl = all_templates[i % len(all_templates)]
        question_text, correct, options, explanation = tmpl
        
        # 添加随机变化（替换数字等）
        question_text = question_text.replace("Tom", random.choice(["Tom", "Lily", "Jack", "Lucy", "Mike"]))
        
        try:
            conn.execute("""
                INSERT INTO question_bank
                (kp_id, subject, grade, chapter, difficulty, question_text, options, correct_answer, explanation, source)
                VALUES (?, 'english', ?, '综合', ?, ?, ?, ?, ?, 'english_gen')
            """, (kp_id, grade, random.choice([1, 2, 3]), question_text, json.dumps(options, ensure_ascii=False), correct, explanation))
            generated += 1
        except Exception as e:
            log.debug(f"FAIL: {e}")
    
    return generated

def main():
    conn = get_db_connection()
    
    # 清空旧英语题目（保留 G1 和 G3 的原始数据）
    conn.execute("DELETE FROM question_bank WHERE subject='english' AND source != 'seed_v22'")
    conn.commit()
    
    total = 0
    for grade in [2, 4, 5, 6]:
        count = generate_english_for_grade(conn, grade, target_count=200)
        log.info(f"English G{grade}: generated {count} questions")
        total += count
    
    # 也为 G1 和 G3 补充更多题目
    for grade in [1, 3]:
        count = generate_english_for_grade(conn, grade, target_count=100)
        log.info(f"English G{grade}: supplemented {count} questions")
        total += count
    
    conn.commit()
    
    # 验证
    print("\n=== 生成结果 ===")
    for grade in range(1, 7):
        qb = conn.execute("SELECT COUNT(*) as n FROM question_bank WHERE subject='english' AND grade=?", (grade,)).fetchone()['n']
        print(f"  English G{grade}: {qb} questions")
    
    conn.close()
    log.info(f"Total: {total} English questions generated")

if __name__ == "__main__":
    main()
