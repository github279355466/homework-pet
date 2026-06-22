#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实现7个新功能的一体化脚本"""

import re

# ===== 读取文件 =====
with open('main.py', 'r', encoding='utf-8') as f:
    main_content = f.read()

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

# ============================================================
# FEATURE 1: 宠物改名功能
# ============================================================

rename_endpoint = '''
@app.post("/api/pet/rename")
async def rename_pet(name: str = Form(...)):
    """修改宠物名字"""
    name = name.strip()
    if not name or len(name) > 20:
        return {"success": False, "message": "名字长度需在1-20个字符之间"}
    conn = get_db_connection()
    conn.execute("UPDATE pet SET name = ?, updated_at = ? WHERE id = 1",
                 (name, get_current_time().isoformat()))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"小龙的新名字「{name}」已生效！", "name": name}
'''

# 在 pet_interact 后面插入
insert_pos = main_content.find('@app.get("/api/tasks")')
if rename_endpoint not in main_content:
    main_content = main_content[:insert_pos] + rename_endpoint + '\n' + main_content[insert_pos:]

# ============================================================
# FEATURE 3: 真实实时衰减（每小时衰减，取代每日一次）
# ============================================================

old_decay = '''    # 每日衰减（只执行一次，通过 last_decay_date 控制）
    if pet_dict['status'] != 'sleeping' and pet_dict.get('last_decay_date') != today:
        # 中衰减：hunger -8, mood -5, bond -6（每天一次）
        # 2-3天不互动能感觉到变化，一周不玩 bond 从50降到约8
        conn.execute("""
            UPDATE pet SET hunger = max(0, hunger - 8), mood = max(0, mood - 5),
                bond = max(0, bond - 6), last_decay_date = ?
            WHERE id = 1
        """, (today,))
        logger.info(f"[scheduler] 每日衰减执行: hunger-8, mood-5, bond-6")'''

new_decay = '''    # 实时衰减（每小时衰减一次，通过 last_decay_date 跟踪上次衰减时间）
    if pet_dict['status'] != 'sleeping':
        # 检查上次衰减时间，如果超过1小时则执行
        last_decay = pet_dict.get('last_decay_date')
        should_decay = False
        if last_decay is None:
            should_decay = True
        else:
            try:
                if last_decay.endswith('+00:00') or '+' in last_decay:
                    from datetime import timezone
                    decay_time = datetime.fromisoformat(last_decay)
                    if decay_time.tzinfo is None:
                        decay_time = decay_time.replace(tzinfo=timezone.utc)
                    decay_time = decay_time.astimezone(tz)
                else:
                    decay_time = datetime.fromisoformat(last_decay)
                    if decay_time.tzinfo is None:
                        decay_time = tz.localize(decay_time)
                hours_diff = (current_time - decay_time).total_seconds() / 3600
                should_decay = hours_diff >= 1
            except Exception:
                should_decay = True

        if should_decay:
            # 每小时衰减：保持每天总量和原来一致（约24小时 = 原来每天）
            # hunger: -0.33/h, mood: -0.2/h, bond: -0.25/h
            conn.execute("""
                UPDATE pet SET hunger = max(0, hunger - 1), mood = max(0, mood - 1),
                    bond = max(0, bond - 1), last_decay_date = ?
                WHERE id = 1
            """, (current_time.isoformat(),))
            logger.info(f"[scheduler] 实时衰减执行: hunger-1, mood-1, bond-1")'''

main_content = main_content.replace(old_decay, new_decay)

# ============================================================
# FEATURE 4: 丰富情绪系统（修改 get_pet_mood）
# ============================================================

old_mood_func = '''@app.get("/api/pet/mood")
async def get_pet_mood():
    """获取宠物心情状态（前端定时轮询用）"""
    conn = get_db_connection()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    conn.close()
    if not pet:
        return {"error": "宠物不存在"}

    pet_dict = dict(pet)
    hunger = pet_dict['hunger']
    mood = pet_dict['mood']
    bond = pet_dict.get('bond', 50)
    status = pet_dict['status']

    # 气泡文案逻辑
    bubble = None
    bubble_type = None  #撒娇/躲藏/普通

    if status == 'sleeping':
        bubble = "zzZ... 💤"
        bubble_type = "sleeping"
    elif hunger < 20:
        bubble = random.choice(["好饿呀...想吃东西 😫", "肚子咕咕叫～", "有零食吗..."])
        bubble_type = "begging"
    elif mood < 20:
        bubble = random.choice(["哼...不理你了 😤", "好无聊啊", "人家不开心..."])
        bubble_type = "pouting"
    elif bond < 20:
        bubble = random.choice(["你...你都不理我 😢", "好想你啊...", "你是不是忘了我？"])
        bubble_type = "hiding"
    elif bond < 40:
        bubble = random.choice(["...哼", "你来了啊", "有点想你哦"])
        bubble_type = "shy"
    elif hunger > 80 and mood > 80 and bond > 80:
        bubble = random.choice(["今天好开心！😊", "最喜欢和你在一起啦～", "嘿嘿嘿～", "你最好啦！💕"])
        bubble_type = "happy"
    elif hunger < 50:
        bubble = random.choice(["有点饿了～", "想吃东西...", "主人～喂我～"])
        bubble_type = "begging"
    else:
        # 正常随机气泡
        bubble = random.choice(["嗯？", "干嘛呀～", "嘿嘿", "无聊...", "玩会儿嘛！"])
        bubble_type = "normal"

    return {
        "hunger": hunger,
        "mood": mood,
        "bond": bond,
        "status": status,
        "bubble": bubble,
        "bubble_type": bubble_type,
    }'''

