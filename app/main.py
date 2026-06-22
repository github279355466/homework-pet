import sqlite3
import os
import random
import json
import logging
from datetime import datetime, timedelta, date
from typing import Optional
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import pytz

from database import get_db_connection, init_db

# ===== 日志配置 =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("homework-pet")

# ===== 配置 =====

DEFAULT_TASKS = [
    {'name': '语文', 'type': 'daily', 'exp': 50, 'coins': 5},
    {'name': '数学', 'type': 'daily', 'exp': 100, 'coins': 10},
    {'name': '英语', 'type': 'daily', 'exp': 50, 'coins': 5},
    {'name': '课外阅读', 'type': 'daily', 'exp': 40, 'coins': 4},
    {'name': '体育锻炼', 'type': 'daily', 'exp': 30, 'coins': 3},
]

# 家长额外任务预设模板
CUSTOM_TASK_TEMPLATES = [
    {'name': '口算练习20题', 'category': 'math', 'exp': 80, 'coins': 8},
    {'name': '数学练习册2页', 'category': 'math', 'exp': 100, 'coins': 10},
    {'name': '背诵乘法口诀', 'category': 'math', 'exp': 80, 'coins': 8},
    {'name': '读一篇课文', 'category': 'chinese', 'exp': 50, 'coins': 5},
    {'name': '抄写生字10个', 'category': 'chinese', 'exp': 60, 'coins': 6},
    {'name': '背诵古诗', 'category': 'chinese', 'exp': 70, 'coins': 7},
    {'name': '英语单词听写10个', 'category': 'english', 'exp': 60, 'coins': 6},
    {'name': '读英语绘本', 'category': 'english', 'exp': 50, 'coins': 5},
    {'name': '练字15分钟', 'category': 'other', 'exp': 40, 'coins': 4},
    {'name': '跳绳100个', 'category': 'other', 'exp': 30, 'coins': 3},
    {'name': '整理书包', 'category': 'other', 'exp': 20, 'coins': 2},
    {'name': '阅读课外书20分钟', 'category': 'other', 'exp': 40, 'coins': 4},
]

# 专注打卡龙币奖励
FOCUS_COINS = {10: 15, 20: 30, 30: 50}

TREASURE_REWARDS = [
    {'type': 'title', 'name': '数学小达人', 'icon': '🏅', 'rarity': 'common'},
    {'type': 'title', 'name': '算术高手', 'icon': '🧮', 'rarity': 'common'},
    {'type': 'title', 'name': '数字魔法师', 'icon': '✨', 'rarity': 'rare'},
    {'type': 'item', 'name': '小龙帽子', 'icon': '🎩', 'rarity': 'common'},
    {'type': 'item', 'name': '彩虹翅膀', 'icon': '🌈', 'rarity': 'rare'},
    {'type': 'item', 'name': '星星围巾', 'icon': '⭐', 'rarity': 'common'},
    {'type': 'exp_card', 'name': '经验加成卡', 'icon': '💫', 'rarity': 'rare'},
    {'type': 'item', 'name': '幸运草', 'icon': '🍀', 'rarity': 'common'},
]

# ===== FastAPI 初始化 =====

app = FastAPI(title="作业小龙 v3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# Jinja2 模板
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
from jinja2 import Environment, FileSystemLoader
_jinja_env = Environment(loader=FileSystemLoader(os.path.join(_THIS_DIR, "templates")))

def render_template(name: str, context: dict) -> str:
    tmpl = _jinja_env.get_template(name)
    return tmpl.render(**context)

templates = None
tz = pytz.timezone('Asia/Shanghai')

def get_current_time():
    return datetime.now(tz)

# ===== 进化系统 =====

STAGE_NAMES = ['龙蛋', '幼龙', '少年龙', '青年龙', '神龙']
STAGE_COLORS = ['#B388FF', '#69F0AE', '#40C4FF', '#FF8A65', '#FFD740']
STAGE_BG_GRADIENTS = [
    'linear-gradient(135deg, #CE93D8, #B388FF)',
    'linear-gradient(135deg, #A5D6A7, #69F0AE)',
    'linear-gradient(135deg, #80DEEA, #40C4FF)',
    'linear-gradient(135deg, #FFAB91, #FF8A65)',
    'linear-gradient(135deg, #FFF176, #FFD740)',
]

def calculate_level(exp):
    """兼容旧调用的等级计算（现在映射到进化阶段）"""
    return calculate_evolution_stage(exp) + 1

# 进化经验阈值：0→800→2000→4000→8000（前快后慢，适合一年级）
EVOLUTION_THRESHOLDS = [0, 800, 2000, 4000, 8000]

def calculate_evolution_stage(exp):
    """根据经验值计算进化阶段 (0-4)，前快后慢递进"""
    for i in range(len(EVOLUTION_THRESHOLDS) - 1, -1, -1):
        if exp >= EVOLUTION_THRESHOLDS[i]:
            return i
    return 0

def calculate_stage_progress(exp):
    """当前阶段内进度百分比 0-100"""
    stage = calculate_evolution_stage(exp)
    if stage >= 4:
        return 100
    stage_start = EVOLUTION_THRESHOLDS[stage]
    stage_end = EVOLUTION_THRESHOLDS[stage + 1]
    progress = ((exp - stage_start) / (stage_end - stage_start)) * 100
    return min(100, progress)

def get_pet_appearance(exp, status, bond=50, skin_id='default'):
    """根据经验值和状态获取宠物外观信息（含皮肤配色）"""
    stage = calculate_evolution_stage(exp)
    stage_progress = calculate_stage_progress(exp)
    skin = PET_SKINS.get(skin_id, PET_SKINS['default'])

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
        'primary_color': skin['colors'][min(stage, 4)],
        'bg_gradient': skin['bg_gradients'][min(stage, 4)],
        'name': status_name,
    }

def get_stage_svg_info(stage, skin_id='default'):
    """获取每个阶段的显示参数（含皮肤配色）"""
    skin_colors = PET_SKINS.get(skin_id, PET_SKINS['default']).get('colors', None)
    if skin_colors is None:
        skin_colors = PET_SKINS['default']['colors']
    configs = [
        {'svg_id': 'egg', 'size': 80, 'color': skin_colors[0]},
        {'svg_id': 'hatchling', 'size': 90, 'color': skin_colors[1]},
        {'svg_id': 'young', 'size': 100, 'color': skin_colors[2]},
        {'svg_id': 'adult', 'size': 110, 'color': skin_colors[3]},
        {'svg_id': 'divine', 'size': 120, 'color': skin_colors[4]},
    ]
    return configs[min(stage, 4)]

# 皮肤对应的 CSS 色相旋转滤镜值（在默认紫/绿/蓝/橙/金上模拟对应配色）
SKIN_FILTERS = {
    'default': '',
    'fire': 'hue-rotate(-40deg) saturate(1.4)',
    'ice': 'hue-rotate(95deg) saturate(0.85) brightness(1.15)',
    'gold': 'hue-rotate(-25deg) saturate(1.5) brightness(1.1)',
    'nature': 'hue-rotate(62deg) saturate(1.25)',
}

SKIN_STAGE_IMAGE_ROOT = "/static/dragon-skins"

def get_skin_stage_image_path(skin_id, stage):
    """返回当前皮肤和进化阶段对应的静态图片路径。"""
    safe_skin = skin_id if skin_id in PET_SKINS else 'default'
    safe_stage = max(0, min(int(stage or 0), 4))
    return f"{SKIN_STAGE_IMAGE_ROOT}/{safe_skin}/stage-{safe_stage}.png"

def calculate_realtime_decay(current_values, hours_elapsed):
    """按真实经过时间计算属性衰减，低饱腹阶段自动放慢。"""
    if hours_elapsed <= 0:
        return current_values

    hunger = float(current_values.get('hunger', 0))
    mood = float(current_values.get('mood', 0))
    bond = float(current_values.get('bond', 0))

    high_hours = hours_elapsed
    if hunger > 30:
        high_drop_needed = hunger - 30
        high_hours = min(hours_elapsed, high_drop_needed / 1.5)
        hunger -= high_hours * 1.5

    low_hours = hours_elapsed - high_hours
    if low_hours > 0:
        hunger -= low_hours / 6.0

    mood -= hours_elapsed * 1.0
    bond -= hours_elapsed * 0.75

    return {
        'hunger': max(0, min(100, int(hunger))),
        'mood': max(0, min(100, int(round(mood)))),
        'bond': max(0, min(100, int(round(bond)))),
    }

# ===== 工具函数 =====

def get_today_tasks_summary(conn, today):
    """获取今日任务完成摘要"""
    # 科目列表必须与 DEFAULT_TASKS 和前端弹窗完全一致
    all_subjects = [
        {'name': '语文', 'type': 'daily', 'is_math': False, 'exp': 50, 'coins': 5},
        {'name': '数学', 'type': 'daily', 'is_math': True,  'exp': 100, 'coins': 10},
        {'name': '英语', 'type': 'daily', 'is_math': False, 'exp': 50, 'coins': 5},
        {'name': '课外阅读', 'type': 'daily', 'is_math': False, 'exp': 40, 'coins': 4},
        {'name': '体育锻炼', 'type': 'daily', 'is_math': False, 'exp': 30, 'coins': 3},
    ]
    
    completed = conn.execute("""
        SELECT subject FROM tasks 
        WHERE created_date = ? AND completed = 1
    """, (today,)).fetchall()
    completed_set = {r['subject'] for r in completed}
    
    tasks = []
    for s in all_subjects:
        tasks.append({
            'subject': s['name'],
            'type': s['type'],
            'completed': s['name'] in completed_set,
            'is_math': s['is_math'],
            'exp': s['exp'],
            'coins': s['coins'],
        })
    
    total_daily = len(all_subjects)
    done_daily = sum(1 for t in tasks if t['completed'])
    return tasks, done_daily, total_daily

