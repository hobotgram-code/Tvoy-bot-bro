"""Слой доступа к данным на SQLite (aiosqlite)."""
import aiosqlite

from config import DB_PATH, DEFAULT_TZ_OFFSET
from utils import now_utc, to_iso

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id          INTEGER PRIMARY KEY,
    username         TEXT,
    tz_offset        INTEGER DEFAULT 3,
    notify           INTEGER DEFAULT 1,
    created_at       TEXT,
    xp               INTEGER DEFAULT 0,
    partner_id       INTEGER,
    cravings_survived INTEGER DEFAULT 0,
    quest_date       TEXT,
    quest_text       TEXT,
    quest_done       INTEGER DEFAULT 0,
    quest_streak     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS habits (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    htype        TEXT NOT NULL,
    title        TEXT,
    started_at   TEXT NOT NULL,
    best_streak  INTEGER DEFAULT 0,
    relapses     INTEGER DEFAULT 0,
    cost_per_day REAL DEFAULT 0,
    created_at   TEXT,
    why          TEXT,
    goal         TEXT,
    goal_cost    REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS relapse_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id  INTEGER NOT NULL,
    user_id   INTEGER,
    ts        TEXT NOT NULL,
    trigger   TEXT,
    mood      INTEGER
);

CREATE TABLE IF NOT EXISTS achievements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    code         TEXT NOT NULL,
    unlocked_at  TEXT,
    UNIQUE(user_id, code)
);
"""

# Колонки, которые могли отсутствовать в старых базах: (таблица, колонка, тип).
_MIGRATIONS = [
    ("users", "xp", "INTEGER DEFAULT 0"),
    ("users", "partner_id", "INTEGER"),
    ("users", "cravings_survived", "INTEGER DEFAULT 0"),
    ("users", "quest_date", "TEXT"),
    ("users", "quest_text", "TEXT"),
    ("users", "quest_done", "INTEGER DEFAULT 0"),
    ("users", "quest_streak", "INTEGER DEFAULT 0"),
    ("habits", "why", "TEXT"),
    ("habits", "goal", "TEXT"),
    ("habits", "goal_cost", "REAL DEFAULT 0"),
    ("relapse_log", "user_id", "INTEGER"),
    ("relapse_log", "trigger", "TEXT"),
    ("relapse_log", "mood", "INTEGER"),
]


async def _migrate(db):
    for table, column, decl in _MIGRATIONS:
        cur = await db.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in await cur.fetchall()}
        if column not in cols:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


async def init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await _migrate(db)
        await db.commit()


# --------------------------------------------------------------------------- users
async def ensure_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO users (user_id, username, tz_offset, notify, created_at) "
                "VALUES (?, ?, ?, 1, ?)",
                (user_id, username, DEFAULT_TZ_OFFSET, to_iso(now_utc())),
            )
        else:
            await db.execute(
                "UPDATE users SET username = ? WHERE user_id = ?", (username, user_id)
            )
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_notify(user_id: int, value: int):
    await _exec("UPDATE users SET notify = ? WHERE user_id = ?", (value, user_id))


async def set_tz(user_id: int, offset: int):
    await _exec("UPDATE users SET tz_offset = ? WHERE user_id = ?", (offset, user_id))


async def add_xp(user_id: int, amount: int):
    await _exec("UPDATE users SET xp = xp + ? WHERE user_id = ?", (amount, user_id))


async def inc_cravings(user_id: int):
    await _exec(
        "UPDATE users SET cravings_survived = cravings_survived + 1 WHERE user_id = ?",
        (user_id,),
    )


async def set_partner(user_id: int, partner_id):
    await _exec("UPDATE users SET partner_id = ? WHERE user_id = ?", (partner_id, user_id))


# --------------------------------------------------------------------------- habits
async def add_habit(user_id: int, htype: str, title: str, cost: float):
    ts = to_iso(now_utc())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO habits (user_id, htype, title, started_at, best_streak, "
            "relapses, cost_per_day, created_at) VALUES (?, ?, ?, ?, 0, 0, ?, ?)",
            (user_id, htype, title, ts, cost, ts),
        )
        await db.commit()
        return cur.lastrowid


async def get_habits(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM habits WHERE user_id = ? ORDER BY id", (user_id,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_habit(habit_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM habits WHERE id = ?", (habit_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def user_has_type(user_id: int, htype: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM habits WHERE user_id = ? AND htype = ? LIMIT 1",
            (user_id, htype),
        )
        return await cur.fetchone() is not None


async def set_why_goal(habit_id: int, why: str, goal: str, goal_cost: float):
    await _exec(
        "UPDATE habits SET why = ?, goal = ?, goal_cost = ? WHERE id = ?",
        (why, goal, goal_cost, habit_id),
    )


async def relapse(user_id: int, habit_id: int, current_streak: int) -> int:
    """Сбрасывает стрик, обновляет рекорд/счётчик, пишет лог. Возвращает id лога."""
    ts = to_iso(now_utc())
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT best_streak FROM habits WHERE id = ?", (habit_id,))
        row = await cur.fetchone()
        if row is None:
            return 0
        best = max(row["best_streak"], current_streak)
        await db.execute(
            "UPDATE habits SET started_at = ?, best_streak = ?, relapses = relapses + 1 "
            "WHERE id = ?",
            (ts, best, habit_id),
        )
        log_cur = await db.execute(
            "INSERT INTO relapse_log (habit_id, user_id, ts) VALUES (?, ?, ?)",
            (habit_id, user_id, ts),
        )
        await db.commit()
        return log_cur.lastrowid


async def set_relapse_details(log_id: int, trigger=None, mood=None):
    if trigger is not None:
        await _exec("UPDATE relapse_log SET trigger = ? WHERE id = ?", (trigger, log_id))
    if mood is not None:
        await _exec("UPDATE relapse_log SET mood = ? WHERE id = ?", (mood, log_id))


async def remove_habit(habit_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
        await db.execute("DELETE FROM relapse_log WHERE habit_id = ?", (habit_id,))
        await db.commit()


async def set_cost(habit_id: int, cost: float):
    await _exec("UPDATE habits SET cost_per_day = ? WHERE id = ?", (cost, habit_id))


# --------------------------------------------------------------------------- quests
async def set_quest(user_id: int, date_str: str, text: str):
    await _exec(
        "UPDATE users SET quest_date = ?, quest_text = ?, quest_done = 0 WHERE user_id = ?",
        (date_str, text, user_id),
    )


async def complete_quest(user_id: int):
    await _exec(
        "UPDATE users SET quest_done = 1, quest_streak = quest_streak + 1 WHERE user_id = ?",
        (user_id,),
    )


# --------------------------------------------------------------------------- achievements
async def get_achievements(user_id: int) -> set:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT code FROM achievements WHERE user_id = ?", (user_id,)
        )
        return {r[0] for r in await cur.fetchall()}


async def unlock_achievement(user_id: int, code: str) -> bool:
    """Возвращает True, если ачивка новая (была добавлена)."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO achievements (user_id, code, unlocked_at) VALUES (?, ?, ?)",
                (user_id, code, to_iso(now_utc())),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


# --------------------------------------------------------------------------- analytics
async def relapse_stats(user_id: int, days: int = 30):
    """Статистика срывов за период: триггеры, среднее настроение, количество."""
    since = to_iso(now_utc())  # placeholder, filter in python below
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT ts, trigger, mood FROM relapse_log WHERE user_id = ? ORDER BY ts DESC",
            (user_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def all_relapse_days(user_id: int):
    """Множество дат (ISO date) срывов для календаря-heatmap."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT ts FROM relapse_log WHERE user_id = ?", (user_id,)
        )
        return [r[0] for r in await cur.fetchall()]


async def users_to_notify():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE notify = 1")
        return [dict(r) for r in await cur.fetchall()]


async def leaderboard_data():
    """Все привычки всех пользователей — для расчёта рейтинга по стрику."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT user_id, started_at FROM habits")
        return [dict(r) for r in await cur.fetchall()]


async def _exec(query: str, params: tuple):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()