new_mood_func = '''@app.get("/api/pet/mood")
async def get_pet_mood():
    """获取宠物心情状态（前端定时轮询用）v3.2 丰富情绪"""
    conn = get_db_connection()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    conn.close()
    if not pet:
        return {"error": "宠物不存在"}

    pet_dict = dict(pet)
    hunger = pet_dict['hunger']
    mood = pet_dict['mood']
    bond = pet_dict.get('bond', 50)
    exp = pet_dict['exp']
    status = pet_dict['status']
    stage = calculate_evolution_stage(exp)

    bubble = None
    bubble_type = None

    if status == 'sleeping':
        bubble = "zzZ... 💤"
        bubble_type = "sleeping"
    elif hunger < 10 or mood < 5:
        bubble = random.choice(["😤 气死我啦！", "🔥 不理你了！", "哼！哄不好了！", "我要生气了哦！"])
        bubble_type = "angry"
    elif mood < 15:
        bubble = random.choice(["😢 呜呜...好委屈", "🥺 你都不在乎我", "人家好伤心...", "眼泪止不住了..."])
        bubble_type = "wronged"
    elif hunger < 20:
        bubble = random.choice(["好饿呀...想吃东西 😫", "肚子咕咕叫～", "有零食吗...", "饿得走不动了～"])
        bubble_type = "begging"
    elif mood < 30:
        bubble = random.choice(["哼...不开心 😤", "好无聊啊", "人家不开心...", "想要人陪..."])
        bubble_type = "pouting"
    elif bond < 15:
        bubble = random.choice(["你...你都不理我 😢", "好想你啊...", "你是不是忘了我？", "我好孤单..."])
        bubble_type = "hiding"
    elif bond < 35:
        bubble = random.choice(["...哼", "你来了啊", "有点想你哦", "今天怎么不理我～"])
        bubble_type = "shy"
    elif hunger > 90 and mood > 90 and bond > 90:
        bubble = random.choice(["🦚 本龙天下第一！", "嘻嘻我超棒！", "有没有觉得我很厉害？", "✨ 闪耀登场！"])
        bubble_type = "proud"
    elif hunger > 80 and mood > 80 and bond > 80:
        bubble = random.choice(["今天好开心！😊", "最喜欢和你在一起啦～", "嘿嘿嘿～", "你最好啦！💕", "好幸福呀～"])
        bubble_type = "happy"
    elif hunger < 45:
        bubble = random.choice(["有点饿了～", "想吃东西...", "主人～喂我～", "什么时候开饭？"])
        bubble_type = "begging"
    elif mood < 50:
        bubble = random.choice(["有点小郁闷...", "陪我玩会儿嘛", "好无聊啊～", "发呆中..."])
        bubble_type = "pouting"
    elif bond < 60:
        bubble = random.choice(["我们是不是好朋友？", "多陪陪我嘛～", "你在这里我就安心"])
        bubble_type = "shy"
    else:
        normal_bubbles = [
            "嗯？", "干嘛呀～", "嘿嘿", "无聊...", "玩会儿嘛！",
            "今天天气真好", "你有没有想我？", "猜猜我在想什么？",
            "嘿嘿嘿", "好想出去玩～", "你今天开心吗？"
        ]
        bubble = random.choice(normal_bubbles)
        bubble_type = "normal"

    return {
        "hunger": hunger,
        "mood": mood,
        "bond": bond,
        "status": status,
        "bubble": bubble,
        "bubble_type": bubble_type,
        "stage": stage,
    }'''

main_content = main_content.replace(old_mood_func, new_mood_func)

# ============================================================
# FEATURE 5: 提前完成奖励（放学1小时内额外龙币）
# ============================================================

old_bonus_section = '''    # 21点前额外奖励
    bonus_mood = 20 if current_time.hour < 21 else 0
    new_mood = min(100, new_mood + bonus_mood)'''

new_bonus_section = '''    # 21点前额外奖励
    bonus_mood = 20 if current_time.hour < 21 else 0
    new_mood = min(100, new_mood + bonus_mood)

    # v3.2 放学1小时内完成额外龙币奖励
    early_bird_bonus = 0
    try:
        school_end = conn.execute("SELECT value FROM parent_settings WHERE key = 'school_end_time'").fetchone()
        school_end_hour = int(school_end['value'].split(':')[0]) if school_end else 16
    except Exception:
        school_end_hour = 16
    if school_end_hour <= current_time.hour < school_end_hour + 1:
        early_bird_bonus = coins_reward
        new_coins = add_coins(conn, early_bird_bonus, 'early_bird', f'放学1小时内完成{subject}，额外奖励！')
        logger.info(f"[task/complete] 提前完成奖励: subject={subject}, bonus={early_bird_bonus}")'''

main_content = main_content.replace(old_bonus_section, new_bonus_section)

old_return_line = '            "challenge_bonus": challenge_bonus,'
new_return_line = '            "challenge_bonus": challenge_bonus,\n            "early_bird_bonus": early_bird_bonus,'
main_content = main_content.replace(old_return_line, new_return_line)

# ============================================================
# FEATURE 6: 宠物皮肤 + 猜数字 + 平台联动
# ============================================================

