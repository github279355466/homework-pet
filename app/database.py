import sqlite3
import os
import shutil
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("homework-pet")

DEFAULT_DATABASE_URL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "homework_pet.db")

def get_database_url():
    """返回当前数据库路径。

    优先级：
      1. HOMEWORK_PET_DB_PATH（显式指定，如 Railway Volume 挂载路径 /data/homework_pet.db）
      2. RAILWAY_VOLUME_MOUNT_PATH 环境变量（Railway 挂卷后自动注入）下的 homework_pet.db
      3. 默认 app/homework_pet.db（镜像内 bundled，部署后临时盘，重启会丢）
    测试可通过环境变量隔离。
    """
    env = os.environ.get("HOMEWORK_PET_DB_PATH")
    if env:
        return env
    vol = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    if vol:
        return os.path.join(vol, "homework_pet.db")
    return DEFAULT_DATABASE_URL


def _ensure_persistent_db():
    """首启种子迁移：当目标库（如 Volume 持久盘）不存在时，从镜像内 bundled 库拷贝过去。

    这是消除「部署丢数据」的核心：Railway 临时盘在每次重新部署时会被重置为镜像状态，
    若直接连 Volume 路径且卷为空，init_db() 会建一个空库。本函数在 init_db() 之前把
    现有（bundled）数据搬到持久盘，保证首次挂载 Volume 也不丢数据。

    仅拷贝一次；目标已存在则跳过（幂等）。
    """
    target = get_database_url()
    if target == DEFAULT_DATABASE_URL:
        # 未配置持久盘，使用镜像内库，无需迁移
        return
    if os.path.exists(target):
        return
    source = DEFAULT_DATABASE_URL
    if not os.path.exists(source) or os.path.getsize(source) == 0:
        logger.info("[db] 未找到 bundled 源库，跳过种子迁移（将新建空库）")
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        # 先 checkpoint bundled 库，把 WAL 中未提交事务落盘，避免拷贝时丢失
        try:
            sc = sqlite3.connect(source, timeout=5)
            sc.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            sc.close()
        except Exception:
            pass
        shutil.copy2(source, target)
        for ext in ("-wal", "-shm"):
            sp = source + ext
            if os.path.exists(sp):
                shutil.copy2(sp, target + ext)
        logger.info(f"[db] 已从镜像内库种子迁移到持久盘: {target}")
    except Exception:
        logger.exception("[db] 种子迁移失败（将使用空库，请检查持久盘权限/挂载）")


def register_shutdown_dump():
    """注册退出信号处理：容器被 Railway 停止(SIGTERM)前，对持久盘库做 wal_checkpoint。

    保证**配置持久盘之后**的每次部署零丢失——运行时写入直接落在 Volume 文件，
    退出前 flush WAL 即可避免被 SIGKILL 前的极小窗口丢未提交事务。
    未配置持久盘时为空操作。
    """
    target = get_database_url()
    if target == DEFAULT_DATABASE_URL:
        return
    parent = os.path.dirname(os.path.abspath(target))
    if not parent or not os.path.isdir(parent):
        return

    def _on_exit(signum, frame):
        try:
            sc = sqlite3.connect(target, timeout=5)
            sc.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            sc.close()
            logger.info(f"[db] 收到退出信号 {signum}，已 checkpoint 持久盘: {target}")
        except Exception:
            logger.exception("[db] 退出前 checkpoint 失败")

    try:
        import signal
        signal.signal(signal.SIGTERM, _on_exit)
        signal.signal(signal.SIGINT, _on_exit)
    except Exception:
        logger.warning("[db] 无法注册退出信号处理（平台可能不支持），部署零丢失需依赖 WAL 自动恢复")