def add_coins(conn, amount, source, description="", double_weekend=False):
    """龙币交易（原子操作），double_weekend=True时周末自动双倍"""
    pet = conn.execute("SELECT coins FROM pet WHERE id = 1").fetchone()
    
    # 周末双倍龙币活动
    actual_amount = amount
    current_time = get_current_time()
    if double_weekend and amount > 0 and current_time.weekday() >= 5:  # 5=周六, 6=周日
        actual_amount = amount * 2
        description += " [周末双倍🎉]"
    
    new_balance = max(0, pet['coins'] + actual_amount)
    conn.execute("""
        INSERT INTO coin_transactions (type, source, amount, balance_after, description)
        VALUES (?, ?, ?, ?, ?)
    """, ('earn' if actual_amount > 0 else 'spend', source, actual_amount, new_balance, description))
    conn.execute("UPDATE pet SET coins = ? WHERE id = 1", (new_balance,))
    return new_balance

def check_achievements(conn, streak, stage, math_streak=0, bond=50, total_focus_minutes=0, total_coins_earned=0):
    """检查并解锁成就"""
    achievements = conn.execute("SELECT * FROM achievements WHERE unlocked = 0").fetchall()
    current_time = get_current_time()
    
    newly_unlocked = []
    
    for ach in achievements:
        unlocked = False
        
        if ach['name'] == '初学者' and streak >= 3:
            unlocked = True
        elif ach['name'] == '习惯者' and streak >= 7:
            unlocked = True
        elif ach['name'] == '坚持者' and streak >= 30:
            unlocked = True
        elif ach['name'] == '学霸':
            count = conn.execute("SELECT COUNT(*) as cnt FROM tasks WHERE completed = 1").fetchone()['cnt']
            if count >= 100:
                unlocked = True
        elif ach['name'] == '龙之守护者' and stage >= 4:
            unlocked = True
        elif ach['name'] == '数学勇士' and math_streak >= 7:
            unlocked = True
        elif ach['name'] == '破壳而出' and stage >= 1:
            unlocked = True
        elif ach['name'] == '成长之龙' and stage >= 2:
            unlocked = True
        elif ach['name'] == '龙之力量' and stage >= 3:
            unlocked = True
        elif ach['name'] == '神龙降临' and stage >= 4:
            unlocked = True
        elif ach['name'] == '最佳拍档' and bond >= 100:
            unlocked = True
        elif ach['name'] == '专注达人' and total_focus_minutes >= 600:
            unlocked = True
        elif ach['name'] == '小富翁' and total_coins_earned >= 1000:
            unlocked = True
        # v3.1 新成就
        elif ach['name'] == '喂养达人':
            feed_count = conn.execute("SELECT COUNT(*) as cnt FROM coin_transactions WHERE source LIKE 'shop_feed%' OR source = 'feed'").fetchone()['cnt']
            if feed_count >= 50:
                unlocked = True
        elif ach['name'] == '互动高手':
            interact_count = conn.execute("SELECT COUNT(*) as cnt FROM coin_transactions WHERE source = 'interact'").fetchone()['cnt']
            if interact_count >= 100:
                unlocked = True
        elif ach['name'] == '暖心天使':
            # 亲密度连续7天不低于80 - 检查最近7天是否有衰减记录（简化判断）
            current_bond = conn.execute("SELECT bond FROM pet WHERE id = 1").fetchone()['bond']
            if current_bond >= 80:
                unlocked = True
        elif ach['name'] == '挑战勇士':
            challenge_count = conn.execute("SELECT COUNT(*) as cnt FROM coin_transactions WHERE source = 'math_challenge'").fetchone()['cnt']
            if challenge_count >= 10:
                unlocked = True
        
        if unlocked:
            conn.execute("""
                UPDATE achievements SET unlocked = 1, unlocked_at = ?
                WHERE id = ?
            """, (current_time.isoformat(), ach['id']))
            newly_unlocked.append({'name': ach['name'], 'icon': ach['icon'], 'description': ach['description']})
    
    return newly_unlocked