# 初始化皮肤系统在PET_SKINS之后
skin_system = '''

# ===== v3.2 宠物皮肤系统 =====

PET_SKINS = {
    'default': {'name': '经典小龙',
        'colors': ['#B388FF', '#69F0AE', '#40C4FF', '#FF8A65', '#FFD740'],
        'bg_gradients': [
            'linear-gradient(135deg, #CE93D8, #B388FF)',
            'linear-gradient(135deg, #A5D6A7, #69F0AE)',
            'linear-gradient(135deg, #80DEEA, #40C4FF)',
            'linear-gradient(135deg, #FFAB91, #FF8A65)',
            'linear-gradient(135deg, #FFF176, #FFD740)',
        ], 'icon': '\U0001F432', 'desc': '经典的紫色到金色渐变'},
    'fire': {'name': '火焰小龙',
        'colors': ['#FF6B6B', '#FF5252', '#FF1744', '#D50000', '#FF6D00'],
        'bg_gradients': [
            'linear-gradient(135deg, #FFCDD2, #FF6B6B)',
            'linear-gradient(135deg, #FFCDD2, #FF5252)',
            'linear-gradient(135deg, #FF8A80, #FF1744)',
            'linear-gradient(135deg, #FF9E80, #D50000)',
            'linear-gradient(135deg, #FFD180, #FF6D00)',
        ], 'icon': '\U0001F525', 'desc': '热情似火的红色小龙'},
    'ice': {'name': '冰雪小龙',
        'colors': ['#80DEEA', '#4DD0E1', '#26C6DA', '#00ACC1', '#0097A7'],
        'bg_gradients': [
            'linear-gradient(135deg, #E0F7FA, #80DEEA)',
            'linear-gradient(135deg, #E0F7FA, #4DD0E1)',
            'linear-gradient(135deg, #B2EBF2, #26C6DA)',
            'linear-gradient(135deg, #80DEEA, #00ACC1)',
            'linear-gradient(135deg, #4DD0E1, #0097A7)',
        ], 'icon': '❄️', 'desc': '冰冰凉凉的冰雪小龙'},
    'gold': {'name': '黄金小龙',
        'colors': ['#FFD740', '#FFC400', '#FFAB00', '#FF8F00', '#FF6F00'],
        'bg_gradients': [
            'linear-gradient(135deg, #FFF8E1, #FFD740)',
            'linear-gradient(135deg, #FFF8E1, #FFC400)',
            'linear-gradient(135deg, #FFECB3, #FFAB00)',
            'linear-gradient(135deg, #FFE082, #FF8F00)',
            'linear-gradient(135deg, #FFD54F, #FF6F00)',
        ], 'icon': '\U0001F451', 'desc': '闪闪发光的黄金小龙'},
    'nature': {'name': '森林小龙',
        'colors': ['#81C784', '#66BB6A', '#4CAF50', '#388E3C', '#2E7D32'],
        'bg_gradients': [
            'linear-gradient(135deg, #E8F5E9, #81C784)',
            'linear-gradient(135deg, #E8F5E9, #66BB6A)',
            'linear-gradient(135deg, #C8E6C9, #4CAF50)',
            'linear-gradient(135deg, #A5D6A7, #388E3C)',
            'linear-gradient(135deg, #81C784, #2E7D32)',
        ], 'icon': '\U0001F33F', 'desc': '充满生机的森林小龙'},
}

@app.get("/api/pet/skins")
async def get_pet_skins():
    """获取所有可用皮肤"""
    conn = get_db_connection()
    current_skin = conn.execute("SELECT value FROM parent_settings WHERE key = 'current_skin'").fetchone()
    current = current_skin['value'] if current_skin else 'default'
    unlocked_row = conn.execute("SELECT value FROM parent_settings WHERE key = 'unlocked_skins'").fetchone()
    conn.close()

    unlocked = set(unlocked_row['value'].split(',')) if unlocked_row and unlocked_row['value'] else {'default'}
    skins = []
    for skin_id, skin in PET_SKINS.items():
        skins.append({
            'id': skin_id,
            'name': skin['name'],
            'icon': skin['icon'],
            'desc': skin['desc'],
            'current': skin_id == current,
            'unlocked': skin_id in unlocked,
            'price': 0 if skin_id == 'default' else 50,
        })
    return {"skins": skins, "current_skin": current}

@app.post("/api/pet/skin/select")
async def select_pet_skin(skin_id: str = Form(...)):
    """选择宠物皮肤"""
    if skin_id not in PET_SKINS:
        return {"success": False, "message": "皮肤不存在"}
    conn = get_db_connection()
    unlocked_row = conn.execute("SELECT value FROM parent_settings WHERE key = 'unlocked_skins'").fetchone()
    unlocked = set(unlocked_row['value'].split(',')) if unlocked_row and unlocked_row['value'] else {'default'}
    if skin_id not in unlocked:
        conn.close()
        return {"success": False, "message": "该皮肤尚未解锁"}
    existing = conn.execute("SELECT key FROM parent_settings WHERE key = 'current_skin'").fetchone()
    if existing:
        conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'current_skin'", (skin_id,))
    else:
        conn.execute("INSERT INTO parent_settings (key, value) VALUES ('current_skin', ?)", (skin_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"已切换为{PET_SKINS[skin_id]['name']}！"}

@app.post("/api/pet/skin/unlock")
async def unlock_pet_skin(skin_id: str = Form(...), price: int = Form(50)):
    """用龙币解锁皮肤"""
    if skin_id not in PET_SKINS or skin_id == 'default':
        return {"success": False, "message": "皮肤不存在或无法解锁"}
    conn = get_db_connection()
    unlocked_row = conn.execute("SELECT value FROM parent_settings WHERE key = 'unlocked_skins'").fetchone()
    unlocked = set(unlocked_row['value'].split(',')) if unlocked_row and unlocked_row['value'] else {'default'}
    if skin_id in unlocked:
        conn.close()
        return {"success": False, "message": "该皮肤已解锁"}
    pet = conn.execute("SELECT coins FROM pet WHERE id = 1").fetchone()
    if pet['coins'] < price:
        conn.close()
        return {"success": False, "message": f"龙币不够，需要{price}龙币"}
    add_coins(conn, -price, 'shop', f'解锁皮肤:{PET_SKINS[skin_id]["name"]}')
    unlocked.add(skin_id)
    new_unlocked = ','.join(sorted(unlocked))
    existing = conn.execute("SELECT key FROM parent_settings WHERE key = 'unlocked_skins'").fetchone()
    if existing:
        conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'unlocked_skins'", (new_unlocked,))
    else:
        conn.execute("INSERT INTO parent_settings (key, value) VALUES ('unlocked_skins', ?)", (new_unlocked,))
    existing_skin = conn.execute("SELECT key FROM parent_settings WHERE key = 'current_skin'").fetchone()
    if existing_skin:
        conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'current_skin'", (skin_id,))
    else:
        conn.execute("INSERT INTO parent_settings (key, value) VALUES ('current_skin', ?)", (skin_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"解锁成功！获得{PET_SKINS[skin_id]['name']}"}

# ===== v3.2 猜数字互动游戏 =====

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
        bubble = random.choice(["哇！猜对了！你好聪明！🎉", f"没错！就是{target}！太厉害了！", "你太厉害啦！🥳"])
    else:
        new_coins = pet['coins']
        new_mood = min(100, pet['mood'] + 3)
        new_bond = min(100, bond + 1)
        bubble = random.choice(["不对哦～再想想！🤔", "差一点点！再来！", "下次一定能猜对！💪"])
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
    }

# ===== v3.2 学习平台联动（模拟） =====

PLATFORM_DATA = {
    'xueersi': {'name': '学而思', 'icon': '📚', 'homework_templates': [
        {'subject': '数学', 'title': '学而思·数学练习', 'exp': 80, 'coins': 8},
        {'subject': '语文', 'title': '学而思·阅读打卡', 'exp': 60, 'coins': 6},
        {'subject': '英语', 'title': '学而思·英语跟读', 'exp': 60, 'coins': 6},
    ]},
    'zuoyebang': {'name': '作业帮', 'icon': '✏️', 'homework_templates': [
        {'subject': '数学', 'title': '作业帮·口算练习', 'exp': 100, 'coins': 10},
        {'subject': '语文', 'title': '作业帮·生字听写', 'exp': 70, 'coins': 7},
        {'subject': '英语', 'title': '作业帮·单词打卡', 'exp': 80, 'coins': 8},
    ]},
    'xiaozao': {'name': '小早启蒙', 'icon': '🌱', 'homework_templates': [
        {'subject': '语文', 'title': '小早·古诗背诵', 'exp': 50, 'coins': 5},
        {'subject': '英语', 'title': '小早·英语儿歌', 'exp': 40, 'coins': 4},
    ]},
}

@app.get("/api/platform/list")
async def get_platforms():
    """获取支持的学习平台列表"""
    platforms = []
    for pid, data in PLATFORM_DATA.items():
        platforms.append({'id': pid, 'name': data['name'], 'icon': data['icon'], 'connected': False})
    return {"platforms": platforms}

@app.post("/api/platform/connect")
async def connect_platform(platform_id: str = Form(...)):
    """模拟连接学习平台"""
    if platform_id not in PLATFORM_DATA:
        return {"success": False, "message": "不支持该平台"}
    platform = PLATFORM_DATA[platform_id]
    return {"success": True, "message": f"已成功连接{platform['name']}！",
            "platform": {'id': platform_id, 'name': platform['name'], 'icon': platform['icon'], 'connected': True}}

@app.get("/api/platform/{platform_id}/homework")
async def get_platform_homework(platform_id: str):
    """获取学习平台的作业列表（模拟数据）"""
    if platform_id not in PLATFORM_DATA:
        return {"success": False, "message": "不支持该平台"}
    platform = PLATFORM_DATA[platform_id]
    import random as rnd
    count = rnd.randint(1, min(3, len(platform['homework_templates'])))
    selected = rnd.sample(platform['homework_templates'], count)
    homeworks = [{'title': item['title'], 'subject': item['subject'],
                  'exp_reward': item['exp'], 'coins_reward': item['coins']} for item in selected]
    return {"success": True, "platform": platform['name'], "homeworks": homeworks}

@app.post("/api/platform/{platform_id}/sync")
async def sync_platform_homework(platform_id: str):
    """同步学习平台作业到今日任务"""
    if platform_id not in PLATFORM_DATA:
        return {"success": False, "message": "不支持该平台"}
    conn = get_db_connection()
    current_time = get_current_time()
    today = current_time.strftime('%Y-%m-%d')
    platform = PLATFORM_DATA[platform_id]
    import random as rnd
    count = rnd.randint(1, min(3, len(platform['homework_templates'])))
    selected = rnd.sample(platform['homework_templates'], count)
    synced = []
    for item in selected:
        existing = conn.execute("SELECT id FROM custom_tasks WHERE subject = ? AND status = 'pending' AND date(created_at) = ?",
                                (item['title'], today)).fetchone()
        if not existing:
            conn.execute("INSERT INTO custom_tasks (subject, category, exp_reward, coins_reward, deadline, status, created_at) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                        (item['title'], item['subject'], item['exp'], item['coins'], today, current_time.isoformat()))
            synced.append(item['title'])
    conn.commit()
    conn.close()
    if synced:
        return {"success": True, "message": f"从{platform['name']}同步了{len(synced)}个作业：{'、'.join(synced)}"}
    else:
        return {"success": True, "message": f"没有新的作业需要同步（今日已同步过）"}
'''

