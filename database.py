"""Слой доступа к данным на SQLite (aiosqlite)."""
import aiosqlite

from config import DB_PATH, DEFAULT_TZ_OFFSET
from utils import now_utc, to_iso

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    tz_offset  INTEGER DEFAULT 3,
    notify     INTEGER DEFAULT 1,
    created_at TEXT
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
    created_at   TEXT
);

CREATE TABLE IF NOT EXISTS relapse_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL,
    ts       TEXT NOT NULL
);
"""


async def init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET notify = ? WHERE user_id = ?", (value, user_id))
        await db.commit()


async def set_tz(user_id: int, offset: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET tz_offset = ? WHERE user_id = ?", (offset, user_id))
        await db.commit()


async def add_habit(user_id: int, htype: str, title: str, cost: float):
    ts = to_iso(now_utc())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO habits (user_id, htype, title, started_at, best_streak, "
            "relapses, cost_per_day, created_at) VALUES (?, ?, ?, ?, 0, 0, ?, ?)",
            (user_id, htype, title, ts, cost, ts),
        )
        await db.commit()


async def get_habits(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM habits WHERE user_id = ? ORDER BY id", (user_id,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


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


async def relapse(habit_id: int, current_streak: int):
    """Сбрасывает стрик, обновляет рекорд и счётчик срывов."""
    ts = to_iso(now_utc())
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT best_streak FROM habits WHERE id = ?", (habit_id,))
        row = await cur.fetchone()
        if row is None:
            return
        best = max(row["best_streak"], current_streak)
        await db.execute(
            "UPDATE habits SET started_at = ?, best_streak = ?, relapses = relapses + 1 "
            "WHERE id = ?",
            (ts, best, habit_id),
        )
        await db.execute(
            "INSERT INTO relapse_log (habit_id, ts) VALUES (?, ?)", (habit_id, ts)
        )
        await db.commit()


async def remove_habit(habit_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
        await db.execute("DELETE FROM relapse_log WHERE habit_id = ?", (habit_id,))
        await db.commit()


async def set_cost(habit_id: int, cost: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE habits SET cost_per_day = ? WHERE id = ?", (cost, habit_id)
        )
        await db.commit()


async def users_to_notify():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE notify = 1")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