# ===== 页面路由 =====

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, role: str = "kid"):
    """主页"""
    conn = get_db_connection()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    achievements = conn.execute("SELECT * FROM achievements ORDER BY id").fetchall()
    today = get_current_time().strftime('%Y-%m-%d')
    current_time = get_current_time()
    pet_dict = dict(pet)
    
    # 处理宠物睡眠
    if pet_dict.get('runaway_until'):
        try:
            sleep_time_str = pet_dict['runaway_until']
            if sleep_time_str.endswith('+00:00') or '+' in sleep_time_str:
                from datetime import timezone
                sleep_time = datetime.fromisoformat(sleep_time_str)
                if sleep_time.tzinfo is None:
                    sleep_time = sleep_time.replace(tzinfo=timezone.utc)
                sleep_time = sleep_time.astimezone(tz)
            else:
                sleep_time = datetime.fromisoformat(sleep_time_str)
                if sleep_time.tzinfo is None:
                    sleep_time = tz.localize(sleep_time)
            
            if sleep_time < current_time and pet_dict['status'] in ('sleeping', 'runaway'):
                conn.execute("UPDATE pet SET status = 'happy', runaway_until = NULL WHERE id = 1")
                conn.commit()
                pet_dict['status'] = 'happy'
                pet_dict['runaway_until'] = None
        except Exception:
            pass
    
    tasks, done_daily, total_daily = get_today_tasks_summary(conn, today)
    
    # 家长额外任务（孩子端）：未过期pending + 今天已完成
    custom_tasks = []
    if role == 'kid':
        custom_tasks = conn.execute("""
            SELECT * FROM custom_tasks 
            WHERE (status = 'pending' AND (deadline IS NULL OR deadline >= ?))
               OR (status = 'completed' AND date(completed_at) = ?)
            ORDER BY status ASC, deadline ASC, created_at ASC
        """, (today, today)).fetchall()
    
    # 家长额外任务列表（家长端）
    parent_custom_tasks = []
    if role == 'parent':
        parent_custom_tasks = conn.execute("""
            SELECT * FROM custom_tasks ORDER BY created_at DESC LIMIT 20
        """).fetchall()
    
    # 未审批的零花钱请求
    pending_pocket = []
    if role == 'parent':
        pending_pocket = conn.execute("""
            SELECT * FROM pocket_money_records WHERE status = 'pending' ORDER BY requested_at DESC
        """).fetchall()
    
    # 行为评价规则
    behavior_rules = []
    if role == 'parent':
        behavior_rules = conn.execute("SELECT * FROM behavior_rules ORDER BY category, id").fetchall()
    
    # 今日行为记录（家长端）
    today_behavior = []
    if role == 'parent':
        today_behavior = conn.execute("""
            SELECT * FROM behavior_records WHERE date(created_at) = ? ORDER BY created_at DESC
        """, (today,)).fetchall()
    
    # 今日行为记录（孩子端）- 只显示正向评价
    kid_today_behavior = []
    kid_bh_positive = 0
    kid_bh_negative = 0
    if role == 'kid':
        kid_today_behavior = conn.execute("""
            SELECT * FROM behavior_records WHERE date(created_at) = ? ORDER BY created_at DESC
        """, (today,)).fetchall()
        kid_bh_positive = sum(b['coins'] for b in kid_today_behavior if b['coins'] > 0)
        kid_bh_negative = sum(b['coins'] for b in kid_today_behavior if b['coins'] < 0)
    
    # 鼓励消息
    encourage = conn.execute("""
        SELECT * FROM encourage WHERE expires_at > ? ORDER BY created_at DESC LIMIT 1
    """, (current_time.isoformat(),)).fetchone()
    
    last_treasure = conn.execute("SELECT * FROM treasure_log ORDER BY id DESC LIMIT 1").fetchone()
    
    # 专注打卡统计
    focus_today = conn.execute("""
        SELECT COALESCE(SUM(duration_minutes), 0) as total FROM focus_sessions WHERE date(completed_at) = ?
    """, (today,)).fetchone()['total']
    focus_count_today = conn.execute("""
        SELECT COUNT(*) as cnt FROM focus_sessions WHERE date(completed_at) = ?
    """, (today,)).fetchone()['cnt']
    
    # 专注总时长
    total_focus = conn.execute("SELECT COALESCE(SUM(duration_minutes), 0) as total FROM focus_sessions").fetchone()['total']
    
    # 龙币总获取
    total_coins_earned = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) as total FROM coin_transactions WHERE type = 'earn'
    """).fetchone()['total']
    
    # 活动状态（周末双倍等）
    weekday = current_time.weekday()
    is_weekend = weekday >= 5
    
    # 随机惊喜检查（今天是否已获得）
    today_surprise = conn.execute("""
        SELECT * FROM random_surprises WHERE date(created_at) = ?
    """, (today,)).fetchone()
    
    # 数学挑战赛状态
    math_challenge_done = pet_dict.get('math_challenge_today', 0)
    
    # 家长设置
    parent_settings = {}
    for row in conn.execute("SELECT key, value FROM parent_settings").fetchall():
        parent_settings[row['key']] = row['value']
    
    # v3.2 皮肤信息（必须在 conn.close() 之前读取）
    current_skin_id = 'default'
    unlocked_skins_list = ['default']
    try:
        cs = conn.execute("SELECT value FROM parent_settings WHERE key = 'current_skin'").fetchone()
        if cs: current_skin_id = cs['value']
        us = conn.execute("SELECT value FROM parent_settings WHERE key = 'unlocked_skins'").fetchone()
        if us and us['value']: unlocked_skins_list = us['value'].split(',')
    except Exception:
        pass

    conn.close()

    appearance = get_pet_appearance(pet_dict['exp'], pet_dict['status'], pet_dict.get('bond', 50), current_skin_id)
    svg_info = get_stage_svg_info(appearance['stage'], current_skin_id)
    skin_filter = SKIN_FILTERS.get(current_skin_id, '')
    skin_stage_image = get_skin_stage_image_path(current_skin_id, appearance['stage'])

    return HTMLResponse(render_template("index.html", {
        "pet": pet_dict,
        "appearance": appearance,
        "svg_info": svg_info,
        "skin_filter": skin_filter,
        "skin_stage_image": skin_stage_image,
        "tasks": tasks,
        "achievements": [dict(a) for a in achievements],
        "role": role,
        "today": today,
        "done_daily": done_daily,
        "total_daily": total_daily,
        "encourage": dict(encourage) if encourage else None,
        "last_treasure": dict(last_treasure) if last_treasure else None,
        "current_hour": current_time.hour,
        "custom_tasks": [dict(t) for t in custom_tasks],
        "parent_custom_tasks": [dict(t) for t in parent_custom_tasks],
        "pending_pocket": [dict(p) for p in pending_pocket],
        "behavior_rules": [dict(r) for r in behavior_rules],
        "today_behavior": [dict(b) for b in today_behavior],
        "focus_today": focus_today,
        "focus_count_today": focus_count_today,
        "total_focus": total_focus,
        "total_coins_earned": total_coins_earned,
        "parent_settings": parent_settings,
        "custom_task_templates": CUSTOM_TASK_TEMPLATES,
        "kid_today_behavior": [dict(b) for b in kid_today_behavior],
        "kid_bh_positive": kid_bh_positive,
        "kid_bh_negative": kid_bh_negative,
        "is_weekend": is_weekend,
        "today_surprise": dict(today_surprise) if today_surprise else None,
        "math_challenge_done": math_challenge_done,
        "current_skin_id": current_skin_id,
        "unlocked_skins": unlocked_skins_list,
        "pet_skins": PET_SKINS,
    }))

# ===== API 路由 =====

@app.get("/api/pet")
async def get_pet():
    """获取宠物状态"""
    conn = get_db_connection()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    current_skin_id = 'default'
    try:
        cs = conn.execute("SELECT value FROM parent_settings WHERE key = 'current_skin'").fetchone()
        if cs: current_skin_id = cs['value']
    except Exception:
        pass
    conn.close()
    if pet:
        pet_dict = dict(pet)
        appearance = get_pet_appearance(pet_dict['exp'], pet_dict['status'], pet_dict.get('bond', 50), current_skin_id)
        appearance['image'] = get_skin_stage_image_path(current_skin_id, appearance['stage'])
        
        # sleeping 状态信息：剩余秒数和原因
        sleeping_info = None
        if pet_dict['status'] == 'sleeping':
            sleeping_info = {
                "status": "sleeping",
                "runaway_until": pet_dict.get('runaway_until'),
            }
        
        return {"pet": pet_dict, "appearance": appearance, "sleeping_info": sleeping_info}
    return {"error": "宠物不存在"}

@app.post("/api/task/complete")
async def complete_task(
    task_type: str = Form("daily"),
    subject: str = Form("语文"),
    completed_by: str = Form("kid")
):
    """完成日常作业"""
    conn = get_db_connection()
    today = get_current_time().strftime('%Y-%m-%d')
    current_time = get_current_time()
    
    logger.info(f"[task/complete] 收到请求: type={task_type}, subject={subject}")
    
    existing = conn.execute("""
        SELECT * FROM tasks WHERE subject = ? AND created_date = ? AND completed = 1
    """, (subject, today)).fetchone()
    if existing:
        conn.close()
        return {"success": False, "message": f"今天{subject}已经完成过了！"}
    
    is_math = (subject == '数学')
    # 按科目设定奖励
    SUBJECT_REWARDS = {
        '数学': {'exp': 100, 'hunger': 30, 'mood': 15, 'coins': 10},
        '语文': {'exp': 50, 'hunger': 20, 'mood': 10, 'coins': 5},
        '英语': {'exp': 50, 'hunger': 20, 'mood': 10, 'coins': 5},
        '课外阅读': {'exp': 40, 'hunger': 15, 'mood': 12, 'coins': 4},
        '体育锻炼': {'exp': 30, 'hunger': 10, 'mood': 15, 'coins': 3},
    }
    rewards = SUBJECT_REWARDS.get(subject, {'exp': 50, 'hunger': 20, 'mood': 10, 'coins': 5})
    exp_reward = rewards['exp']
    hunger_reward = rewards['hunger']
    mood_reward = rewards['mood']
    coins_reward = rewards['coins']
    
    conn.execute("""
        INSERT INTO tasks (task_type, subject, completed, completed_by, completed_at, exp_reward, created_date)
        VALUES (?, ?, 1, ?, ?, ?, ?)
    """, (task_type, subject, completed_by, current_time.isoformat(), exp_reward, today))
    
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    pet_dict = dict(pet)
    
    was_sleeping = pet_dict['status'] == 'sleeping'
    logger.info(f"[task/complete] 宠物状态: status={pet_dict['status']}, coins={pet_dict['coins']}")
    
    new_exp = pet_dict['exp'] + exp_reward
    old_stage = calculate_evolution_stage(pet_dict['exp'])
    new_stage = calculate_evolution_stage(new_exp)
    new_hunger = min(100, pet_dict['hunger'] + hunger_reward)
    new_mood = min(100, pet_dict['mood'] + mood_reward)
    
    # 连续天数
    new_streak = pet_dict['streak']
    last_streak_date = pet_dict.get('last_streak_date')
    if last_streak_date != today:
        today_count_after = conn.execute("""
            SELECT COUNT(*) as cnt FROM tasks WHERE created_date = ? AND completed = 1
        """, (today,)).fetchone()['cnt']
        if today_count_after == 1:
            yesterday = (get_current_time() - timedelta(days=1)).strftime('%Y-%m-%d')
            yesterday_done = conn.execute("""
                SELECT COUNT(*) as cnt FROM tasks WHERE created_date = ? AND completed = 1
            """, (yesterday,)).fetchone()['cnt']
            new_streak = pet_dict['streak'] + 1 if (yesterday_done > 0 or pet_dict['streak'] == 0) else 1
        elif last_streak_date == today:
            new_streak = pet_dict['streak']
    
    # 数学连续天数
    new_math_streak = pet_dict.get('math_streak', 0)
    math_update = {}
    if is_math and pet_dict.get('last_math_date') != today:
        yesterday = (get_current_time() - timedelta(days=1)).strftime('%Y-%m-%d')
        new_math_streak = (pet_dict.get('math_streak') or 0) + 1 if pet_dict.get('last_math_date') == yesterday else 1
        math_update = {'math_streak': new_math_streak, 'last_math_date': today}
    
    # 21点前额外奖励
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
        logger.info(f"[task/complete] 提前完成奖励: subject={subject}, bonus={early_bird_bonus}")
    
    new_level = calculate_level(new_exp)
    conn.execute("""
        UPDATE pet SET exp = ?, level = ?, hunger = ?, mood = ?,
            streak = ?, last_streak_date = ?,
            math_streak = ?, last_math_date = ?,
            status = 'happy', runaway_until = NULL, updated_at = ?
        WHERE id = 1
    """, (
        new_exp, new_level, new_hunger, new_mood, new_streak, today,
        new_math_streak, math_update.get('last_math_date', pet_dict.get('last_math_date')),
        current_time.isoformat()
    ))
    
    # 龙币奖励
    new_coins = add_coins(conn, coins_reward, 'homework', f'完成{subject}', double_weekend=True)
    
    # 数学挑战赛：每天第一道数学额外 +20 龙币
    challenge_bonus = 0
    if is_math and pet_dict.get('math_challenge_today', 0) == 0:
        challenge_bonus = 20
        new_coins = add_coins(conn, challenge_bonus, 'math_challenge', '数学挑战赛·每日首题奖励')
        conn.execute("UPDATE pet SET math_challenge_today = 1 WHERE id = 1")
        conn.commit()
    
    # 检查成就
    total_focus = conn.execute("SELECT COALESCE(SUM(duration_minutes), 0) FROM focus_sessions").fetchone()[0]
    total_coins_earned = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM coin_transactions WHERE type = 'earn'").fetchone()[0]
    check_achievements(conn, new_streak, new_stage, new_math_streak, pet_dict.get('bond', 50), total_focus, total_coins_earned)
    
    conn.commit()
    
    # 宝箱逻辑
    treasure = None
    trigger_prob = 0.6 if is_math else 0.1
    if random.random() < trigger_prob:
        reward = random.choice(TREASURE_REWARDS)
        conn.execute("INSERT INTO treasure_log (reward_type, reward_name, reward_icon) VALUES (?, ?, ?)",
                      (reward['type'], reward['name'], reward['icon']))
        conn.commit()
        treasure = reward
        if reward['type'] == 'exp_card':
            conn.execute("UPDATE pet SET exp = exp + 20 WHERE id = 1")
            new_exp += 20
            new_stage = calculate_evolution_stage(new_exp)
            conn.commit()
    
    conn.close()
    
    msg = f"太棒了！{subject}完成了！+{exp_reward}经验 +{coins_reward}龙币"
    if bonus_mood > 0:
        msg += " 🌟黄金时段额外奖励！"
    if is_math:
        msg = f"🔢 数学完成！双倍经验 +{exp_reward}！+{coins_reward}龙币"
    if challenge_bonus > 0:
        msg += f" ⚔️挑战赛奖励+{challenge_bonus}龙币！"
    if early_bird_bonus > 0:
        msg += f" 🐦放学1小时内完成，额外+{early_bird_bonus}龙币！"
    if was_sleeping:
        msg += " ✨ 小龙被你唤醒啦！"
        logger.info(f"[task/complete] 小龙从睡眠中被唤醒！")
    
    return {
        "success": True, "message": msg, "exp": exp_reward, "coins": coins_reward,
        "is_math": is_math, "bonus_mood": bonus_mood, "treasure": treasure,
        "old_stage": old_stage, "new_stage": new_stage,
        "stage_up": new_stage > old_stage,
        "new_coins": new_coins,
        "woke_up": was_sleeping,
        "challenge_bonus": challenge_bonus,
        "early_bird_bonus": early_bird_bonus,
    }

@app.post("/api/pet/feed")
async def feed_pet():
    """喂食"""
    conn = get_db_connection()
    current_time = get_current_time()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    
    if pet['status'] == 'sleeping':
        conn.close()
        return {"success": False, "message": "嘘...小龙正在睡觉，不要打扰它哦～"}
    
    new_hunger = min(100, pet['hunger'] + 30)
    new_mood = min(100, pet['mood'] + 10)
    new_bond = min(100, (dict(pet).get('bond') or 50) + 1)
    
    conn.execute("UPDATE pet SET hunger = ?, mood = ?, bond = ?, updated_at = ? WHERE id = 1",
                 (new_hunger, new_mood, new_bond, current_time.isoformat()))

    # 检查成就（亲密度相关的成就）
    pet_after = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    pet_after_dict = dict(pet_after)
    total_focus = conn.execute("SELECT COALESCE(SUM(duration_minutes), 0) FROM focus_sessions").fetchone()[0]
    total_coins_earned = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM coin_transactions WHERE type = 'earn'").fetchone()[0]
    check_achievements(conn, pet_after_dict['streak'], calculate_evolution_stage(pet_after_dict['exp']),
                       pet_after_dict.get('math_streak', 0), new_bond, total_focus, total_coins_earned)

    conn.commit()
    conn.close()

    return {"success": True, "message": "喂食成功！🍖 小龙吃得饱饱的！亲密度+1"}

# ===== v3.0 新增 API =====

@app.post("/api/pet/interact")
async def pet_interact(interaction_type: str = Form("pat")):
    """宠物互动：pat/tickle/play"""
    conn = get_db_connection()
    current_time = get_current_time()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    
    if pet['status'] == 'sleeping':
        conn.close()
        return {"success": False, "message": "嘘...小龙正在睡觉～"}
    
    bond = dict(pet).get('bond', 50)
    
    if interaction_type == 'pat':
        bond_delta, mood_delta = 2, 1
        bubble = random.choice(['好舒服～', '再摸摸～', '嘿嘿😊', '嗯～好暖和', '最喜欢你了💕'])
    elif interaction_type == 'tickle':
        bond_delta, mood_delta = 3, 2
        bubble = random.choice(['哈哈哈好痒！', '别挠了～', '受不了啦😆', '嘻嘻嘻～', '好好玩！'])
    elif interaction_type == 'play':
        bond_delta, mood_delta = 2, 0
        bubble = random.choice(['太好玩了！', '再来再来！', '耶！', '好开心！', '转圈圈～'])
    else:
        bond_delta, mood_delta = 1, 1
        bubble = random.choice(['嗯？', '干嘛呀～', '嘿嘿'])
    
    new_bond = min(100, bond + bond_delta)
    new_mood = min(100, pet['mood'] + mood_delta)
    
    conn.execute("UPDATE pet SET bond = ?, mood = ?, updated_at = ? WHERE id = 1",
                 (new_bond, new_mood, current_time.isoformat()))

    # 记录互动次数（amount=0 不影响龙币，仅用于成就统计）
    conn.execute("""
        INSERT INTO coin_transactions (type, source, amount, balance_after, description)
        VALUES ('earn', 'interact', 0, (SELECT coins FROM pet WHERE id = 1), ?)
    """, (f'互动:{interaction_type}',))

    # 检查成就（互动可能解锁亲密度相关成就）
    pet_after = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    pet_after_dict = dict(pet_after)
    total_focus = conn.execute("SELECT COALESCE(SUM(duration_minutes), 0) FROM focus_sessions").fetchone()[0]
    total_coins_earned = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM coin_transactions WHERE type = 'earn'").fetchone()[0]
    check_achievements(conn, pet_after_dict['streak'], calculate_evolution_stage(pet_after_dict['exp']),
                       pet_after_dict.get('math_streak', 0), new_bond, total_focus, total_coins_earned)

    conn.commit()
    conn.close()

    return {
        "success": True,
        "interaction": interaction_type,
        "bubble": bubble,
        "bond": new_bond,
        "mood": new_mood,
    }


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

@app.get("/api/tasks")
async def get_tasks():
    """获取今日任务"""
    conn = get_db_connection()
    today = get_current_time().strftime('%Y-%m-%d')
    tasks, done_daily, total_daily = get_today_tasks_summary(conn, today)
    conn.close()
    return {"tasks": tasks, "done_daily": done_daily, "total_daily": total_daily}

@app.get("/api/achievements")
async def get_achievements():
    """获取成就"""
    conn = get_db_connection()
    achievements = conn.execute("SELECT * FROM achievements ORDER BY id").fetchall()
    conn.close()
    return {"achievements": [dict(a) for a in achievements]}

# ----- 家长额外任务 API -----

@app.get("/api/custom-tasks/templates")
async def get_custom_task_templates():
    """获取预设任务模板"""
    return {"templates": CUSTOM_TASK_TEMPLATES}

@app.post("/api/custom-tasks/create")
async def create_custom_task(
    subject: str = Form(...),
    category: str = Form("other"),
    exp_reward: int = Form(30),
    coins_reward: int = Form(3),
    deadline: str = Form("")
):
    """家长创建额外任务"""
    conn = get_db_connection()
    deadline_val = deadline if deadline else None
    
    conn.execute("""
        INSERT INTO custom_tasks (subject, category, exp_reward, coins_reward, deadline, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    """, (subject, category, exp_reward, coins_reward, deadline_val))
    conn.commit()
    conn.close()
    
    return {"success": True, "message": f"任务「{subject}」已布置！"}

@app.post("/api/custom-tasks/{task_id}/complete")
async def complete_custom_task(task_id: int):
    """孩子完成家长额外任务"""
    conn = get_db_connection()
    current_time = get_current_time()
    
    task = conn.execute("SELECT * FROM custom_tasks WHERE id = ? AND status = 'pending'", (task_id,)).fetchone()
    if not task:
        conn.close()
        return {"success": False, "message": "任务不存在或已完成"}
    
    # 更新任务状态
    conn.execute("""
        UPDATE custom_tasks SET status = 'completed', completed_at = ? WHERE id = ?
    """, (current_time.isoformat(), task_id))
    
    # 更新宠物经验+龙币
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    pet_dict = dict(pet)
    
    new_exp = pet_dict['exp'] + task['exp_reward']
    old_stage = calculate_evolution_stage(pet_dict['exp'])
    new_stage = calculate_evolution_stage(new_exp)
    new_mood = min(100, pet_dict['mood'] + 10)
    
    new_level = calculate_level(new_exp)
    conn.execute("""
        UPDATE pet SET exp = ?, level = ?, mood = ?, status = 'happy', updated_at = ?
        WHERE id = 1
    """, (new_exp, new_level, new_mood, current_time.isoformat()))
    
    new_coins = add_coins(conn, task['coins_reward'], 'custom_task', f'完成{task["subject"]}', double_weekend=True)
    
    total_focus = conn.execute("SELECT COALESCE(SUM(duration_minutes), 0) FROM focus_sessions").fetchone()[0]
    total_coins_earned = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM coin_transactions WHERE type = 'earn'").fetchone()[0]
    check_achievements(conn, pet_dict['streak'], new_stage, pet_dict.get('math_streak', 0), pet_dict.get('bond', 50), total_focus, total_coins_earned)
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": f"太棒了！{task['subject']}完成了！+{task['exp_reward']}经验 +{task['coins_reward']}龙币",
        "exp": task['exp_reward'],
        "coins": task['coins_reward'],
        "stage_up": new_stage > old_stage,
        "new_stage": new_stage,
        "new_coins": new_coins,
    }

@app.delete("/api/custom-tasks/{task_id}")
async def delete_custom_task(task_id: int):
    """家长删除额外任务"""
    conn = get_db_connection()
    conn.execute("DELETE FROM custom_tasks WHERE id = ? AND status = 'pending'", (task_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "任务已删除"}

# ----- 行为评价 API -----

@app.get("/api/behavior/rules")
async def get_behavior_rules():
    """获取行为评价规则"""
    conn = get_db_connection()
    rules = conn.execute("SELECT * FROM behavior_rules ORDER BY category, id").fetchall()
    conn.close()
    return {"rules": [dict(r) for r in rules]}

@app.post("/api/behavior/evaluate")
async def behavior_evaluate(rule_id: int = Form(...)):
    """家长执行行为评价"""
    conn = get_db_connection()
    current_time = get_current_time()
    
    rule = conn.execute("SELECT * FROM behavior_rules WHERE id = ?", (rule_id,)).fetchone()
    if not rule:
        conn.close()
        return {"success": False, "message": "规则不存在"}
    
    # 记录评价
    conn.execute("""
        INSERT INTO behavior_records (rule_id, rule_name, coins, category)
        VALUES (?, ?, ?, ?)
    """, (rule_id, rule['name'], rule['coins'], rule['category']))
    
    # 更新龙币
    new_coins = add_coins(conn, rule['coins'], 'behavior', f'{rule["name"]}({rule["category"]})', double_weekend=rule['coins'] > 0)
    
    # 扣分时影响心情
    if rule['coins'] < 0:
        pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
        new_mood = max(0, pet['mood'] + rule['coins'] // 2)  # 扣分影响减半
        conn.execute("UPDATE pet SET mood = ? WHERE id = 1", (new_mood,))
    
    conn.commit()
    conn.close()
    
    action = "奖励" if rule['coins'] > 0 else "扣除"
    return {
        "success": True,
        "message": f"{rule['name']}：{action}{abs(rule['coins'])}龙币",
        "coins": rule['coins'],
        "new_balance": new_coins,
    }

@app.post("/api/behavior/evaluate/custom")
async def behavior_evaluate_custom(
    name: str = Form(...),
    behavior_type: str = Form("positive"),
    coins: int = Form(5)
):
    """家长临时输入自定义行为评价，不保存为长期规则。"""
    name = name.strip()
    if not name or len(name) > 30:
        return {"success": False, "message": "评价名称需在1-30个字符之间"}
    if behavior_type not in ("positive", "improve"):
        return {"success": False, "message": "评价类型不正确"}
    if coins < -20 or coins > 20:
        return {"success": False, "message": "龙币变化必须在 -20 到 +20 之间"}

    conn = get_db_connection()
    current_time = get_current_time()
    category = "behavior" if behavior_type == "positive" else "improve"

    conn.execute("""
        INSERT INTO behavior_records (rule_id, rule_name, coins, category)
        VALUES (NULL, ?, ?, ?)
    """, (name, coins, category))

    new_balance = add_coins(conn, coins, 'behavior', f'{name}({category})', double_weekend=coins > 0)

    pet = conn.execute("SELECT mood, bond FROM pet WHERE id = 1").fetchone()
    mood_delta = 3 if behavior_type == "positive" else -3
    bond_delta = 2 if behavior_type == "positive" else -2
    if coins > 0:
        mood_delta += min(4, coins // 5)
        bond_delta += min(3, coins // 8)
    elif coins < 0:
        mood_delta -= min(4, abs(coins) // 5)
        bond_delta -= min(3, abs(coins) // 8)

    new_mood = max(0, min(100, pet['mood'] + mood_delta))
    new_bond = max(0, min(100, pet['bond'] + bond_delta))
    conn.execute("UPDATE pet SET mood = ?, bond = ?, updated_at = ? WHERE id = 1",
                 (new_mood, new_bond, current_time.isoformat()))

    conn.commit()
    conn.close()

    action = "奖励" if coins >= 0 else "扣除"
    return {
        "success": True,
        "message": f"{name}：{action}{abs(coins)}龙币",
        "coins": coins,
        "new_balance": new_balance,
        "mood": new_mood,
        "bond": new_bond,
    }

@app.post("/api/behavior/rules/create")
async def create_behavior_rule(
    name: str = Form(...),
    coins: int = Form(10),
    category: str = Form("other"),
    icon: str = Form("⭐")
):
    """家长自定义行为规则"""
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO behavior_rules (name, coins, category, icon, is_custom)
        VALUES (?, ?, ?, ?, 1)
    """, (name, coins, category, icon))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"规则「{name}」已添加！"}