# 在文件末尾的启动代码之前插入
last_import = main_content.find('# ===== 启动 =====')
main_content = main_content[:last_import] + skin_system + '\n' + main_content[last_import:]

# 修改 get_pet_appearance 以支持皮肤
old_get_appearance = '''def get_pet_appearance(exp, status, bond=50):
    """根据经验值和状态获取宠物外观信息"""
    stage = calculate_evolution_stage(exp)
    stage_progress = calculate_stage_progress(exp)

    # 基础状态 emoji（保留给 SVG 加载前的 fallback）
    if status == 'sleeping':
        emoji = '😴'
        status_name = '睡着了'
    elif status == 'sad':
        emoji = '😢'
        status_name = '难过'
    elif status == 'happy':
        emoji = '😊'
        status_name = '开心'
    elif status == 'hungry':
        emoji = '😫'
        status_name = '饿了'
    else:
        emoji = '😐'
        status_name = '一般'

    return {
        'emoji': emoji,
        'stage': stage,
        'stage_name': STAGE_NAMES[stage],
        'stage_progress': stage_progress,
        'primary_color': STAGE_COLORS[stage],
        'bg_gradient': STAGE_BG_GRADIENTS[stage],
        'name': status_name,
    }'''

new_get_appearance = '''def get_pet_appearance(exp, status, bond=50):
    """根据经验值和状态获取宠物外观信息（支持皮肤）"""
    stage = calculate_evolution_stage(exp)
    stage_progress = calculate_stage_progress(exp)

    # v3.2 加载当前皮肤
    current_skin_id = 'default'
    try:
        conn_skin = get_db_connection()
        skin_row = conn_skin.execute("SELECT value FROM parent_settings WHERE key = 'current_skin'").fetchone()
        if skin_row and skin_row['value'] in PET_SKINS:
            current_skin_id = skin_row['value']
        conn_skin.close()
    except Exception:
        pass

    skin = PET_SKINS.get(current_skin_id, PET_SKINS['default'])
    stage_colors = skin['colors'] if len(skin['colors']) > stage else STAGE_COLORS
    stage_bgs = skin['bg_gradients'] if len(skin['bg_gradients']) > stage else STAGE_BG_GRADIENTS

    # 基础状态 emoji（保留给 SVG 加载前的 fallback）
    if status == 'sleeping':
        emoji = '😴'
        status_name = '睡着了'
    elif status == 'sad':
        emoji = '😢'
        status_name = '难过'
    elif status == 'happy':
        emoji = '😊'
        status_name = '开心'
    elif status == 'hungry':
        emoji = '😫'
        status_name = '饿了'
    else:
        emoji = '😐'
        status_name = '一般'

    return {
        'emoji': emoji,
        'stage': stage,
        'stage_name': STAGE_NAMES[stage],
        'stage_progress': stage_progress,
        'primary_color': stage_colors[stage],
        'bg_gradient': stage_bgs[stage],
        'name': status_name,
        'skin_id': current_skin_id,
        'skin_name': skin['name'],
        'skin_icon': skin['icon'],
    }'''

