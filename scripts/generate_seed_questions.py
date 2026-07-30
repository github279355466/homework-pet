#!/usr/bin/env python3
"""
本地种子题库生成器
不依赖 Hermes API，基于模板生成基础选择题
"""
import os
import sys
import json
import random
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("seed-questions")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "app"))
from database import get_db_connection

# 按学科/年级的模板题库
SEED_TEMPLATES = {
    "math": {
        1: [
            ("{a} + {b} = ?", "B", ["A.{a+b-1}", "B.{a+b}", "C.{a+b+1}", "D.{a+b+2}"], "加法计算"),
            ("{a} - {b} = ?", "C", ["A.{a-b-1}", "B.{a-b+1}", "C.{a-b}", "D.{a-b+2}"], "减法计算"),
            ("下列哪个数最大？", "C", ["A.{min(a,b)}", "B.{min(a,b)+2}", "C.{max(a,b)}", "D.{max(a,b)+3}"], "比较大小"),
            ("{a} 后面的第2个数是？", "C", ["A.{a}", "B.{a+1}", "C.{a+2}", "D.{a+3}"], "数的顺序"),
            ("小明有{a}个苹果，又买了{b}个，一共有？", "B", ["A.{a+b-1}", "B.{a+b}", "C.{a+b+1}", "D.{a-b}"], "加法应用"),
        ],
        2: [
            ("{a} * {b} = ?", "B", ["A.{a*b-1}", "B.{a*b}", "C.{a*b+1}", "D.{a*b+b}"], "乘法计算"),
            ("{a} / {b} = ?", "C", ["A.{a//b-1}", "B.{a//b+1}", "C.{a//b}", "D.{a//b+2}"], "除法计算"),
            ("{a} + {b} + {c} = ?", "B", ["A.{a+b+c-1}", "B.{a+b+c}", "C.{a+b+c+1}", "D.{a+b+c+2}"], "连加计算"),
            ("下列哪个算式的结果最大？", "B", ["A.{a}+{b}", "B.{a}*{b}", "C.{a}-{b}", "D.{a}/{b}"], "算式比较"),
            ("{a}00 + {b}0 = ?", "B", ["A.{a}{b}0", "B.{a}00+{b}0={a}{b}0", "C.{a}{b}00", "D.{a+b}00"], "整百整十加法"),
        ],
        3: [
            ("{a} * {b} = ?", "B", ["A.{a*b-10}", "B.{a*b}", "C.{a*b+10}", "D.{a*b+b}"], "两位数乘法"),
            ("{a}0 * {b}0 = ?", "B", ["A.{a*b*10}", "B.{a*b*100}", "C.{a*b*1000}", "D.{a*b}"], "整十乘法"),
            ("长方形长{a}cm宽{b}cm，面积是？", "B", ["A.{a+b}", "B.{a*b}", "C.{2*(a+b)}", "D.{a*b*2}"], "长方形面积"),
            ("{a}米 = ?厘米", "B", ["A.{a*10}", "B.{a*100}", "C.{a*1000}", "D.{a}"], "单位换算"),
            ("把绳子对折{a}次后每段是原来的？", "C", ["A.1/{a}", "B.1/{2*a}", "C.1/{2**a}", "D.1/{a**2}"], "分数初步"),
        ],
    },
    "chinese": {
        1: [
            ("「数」字的读音是？", "A", ["A.shu3", "B.shuo1", "C.hua4", "D.yu3"], "字音辨析"),
            ("「大」字共有几画？", "B", ["A.2画", "B.3画", "C.4画", "D.5画"], "笔画数"),
            ("下列哪个词语表示颜色？", "A", ["A.红色", "B.桌子", "C.跑步", "D.吃饭"], "词语分类"),
            ("「上」的反义词是？", "B", ["A.前", "B.下", "C.左", "D.右"], "反义词"),
            ("哪个字可以和「天」组成词语？", "B", ["A.天+上", "B.天+气", "C.天+下", "D.天+地"], "组词"),
        ],
        2: [
            ("「春」字的部首是？", "A", ["A.日", "B.木", "C.一", "D.人"], "部首识别"),
            ("哪个词语描写春天？", "A", ["A.春暖花开", "B.烈日炎炎", "C.秋高气爽", "D.冰天雪地"], "词语理解"),
            ("「床前明月光」的作者是？", "B", ["A.杜甫", "B.李白", "C.白居易", "D.王维"], "古诗作者"),
            ("哪个读音是正确的？", "A", ["A.xue2 xiao4", "B.xiao4 xue2", "C.xue4 xiao2", "D.xiao2 xue4"], "拼音辨析"),
            ("「美丽的」后面可以接？", "A", ["A.花朵", "B.跑步", "C.吃饭", "D.写字"], "词语搭配"),
        ],
    },
    "english": {
        1: [
            ("Apple 是什么意思？", "B", ["A.香蕉", "B.苹果", "C.橙子", "D.葡萄"], "单词认知"),
            ("How are you?", "A", ["A.I'm fine", "B.Thank you", "C.Goodbye", "D.Hello"], "情景对话"),
            ("Cat 是什么动物？", "C", ["A.狗", "B.鸟", "C.猫", "D.鱼"], "单词认知"),
            ("哪个是颜色单词？", "B", ["A.dog", "B.red", "C.book", "D.pen"], "单词分类"),
            ("Good morning 是什么意思？", "B", ["A.晚安", "B.早上好", "C.下午好", "D.你好"], "日常用语"),
        ],
        3: [
            ("What's your name?", "B", ["A.How are you?", "B.What's your name?", "C.How old are you?", "D.Where are you?"], "日常对话"),
            ("I ___ a student. 填什么？", "A", ["A.am", "B.is", "C.are", "D.be"], "be动词"),
            ("哪个单词拼写正确？", "C", ["A.recieve", "B.belive", "C.receive", "D.wierd"], "单词拼写"),
            ("There ___ a book. 填什么？", "B", ["A.am", "B.is", "C.are", "D.be"], "there be"),
            ("She ___ to school every day. 填什么？", "B", ["A.go", "B.goes", "C.going", "D.went"], "一般现在时"),
        ],
    },
}

