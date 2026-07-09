"""多宠物数据层（v3.3）。

纯数据层，不依赖 main.py，避免循环 import。
提供：
- 物种目录初始化（幂等）
- 单宠物 → 多宠物迁移（幂等、生产库安全网、继承真实昵称）
- 激活宠物 ID 取用（单一事实来源）
- 激活宠物 → pet 表镜像兼容层（保证旧 SELECT * FROM pet WHERE id=1 不崩）

所有 DB 操作经 database.get_db_connection()，提交后由调用方关闭（own 连接时本模块关闭）。
"""
import logging
import os
import shutil
from datetime import datetime

from database import get_db_connection, get_database_url

logger = logging.getLogger("homework-pet.multi_pet")

# 物种目录初始数据（与 docs/multi-pet-implementation-plan.md §4 一致）
# (id, name, icon, desc, base_price, rarity, acquisition_methods, stage_image_root, sort_order)
SPECIES_CATALOG_SEED = [
    ('dragon',  '龙',     '\U0001F432', '经典陪伴小龙，初始伙伴',        0,   'common', 'initial',            '/static/species/dragon',  1),
    ('cat',     '魔法猫', '\U0001F431', '灵动的魔法小猫',              80,  'common', 'shop',                '/static/species/cat',     2),
    ('rabbit',  '月光兔', '\U0001F430', '沐浴月光的温柔兔子',          150, 'rare',   'shop,gacha',           '/static/species/rabbit',  3),
    ('fox',     '九尾狐', '\U0001F42A', '神秘聪慧的九尾狐',            300, 'epic',   'gacha,achievement',    '/static/species/fox',     4),
    ('unicorn', '独角兽', '\U0001F984', '纯洁高贵的解锁独角兽',        500, 'legend', 'achievement,gacha',    '/static/species/unicorn', 5),
    ('phoenix', '凤凰',   '\U0001F525', '浴火重生的神鸟（成就专属）',    0,   'legend', 'achievement',         '/static/species/phoenix', 6),
    ('panda',   '熊猫',   '\U0001F43C', '憨态可掬的熊猫',              120, 'rare',   'shop,signin',          '/static/species/panda',   7),
]

# 成就解锁 → 自动发放宠物（同物种限 1 只）
ACHIEVEMENT_PET_REWARDS = {
    '龙之守护者': 'phoenix',   # 进化为神龙 → 解锁凤凰
    '学霸':       'unicorn',    # 完成100次作业 → 解锁独角兽
    '专注达人':   'fox',        # 累计专注10小时 → 解锁九尾狐
}


def init_species_catalog(conn):
    """幂等写入物种目录（建表 + INSERT OR IGNORE，不覆盖已有）。"""
    conn.execute("""CREATE TABLE IF NOT EXISTS species_catalog (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, icon TEXT NOT NULL, desc TEXT,
        base_price INTEGER DEFAULT 0, rarity TEXT DEFAULT 'common',
        acquisition_methods TEXT, stage_image_root TEXT,
        stage_count INTEGER DEFAULT 5, sort_order INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_species_catalog_enabled ON species_catalog(enabled)")
    for s in SPECIES_CATALOG_SEED:
        conn.execute("""INSERT OR IGNORE INTO species_catalog
            (id, name, icon, desc, base_price, rarity, acquisition_methods, stage_image_root, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8]))


def backup_before_migrate(src_path):
    """迁移前物理备份（拷贝到同目录，不改动源库）。失败返回 None。"""
    if not src_path or not os.path.exists(src_path):
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(os.path.dirname(os.path.abspath(src_path)), f"pre_multi_{ts}.db")
    if os.path.abspath(src_path) == os.path.abspath(dst):
        return dst
    shutil.copy2(src_path, dst)
    logger.info(f"[migrate] 已备份 {src_path} -> {dst}")
    return dst


def _ensure_active_pointer(cur, conn):
    """确保 pet.active_pet_id 指向一只真实存在的宠物（兜底）。"""
    row = cur.execute("SELECT active_pet_id FROM pet WHERE id = 1").fetchone()
    aid = row['active_pet_id'] if row else None
    if aid and cur.execute("SELECT 1 FROM pet_collection WHERE id = ?", (aid,)).fetchone():
        return
    first = cur.execute("SELECT id FROM pet_collection ORDER BY id LIMIT 1").fetchone()
    if first:
        cur.execute("UPDATE pet SET active_pet_id = ? WHERE id = 1", (first['id'],))
        conn.commit()


