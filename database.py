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

CREATE TABLE IF NOT EXISTS photos (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    file_id  TEXT NOT NULL,
    ts       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workouts (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    exercise TEXT NOT NULL,
    target   INTEGER NOT NULL,
    step     INTEGER NOT NULL,
    sessions INTEGER DEFAULT 0,
    UNIQUE(user_id, exercise)
);

CREATE TABLE IF NOT EXISTS affirmations (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    text    TEXT NOT NULL,
    ts      TEXT
);

CREATE TABLE IF NOT EXISTS metrics (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind    TEXT NOT NULL,
    value   REAL NOT NULL,
    ts      TEXT NOT NULL
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
    ("users", "workout_done_date", "TEXT"),
    ("users", "vitamins_done_date", "TEXT"),
    ("users", "morning_hour", "INTEGER"),
    ("users", "evening_hour", "INTEGER"),
    ("users", "workout_hour", "INTEGER"),
    ("users", "freeze_month", "TEXT"),
    ("users", "freeze_used", "INTEGER DEFAULT 0"),
    ("users", "onboarded", "INTEGER DEFAULT 0"),
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


async def set_onboarded(user_id: int):
    await _exec("UPDATE users SET onboarded = 1 WHERE user_id = ?", (user_id,))


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


# --------------------------------------------------------------------------- photos
async def latest_photo(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM photos WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def first_photo(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM photos WHERE user_id = ? ORDER BY id ASC LIMIT 1", (user_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_photo(user_id: int, file_id: str):
    await _exec(
        "INSERT INTO photos (user_id, file_id, ts) VALUES (?, ?, ?)",
        (user_id, file_id, to_iso(now_utc())),
    )


async def count_photos(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM photos WHERE user_id = ?", (user_id,))
        return (await cur.fetchone())[0]


# --------------------------------------------------------------------------- workouts
async def ensure_workouts(user_id: int):
    from content import EXERCISES
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM workouts WHERE user_id = ?", (user_id,))
        if (await cur.fetchone())[0] == 0:
            for key, _name, _emoji, start, step in EXERCISES:
                await db.execute(
                    "INSERT OR IGNORE INTO workouts (user_id, exercise, target, step, sessions) "
                    "VALUES (?, ?, ?, ?, 0)",
                    (user_id, key, start, step),
                )
            await db.commit()


async def get_workouts(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM workouts WHERE user_id = ? ORDER BY id", (user_id,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def complete_workout(user_id: int, date_str: str):
    """Прибавляет повторения ко всем упражнениям и отмечает день выполненным."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE workouts SET target = target + step, sessions = sessions + 1 "
            "WHERE user_id = ?",
            (user_id,),
        )
        await db.execute(
            "UPDATE users SET workout_done_date = ? WHERE user_id = ?", (date_str, user_id)
        )
        await db.commit()


async def set_vitamins_done(user_id: int, date_str: str):
    await _exec("UPDATE users SET vitamins_done_date = ? WHERE user_id = ?", (date_str, user_id))


# --------------------------------------------------------------------------- hours
async def set_hour(user_id: int, field: str, value: int):
    if field not in ("morning_hour", "evening_hour", "workout_hour"):
        return
    await _exec(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))


# --------------------------------------------------------------------------- affirmations
async def add_affirmation(user_id: int, text: str):
    await _exec(
        "INSERT INTO affirmations (user_id, text, ts) VALUES (?, ?, ?)",
        (user_id, text, to_iso(now_utc())),
    )


async def get_affirmations(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM affirmations WHERE user_id = ? ORDER BY id", (user_id,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def delete_affirmation(aff_id: int, user_id: int):
    await _exec("DELETE FROM affirmations WHERE id = ? AND user_id = ?", (aff_id, user_id))


# --------------------------------------------------------------------------- metrics
async def add_metric(user_id: int, kind: str, value: float):
    await _exec(
        "INSERT INTO metrics (user_id, kind, value, ts) VALUES (?, ?, ?, ?)",
        (user_id, kind, value, to_iso(now_utc())),
    )


async def get_metrics(user_id: int, kind: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM metrics WHERE user_id = ? AND kind = ? ORDER BY ts",
            (user_id, kind),
        )
        return [dict(r) for r in await cur.fetchall()]


# --------------------------------------------------------------------------- freeze
async def use_freeze(user_id: int, month: str):
    user = await get_user(user_id)
    if user.get("freeze_month") == month:
        used = (user.get("freeze_used") or 0) + 1
    else:
        used = 1
    await _exec(
        "UPDATE users SET freeze_month = ?, freeze_used = ? WHERE user_id = ?",
        (month, used, user_id),
    )


def freeze_available(user: dict, month: str) -> int:
    from content import FREEZE_PER_MONTH
    used = user.get("freeze_used") or 0 if user.get("freeze_month") == month else 0
    return max(0, FREEZE_PER_MONTH - used)


async def reset_streak(habit_id: int):
    """Мягкий сброс времени старта на «сейчас» без записи срыва (для заморозки — не нужно)."""
    await _exec("UPDATE habits SET started_at = ? WHERE id = ?", (to_iso(now_utc()), habit_id))


# --------------------------------------------------------------------------- export
async def export_data(user_id: int) -> dict:
    user = await get_user(user_id)
    habits = await get_habits(user_id)
    achievements = list(await get_achievements(user_id))
    workouts = await get_workouts(user_id)
    affirmations = await get_affirmations(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rl = await db.execute("SELECT * FROM relapse_log WHERE user_id = ?", (user_id,))
        relapses = [dict(r) for r in await rl.fetchall()]
        mt = await db.execute("SELECT * FROM metrics WHERE user_id = ?", (user_id,))
        metrics = [dict(r) for r in await mt.fetchall()]
    return {
        "user": user,
        "habits": habits,
        "relapses": relapses,
        "achievements": achievements,
        "workouts": workouts,
        "metrics": metrics,
        "affirmations": affirmations,
        "photos_count": await count_photos(user_id),
    }


async def relapses_since(user_id: int, since_iso: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM relapse_log WHERE user_id = ? AND ts >= ?",
            (user_id, since_iso),
        )
        return (await cur.fetchone())[0]


async def _exec(query: str, params: tuple):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()
