import os, sys, json, random, logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed-v22")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "app"))
from database import get_db_connection

def math_templates(grade):
    a = random.randint(10, 99) if grade >= 3 else random.randint(1, 20)
    b = random.randint(2, 9)
    c = random.randint(1, 5)
    d = random.randint(1, 9)
    if grade == 1:
        return [
            lambda: (f"{a} + {b} = ?", "B", [f"A.{a+b-1}", f"B.{a+b}", f"C.{a+b+1}", f"D.{a+b+2}"], "加法"),
            lambda: (f"{a} - {b} = ?", "B", [f"A.{a-b-1}", f"B.{a-b}", f"C.{a-b+1}", f"D.{a-b+2}"], "减法"),
            lambda: ("下列哪个数最大？", "C", [f"A.{a}", f"B.{a+1}", f"C.{a+3}", f"D.{a+2}"], "比较大小"),
            lambda: (f"{a} 后面的第2个数是？", "C", [f"A.{a}", f"B.{a+1}", f"C.{a+2}", f"D.{a+3}"], "数的顺序"),
            lambda: (f"{a} + {b} + {c} = ?", "B", [f"A.{a+b+c-1}", f"B.{a+b+c}", f"C.{a+b+c+1}", f"D.{a+b+c+2}"], "连加"),
        ]
    elif grade == 2:
        return [
            lambda: (f"{a} x {b} = ?", "B", [f"A.{a*b-1}", f"B.{a*b}", f"C.{a*b+1}", f"D.{a*b+b}"], "乘法"),
            lambda: (f"{a*b} / {b} = ?", "B", [f"A.{a-1}", f"B.{a}", f"C.{a+1}", f"D.{a+2}"], "除法"),
            lambda: (f"{a} + {b} + {c} = ?", "B", [f"A.{a+b+c-1}", f"B.{a+b+c}", f"C.{a+b+c+1}", f"D.{a+b+c+2}"], "连加"),
            lambda: ("下列哪个算式的结果最大？", "B", [f"A.{a}+{b}={a+b}", f"B.{a}x{b}={a*b}", f"C.{a}-{b}={a-b}", f"D.{a}/{b}={a//b if b else 0}"], "算式比较"),
            lambda: (f"{a}0 + {b}0 = ?", "B", [f"A.{a+b}0", f"B.{a}{b}0", f"C.{a+b}00", f"D.{a}{b}0"], "整十加法"),
        ]
    elif grade == 3:
        a = random.randint(10, 99)
        return [
            lambda: (f"{a}0 x {b}0 = ?", "B", [f"A.{a*b*10}", f"B.{a*b*100}", f"C.{a*b*1000}", f"D.{a*b}"], "整十乘法"),
            lambda: (f"{a} x {b} = ?", "C", [f"A.{a*b-10}", f"B.{a*b-5}", f"C.{a*b}", f"D.{a*b+10}"], "两位数乘法"),
            lambda: (f"长方形长{a}cm，宽{b}cm，面积是？", "B", [f"A.{a+b}cm2", f"B.{a*b}cm2", f"C.{2*(a+b)}cm2", f"D.{a*b*2}cm2"], "长方形面积"),
            lambda: (f"正方形边长{a}cm，周长是？", "C", [f"A.{a}cm", f"B.{a*2}cm", f"C.{a*4}cm", f"D.{a*a}cm"], "正方形周长"),
            lambda: (f"{a}米 = ()厘米", "B", [f"A.{a*10}", f"B.{a*100}", f"C.{a*1000}", f"D.{a}"], "单位换算"),
        ]
    elif grade == 4:
        return [
            lambda: (f"{a} x {b}0 = ?", "B", [f"A.{a*b*10-10}", f"B.{a*b*10}", f"C.{a*b*10+10}", f"D.{a*b*10+b}"], "三位数乘法"),
            lambda: (f"{a*10}0 / {b*10} = ?", "B", [f"A.{a*100//(b*10)-1}", f"B.{a*100//(b*10)}", f"C.{a*100//(b*10)+1}", f"D.{a*100//(b*10)+2}"], "三位数除法"),
            lambda: (f"一个角是{a*b}度，这是什么角？", "B", ["A.锐角", "B.直角", "C.钝角", "D.平角"], "角的认识"),
            lambda: (f"{a}.{b} + {c}.{d} = ?", "B", [f"A.{a+c}.{b+d+1}", f"B.{a+c}.{b+d}", f"C.{a+c+1}.{b+d}", f"D.{a+c}.{b+d-1}"], "小数加法"),
            lambda: (f"{a}0 x {b} = ?", "B", [f"A.{a*b*10-1}", f"B.{a*b*10}", f"C.{a*b*10+1}", f"D.{a*b*10+b}"], "整十乘法"),
        ]
    elif grade == 5:
        return [
            lambda: (f"{a}/{b} + {c}/{b} = ?", "B", [f"A.{a+c}/{b+1}", f"B.{a+c}/{b}", f"C.{a+c}/{b-1}", f"D.{a+c+1}/{b}"], "同分母分数加法"),
            lambda: (f"三角形底{a}cm，高{b}cm，面积是？", "B", [f"A.{a*b}cm2", f"B.{a*b//2}cm2", f"C.{a*b*2}cm2", f"D.{a+b}cm2"], "三角形面积"),
            lambda: (f"x + {a} = {a+b}，x = ?", "B", [f"A.{b-1}", f"B.{b}", f"C.{b+1}", f"D.{b+2}"], "简单方程"),
            lambda: (f"{a}.{b} x {c} = ?", "B", [f"A.{int(a*b*c/10)-1}", f"B.{int(a*b*c/10)}", f"C.{int(a*b*c/10)+1}", f"D.{int(a*b*c/10)+2}"], "小数乘法"),
            lambda: (f"{a}/{b} = ()/{b*c}", "B", [f"A.{a*c-1}", f"B.{a*c}", f"C.{a*c+1}", f"D.{a*c+2}"], "分数的基本性质"),
        ]
    elif grade == 6:
        return [
            lambda: (f"{a}/{b} x {c}/{d} = ?", "B", [f"A.{a*c}/{b+d}", f"B.{a*c}/{b*d}", f"C.{a+c}/{b*d}", f"D.{a*c}/{b*d+1}"], "分数乘法"),
            lambda: (f"{a}/{b} / {c}/{d} = ?", "B", [f"A.{a*d}/{b+c}", f"B.{a*d}/{b*c}", f"C.{a+c}/{b*d}", f"D.{a*d+1}/{b*c}"], "分数除法"),
            lambda: (f"{a}:{b} = {c}:？", "B", [f"A.{b*c//a-1}", f"B.{b*c//a}", f"C.{b*c//a+1}", f"D.{b*c//a+2}"], "比例"),
            lambda: (f"长方体长{a}cm，宽{b}cm，高{c}cm，体积是？", "B", [f"A.{a+b+c}cm3", f"B.{a*b*c}cm3", f"C.{a*b+c}cm3", f"D.{a+b*c}cm3"], "长方体体积"),
            lambda: (f"{a}% = ()/100", "B", [f"A.{a-1}", f"B.{a}", f"C.{a+1}", f"D.{a*10}"], "百分数"),
        ]
    return []

