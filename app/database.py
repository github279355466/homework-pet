import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional

DEFAULT_DATABASE_URL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "homework_pet.db")

def get_database_url():
    """返回当前数据库路径。默认使用真实数据库，测试可通过环境变量隔离。"""
    return os.environ.get("HOMEWORK_PET_DB_PATH", DEFAULT_DATABASE_URL)

def get_db_connection():
    conn = sqlite3.connect(get_database_url(), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ===== 宠物表 =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pet (
            id INTEGER PRIMARY KEY,
            name TEXT DEFAULT '作业小龙',
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            hunger INTEGER DEFAULT 80,
            mood INTEGER DEFAULT 80,
            streak INTEGER DEFAULT 0,
            status TEXT DEFAULT 'happy',
            runaway_until DATETIME,
            last_streak_date DATE,
            math_streak INTEGER DEFAULT 0,
            last_math_date DATE,
            bond INTEGER DEFAULT 50,
            coins INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 兼容旧数据库，逐个添加新字段
    for col, default in [
        ('last_streak_date', None),
        ('math_streak', 0),
        ('last_math_date', None),
        ('bond', 50),
        ('coins', 0),
        ('last_decay_date', None),
        ('math_challenge_today', 0),
    ]:
        try:
            if default is not None:
                cursor.execute(f"ALTER TABLE pet ADD COLUMN {col} INTEGER DEFAULT {default}")
            else:
                cursor.execute(f"ALTER TABLE pet ADD COLUMN {col} DATE")
        except Exception:
            pass
    
    # ===== 任务表 =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            task_type TEXT DEFAULT 'daily',
            subject TEXT,
            completed BOOLEAN DEFAULT 0,
            completed_by TEXT,
            completed_at DATETIME,
            exp_reward INTEGER DEFAULT 50,
            created_date DATE
        )
    """)
    
    # ===== 成就表 =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT,
            icon TEXT,
            unlocked BOOLEAN DEFAULT 0,
            unlocked_at DATETIME
        )
    """)
    
    # ===== 鼓励消息表 =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS encourage (
            id INTEGER PRIMARY KEY,
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME
        )
    """)
    
    # ===== 宝箱记录表 =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treasure_log (
            id INTEGER PRIMARY KEY,
            reward_type TEXT,
            reward_name TEXT,
            reward_icon TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ===== v3.0 新增表 =====

    # 随机惊喜记录
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS random_surprises (
            id INTEGER PRIMARY KEY,
            surprise_type TEXT NOT NULL,
            reward_value INTEGER NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 家长额外任务
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_tasks (
            id INTEGER PRIMARY KEY,
            subject TEXT NOT NULL,
            category TEXT DEFAULT 'other',
            exp_reward INTEGER DEFAULT 30,
            coins_reward INTEGER DEFAULT 3,
            deadline DATE,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME
        )
    """)
    
    # 行为评价规则
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS behavior_rules (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            coins INTEGER NOT NULL,
            category TEXT NOT NULL,
            icon TEXT,
            is_custom INTEGER DEFAULT 0
        )
    """)
    
    # 行为评价记录
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS behavior_records (
            id INTEGER PRIMARY KEY,
            rule_id INTEGER,
            rule_name TEXT,
            coins INTEGER NOT NULL,
            category TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 龙币交易记录
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coin_transactions (
            id INTEGER PRIMARY KEY,
            type TEXT NOT NULL,
            source TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 零花钱记录
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pocket_money_records (
            id INTEGER PRIMARY KEY,
            coins_spent INTEGER NOT NULL,
            amount_yuan REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            approved_at DATETIME
        )
    """)
    
    # 专注打卡记录
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY,
            duration_minutes INTEGER NOT NULL,
            coins_earned INTEGER NOT NULL,
            completed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 宠物装饰
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pet_accessories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            price INTEGER NOT NULL,
            owned INTEGER DEFAULT 0,
            equipped INTEGER DEFAULT 0
        )
    """)
    
    # 家长设置
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parent_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # ===== 初始化默认数据 =====
    
    # 初始化宠物（如果不存在）
    cursor.execute("SELECT COUNT(*) FROM pet")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO pet (name, level, exp, hunger, mood, streak, status, math_streak, bond, coins)
            VALUES ('作业小龙', 1, 0, 80, 80, 0, 'happy', 0, 50, 0)
        """)
    
    # 初始化成就
    cursor.execute("SELECT COUNT(*) FROM achievements")
    if cursor.fetchone()[0] == 0:
        achievements = [
            ('初学者', '连续3天打卡', '🌱', 0),
            ('习惯者', '连续7天打卡', '📚', 0),
            ('坚持者', '连续30天打卡', '⭐', 0),
            ('学霸', '完成100次作业', '🏆', 0),
            ('龙之守护者', '进化为神龙', '🌟', 0),
            ('数学勇士', '连续7天完成数学作业', '🔢', 0),
            ('破壳而出', '龙蛋孵化为幼龙', '🥚', 0),
            ('成长之龙', '进化为少年龙', '🐲', 0),
            ('龙之力量', '进化为青年龙', '🐉', 0),
            ('神龙降临', '进化为神龙', '✨', 0),
            ('最佳拍档', '亲密度达到100', '💕', 0),
            ('专注达人', '累计专注10小时', '⏱️', 0),
            ('小富翁', '累计获得1000龙币', '🪙', 0),
            ('喂养达人', '累计喂食50次', '🍖', 0),
            ('互动高手', '累计互动100次', '🤗', 0),
            ('暖心天使', '亲密度连续7天不低于80', '💖', 0),
            ('挑战勇士', '完成10次数学挑战赛', '⚔️', 0),
        ]
        cursor.executemany("""
            INSERT INTO achievements (name, description, icon, unlocked)
            VALUES (?, ?, ?, ?)
        """, achievements)
    else:
        # 兼容：补充 v3.0 新成就
        new_achievements = [
            ('破壳而出', '龙蛋孵化为幼龙', '🥚'),
            ('成长之龙', '进化为少年龙', '🐲'),
            ('龙之力量', '进化为青年龙', '🐉'),
            ('神龙降临', '进化为神龙', '✨'),
            ('最佳拍档', '亲密度达到100', '💕'),
            ('专注达人', '累计专注10小时', '⏱️'),
            ('小富翁', '累计获得1000龙币', '🪙'),
            # v3.1 新增成就
            ('喂养达人', '累计喂食50次', '🍖'),
            ('互动高手', '累计互动100次', '🤗'),
            ('暖心天使', '亲密度连续7天不低于80', '💖'),
            ('挑战勇士', '完成10次数学挑战赛', '⚔️'),
        ]
        for name, desc, icon in new_achievements:
            existing = cursor.execute("SELECT name FROM achievements WHERE name = ?", (name,)).fetchone()
            if not existing:
                cursor.execute("""
                    INSERT INTO achievements (name, description, icon, unlocked)
                    VALUES (?, ?, ?, 0)
                """, (name, desc, icon))
    
    # 初始化默认行为评价规则
    cursor.execute("SELECT COUNT(*) FROM behavior_rules")
    if cursor.fetchone()[0] == 0:
        default_rules = [
            # 📚 学习习惯 (8条)
            ('主动阅读', 10, 'study', '📖', 0),
            ('认真完成作业', 15, 'study', '✏️', 0),
            ('作业工整', 10, 'study', '📝', 0),
            ('提前预习', 15, 'study', '预习', 0),
            ('考试进步', 20, 'study', '📈', 0),
            ('错题订正', 10, 'study', '橡皮', 0),
            ('朗读课文', 10, 'study', '🗣️', 0),
            ('迟到交作业', -5, 'study', '⏰', 0),
            # 🎯 行为表现 (10条)
            ('帮助家人', 10, 'behavior', '🤝', 0),
            ('礼貌问好', 5, 'behavior', '👋', 0),
            ('收拾玩具', 10, 'behavior', '🧹', 0),
            ('诚实守信', 15, 'behavior', '💎', 0),
            ('自己穿衣', 5, 'behavior', '👕', 0),
            ('主动洗碗', 10, 'behavior', '🍽️', 0),
            ('说脏话', -10, 'behavior', '😤', 0),
            ('发脾气', -5, 'behavior', '😡', 0),
            ('打架', -15, 'behavior', '👊', 0),
            ('顶嘴', -5, 'behavior', '🗣️', 0),
            # 💪 健康运动 (6条)
            ('跳绳运动', 10, 'health', '🏃', 0),
            ('早睡早起', 10, 'health', '🌅', 0),
            ('做眼保健操', 5, 'health', '👁️', 0),
            ('按时吃饭', 5, 'health', '🍚', 0),
            ('少吃零食', 5, 'health', '🥦', 0),
            ('久坐提醒', -5, 'health', '🪑', 0),
            # 📝 其他 (6条)
            ('获得老师表扬', 20, 'other', '🌟', 0),
            ('完成小目标', 10, 'other', '🎯', 0),
            ('坚持打卡', 5, 'other', '📅', 0),
            ('浪费食物', -5, 'other', '🗑️', 0),
            ('乱丢垃圾', -5, 'other', '♻️', 0),
            ('电子产品超时', -10, 'other', '📱', 0),
        ]
        cursor.executemany("""
            INSERT INTO behavior_rules (name, coins, category, icon, is_custom)
            VALUES (?, ?, ?, ?, ?)
        """, default_rules)
    
    # 初始化默认装饰商品
    cursor.execute("SELECT COUNT(*) FROM pet_accessories")
    if cursor.fetchone()[0] == 0:
        accessories = [
            ('小龙帽子', 'hat', 20, 0, 0),
            ('彩虹翅膀', 'hat', 30, 0, 0),
            ('星星围巾', 'hat', 25, 0, 0),
            ('皇冠', 'hat', 50, 0, 0),
            ('星空背景', 'background', 40, 0, 0),
            ('彩虹背景', 'background', 35, 0, 0),
            ('花园背景', 'background', 30, 0, 0),
        ]
        cursor.executemany("""
            INSERT INTO pet_accessories (name, type, price, owned, equipped)
            VALUES (?, ?, ?, ?, ?)
        """, accessories)
    
    # 初始化家长设置
    cursor.execute("SELECT COUNT(*) FROM parent_settings")
    if cursor.fetchone()[0] == 0:
        settings = [
            ('exchange_rate', '100'),       # 100龙币 = 1元
            ('weekly_coin_limit', '200'),    # 每周最多兑换200龙币
            ('pocket_money_enabled', '1'),   # 零花钱功能开启
            ('parent_password', '1234'),     # 家长密码默认1234
        ]
        cursor.executemany("""
            INSERT INTO parent_settings (key, value) VALUES (?, ?)
        """, settings)
    else:
        # 兼容：补充 v3.2 新设置
        for key, val in [('parent_password', '1234'), ('school_end_time', '16:00'), ('skins_enabled', '1')]:
            existing = cursor.execute("SELECT key FROM parent_settings WHERE key = ?", (key,)).fetchone()
            if not existing:
                cursor.execute("INSERT INTO parent_settings (key, value) VALUES (?, ?)", (key, val))
    
    conn.commit()
    conn.close()

# 初始化数据库
init_db()