def migrate_single_to_multi_pet(conn=None, allow_production=False):
    """幂等迁移：单宠物 → 多宠物。可重跑，已迁移则跳过。

    默认只允许在测试库跑；若指向生产库路径必须显式 allow_production=True。
    返回 True 表示迁移成功或已跳过（幂等），False 表示被安全网拦截或失败。
    """
    own = conn is None
    if conn is None:
        conn = get_db_connection()
    try:
        cur = conn.cursor()
        init_species_catalog(conn)

        # 安全网：防止误连生产库自动迁移
        if not allow_production and os.environ.get("MULTI_PET_MIGRATE_PROD") != "1":
            if get_database_url().endswith("homework_pet.db") and not os.environ.get("HOMEWORK_PET_DB_PATH"):
                logger.error(
                    "[migrate] 拒绝在生产库上自动迁移！"
                    "请设置 HOMEWORK_PET_DB_PATH 指向测试库，或显式 allow_production=True。"
                )
                return False

        # 幂等核心：pet_collection 已有数据 => 视为已迁移，跳过
        if cur.execute("SELECT COUNT(*) FROM pet_collection").fetchone()[0] > 0:
            logger.info("[migrate] pet_collection 非空，跳过（幂等）")
            _ensure_active_pointer(cur, conn)
            return True

        old = cur.execute("SELECT * FROM pet WHERE id = 1").fetchone()
        if not old:
            logger.info("[migrate] pet 表无数据，跳过")
            return True
        old = dict(old)

        # 关键修正：继承真实昵称（生产库为 '紫宝'），不再写死 '作业小龙'
        old_name = old.get('name') or '作业小龙'
        old_exp = old.get('exp', 0)
        old_hunger = old.get('hunger', 80)
        old_mood = old.get('mood', 80)
        old_bond = old.get('bond', 50)
        old_status = old.get('status', 'happy')
        old_runaway = old.get('runaway_until')
        old_decay = old.get('last_decay_date')
        old_created = old.get('created_at')

        # 读取旧皮肤（current_skin，仅作用于龙）
        skin_id = 'default'
        cs = cur.execute("SELECT value FROM parent_settings WHERE key = 'current_skin'").fetchone()
        if cs and cs['value']:
            skin_id = cs['value']

        # 首次迁移前物理备份（仅一次，幂等跳过后不再触发）
        try:
            backup_before_migrate(get_database_url())
        except Exception as e:
            logger.warning(f"[migrate] 备份失败(忽略): {e}")

        # 创建第一只宠物（dragon），继承旧数据；is_frozen=0 表示激活
        cur.execute("""
            INSERT INTO pet_collection
                (species_id, skin_id, name, exp, hunger, mood, bond, status, runaway_until,
                 acquired_at, acquisition, is_frozen, last_decay_date)
            VALUES ('dragon', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'initial', 0, ?)
        """, (skin_id, old_name, old_exp, old_hunger, old_mood, old_bond, old_status,
              old_runaway, old_created, old_decay))
        new_pet_id = cur.lastrowid

        # 给 pet 表加 active_pet_id（幂等 try/except，init_db 可能已加过）
        try:
            cur.execute("ALTER TABLE pet ADD COLUMN active_pet_id INTEGER")
        except Exception:
            pass

        cur.execute("UPDATE pet SET active_pet_id = ? WHERE id = 1", (new_pet_id,))

        # 顺手修复 level 脏值：level 由 exp 派生（exp=8650 → 5；exp=4075 → 5 等同理）
        new_level = 1 + (old_exp >= 800) + (old_exp >= 2000) + (old_exp >= 4000) + (old_exp >= 8000)
        cur.execute("UPDATE pet SET level = ? WHERE id = 1", (new_level,))

        conn.commit()
        logger.info(f"[migrate] 迁移完成：首只宠物 id={new_pet_id} name='{old_name}' level={new_level} exp={old_exp}")
        return True
    except Exception as e:
        conn.rollback()
        logger.exception(f"[migrate] 迁移失败: {e}")
        return False
    finally:
        if own:
            conn.close()


def get_active_pet_id(conn):
    """取当前激活宠物 id（pet_collection.id）。单一事实来源，禁止硬编码 id=1 取个体属性。"""
    try:
        row = conn.execute("SELECT active_pet_id FROM pet WHERE id = 1").fetchone()
    except Exception:
        return None
    aid = row['active_pet_id'] if row else None
    if aid and conn.execute("SELECT 1 FROM pet_collection WHERE id = ?", (aid,)).fetchone():
        return aid
    # 兜底：pet_collection 中唯一未冻结的宠物
    r = conn.execute("SELECT id FROM pet_collection WHERE is_frozen = 0 LIMIT 1").fetchone()
    return r['id'] if r else None


def sync_active_pet_mirror(conn):
    """激活宠物 → pet 表镜像字段（兼容旧 SELECT * FROM pet WHERE id=1）。

    同步字段：name/exp/hunger/mood/bond/status/runaway_until/level（level 由 exp 派生）。
    """
    try:
        row = conn.execute("SELECT active_pet_id FROM pet WHERE id = 1").fetchone()
    except Exception:
        return
    active_id = row['active_pet_id'] if row else None
    if not active_id:
        return
    a = conn.execute(
        "SELECT name, exp, hunger, mood, bond, status, runaway_until FROM pet_collection WHERE id = ?",
        (active_id,)).fetchone()
    if not a:
        return
    a = dict(a)
    # level 由 exp 派生（修正任何历史脏值）
    level = 1 + (a['exp'] >= 800) + (a['exp'] >= 2000) + (a['exp'] >= 4000) + (a['exp'] >= 8000)
    conn.execute("""
        UPDATE pet SET name = ?, exp = ?, hunger = ?, mood = ?, bond = ?, status = ?, runaway_until = ?, level = ?
        WHERE id = 1
    """, (a['name'], a['exp'], a['hunger'], a['mood'], a['bond'], a['status'], a['runaway_until'], level))