@app.delete("/api/behavior/rules/{rule_id}")
async def delete_behavior_rule(rule_id: int):
    """删除自定义行为规则"""
    conn = get_db_connection()
    rule = conn.execute("SELECT * FROM behavior_rules WHERE id = ? AND is_custom = 1", (rule_id,)).fetchone()
    if not rule:
        conn.close()
        return {"success": False, "message": "只能删除自定义规则"}
    conn.execute("DELETE FROM behavior_rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "规则已删除"}

# ----- 龙币经济 API -----

@app.get("/api/coins/transactions")
async def get_coin_transactions(limit: int = 20):
    """获取龙币交易记录"""
    conn = get_db_connection()
    txns = conn.execute("""
        SELECT * FROM coin_transactions ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return {"transactions": [dict(t) for t in txns]}

@app.get("/api/coins/stats")
async def get_coin_stats():
    """龙币统计"""
    conn = get_db_connection()
    pet = conn.execute("SELECT coins FROM pet WHERE id = 1").fetchone()
    total_earned = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM coin_transactions WHERE type = 'earn'").fetchone()[0]
    total_spent = conn.execute("SELECT COALESCE(SUM(ABS(amount)), 0) FROM coin_transactions WHERE type = 'spend'").fetchone()[0]
    
    # 本周零花钱统计
    week_start = (get_current_time() - timedelta(days=get_current_time().weekday())).strftime('%Y-%m-%d')
    weekly_pocket = conn.execute("""
        SELECT COALESCE(SUM(amount_yuan), 0) FROM pocket_money_records 
        WHERE status = 'approved' AND date(approved_at) >= ?
    """, (week_start,)).fetchone()[0]
    
    conn.close()
    return {
        "balance": pet['coins'],
        "total_earned": total_earned,
        "total_spent": total_spent,
        "weekly_pocket": weekly_pocket,
    }

@app.post("/api/coins/exchange-pocket-money")
async def request_pocket_money(coins_amount: int = Form(...)):
    """孩子请求兑换零花钱"""
    conn = get_db_connection()
    current_time = get_current_time()
    
    pet = conn.execute("SELECT coins FROM pet WHERE id = 1").fetchone()
    if pet['coins'] < coins_amount:
        conn.close()
        return {"success": False, "message": "龙币不够哦～"}
    
    # 获取汇率
    rate = conn.execute("SELECT value FROM parent_settings WHERE key = 'exchange_rate'").fetchone()
    exchange_rate = int(rate['value']) if rate else 100
    
    # 本周额度检查
    limit_row = conn.execute("SELECT value FROM parent_settings WHERE key = 'weekly_coin_limit'").fetchone()
    weekly_limit = int(limit_row['value']) if limit_row else 200
    week_start = (current_time - timedelta(days=current_time.weekday())).strftime('%Y-%m-%d')
    weekly_spent = conn.execute("""
        SELECT COALESCE(SUM(coins_spent), 0) FROM pocket_money_records 
        WHERE status = 'approved' AND date(approved_at) >= ?
    """, (week_start,)).fetchone()[0]
    
    if weekly_spent + coins_amount > weekly_limit:
        conn.close()
        return {"success": False, "message": f"本周兑换额度不足（已用{weekly_spent}/{weekly_limit}龙币）"}
    
    amount_yuan = round(coins_amount / exchange_rate, 2)
    
    conn.execute("""
        INSERT INTO pocket_money_records (coins_spent, amount_yuan, status, requested_at)
        VALUES (?, ?, 'pending', ?)
    """, (coins_amount, amount_yuan, current_time.isoformat()))
    
    # 预扣龙币
    add_coins(conn, -coins_amount, 'pocket_money_pending', f'兑换零花钱{amount_yuan}元（待审批）')
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": f"已提交兑换申请：{coins_amount}龙币 → {amount_yuan}元，等待家长审批",
        "coins": coins_amount,
        "amount_yuan": amount_yuan,
    }

@app.post("/api/pocket-money/{record_id}/approve")
async def approve_pocket_money(record_id: int):
    """家长审批零花钱"""
    conn = get_db_connection()
    current_time = get_current_time()
    
    record = conn.execute("SELECT * FROM pocket_money_records WHERE id = ? AND status = 'pending'", (record_id,)).fetchone()
    if not record:
        conn.close()
        return {"success": False, "message": "记录不存在"}
    
    conn.execute("""
        UPDATE pocket_money_records SET status = 'approved', approved_at = ? WHERE id = ?
    """, (current_time.isoformat(), record_id))
    
    # 将 pending 的扣款记录标记为正式（SQLite 不支持 UPDATE + ORDER BY）
    conn.execute("""
        UPDATE coin_transactions SET source = 'pocket_money', description = ?
        WHERE id = (
            SELECT id FROM coin_transactions
            WHERE source = 'pocket_money_pending' AND amount = ?
            ORDER BY id DESC LIMIT 1
        )
    """, (f'兑换零花钱{record["amount_yuan"]}元（已审批）', -record['coins_spent']))
    
    conn.commit()
    conn.close()
    return {"success": True, "message": f"已批准：{record['coins_spent']}龙币 → {record['amount_yuan']}元"}

@app.post("/api/pocket-money/{record_id}/reject")
async def reject_pocket_money(record_id: int):
    """家长拒绝零花钱"""
    conn = get_db_connection()
    
    record = conn.execute("SELECT * FROM pocket_money_records WHERE id = ? AND status = 'pending'", (record_id,)).fetchone()
    if not record:
        conn.close()
        return {"success": False, "message": "记录不存在"}
    
    conn.execute("UPDATE pocket_money_records SET status = 'rejected' WHERE id = ?", (record_id,))
    
    # 退还龙币
    add_coins(conn, record['coins_spent'], 'pocket_money_refund', f'零花钱兑换被拒绝，退还龙币')
    
    conn.commit()
    conn.close()
    return {"success": True, "message": "已拒绝，龙币已退还"}

# ----- 专注打卡 API -----

@app.post("/api/focus/complete")
async def focus_complete(duration_minutes: int = Form(...)):
    """完成专注打卡"""
    conn = get_db_connection()
    current_time = get_current_time()
    today = current_time.strftime('%Y-%m-%d')
    
    # 每日最多3次
    count_today = conn.execute("""
        SELECT COUNT(*) FROM focus_sessions WHERE date(completed_at) = ?
    """, (today,)).fetchone()[0]
    if count_today >= 3:
        conn.close()
        return {"success": False, "message": "今天已经专注3次啦，明天继续加油！"}
    
    coins_earned = FOCUS_COINS.get(duration_minutes, 15)
    
    conn.execute("""
        INSERT INTO focus_sessions (duration_minutes, coins_earned, completed_at)
        VALUES (?, ?, ?)
    """, (duration_minutes, coins_earned, current_time.isoformat()))
    
    new_coins = add_coins(conn, coins_earned, 'focus', f'专注{duration_minutes}分钟', double_weekend=True)
    
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    pet_dict = dict(pet)
    new_mood = min(100, pet_dict['mood'] + 5)
    conn.execute("UPDATE pet SET mood = ? WHERE id = 1", (new_mood,))
    
    total_focus = conn.execute("SELECT COALESCE(SUM(duration_minutes), 0) FROM focus_sessions").fetchone()[0]
    total_coins_earned = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM coin_transactions WHERE type = 'earn'").fetchone()[0]
    check_achievements(conn, pet_dict['streak'], calculate_evolution_stage(pet_dict['exp']),
                       pet_dict.get('math_streak', 0), pet_dict.get('bond', 50), total_focus, total_coins_earned)
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": f"太棒了！专注{duration_minutes}分钟完成！+{coins_earned}龙币 🪙",
        "coins": coins_earned,
        "new_balance": new_coins,
        "duration": duration_minutes,
    }

@app.get("/api/focus/today")
async def get_focus_today():
    """获取今日专注统计"""
    conn = get_db_connection()
    today = get_current_time().strftime('%Y-%m-%d')
    sessions = conn.execute("""
        SELECT * FROM focus_sessions WHERE date(completed_at) = ? ORDER BY completed_at
    """, (today,)).fetchall()
    total = conn.execute("""
        SELECT COALESCE(SUM(duration_minutes), 0) FROM focus_sessions WHERE date(completed_at) = ?
    """, (today,)).fetchone()[0]
    conn.close()
    return {"sessions": [dict(s) for s in sessions], "total_minutes": total, "count": len(sessions)}

# ----- 商店 API -----

@app.get("/api/shop/accessories")
async def get_shop_accessories():
    """获取装饰商品列表"""
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM pet_accessories ORDER BY price").fetchall()
    conn.close()
    return {"items": [dict(i) for i in items]}

@app.post("/api/shop/buy/{item_id}")
async def buy_accessory(item_id: int):
    """购买装饰"""
    conn = get_db_connection()
    
    item = conn.execute("SELECT * FROM pet_accessories WHERE id = ?", (item_id,)).fetchone()
    if not item:
        conn.close()
        return {"success": False, "message": "商品不存在"}
    if item['owned']:
        conn.close()
        return {"success": False, "message": "已经拥有了"}
    
    pet = conn.execute("SELECT coins FROM pet WHERE id = 1").fetchone()
    if pet['coins'] < item['price']:
        conn.close()
        return {"success": False, "message": "龙币不够哦～"}
    
    add_coins(conn, -item['price'], 'shop', f'购买{item["name"]}')
    conn.execute("UPDATE pet_accessories SET owned = 1 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    
    return {"success": True, "message": f"购买成功！{item['name']}已加入背包 🎉"}

@app.post("/api/shop/equip/{item_id}")
async def equip_accessory(item_id: int):
    """装备/卸下装饰"""
    conn = get_db_connection()
    
    item = conn.execute("SELECT * FROM pet_accessories WHERE id = ? AND owned = 1", (item_id,)).fetchone()
    if not item:
        conn.close()
        return {"success": False, "message": "还没有这个装饰"}
    
    new_equipped = 0 if item['equipped'] else 1
    
    # 同类型只能装备一个
    if new_equipped:
        conn.execute("UPDATE pet_accessories SET equipped = 0 WHERE type = ?", (item['type'],))
    
    conn.execute("UPDATE pet_accessories SET equipped = ? WHERE id = ?", (new_equipped, item_id))
    conn.commit()
    conn.close()
    
    action = "装备" if new_equipped else "卸下"
    return {"success": True, "message": f"已{action}{item['name']}"}

# ----- 家长设置 API -----

@app.get("/api/parent/settings")
async def get_parent_settings():
    """获取家长设置"""
    conn = get_db_connection()
    settings = {}
    for row in conn.execute("SELECT key, value FROM parent_settings").fetchall():
        settings[row['key']] = row['value']
    conn.close()
    return {"settings": settings}

@app.post("/api/parent/settings")
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
    return {"success": True, "message": "设置已保存"}

@app.post("/api/parent/verify")
async def verify_parent(password: str = Form(...)):
    """验证家长密码"""
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM parent_settings WHERE key = 'parent_password'").fetchone()
    conn.close()
    stored = row['value'] if row else '1234'
    if password == stored:
        return {"success": True}
    return {"success": False, "message": "密码错误"}

@app.post("/api/parent/change-password")
async def change_parent_password(
    old_password: str = Form(...),
    new_password: str = Form(...),
):
    """修改家长密码"""
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM parent_settings WHERE key = 'parent_password'").fetchone()
    stored = row['value'] if row else '1234'
    if old_password != stored:
        conn.close()
        return {"success": False, "message": "原密码错误"}
    if len(new_password) < 4:
        conn.close()
        return {"success": False, "message": "新密码至少4位"}
    conn.execute("UPDATE parent_settings SET value = ? WHERE key = 'parent_password'", (new_password,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "密码修改成功"}

@app.post("/api/parent/reset-data")
async def reset_data(password: str = Form(...)):
    """重置所有游戏数据（需要家长密码验证）"""
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM parent_settings WHERE key = 'parent_password'").fetchone()
    stored = row['value'] if row else '1234'
    if password != stored:
        conn.close()
        return {"success": False, "message": "密码错误"}

    # 重置宠物
    conn.execute("""
        UPDATE pet SET exp=0, level=1, hunger=80, mood=80, bond=50, coins=0,
        streak=0, math_streak=0, status='happy', runaway_until=NULL,
        last_streak_date=NULL, last_math_date=NULL, last_decay_date=NULL,
        math_challenge_today=0, updated_at=? WHERE id=1
    """, (get_current_time().isoformat(),))

    # 清空各表
    for table in ['tasks', 'custom_tasks', 'behavior_records', 'coin_transactions',
                  'focus_sessions', 'pocket_money_records', 'random_surprises', 'treasure_log']:
        conn.execute(f"DELETE FROM {table}")

    # 重置成就
    conn.execute("UPDATE achievements SET unlocked=0, unlocked_at=NULL")

    conn.commit()
    conn.close()
    return {"success": True, "message": "所有游戏数据已重置！"}

# ----- 商店直接喂食 API -----

@app.post("/api/shop/buy-feed")
async def shop_buy_feed(food_name: str = Form("肉骨头"), food_emoji: str = Form("🍖"), price: int = Form(5)):
    """商店购买零食并直接喂食"""
    conn = get_db_connection()
    current_time = get_current_time()
    
    logger.info(f"[shop/buy-feed] 收到请求: food_name={food_name}, food_emoji={food_emoji}, price={price}")
    
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    pet_dict = dict(pet)
    
    logger.info(f"[shop/buy-feed] 宠物当前状态: status={pet_dict['status']}, coins={pet_dict['coins']}, hunger={pet_dict['hunger']}, mood={pet_dict['mood']}, bond={pet_dict.get('bond', 50)}")
    
    if pet_dict['status'] == 'sleeping':
        conn.close()
        logger.warning(f"[shop/buy-feed] 购买失败: 小龙在睡觉")
        return {"success": False, "message": "嘘...小龙正在睡觉～"}
    
    if pet_dict['coins'] < price:
        conn.close()
        logger.warning(f"[shop/buy-feed] 购买失败: 龙币不足 (当前={pet_dict['coins']}, 需要={price})")
        return {"success": False, "message": "龙币不够哦～"}
    
    # 扣龙币（原子操作，同时写入交易记录）
    new_coins = add_coins(conn, -price, 'shop_feed', f'购买{food_name}喂小龙')
    logger.info(f"[shop/buy-feed] 扣减龙币: {pet_dict['coins']} -> {new_coins} (交易记录已写入)")
    
    # 不同食物不同的效果
    food_effects = {
        '肉骨头': {'hunger': 25, 'mood': 8},
        '小鱼干': {'hunger': 20, 'mood': 12},
        '蛋糕': {'hunger': 30, 'mood': 15},
        '冰淇淋': {'hunger': 15, 'mood': 18},
        '水果拼盘': {'hunger': 20, 'mood': 10},
        '烤鸡腿': {'hunger': 35, 'mood': 12},
    }
    effect = food_effects.get(food_name, {'hunger': 25, 'mood': 8})
    new_hunger = min(100, pet_dict['hunger'] + effect['hunger'])
    new_mood = min(100, pet_dict['mood'] + effect['mood'])
    new_bond = min(100, (pet_dict.get('bond') or 50) + 1)
    
    conn.execute("""
        UPDATE pet SET hunger = ?, mood = ?, bond = ?, status = 'happy', updated_at = ? WHERE id = 1
    """, (new_hunger, new_mood, new_bond, current_time.isoformat()))
    conn.commit()
    logger.info(f"[shop/buy-feed] 喂食完成: hunger={new_hunger}, mood={new_mood}, bond={new_bond}")
    
    conn.close()
    
    return {
        "success": True,
        "message": f"给小龙买了{food_emoji}{food_name}！小龙吃得好开心～",
        "food_name": food_name,
        "food_emoji": food_emoji,
        "new_coins": new_coins,
        "hunger": new_hunger,
        "mood": new_mood,
    }

# ----- 孩子端：今日行为记录 API -----

@app.get("/api/behavior/today")
async def get_today_behavior():
    """获取今日行为评价记录（孩子端可见）"""
    conn = get_db_connection()
    today = get_current_time().strftime('%Y-%m-%d')
    records = conn.execute("""
        SELECT * FROM behavior_records WHERE date(created_at) = ? ORDER BY created_at DESC
    """, (today,)).fetchall()
    
    # 统计今日龙币变化
    total_positive = sum(r['coins'] for r in records if r['coins'] > 0)
    total_negative = sum(r['coins'] for r in records if r['coins'] < 0)
    
    conn.close()
    return {
        "records": [dict(r) for r in records],
        "total_positive": total_positive,
        "total_negative": total_negative,
        "net": total_positive + total_negative,
    }

@app.get("/api/wallet/detail")
async def get_wallet_detail(limit: int = 30):
    """钱包详情：交易记录+累计零花钱统计"""
    conn = get_db_connection()
    today = get_current_time()
    today_str = today.strftime('%Y-%m-%d')
    week_start = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
    month_start = today.strftime('%Y-%m-01')

    pet = conn.execute("SELECT coins FROM pet WHERE id = 1").fetchone()

    # 交易记录
    txns = conn.execute("""
        SELECT * FROM coin_transactions ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()

    # 本周零花钱
    weekly_pocket = conn.execute("""
        SELECT COALESCE(SUM(amount_yuan), 0) FROM pocket_money_records
        WHERE status = 'approved' AND date(approved_at) >= ?
    """, (week_start,)).fetchone()[0]

    # 本月零花钱
    monthly_pocket = conn.execute("""
        SELECT COALESCE(SUM(amount_yuan), 0) FROM pocket_money_records
        WHERE status = 'approved' AND date(approved_at) >= ?
    """, (month_start,)).fetchone()[0]

    # 累计零花钱
    total_pocket = conn.execute("""
        SELECT COALESCE(SUM(amount_yuan), 0) FROM pocket_money_records
        WHERE status = 'approved'
    """).fetchone()[0]

    # 本周收入/支出统计
    weekly_earned = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM coin_transactions
        WHERE type = 'earn' AND date(created_at) >= ?
    """, (week_start,)).fetchone()[0]
    weekly_spent = conn.execute("""
        SELECT COALESCE(SUM(ABS(amount)), 0) FROM coin_transactions
        WHERE type = 'spend' AND date(created_at) >= ?
    """, (week_start,)).fetchone()[0]

    # 汇率
    rate_row = conn.execute("SELECT value FROM parent_settings WHERE key = 'exchange_rate'").fetchone()
    exchange_rate = int(rate_row['value']) if rate_row else 100

    conn.close()
    return {
        "balance": pet['coins'],
        "transactions": [dict(t) for t in txns],
        "weekly_pocket": round(weekly_pocket, 2),
        "monthly_pocket": round(monthly_pocket, 2),
        "total_pocket": round(total_pocket, 2),
        "weekly_earned": weekly_earned,
        "weekly_spent": weekly_spent,
        "exchange_rate": exchange_rate,
    }


@app.get("/api/weekly-report")
async def get_weekly_report():
    """学习周报：过去7天的作业完成、龙币、专注等统计"""
    conn = get_db_connection()
    today = get_current_time()
    today_str = today.strftime('%Y-%m-%d')

    daily_data = []
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        day_label = (today - timedelta(days=i)).strftime('%m/%d')

        # 作业完成数
        tasks_done = conn.execute("""
            SELECT COUNT(*) as cnt FROM tasks WHERE created_date = ? AND completed = 1
        """, (d,)).fetchone()['cnt']

        # 获取龙币
        coins_earned = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM coin_transactions
            WHERE type = 'earn' AND date(created_at) = ?
        """, (d,)).fetchone()[0]

        coins_spent = conn.execute("""
            SELECT COALESCE(SUM(ABS(amount)), 0) FROM coin_transactions
            WHERE type = 'spend' AND date(created_at) = ?
        """, (d,)).fetchone()[0]

        # 专注时长
        focus_mins = conn.execute("""
            SELECT COALESCE(SUM(duration_minutes), 0) FROM focus_sessions
            WHERE date(completed_at) = ?
        """, (d,)).fetchone()[0]

        # 额外任务完成
        custom_done = conn.execute("""
            SELECT COUNT(*) as cnt FROM custom_tasks
            WHERE status = 'completed' AND date(completed_at) = ?
        """, (d,)).fetchone()['cnt']

        # 行为评价加分
        behavior_coins = conn.execute("""
            SELECT COALESCE(SUM(coins), 0) FROM behavior_records
            WHERE date(created_at) = ? AND coins > 0
        """, (d,)).fetchone()[0]

        daily_data.append({
            "date": d,
            "label": day_label,
            "tasks_done": tasks_done,
            "coins_earned": coins_earned,
            "coins_spent": coins_spent,
            "focus_mins": focus_mins,
            "custom_done": custom_done,
            "behavior_coins": behavior_coins,
            "is_today": d == today_str,
        })

    # 本周汇总
    week_start = (today - timedelta(days=6)).strftime('%Y-%m-%d')
    week_tasks = sum(d['tasks_done'] for d in daily_data)
    week_coins = sum(d['coins_earned'] for d in daily_data)
    week_focus = sum(d['focus_mins'] for d in daily_data)
    week_custom = sum(d['custom_done'] for d in daily_data)

    # 今日行为记录（孩子端可见）
    today_behavior = []
    if today_str:
        today_behavior = conn.execute("""
            SELECT * FROM behavior_records WHERE date(created_at) = ? ORDER BY created_at DESC
        """, (today_str,)).fetchall()

    conn.close()
    return {
        "daily_data": daily_data,
        "week_summary": {
            "tasks": week_tasks,
            "coins": week_coins,
            "focus_mins": week_focus,
            "custom_tasks": week_custom,
        },
        "today_behavior": [dict(b) for b in today_behavior],
    }


# ----- 鼓励消息 API -----

@app.post("/api/encourage")
async def send_encourage(message: str = Form(...)):
    """家长发送鼓励消息"""
    conn = get_db_connection()
    current_time = get_current_time()
    expires_at = current_time + timedelta(hours=24)
    conn.execute("DELETE FROM encourage")
    conn.execute("INSERT INTO encourage (message, created_at, expires_at) VALUES (?, ?, ?)",
                 (message, current_time.isoformat(), expires_at.isoformat()))
    conn.commit()
    conn.close()
    return {"success": True, "message": "鼓励消息已发送！"}

@app.get("/api/encourage")
async def get_encourage():
    """获取当前鼓励消息"""
    conn = get_db_connection()
    current_time = get_current_time()
    encourage = conn.execute("""
        SELECT * FROM encourage WHERE expires_at > ? ORDER BY created_at DESC LIMIT 1
    """, (current_time.isoformat(),)).fetchone()
    conn.close()
    if encourage:
        return {"encourage": dict(encourage)}
    return {"encourage": None}

# ----- v3.1 新增 API -----

@app.get("/api/pet/mood")
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
    }


