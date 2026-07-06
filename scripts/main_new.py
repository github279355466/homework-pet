import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import pytz

from database import get_db_connection, init_db

# 默认任务配置
DEFAULT_TASKS = [
    {'name': '语文', 'type': 'daily', 'exp': 50},
    {'name': '数学', 'type': 'daily', 'exp': 50},
    {'name': '英语', 'type': 'daily', 'exp': 50},
    {'name': '其他', 'type': 'daily', 'exp': 50},
    {'name': '课外阅读', 'type': 'extra', 'exp': 30},
    {'name': '练字', 'type': 'extra', 'exp': 30},
]

app = FastAPI(title="作业小龙")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置 Jinja2 模板
templates = Jinja2Templates(directory="app/templates")

# 时区
tz = pytz.timezone('Asia/Shanghai')

def get_current_time():
    return datetime.now(tz)

def calculate_level(exp):
    """根据经验值计算等级"""
    # 等级公式: 每1000经验升一级
    return min(99, exp // 1000 + 1)

def get_pet_appearance(level, status):
    """根据等级和状态获取宠物外观"""
    if status == 'runaway':
        return {
            'emoji': '💨',
            'name': '离家出走中',
            'color': '#888888'
        }
    
    if level < 10:
        base_emoji = '🐣'
    elif level < 30:
        base_emoji = '🐲'
    elif level < 60:
        base_emoji = '🐉'
    else:
        base_emoji = '🌟'
    
    if status == 'sad':
        emoji = '😢'
    elif status == 'hungry':
        emoji = '😫'
    elif status == 'normal':
        emoji = '😊'
    else:
        emoji = '😊'
    
    return {
        'emoji': emoji,
        'base': base_emoji,
        'name': '开心' if status == 'happy' else '一般' if status == 'normal' else '难过' if status == 'sad' else '饿坏了',
        'color': '#4CAF50' if status == 'happy' else '#FFC107' if status == 'normal' else '#F44336'
    }

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, role: str = "kid"):
    """主页"""
    conn = get_db_connection()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    tasks_today = conn.execute("""
        SELECT * FROM tasks 
        WHERE created_date = date('now')
        ORDER BY id DESC
    """).fetchall()
    achievements = conn.execute("SELECT * FROM achievements").fetchall()
    conn.close()
    
    # 处理宠物状态
    current_time = get_current_time()
    if pet['runaway_until']:
        runaway_time = datetime.fromisoformat(pet['runaway_until'])
        if runaway_time < current_time:
            # 宠物回家
            conn = get_db_connection()
            conn.execute("""
                UPDATE pet SET status = 'happy', runaway_until = NULL, mood = 50
                WHERE id = 1
            """)
            conn.commit()
            conn.close()
            pet = dict(pet)
            pet['status'] = 'happy'
    
    appearance = get_pet_appearance(pet['level'], pet['status'])
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "pet": dict(pet),
        "appearance": appearance,
        "tasks": [dict(t) for t in tasks_today],
        "achievements": [dict(a) for a in achievements],
        "role": role,
        "today": get_current_time().strftime('%Y-%m-%d')
    })

@app.get("/api/pet")
async def get_pet():
    """获取宠物状态"""
    conn = get_db_connection()
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    conn.close()
    
    if pet:
        appearance = get_pet_appearance(pet['level'], pet['status'])
        return {"pet": dict(pet), "appearance": appearance}
    return {"error": "宠物不存在"}