main_content = main_content.replace(old_get_appearance, new_get_appearance)

# 在模板context添加皮肤信息
old_context_marker = '        "math_challenge_done": math_challenge_done,'
new_context_marker = '''        "math_challenge_done": math_challenge_done,
        "current_skin_id": current_skin_id,
        "unlocked_skins": unlocked_skins_list,
        "pet_skins": PET_SKINS,'''

# 需要先找到 appearance 之后添加一些变量
old_route_appearance = '''    appearance = get_pet_appearance(pet_dict['exp'], pet_dict['status'], pet_dict.get('bond', 50))
    svg_info = get_stage_svg_info(appearance['stage'])

    return HTMLResponse(render_template("index.html", {'''

new_route_appearance = '''    appearance = get_pet_appearance(pet_dict['exp'], pet_dict['status'], pet_dict.get('bond', 50))
    svg_info = get_stage_svg_info(appearance['stage'])

    # v3.2 皮肤信息
    current_skin_id = 'default'
    unlocked_skins_list = ['default']
    try:
        cs = conn.execute("SELECT value FROM parent_settings WHERE key = 'current_skin'").fetchone()
        if cs: current_skin_id = cs['value']
        us = conn.execute("SELECT value FROM parent_settings WHERE key = 'unlocked_skins'").fetchone()
        if us and us['value']: unlocked_skins_list = us['value'].split(',')
    except Exception:
        pass

    return HTMLResponse(render_template("index.html", {'''

if old_route_appearance in main_content:
    main_content = main_content.replace(old_route_appearance, new_route_appearance)

# 添加模板context
main_content = main_content.replace(old_context_marker, new_context_marker)

# ===== 更新家长设置API支持school_end_time =====
old_update_settings = '''@app.post("/api/parent/settings")
async def update_parent_settings(
    exchange_rate: str = Form("100"),
    weekly_coin_limit: str = Form("200"),
    pocket_money_enabled: str = Form("1"),
):
    """更新家长设置"""
    conn = get_db_connection()
    conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'exchange_rate'", (exchange_rate,))
    conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'weekly_coin_limit'", (weekly_coin_limit,))
    conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'pocket_money_enabled'", (pocket_money_enabled,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "设置已保存"}'''

new_update_settings = '''@app.post("/api/parent/settings")
async def update_parent_settings(
    exchange_rate: str = Form("100"),
    weekly_coin_limit: str = Form("200"),
    pocket_money_enabled: str = Form("1"),
    school_end_time: str = Form("16:00"),
):
    """更新家长设置"""
    conn = get_db_connection()
    conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'exchange_rate'", (exchange_rate,))
    conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'weekly_coin_limit'", (weekly_coin_limit,))
    conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'pocket_money_enabled'", (pocket_money_enabled,))
    conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'school_end_time'", (school_end_time,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "设置已保存"}'''

main_content = main_content.replace(old_update_settings, new_update_settings)

# ============================================================
# 写回 main.py
# ============================================================
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(main_content)

print("✅ main.py 更新完成")

# ============================================================
# 更新 index.html
# ============================================================

# 1. 宠物名字可点击改名
old_name_html = '<div class="pet-name">{{ pet.name }}{% if pet.status == \'sleeping\' %} <span class="sleep-tag">💤睡觉中</span>{% endif %}</div>'
new_name_html = '<div class="pet-name" onclick="showRenameModal()" style="cursor:pointer;" title="点击改名">{{ pet.name }}{% if pet.status == \'sleeping\' %} <span class="sleep-tag">💤睡觉中</span>{% endif %} ✏️</div>'
html_content = html_content.replace(old_name_html, new_name_html)