def chinese_templates(grade):
    words_map = {
        1: ["大", "小", "上", "下", "天", "地", "日", "月", "水", "火"],
        2: ["春", "夏", "秋", "冬", "花", "草", "树", "木", "鸟", "鱼"],
        3: ["杨", "柳", "松", "柏", "桃", "李", "梅", "兰", "竹", "菊"],
        4: ["江", "河", "湖", "海", "波", "浪", "涛", "潮", "溪", "泉"],
        5: ["仁", "义", "礼", "智", "信", "忠", "孝", "廉", "耻", "勇"],
        6: ["乾", "坤", "阴", "阳", "道", "德", "理", "气", "心", "性"],
    }
    words = words_map.get(grade, words_map[1])
    word = random.choice(words)
    strokes = {"大": 3, "小": 3, "上": 3, "下": 3, "天": 4, "地": 6, "日": 4, "月": 4, "水": 4, "火": 4,
               "春": 9, "夏": 10, "秋": 9, "冬": 5, "花": 7, "草": 9, "杨": 7, "柳": 9, "松": 8, "柏": 9,
               "桃": 10, "李": 7, "梅": 11, "兰": 5, "竹": 6, "菊": 11, "江": 6, "河": 8, "湖": 12, "海": 10,
               "仁": 4, "义": 3, "礼": 5, "智": 12}
    s = strokes.get(word, random.randint(3, 12))
    radicals = {"大": "大", "小": "小", "上": "一", "下": "一", "天": "大", "地": "土", "日": "日", "月": "月",
                "水": "水", "火": "火", "春": "日", "夏": "夂", "秋": "禾", "冬": "冫", "花": "艹", "草": "艹",
                "杨": "木", "柳": "木", "松": "木", "柏": "木", "桃": "木", "李": "木", "梅": "木", "兰": "艹",
                "竹": "竹", "菊": "艹", "江": "氵", "河": "氵"}
    r = radicals.get(word, "一")
    antonyms = {"大": "小", "上": "下", "天": "地", "日": "月", "水": "火", "春": "秋", "夏": "冬"}
    a = antonyms.get(word, "未知")
    idioms = ["画蛇添足", "守株待兔", "掩耳盗铃", "刻舟求剑", "亡羊补牢",
              "完璧归赵", "负荆请罪", "纸上谈兵", "卧薪尝胆", "破釜沉舟",
              "入木三分", "闻鸡起舞", "凿壁偷光", "悬梁刺股", "程门立雪"]
    idiom = random.choice(idioms)
    return [
        lambda: (f'"{word}"字共有几画？', "B", [f"A.{s-1}画", f"B.{s}画", f"C.{s+1}画", f"D.{s+2}画"], "笔画数"),
        lambda: (f'"{word}"字的部首是？', "B", [f"A.一", f"B.{r}", f"C.丨", f"D.丿"], "部首"),
        lambda: (f'"{word}"的反义词是？', "B", [f"A.甲", f"B.{a}", f"C.乙", f"D.丙"], "反义词"),
        lambda: ("下列哪个成语是正确的？", "B", [f"A.画蛇填足", f"B.{idiom}", f"C.守猪待兔", f"D.掩耳盗玲"], "成语辨析"),
        lambda: (f'"{idiom}"的意思是？', "B", ["A.形容事物不好", "B.形容做事多此一举", "C.形容很大", "D.形容很小"], "成语解释"),
    ]