@app.get("/api/random-surprise")
async def check_random_surprise():
    """检查随机惊喜（每次打开页面/刷新时调用，每天最多1次）"""
    conn = get_db_connection()
    current_time = get_current_time()
    today = current_time.strftime('%Y-%m-%d')
    
    # 检查今天是否已获得惊喜
    existing = conn.execute("""
        SELECT * FROM random_surprises WHERE date(created_at) = ?
    """, (today,)).fetchone()
    
    if existing:
        conn.close()
        return {"surprise": None, "message": "今天已经收到过惊喜了，明天再来吧～"}
    
    # 20% 概率触发
    if random.random() > 0.2:
        conn.close()
        return {"surprise": None, "message": ""}
    
    # 随机奖励池
    surprise_pool = [
        {'type': 'coins', 'value': 15, 'desc': '小龙偷偷塞给你15龙币！🪙'},
        {'type': 'coins', 'value': 25, 'desc': '小龙找到藏起来的宝藏！+25龙币！💰'},
        {'type': 'coins', 'value': 50, 'desc': '哇！小龙挖到了大宝藏！+50龙币！✨'},
        {'type': 'exp', 'value': 30, 'desc': '小龙分享了一个学习心得！+30经验！📖'},
        {'type': 'exp', 'value': 50, 'desc': '小龙陪你看了一本书！+50经验！📚'},
        {'type': 'bond', 'value': 10, 'desc': '小龙偷偷抱了你一下！亲密度+10 💕'},
        {'type': 'title', 'value': 0, 'desc': '小龙授予你称号「小可爱」！🎀', 'title_name': '小可爱'},
        {'type': 'title', 'value': 0, 'desc': '小龙授予你称号「小天才」！🧠', 'title_name': '小天才'},
        {'type': 'mood', 'value': 15, 'desc': '小龙给你表演了一个节目！心情+15 🎭'},
    ]
    
    surprise = random.choice(surprise_pool)
    
    # 应用奖励
    if surprise['type'] == 'coins':
        add_coins(conn, surprise['value'], 'random_surprise', surprise['desc'])
    elif surprise['type'] == 'exp':
        conn.execute("UPDATE pet SET exp = exp + ? WHERE id = 1", (surprise['value'],))
    elif surprise['type'] == 'bond':
        conn.execute("UPDATE pet SET bond = min(100, bond + ?) WHERE id = 1", (surprise['value'],))
    elif surprise['type'] == 'mood':
        conn.execute("UPDATE pet SET mood = min(100, mood + ?) WHERE id = 1", (surprise['value'],))
    
    # 记录
    conn.execute("""
        INSERT INTO random_surprises (surprise_type, reward_value, description)
        VALUES (?, ?, ?)
    """, (surprise['type'], surprise['value'], surprise['desc']))
    
    conn.commit()
    conn.close()
    
    return {"surprise": surprise}


