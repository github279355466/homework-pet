"""Fix main.py: skin prices, math quiz API, remove platform code"""
import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# === 1. Add price field to each skin in PET_SKINS ===
# Add 'price': 50 to each skin after 'desc'
content = content.replace(
    """'icon': '\U0001f432', 'desc': '经典的紫色到金色渐变'},""",
    """'icon': '\U0001f432', 'desc': '经典的紫色到金色渐变', 'price': 0},"""
)
content = content.replace(
    """'icon': '\U0001f525', 'desc': '热情似火的红色小龙'},""",
    """'icon': '\U0001f525', 'desc': '热情似火的红色小龙', 'price': 50},"""
)
content = content.replace(
    """'icon': '❄️', 'desc': '冰冰凉凉的冰雪小龙'},""",
    """'icon': '❄️', 'desc': '冰冰凉凉的冰雪小龙', 'price': 50},"""
)
content = content.replace(
    """'icon': '\U0001f451', 'desc': '闪闪发光的黄金小龙'},""",
    """'icon': '\U0001f451', 'desc': '闪闪发光的黄金小龙', 'price': 50},"""
)
content = content.replace(
    """'icon': '\U0001f33f', 'desc': '充满生机的森林小龙'},""",
    """'icon': '\U0001f33f', 'desc': '充满生机的森林小龙', 'price': 50},"""
)

# Also update the GET /api/pet/skins to use skin price from PET_SKINS
content = content.replace(
    """'price': 0 if skin_id == 'default' else 50,""",
    """'price': skin.get('price', 0),"""
)

# === 2. Replace guess-number with math-quiz endpoints ===
old_guess = '''# ===== v3.2 猜数字互动游戏 =====

@app.post("/api/pet/guess-number")
async def pet_guess_number(guess: int = Form(...)):
    """猜数字游戏（1-10）：猜对得龙币，猜错没关系"""
    if guess < 1 or guess > 10:
        return {"success": False, "message": "请输入1-10之间的数字"}
    conn = get_db_connection()
    current_time = get_current_time()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    if pet['status'] == 'sleeping':
        conn.close()
        return {"success": False, "message": "嘘...小龙正在睡觉"}
    target = random.randint(1, 10)
    bond = dict(pet).get('bond', 50)
    if guess == target:
        new_coins = add_coins(conn, 5, 'guess_number', f'猜数字猜对了！数字是{target}')
        new_mood = min(100, pet['mood'] + 10)
        new_bond = min(100, bond + 3)
        bubble = random.choice(["哇！猜对了！你好聪明！\U0001f389", f"没错！就是{target}！太厉害了！", "你太厉害啦！\U0001f973"])
    else:
        new_coins = pet['coins']
        new_mood = min(100, pet['mood'] + 3)
        new_bond = min(100, bond + 1)
        bubble = random.choice(["不对哦～再想想！\U0001f914", "差一点点！再来！", "下次一定能猜对！\U0001f4aa"])
    conn.execute("UPDATE pet SET mood = ?, bond = ?, updated_at = ? WHERE id = 1",
                 (new_mood, new_bond, current_time.isoformat()))
    conn.execute("""
        INSERT INTO coin_transactions (type, source, amount, balance_after, description)
        VALUES ('earn', 'guess_number', 0, (SELECT coins FROM pet WHERE id = 1), ?)
    """, (f'猜数字:猜{guess}答案{target}',))
    conn.commit()
    conn.close()
    return {
        "success": True,
        "target": target,
        "guess": guess,
        "correct": guess == target,
        "new_coins": new_coins,
        "mood": new_mood,
        "bond": new_bond,
        "bubble": bubble,
    }'''

new_math_quiz = '''# ===== v3.2 算术题互动游戏 =====

@app.post("/api/pet/math-quiz")
async def start_math_quiz():
    """生成算术题（100以内加减法），返回题目和选项"""
    conn = get_db_connection()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    conn.close()
    if pet['status'] == 'sleeping':
        return {"success": False, "message": "嘘...小龙正在睡觉"}
    # 随机生成加减法
    if random.random() < 0.5:
        a = random.randint(10, 99)
        b = random.randint(1, min(99 - a, a))
        op = '+'
        answer = a + b
    else:
        a = random.randint(20, 99)
        b = random.randint(1, a)
        op = '-'
        answer = a - b
    question = f"{a} {op} {b} = ?"
    # 生成4个选项（1个正确答案 + 3个干扰项）
    options = [answer]
    while len(options) < 4:
        distractor = answer + random.randint(-15, 15)
        if distractor >= 0 and distractor != answer and distractor not in options:
            options.append(distractor)
    random.shuffle(options)
    return {
        "success": True,
        "question": question,
        "options": options,
        "correct_answer": answer,
    }

@app.post("/api/pet/math-quiz/answer")
async def answer_math_quiz(answer: int = Form(...)):
    """检查算术题答案"""
    conn = get_db_connection()
    current_time = get_current_time()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    if pet['status'] == 'sleeping':
        conn.close()
        return {"success": False, "message": "嘘...小龙正在睡觉"}
    pet_dict = dict(pet)
    bond = pet_dict.get('bond', 50)
    # answer=0 表示答错（前端校验后传0），否则前端已校验正确才提交
    # 这里直接奖励（前端已做答案比对）
    new_coins = add_coins(conn, 10, 'math_quiz', '算术题答对啦！+10龙币')
    new_mood = min(100, pet['mood'] + 5)
    new_bond = min(100, bond + 2)
    bubble = random.choice(["答对啦！数学小天才！🧮", "完全正确！你好厉害！🎉", "太棒了！小龙为你骄傲！😎"])
    conn.execute("UPDATE pet SET mood = ?, bond = ?, updated_at = ? WHERE id = 1",
                 (new_mood, new_bond, current_time.isoformat()))
    conn.commit()
    conn.close()
    return {
        "success": True,
        "correct": True,
        "new_coins": new_coins,
        "mood": new_mood,
        "bond": new_bond,
        "bubble": bubble,
    }'''

if old_guess in content:
    content = content.replace(old_guess, new_math_quiz)
    print("Replaced guess-number with math-quiz")
else:
    print("WARNING: Could not find old guess-number code")

# === 3. Remove platform code ===
# Find the platform section and remove everything from # ===== v3.2 学习平台联动 to the end of the last platform endpoint
platform_start = content.find("\n# ===== v3.2 学习平台联动")
if platform_start > 0:
    # Find the next section marker or end of platform code
    after_platform = content.find("\n# ===== 启动", platform_start)
    if after_platform > 0:
        content = content[:platform_start] + content[after_platform:]
        print("Removed platform code section")
    else:
        print("WARNING: Could not find end of platform section")
else:
    print("WARNING: Could not find platform code start")

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("main.py fixes applied successfully!")