# 2. 互动按钮增加猜数字
html_content = html_content.replace(
    '<div class="interact-btn" onclick="doInteract(\'play\')" title="逗玩">🎾</div>',
    '<div class="interact-btn" onclick="doInteract(\'play\')" title="逗玩">🎾</div>\n            <div class="interact-btn" onclick="showGuessGame()" title="猜数字">🎲</div>'
)
html_content = html_content.replace(
    '<div class="interact-btn disabled" title="小龙睡着了">🎾</div>',
    '<div class="interact-btn disabled" title="小龙睡着了">🎾</div>\n            <div class="interact-btn disabled" title="小龙睡着了">🎲</div>'
)

# 3. 修改弹窗（在 sleep-overlay 标签之前）
rename_modal_html = '''<!-- 改名弹窗 -->
<div class="treasure-modal-overlay" id="renameModal">
  <div class="treasure-box" style="max-width:320px;">
    <div class="treasure-chest">✏️</div>
    <div class="treasure-title">给小龙取个新名字</div>
    <div class="treasure-subtitle">想一个你喜欢的新名字吧！</div>
    <div style="margin-bottom:16px;">
      <input type="text" id="renameInput" placeholder="输入新名字..." maxlength="20"
        style="width:100%;padding:12px 14px;border:2px solid #eee;border-radius:12px;font-size:16px;font-weight:600;text-align:center;outline:none;"
        onkeydown="if(event.key==='Enter')confirmRename()">
    </div>
    <button class="treasure-btn" onclick="confirmRename()" style="margin-bottom:8px;">✅ 确定改名</button>
    <button onclick="closeRenameModal()" style="width:100%;padding:10px;background:#f0f0f0;color:#666;border:none;border-radius:12px;font-size:14px;font-weight:600;cursor:pointer;">取消</button>
  </div>
</div>
'''
if 'id="renameModal"' not in html_content:
    html_content = html_content.replace('id="sleepOverlay"', 'id="sleepOverlay"\n' + rename_modal_html)

# 4. 猜数字弹窗
guess_modal_html = '''<!-- 猜数字游戏弹窗 -->
<div class="treasure-modal-overlay" id="guessGameModal">
  <div class="treasure-box" style="max-width:320px;">
    <div class="treasure-chest" id="guessIcon">🎲</div>
    <div class="treasure-title" id="guessTitle">猜数字游戏</div>
    <div class="treasure-subtitle" id="guessSubtitle">小龙想了一个1-10的数字，猜猜是几？</div>
    <div id="guessResultArea" style="margin-bottom:12px;min-height:40px;"></div>
    <div id="guessActionArea">
      <div style="display:flex;gap:6px;justify-content:center;flex-wrap:wrap;">
        <button onclick="doGuess(1)" style="width:50px;height:50px;border-radius:50%;border:2px solid #6C5CE7;background:#fff;font-size:18px;font-weight:700;cursor:pointer;">1</button>
        <button onclick="doGuess(2)" style="width:50px;height:50px;border-radius:50%;border:2px solid #6C5CE7;background:#fff;font-size:18px;font-weight:700;cursor:pointer;">2</button>
        <button onclick="doGuess(3)" style="width:50px;height:50px;border-radius:50%;border:2px solid #6C5CE7;background:#fff;font-size:18px;font-weight:700;cursor:pointer;">3</button>
        <button onclick="doGuess(4)" style="width:50px;height:50px;border-radius:50%;border:2px solid #6C5CE7;background:#fff;font-size:18px;font-weight:700;cursor:pointer;">4</button>
        <button onclick="doGuess(5)" style="width:50px;height:50px;border-radius:50%;border:2px solid #6C5CE7;background:#fff;font-size:18px;font-weight:700;cursor:pointer;">5</button>
        <button onclick="doGuess(6)" style="width:50px;height:50px;border-radius:50%;border:2px solid #6C5CE7;background:#fff;font-size:18px;font-weight:700;cursor:pointer;">6</button>
        <button onclick="doGuess(7)" style="width:50px;height:50px;border-radius:50%;border:2px solid #6C5CE7;background:#fff;font-size:18px;font-weight:700;cursor:pointer;">7</button>
        <button onclick="doGuess(8)" style="width:50px;height:50px;border-radius:50%;border:2px solid #6C5CE7;background:#fff;font-size:18px;font-weight:700;cursor:pointer;">8</button>
        <button onclick="doGuess(9)" style="width:50px;height:50px;border-radius:50%;border:2px solid #6C5CE7;background:#fff;font-size:18px;font-weight:700;cursor:pointer;">9</button>
        <button onclick="doGuess(10)" style="width:50px;height:50px;border-radius:50%;border:2px solid #6C5CE7;background:#fff;font-size:18px;font-weight:700;cursor:pointer;">10</button>
      </div>
      <br>
      <button onclick="closeGuessGame()" style="width:100%;padding:10px;background:#f0f0f0;color:#666;border:none;border-radius:12px;font-size:14px;font-weight:600;cursor:pointer;">关闭</button>
    </div>
  </div>
</div>
'''
if 'id="guessGameModal"' not in html_content:
    html_content = html_content.replace(
        'id="sleepOverlay"',
        guess_modal_html + '\n' + 'id="sleepOverlay"'
    )