def generate_seed_questions():
    """为每个知识点生成种子题目"""
    conn = get_db_connection()
    
    # 获取所有知识点
    kp_rows = conn.execute("SELECT * FROM knowledge_points ORDER BY subject, grade, sort_order").fetchall()
    logger.info(f"知识点总数: {len(kp_rows)}")
    
    total_generated = 0
    total_skipped = 0
    
    for kp in kp_rows:
        kp = dict(kp)
        subject = kp['subject']
        grade = kp['grade']
        kp_id = kp['id']
        
        # 检查是否已有足够题目
        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM question_bank WHERE kp_id = ?", (kp_id,)
        ).fetchone()['cnt']
        
        if existing >= 5:
            total_skipped += 1
            continue
        
        # 获取模板
        subject_templates = SEED_TEMPLATES.get(subject, {})
        templates = subject_templates.get(grade)
        
        if not templates:
            # 使用相近年级
            for g in [grade-1, grade+1, grade-2, grade+2, 1]:
                if g in subject_templates:
                    templates = subject_templates[g]
                    break
        
        if not templates:
            continue
        
        # 生成 5 题
        questions_to_generate = min(5, len(templates))
        random.shuffle(templates)
        
        for i in range(questions_to_generate):
            template = templates[i]
            question_tmpl, correct_label, options_tmpl, knowledge = template
            
            a = random.randint(2, 20)
            b = random.randint(2, 10)
            c = random.randint(1, 5)
            
            try:
                question_text = question_tmpl.format(a=a, b=b, c=c)
                
                options = []
                for opt in options_tmpl:
                    formatted = opt.format(a=a, b=b, c=c)
                    options.append(formatted)
                
                conn.execute("""
                    INSERT INTO question_bank
                    (kp_id, subject, grade, chapter, difficulty, question_text, options, correct_answer, explanation, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    kp_id, subject, grade, kp.get('chapter', ''),
                    random.choice([1, 2]),
                    question_text,
                    json.dumps(options, ensure_ascii=False),
                    correct_label,
                    f"{knowledge}: {question_text}",
                    'seed',
                ))
                
                total_generated += 1
            except Exception as e:
                logger.debug(f"生成题目失败 {kp_id}: {e}")
                continue
    
    conn.commit()
    conn.close()
    
    logger.info(f"种子题库生成完成: 新增 {total_generated} 题, 跳过 {total_skipped} 个已有知识点")
    return total_generated

if __name__ == "__main__":
    generate_seed_questions()