@app.post("/api/task/complete")
async def complete_task(
    task_type: str = Form("daily"),
    subject: str = Form("语文"),
    completed_by: str = Form("kid")
):
    """完成任务"""
    conn = get_db_connection()
    today = get_current_time().strftime('%Y-%m-%d')
    current_time = get_current_time()
    
    # 检查今天是否已有该科目任务
    existing = conn.execute("""
        SELECT * FROM tasks 
        WHERE subject = ? AND created_date = ? AND completed = 1
    """, (subject, today)).fetchone()
    
    if existing:
        conn.close()
        return {"success": False, "message": f"今天{subject}已经完成过了！"}
    
    # 经验奖励
    exp_reward = 50 if task_type == "daily" else 30
    
    # 插入任务
    cursor = conn.execute("""
        INSERT INTO tasks (task_type, subject, completed, completed_by, completed_at, exp_reward, created_date)
        VALUES (?, ?, 1, ?, ?, ?, ?)
    """, (task_type, subject, completed_by, current_time.isoformat(), exp_reward, today))
    
    # 更新宠物状态
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    new_exp = pet['exp'] + exp_reward
    new_level = calculate_level(new_exp)
    new_hunger = min(100, pet['hunger'] + 20)
    new_mood = min(100, pet['mood'] + 10)
    new_streak = pet['streak'] + 1
    
    # 检查是否21点前完成（额外奖励）
    if current_time.hour < 21:
        new_mood = min(100, new_mood + 20)
    
    # 更新宠物
    conn.execute("""
        UPDATE pet SET 
            exp = ?, level = ?, hunger = ?, mood = ?, streak = ?, 
            status = 'happy', updated_at = ?
        WHERE id = 1
    """, (new_exp, new_level, new_hunger, new_mood, new_streak, current_time.isoformat()))
    
    # 检查成就
    check_achievements(conn, new_streak, new_level)
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": f"太棒了！{subject}完成了！+{exp_reward}经验", "exp": exp_reward}

def check_achievements(conn, streak, level):
    """检查并解锁成就"""
    achievements = conn.execute("SELECT * FROM achievements WHERE unlocked = 0").fetchall()
    current_time = get_current_time()
    
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
        elif ach['name'] == '龙之守护者' and level >= 99:
            unlocked = True
        
        if unlocked:
            conn.execute("""
                UPDATE achievements SET unlocked = 1, unlocked_at = ?
                WHERE id = ?
            """, (current_time.isoformat(), ach['id']))

@app.post("/api/pet/feed")
async def feed_pet():
    """喂食"""
    conn = get_db_connection()
    current_time = get_current_time()
    
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    new_hunger = min(100, pet['hunger'] + 30)
    new_mood = min(100, pet['mood'] + 10)
    
    conn.execute("""
        UPDATE pet SET hunger = ?, mood = ?, updated_at = ?
        WHERE id = 1
    """, (new_hunger, new_mood, current_time.isoformat()))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "喂食成功！宠物饱饱的！"}

@app.get("/api/tasks")
async def get_tasks():
    """获取今日任务"""
    conn = get_db_connection()
    today = get_current_time().strftime('%Y-%m-%d')
    tasks = conn.execute("""
        SELECT * FROM tasks WHERE created_date = ? ORDER BY id DESC
    """, (today,)).fetchall()
    conn.close()
    
    return {"tasks": [dict(t) for t in tasks]}

@app.get("/api/achievements")
async def get_achievements():
    """获取成就"""
    conn = get_db_connection()
    achievements = conn.execute("SELECT * FROM achievements ORDER BY id").fetchall()
    conn.close()
    
    return {"achievements": [dict(a) for a in achievements]}

@app.post("/api/scheduler/run")
async def scheduler_check():
    """定时检查：处理宠物状态"""
    conn = get_db_connection()
    current_time = get_current_time()
    today = current_time.strftime('%Y-%m-%d')
    
    # 检查今天是否完成作业
    today_tasks = conn.execute("""
        SELECT COUNT(*) as cnt FROM tasks 
        WHERE created_date = ? AND completed = 1
    """, (today,)).fetchone()
    
    pet = conn.execute("SELECT * FROM pet WHERE id = 1").fetchone()
    
    # 如果今天没完成作业，且宠物还在happy状态
    if today_tasks['cnt'] == 0 and pet['status'] == 'happy':
        # 检查是否已经过了21点
        if current_time.hour >= 21:
            # 宠物离家出走
            runaway_until = current_time + timedelta(hours=2)  # 2小时后回来
            conn.execute("""
                UPDATE pet SET 
                    status = 'runaway', 
                    runaway_until = ?,
                    hunger = max(0, hunger - 20),
                    mood = max(0, mood - 30)
                WHERE id = 1
            """, (runaway_until.isoformat(),))
            conn.commit()
    
    # 宠物自然饥饿衰减
    conn.execute("""
        UPDATE pet SET 
            hunger = max(0, hunger - 1),
            mood = max(0, mood - 1)
        WHERE id = 1
    """)
    conn.commit()
    conn.close()
    
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