def get_db_connection():
    conn = sqlite3.connect(get_database_url(), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def _init_multi_pet_schema(cursor):
    """多宠物架构（v3.3）增量建表 + 物种目录 seed（幂等，仅增不删，绝不 DROP/DELETE 业务数据）。"""
    # ===== 物种目录表 =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS species_catalog (
            id               TEXT    PRIMARY KEY,
            name             TEXT    NOT NULL,
            icon             TEXT    NOT NULL,
            desc             TEXT,
            base_price       INTEGER DEFAULT 0,
            rarity           TEXT    DEFAULT 'common',
            acquisition_methods TEXT,
            stage_image_root TEXT,
            stage_count      INTEGER DEFAULT 5,
            sort_order       INTEGER DEFAULT 0,
            enabled          INTEGER DEFAULT 1
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_species_catalog_enabled ON species_catalog(enabled)")

    # ===== 宠物个体表（不含 level，等级由 exp 派生）=====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pet_collection (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            species_id     TEXT    NOT NULL,
            skin_id        TEXT    DEFAULT 'default',
            name           TEXT    NOT NULL,
            exp            INTEGER DEFAULT 0,
            hunger         INTEGER DEFAULT 80,
            mood           INTEGER DEFAULT 80,
            bond           INTEGER DEFAULT 50,
            status         TEXT    DEFAULT 'happy',
            runaway_until  DATETIME,
            acquired_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            acquisition    TEXT    DEFAULT 'initial',
            is_frozen      INTEGER DEFAULT 1,
            last_decay_date DATETIME,
            created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pet_collection_species ON pet_collection(species_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pet_collection_frozen ON pet_collection(is_frozen)")

    # ===== pet 表增量字段（幂等）=====
    try:
        cursor.execute("ALTER TABLE pet ADD COLUMN active_pet_id INTEGER")
    except Exception:
        pass

    # ===== 物种目录初始数据（INSERT OR IGNORE 幂等）=====
    _SEED_SPECIES = [
        ('dragon',  '龙',     '\U0001F432', '经典陪伴小龙，初始伙伴',        0,   'common', 'initial',            '/static/species/dragon',  1),
        ('cat',     '魔法猫', '\U0001F431', '灵动的魔法小猫',              80,  'common', 'shop',                '/static/species/cat',     2),
        ('rabbit',  '月光兔', '\U0001F430', '沐浴月光的温柔兔子',          150, 'rare',   'shop,gacha',           '/static/species/rabbit',  3),
        ('fox',     '九尾狐', '\U0001F42A', '神秘聪慧的九尾狐',            300, 'epic',   'gacha,achievement',    '/static/species/fox',     4),
        ('unicorn', '独角兽', '\U0001F984', '纯洁高贵的解锁独角兽',        500, 'legend', 'achievement,gacha',    '/static/species/unicorn', 5),
        ('phoenix', '凤凰',   '\U0001F525', '浴火重生的神鸟（成就专属）',    0,   'legend', 'achievement',         '/static/species/phoenix', 6),
        ('panda',   '熊猫',   '\U0001F43C', '憨态可掬的熊猫',              120, 'rare',   'shop,signin',          '/static/species/panda',   7),
    ]
    for s in _SEED_SPECIES:
        cursor.execute("""
            INSERT OR IGNORE INTO species_catalog
                (id, name, icon, desc, base_price, rarity, acquisition_methods, stage_image_root, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, s)


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
        # ===== v3.3 Phase 3 新增：签到字段（增量、幂等）=====
        ('last_signin_date', None),   # 签到防重（每天一次，全局，与 last_streak_date 同层）
        ('signin_count', 0),          # 累计签到次数，用于里程碑发宠（避免依赖 streak 语义）
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

    # ===== 多宠物架构（v3.3）增量建表 + 物种目录 seed =====
    _init_multi_pet_schema(cursor)

    conn.commit()
    conn.close()

    # ===== 迁移（仅非生产路径或显式允许时执行，保护生产库不被自动改动）=====
    try:
        from multi_pet import migrate_single_to_multi_pet
        db_url = get_database_url()
        if db_url != DEFAULT_DATABASE_URL or os.environ.get("MULTI_PET_MIGRATE_PROD") == "1":
            migrate_single_to_multi_pet(allow_production=(os.environ.get("MULTI_PET_MIGRATE_PROD") == "1"))
        else:
            logger.info(
                "[init_db] 生产路径：跳过自动迁移"
                "（设置 HOMEWORK_PET_DB_PATH 或 MULTI_PET_MIGRATE_PROD=1 可启用）"
            )
    except Exception:
        logger.exception("[init_db] 迁移调用失败（已忽略）")

# 持久盘种子迁移（必须在 init_db 之前，避免 Volume 首启建空库丢数据）
_ensure_persistent_db()

# 初始化数据库
init_db()

# 注册退出时 checkpoint（保证配置持久盘后的后续部署零丢失）
register_shutdown_dump()