def english_templates(grade):
    words = {
        1: [("apple", "苹果"), ("cat", "猫"), ("dog", "狗"), ("book", "书"), ("pen", "笔")],
        2: [("teacher", "老师"), ("student", "学生"), ("school", "学校"), ("friend", "朋友")],
        3: [("computer", "电脑"), ("beautiful", "美丽"), ("important", "重要")],
        4: [("environment", "环境"), ("technology", "技术")],
        5: [("knowledge", "知识"), ("experience", "经历")],
        6: [("philosophy", "哲学"), ("literature", "文学")],
    }
    word_list = words.get(grade, words[1])
    word, meaning = random.choice(word_list)
    past = {"go": "went", "eat": "ate", "see": "saw", "do": "did", "have": "had"}
    past_tense = past.get(word, word + "ed")
    return [
        lambda: (f"{word} 是什么意思？", "B", [f"A.苹果" if meaning != "苹果" else "香蕉", f"B.{meaning}", f"C.红色" if meaning != "红色" else "蓝色", f"D.大" if meaning != "大" else "小"], "单词认知"),
        lambda: ("How are you?", "A", ["A.I am fine", "B.Thank you", "C.Goodbye", "D.Hello"], "日常问候"),
        lambda: ("Good morning 是什么意思？", "B", ["A.晚安", "B.早上好", "C.下午好", "D.你好"], "日常用语"),
        lambda: ("I ___ a student. 填什么？", "A", ["A.am", "B.is", "C.are", "D.be"], "be动词"),
        lambda: (f"{word} 的过去式是？", "B", [f"A.{word}", f"B.{past_tense}", f"C.{word}ing", f"D.{word}s"], "过去式"),
    ]

def main():
    conn = get_db_connection()
    conn.execute("DELETE FROM question_bank WHERE source LIKE 'seed%'")
    conn.commit()
    kp_rows = conn.execute("SELECT * FROM knowledge_points ORDER BY subject, grade, sort_order").fetchall()
    log.info(f"知识点总数: {len(kp_rows)}")
    kp_by_sg = defaultdict(list)
    for kp in kp_rows:
        kp_by_sg[(kp["subject"], kp["grade"])].append(dict(kp))
    total = 0
    for (subject, grade), kps in sorted(kp_by_sg.items()):
        if subject == "math": tfs = math_templates(grade)
        elif subject == "chinese": tfs = chinese_templates(grade)
        elif subject == "english": tfs = english_templates(grade)
        else: continue
        if not tfs:
            log.warning(f"无模板: {subject} G{grade}")
            continue
        log.info(f"{subject} G{grade}: {len(kps)} kps, {len(tfs)} templates")
        for i, kp in enumerate(kps):
            try:
                qt, correct, opts, exp = tfs[i % len(tfs)]()
                conn.execute("INSERT INTO question_bank (kp_id, subject, grade, chapter, difficulty, question_text, options, correct_answer, explanation, source) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (kp["id"], subject, grade, kp.get("chapter",""), random.choice([1,2]), qt, json.dumps(opts, ensure_ascii=False), correct, exp, "seed_v22"))
                total += 1
            except Exception as e:
                log.debug(f"FAIL: {e}")
    conn.commit()
    conn.close()
    log.info(f"v2.2 done: {total} questions")

if __name__ == "__main__":
    main()