@app.get("/api/event/status")
async def get_event_status():
    """获取当前活动状态"""
    current_time = get_current_time()
    weekday = current_time.weekday()  # 0=周一 ... 6=周日
    
    is_weekend = weekday >= 5
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    
    events = []
    
    if is_weekend:
        events.append({
            "name": "周末双倍龙币",
            "icon": "🎉",
            "desc": f"本周{weekday_names[weekday]}，所有龙币奖励翻倍！",
            "active": True,
        })
    
    conn = get_db_connection()
    pet = conn.execute("SELECT math_challenge_today, last_math_date FROM pet WHERE id = 1").fetchone()
    today = current_time.strftime('%Y-%m-%d')
    
    # 数学挑战赛：每天首题数学额外 +20 龙币
    challenge_done = pet['math_challenge_today'] if pet['math_challenge_today'] else 0
    challenge_date_match = pet['last_math_date'] == today if pet['last_math_date'] else False
    
    events.append({
        "name": "数学挑战赛",
        "icon": "⚔️",
        "desc": "每天第一道数学作业额外+20龙币！",
        "active": True,
        "claimed_today": challenge_done and challenge_date_match,
    })
    
    conn.close()
    
    return {
        "is_weekend": is_weekend,
        "weekday_name": weekday_names[weekday],
        "events": events,
    }