# 5. 添加CSS新样式
new_css = '''
    /* v3.2 新情绪状态样式 */
    .pet-avatar.mood-angry .dragon-svg-wrap {
      filter: hue-rotate(-20deg) saturate(1.5) brightness(0.9);
      animation: shake 0.5s ease-in-out !important;
    }
    .pet-avatar.mood-wronged .dragon-svg-wrap {
      filter: grayscale(30%) brightness(0.8) drop-shadow(0 4px 12px rgba(100,100,255,0.3));
      animation-duration: 6s !important;
    }
    .pet-avatar.mood-proud .dragon-svg-wrap {
      filter: brightness(1.15) saturate(1.3) drop-shadow(0 0 20px rgba(255,215,0,0.4));
      animation: proud-float 2.5s ease-in-out infinite !important;
    }
    @keyframes proud-float {
      0%,100% { transform: translateY(0) rotate(0); }
      25% { transform: translateY(-8px) rotate(-3deg); }
      75% { transform: translateY(-4px) rotate(3deg); }
    }
    /* v3.2 皮肤样式 */
    .skin-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .skin-card {
      background: #f8f9fb; border-radius: 14px; padding: 12px; text-align: center;
      cursor: pointer; transition: all 0.2s; border: 2px solid transparent;
    }
    .skin-card:active { transform: scale(0.95); }
    .skin-card.current { border-color: var(--primary); background: #F3E5F5; }
    .skin-card .card-icon { font-size: 32px; margin-bottom: 4px; }
    .skin-card .card-name { font-size: 12px; font-weight: 600; color: #2D3436; }
    .skin-card .card-desc { font-size: 9px; color: #aaa; margin-top: 2px; }
    /* 学习平台联动 */
    .platform-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
    .platform-card {
      background: #f8f9fb; border-radius: 12px; padding: 12px 8px; text-align: center;
      cursor: pointer; transition: all 0.2s; border: 2px solid transparent;
    }
    .platform-card:active { transform: scale(0.95); }
'''

style_end = html_content.find('</style>')
html_content = html_content[:style_end] + new_css + '\n' + html_content[style_end:]

# 6. 家长设置加放学时间+换肤+平台联动按钮
html_content = html_content.replace(
    '<button class="parent-btn" style="margin-top:10px;" onclick="saveSettings()">💾 保存设置</button>',
    '''      <div class="settings-row">
        <span class="settings-label">⏰ 放学时间</span>
        <input type="time" class="settings-input" id="settingSchoolEnd" value="{{ parent_settings.get('school_end_time', '16:00') }}" style="width:100px;">
      </div>
      <button class="parent-btn" style="margin-top:10px;" onclick="saveSettings()">💾 保存设置</button>
      <button class="parent-btn" style="margin-top:8px;background:linear-gradient(135deg,#A29BFE,#6C5CE7);" onclick="showSkinPanel()">🎨 宠物换肤</button>
      <button class="parent-btn" style="margin-top:8px;background:linear-gradient(135deg,#81C784,#43A047);" onclick="showPlatformPanel()">🌐 学习平台联动</button>'''
)

# 7. 更新 saveSettings JS
html_content = html_content.replace(
    "formData.append('pocket_money_enabled', document.getElementById('settingPocketEnabled').checked ? '1' : '0');\n    const resp = await fetch('/api/parent/settings', { method: 'POST', body: formData });",
    "formData.append('pocket_money_enabled', document.getElementById('settingPocketEnabled').checked ? '1' : '0');\n    const schoolEnd = document.getElementById('settingSchoolEnd');\n    if (schoolEnd) formData.append('school_end_time', schoolEnd.value);\n    const resp = await fetch('/api/parent/settings', { method: 'POST', body: formData });"
)