# ----- 定时任务 -----

@app.post("/api/scheduler/run")
async def scheduler_check():
    """定时检查：处理宠物状态、过期任务"""
    conn = get_db_connection()
    current_time = get_current_time()
    today = current_time.strftime('%Y-%m-%d')
    
    logger.info(f"[scheduler] 开始定时检查, 当前时间={current_time.strftime('%H:%M:%S')}")
    
    # 检查今天是否完成作业
    today_tasks = conn.execute("""
        SELECT COUNT(*) as cnt FROM tasks WHERE created_date = ? AND completed = 1
    """, (today,)).fetchone()
    
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    pet_dict = dict(pet)
    
    # 睡眠结束自动唤醒
    if pet_dict['status'] == 'sleeping' and pet_dict.get('runaway_until'):
        try:
            sleep_end_str = pet_dict['runaway_until']
            if sleep_end_str.endswith('+00:00') or '+' in sleep_end_str:
                from datetime import timezone
                sleep_end = datetime.fromisoformat(sleep_end_str)
                if sleep_end.tzinfo is None:
                    sleep_end = sleep_end.replace(tzinfo=timezone.utc)
                sleep_end = sleep_end.astimezone(tz)
            else:
                sleep_end = datetime.fromisoformat(sleep_end_str)
                if sleep_end.tzinfo is None:
                    sleep_end = tz.localize(sleep_end)
            
            if sleep_end < current_time:
                conn.execute("""
                    UPDATE pet SET status = 'normal', runaway_until = NULL, mood = 40, hunger = 40
                    WHERE id = 1
                """)
                conn.commit()
                logger.info(f"[scheduler] 小龙睡眠结束，自动唤醒 (sleep_end={sleep_end})")
        except Exception as e:
            logger.error(f"[scheduler] 检查睡眠结束时间出错: {e}")
    
    # 重新获取宠物状态（可能已唤醒）
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    pet_dict = dict(pet)
    
    # 21点没完成作业 → 宠物睡觉（仅当 status 不是 sleeping 时）
    if pet_dict['status'] != 'sleeping' and today_tasks['cnt'] == 0 and current_time.hour >= 21:
        sleep_until = current_time + timedelta(hours=8)
        conn.execute("""
            UPDATE pet SET status = 'sleeping', runaway_until = ?,
                hunger = max(0, hunger - 15), mood = max(0, mood - 20),
                bond = max(0, bond - 3)
            WHERE id = 1
        """, (sleep_until.isoformat(),))
        conn.commit()
        logger.info(f"[scheduler] 21点无作业完成，小龙进入睡眠，预计 {sleep_until.strftime('%H:%M')} 醒来")
    
    # 实时衰减：按真实经过时间累计，饱腹低于 30 后自动放慢，避免快速归零
    if pet_dict['status'] != 'sleeping':
        last_decay = pet_dict.get('last_decay_date')
        decay_time = None
        if last_decay is None:
            decay_time = current_time
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
            except Exception:
                decay_time = current_time

        hours_diff = max(0, (current_time - decay_time).total_seconds() / 3600) if decay_time else 0
        if hours_diff >= 0.1:
            decayed = calculate_realtime_decay({
                'hunger': pet_dict['hunger'],
                'mood': pet_dict['mood'],
                'bond': pet_dict.get('bond', 50),
            }, hours_diff)
            conn.execute("""
                UPDATE pet SET hunger = ?, mood = ?, bond = ?, last_decay_date = ?
                WHERE id = 1
            """, (decayed['hunger'], decayed['mood'], decayed['bond'], current_time.isoformat()))
            logger.info(
                f"[scheduler] 实时衰减执行: hours={hours_diff:.2f}, "
                f"hunger {pet_dict['hunger']}->{decayed['hunger']}, "
                f"mood {pet_dict['mood']}->{decayed['mood']}, "
                f"bond {pet_dict.get('bond', 50)}->{decayed['bond']}"
            )
        elif last_decay is None:
            conn.execute("UPDATE pet SET last_decay_date = ? WHERE id = 1", (current_time.isoformat(),))
    
    # 重置每日数学挑战赛标记（每天0点重置）
    if pet_dict.get('math_challenge_today', 0) > 0 and pet_dict.get('last_math_date') != today:
        conn.execute("UPDATE pet SET math_challenge_today = 0 WHERE id = 1")
    
    # 过期额外任务标记
    conn.execute("""
        UPDATE custom_tasks SET status = 'expired' 
        WHERE status = 'pending' AND deadline IS NOT NULL AND deadline < ?
    """, (today,))
    
    # 清理过期鼓励消息
    conn.execute("DELETE FROM encourage WHERE expires_at < ?", (current_time.isoformat(),))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "定时检查完成"}



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
        ], 'icon': '🐲', 'desc': '经典的紫色到金色渐变', 'price': 0},
    'fire': {'name': '火焰小龙',
        'colors': ['#FF6B6B', '#FF5252', '#FF1744', '#D50000', '#FF6D00'],
        'bg_gradients': [
            'linear-gradient(135deg, #FFCDD2, #FF6B6B)',
            'linear-gradient(135deg, #FFCDD2, #FF5252)',
            'linear-gradient(135deg, #FF8A80, #FF1744)',
            'linear-gradient(135deg, #FF9E80, #D50000)',
            'linear-gradient(135deg, #FFD180, #FF6D00)',
        ], 'icon': '🔥', 'desc': '热情似火的红色小龙', 'price': 50},
    'ice': {'name': '冰雪小龙',
        'colors': ['#80DEEA', '#4DD0E1', '#26C6DA', '#00ACC1', '#0097A7'],
        'bg_gradients': [
            'linear-gradient(135deg, #E0F7FA, #80DEEA)',
            'linear-gradient(135deg, #E0F7FA, #4DD0E1)',
            'linear-gradient(135deg, #B2EBF2, #26C6DA)',
            'linear-gradient(135deg, #80DEEA, #00ACC1)',
            'linear-gradient(135deg, #4DD0E1, #0097A7)',
        ], 'icon': '❄️', 'desc': '冰冰凉凉的冰雪小龙', 'price': 50},
    'gold': {'name': '黄金小龙',
        'colors': ['#FFD740', '#FFC400', '#FFAB00', '#FF8F00', '#FF6F00'],
        'bg_gradients': [
            'linear-gradient(135deg, #FFF8E1, #FFD740)',
            'linear-gradient(135deg, #FFF8E1, #FFC400)',
            'linear-gradient(135deg, #FFECB3, #FFAB00)',
            'linear-gradient(135deg, #FFE082, #FF8F00)',
            'linear-gradient(135deg, #FFD54F, #FF6F00)',
        ], 'icon': '👑', 'desc': '闪闪发光的黄金小龙', 'price': 50},
    'nature': {'name': '森林小龙',
        'colors': ['#81C784', '#66BB6A', '#4CAF50', '#388E3C', '#2E7D32'],
        'bg_gradients': [
            'linear-gradient(135deg, #E8F5E9, #81C784)',
            'linear-gradient(135deg, #E8F5E9, #66BB6A)',
            'linear-gradient(135deg, #C8E6C9, #4CAF50)',
            'linear-gradient(135deg, #A5D6A7, #388E3C)',
            'linear-gradient(135deg, #81C784, #2E7D32)',
        ], 'icon': '🌿', 'desc': '充满生机的森林小龙', 'price': 50},
}

@app.get("/api/pet/skins")
async def get_pet_skins():
    """获取所有可用皮肤"""
    conn = get_db_connection()
    current_skin = conn.execute("SELECT value FROM parent_settings WHERE key = 'current_skin'").fetchone()
    current = current_skin['value'] if current_skin else 'default'
    unlocked_row = conn.execute("SELECT value FROM parent_settings WHERE key = 'unlocked_skins'").fetchone()
    pet = conn.execute("SELECT exp FROM pet WHERE id = 1").fetchone()
    current_stage = calculate_evolution_stage(pet['exp']) if pet else 0
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
            'price': skin.get('price', 0),
            'image': get_skin_stage_image_path(skin_id, current_stage),
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
async def unlock_pet_skin(skin_id: str = Form(...)):
    if skin_id not in PET_SKINS or skin_id == 'default':
        return {"success": False, "message": "皮肤不存在或无法解锁"}
    price = PET_SKINS[skin_id].get('price', 50)
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
    return {"success": True, "message": f"解锁成功！获得{PET_SKINS[skin_id]['name']}", "new_coins": pet['coins'] - price}

# ===== v3.2 算术题互动游戏 =====

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
async def answer_math_quiz(answer: int = Form(...), correct_answer: int = Form(...)):
    """检查算术题答案"""
    correct = answer == correct_answer
    conn = get_db_connection()
    current_time = get_current_time()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    if pet['status'] == 'sleeping':
        conn.close()
        return {"success": False, "message": "嘘...小龙正在睡觉"}
    pet_dict = dict(pet)
    bond = pet_dict.get('bond', 50)
    if correct:
        new_coins = add_coins(conn, 10, 'math_quiz', '算术题答对啦！+10龙币')
        new_mood = min(100, pet['mood'] + 5)
        new_bond = min(100, bond + 2)
        bubble = random.choice(["答对啦！数学小天才！🧮", "完全正确！你好厉害！🎉", "太棒了！小龙为你骄傲！😎"])
    else:
        new_coins = pet['coins']
        new_mood = min(100, pet['mood'] + 1)
        new_bond = min(100, bond + 1)
        bubble = random.choice(["不对哦～再想想！🤔", "差一点点！再来！", "下次一定能算对！💪", "没关系，再试试吧！📝"])
    conn.execute("UPDATE pet SET mood = ?, bond = ?, updated_at = ? WHERE id = 1",
                 (new_mood, new_bond, current_time.isoformat()))
    conn.execute("""
        INSERT INTO coin_transactions (type, source, amount, balance_after, description)
        VALUES ('earn', 'math_quiz', ?, (SELECT coins FROM pet WHERE id = 1), ?)
    """, (10 if correct else 0, f'算术题:答案{answer}正确答案{correct_answer}'))
    conn.commit()
    conn.close()
    return {
        "success": True,
        "correct": correct,
        "new_coins": new_coins,
        "mood": new_mood,
        "bond": new_bond,
        "bubble": bubble,
    }

# ===== 启动 =====

if __name__ == "__main__":
    import uvicorn
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