# 8. 添加新JS函数
new_js = '''
// ===== v3.2 改名 =====
function showRenameModal() {
  if (petStatus === 'sleeping') { showToast('小龙睡着了，等它醒了再改名吧'); return; }
  document.getElementById('renameInput').value = '';
  document.getElementById('renameModal').classList.add('show');
  setTimeout(() => document.getElementById('renameInput').focus(), 300);
}
function closeRenameModal() { document.getElementById('renameModal').classList.remove('show'); }
async function confirmRename() {
  const name = document.getElementById('renameInput').value.trim();
  if (!name || name.length > 20) { showToast('名字长度需在1-20个字符之间'); return; }
  const formData = new FormData();
  formData.append('name', name);
  try {
    const resp = await fetch('/api/pet/rename', { method: 'POST', body: formData });
    const result = await resp.json();
    if (result.success) { showToast(result.message); closeRenameModal(); setTimeout(() => location.reload(), 1200); }
    else { showToast(result.message); }
  } catch(e) { showToast('改名失败'); }
}

// ===== v3.2 猜数字 =====
function showGuessGame() {
  if (petStatus === 'sleeping') { showToast('小龙睡着了，等它醒来再玩吧'); return; }
  document.getElementById('guessIcon').textContent = '🎲';
  document.getElementById('guessTitle').textContent = '猜数字游戏';
  document.getElementById('guessSubtitle').textContent = '小龙想了一个1-10的数字，猜猜是几？';
  document.getElementById('guessResultArea').innerHTML = '';
  document.getElementById('guessActionArea').style.display = 'block';
  document.getElementById('guessGameModal').classList.add('show');
}
async function doGuess(num) {
  const formData = new FormData();
  formData.append('guess', num);
  try {
    const resp = await fetch('/api/pet/guess-number', { method: 'POST', body: formData });
    const result = await resp.json();
    const resultArea = document.getElementById('guessResultArea');
    const actionArea = document.getElementById('guessActionArea');
    if (result.correct) {
      document.getElementById('guessIcon').textContent = '🎉';
      document.getElementById('guessTitle').textContent = '🎉 猜对了！+5龙币！';
      resultArea.innerHTML = '<div style="font-size:24px;font-weight:800;color:#FFD700;">超级棒！</div>';
      actionArea.style.display = 'none';
      showBubble(result.bubble);
      spawnParticles('play');
      updateCoinDisplay(result.new_coins);
      updateAttrBar('mood', result.mood);
      updateAttrBar('bond', result.bond);
      setTimeout(() => location.reload(), 2500);
    } else {
      document.getElementById('guessIcon').textContent = '😅';
      resultArea.innerHTML = '<div style="font-size:16px;font-weight:700;color:#E53935;">不对哦～答案不是'+num+'，再试试！</div>';
      updateAttrBar('mood', result.mood);
      updateAttrBar('bond', result.bond);
    }
  } catch(e) { showToast('游戏出错啦'); }
}
function closeGuessGame() { document.getElementById('guessGameModal').classList.remove('show'); }

// ===== v3.2 皮肤 =====
async function showSkinPanel() {
  try {
    const resp = await fetch('/api/pet/skins');
    const data = await resp.json();
    let html = '<div style="padding:16px;"><div style="font-size:18px;font-weight:700;margin-bottom:12px;">🎨 宠物换肤</div><div class="skin-grid">';
    data.skins.forEach(skin => {
      const isCurrent = skin.current;
      html += '<div class="skin-card ' + (isCurrent ? 'current' : '') + '" onclick="selectSkin(\\'' + skin.id + '\\')">';
      html += '<div style="font-size:32px;margin-bottom:4px;">' + skin.icon + '</div>';
      html += '<div style="font-size:12px;font-weight:600;">' + skin.name + '</div>';
      html += '<div style="font-size:9px;color:#aaa;">' + skin.desc + '</div>';
      html += '<div style="font-size:9px;margin-top:4px;">' + (isCurrent ? '✅ 使用中' : (skin.unlocked ? '点击切换' : '🔒 未解锁')) + '</div>';
      html += '</div>';
    });
    html += '</div></div>';
    const existing = document.getElementById('customModalOverlay');
    if (existing) existing.remove();
    const overlay = document.createElement('div'); overlay.id = 'customModalOverlay';
    overlay.className = 'wallet-overlay show';
    overlay.innerHTML = '<div class="wallet-popup" style="max-width:420px;"><div class="wallet-header"><div class="wallet-title">🎨 宠物换肤</div><button class="wallet-close" onclick="this.closest(\\'.wallet-overlay\\').remove()">×</button></div>' + html + '</div>';
    overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
  } catch(e) { showToast('加载皮肤失败'); }
}
async function selectSkin(skinId) {
  const formData = new FormData();
  formData.append('skin_id', skinId);
  try {
    const resp = await fetch('/api/pet/skin/select', { method: 'POST', body: formData });
    const result = await resp.json();
    showToast(result.message);
    if (result.success) setTimeout(() => location.reload(), 1200);
  } catch(e) { showToast('切换失败'); }
}

// ===== v3.2 学习平台 =====
async function showPlatformPanel() {
  try {
    const resp = await fetch('/api/platform/list');
    const data = await resp.json();
    let html = '<div style="padding:16px;"><div style="font-size:18px;font-weight:700;margin-bottom:12px;">🌐 学习平台联动</div>';
    html += '<div style="font-size:13px;color:#888;margin-bottom:12px;">连接学习平台，自动导入作业任务（模拟）</div><div class="platform-grid">';
    data.platforms.forEach(p => {
      html += '<div class="platform-card"><div style="font-size:28px;margin-bottom:4px;">' + p.icon + '</div>';
      html += '<div style="font-size:11px;font-weight:600;">' + p.name + '</div>';
      html += '<button onclick="connectPlatform(\\'' + p.id + '\\')" style="margin-top:6px;padding:4px 10px;border:none;border-radius:8px;background:#6C5CE7;color:#fff;font-size:10px;font-weight:600;cursor:pointer;">连接并同步</button></div>';
    });
    html += '</div></div>';
    const existing = document.getElementById('customModalOverlay');
    if (existing) existing.remove();
    const overlay = document.createElement('div'); overlay.id = 'customModalOverlay';
    overlay.className = 'wallet-overlay show';
    overlay.innerHTML = '<div class="wallet-popup" style="max-width:420px;"><div class="wallet-header"><div class="wallet-title">🌐 学习平台联动</div><button class="wallet-close" onclick="this.closest(\\'.wallet-overlay\\').remove()">×</button></div>' + html + '</div>';
    overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
  } catch(e) { showToast('加载平台列表失败'); }
}
async function connectPlatform(platformId) {
  const formData = new FormData();
  formData.append('platform_id', platformId);
  try {
    const resp = await fetch('/api/platform/connect', { method: 'POST', body: formData });
    const result = await resp.json();
    showToast(result.message);
    if (result.success) {
      const syncResp = await fetch('/api/platform/' + platformId + '/sync', { method: 'POST' });
      const syncResult = await syncResp.json();
      showToast(syncResult.message);
      if (syncResult.success && syncResult.synced_count > 0) setTimeout(() => location.reload(), 1500);
    }
  } catch(e) { showToast('操作失败'); }
}

// ===== v3.2 扩展心情显示 =====
const _origUpdateMood = window.updateMoodDisplay || function(){};
updateMoodDisplay = async function() {
  try {
    const resp = await fetch('/api/pet/mood');
    const data = await resp.json();
    if (data.error) return;
    const avatar = document.getElementById('petAvatar');
    const moodBubble = document.getElementById('moodBubble');
    if (!avatar || !moodBubble) return;
    avatar.classList.remove('mood-sad', 'mood-happy', 'mood-hiding', 'mood-begging', 'mood-angry', 'mood-wronged', 'mood-proud');
    const map = { 'angry': 'mood-angry', 'wronged': 'mood-wronged', 'proud': 'mood-proud', 'begging': 'mood-begging', 'pouting': 'mood-sad', 'hiding': 'mood-hiding', 'happy': 'mood-happy' };
    if (map[data.bubble_type]) avatar.classList.add(map[data.bubble_type]);
    if (data.bubble && data.bubble_type !== 'normal') { moodBubble.textContent = data.bubble; moodBubble.style.display = 'block'; }
    else { moodBubble.style.display = 'none'; }
    updateAttrBar('hunger', data.hunger);
    updateAttrBar('bond', data.bond);
  } catch(e) { console.error('心情轮询失败:', e); }
};
'''

script_tag = html_content.find('</script>')
html_content = html_content[:script_tag] + new_js + '\n' + html_content[script_tag:]

# ============================================================
# 写回 index.html
# ============================================================
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("✅ index.html 更新完成")
print("\n🎉 所有v3.2功能已实现完成！")
