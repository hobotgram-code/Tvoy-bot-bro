"""Система достижений (ачивок)."""
import database as db
from cards import habit_streak_seconds

# code -> (эмодзи, название, описание, условие(stats)->bool)
ACHIEVEMENTS = [
    ("first_day", "🌱", "Первый день", "Продержись 1 день",
     lambda s: s["max_days"] >= 1),
    ("week", "⚡", "Железная неделя", "Стрик 7 дней",
     lambda s: s["max_days"] >= 7),
    ("month", "🏅", "Месяц дисциплины", "Стрик 30 дней",
     lambda s: s["max_days"] >= 30),
    ("quarter", "🥇", "Квартал характера", "Стрик 90 дней",
     lambda s: s["max_days"] >= 90),
    ("halfyear", "💎", "Полгода алмаза", "Стрик 180 дней",
     lambda s: s["max_days"] >= 180),
    ("year", "👑", "Год свободы", "Стрик 365 дней",
     lambda s: s["max_days"] >= 365),
    ("panic1", "🆘", "Устоял", "Переживи первую тягу через «Панику»",
     lambda s: s["cravings"] >= 1),
    ("panic10", "🧘", "Мастер спокойствия", "Переживи 10 тяг",
     lambda s: s["cravings"] >= 10),
    ("quest7", "🎯", "Неделя квестов", "Серия квестов 7 дней",
     lambda s: s["quest_streak"] >= 7),
    ("comeback", "🔁", "Возвращение", "После срыва снова дойди до 7 дней",
     lambda s: s["relapses"] >= 1 and s["max_days"] >= 7),
    ("saver1k", "💰", "Первая тысяча", "Сэкономь 1 000 ₽",
     lambda s: s["saved"] >= 1000),
    ("saver10k", "🤑", "Десять тысяч", "Сэкономь 10 000 ₽",
     lambda s: s["saved"] >= 10000),
]
ACH_MAP = {code: (emoji, title, desc) for code, emoji, title, desc, _ in ACHIEVEMENTS}

XP_PER_ACHIEVEMENT = 25


async def gather_stats(user_id: int) -> dict:
    user = await db.get_user(user_id)
    habits = await db.get_habits(user_id)
    max_days = 0
    saved = 0
    relapses = 0
    for h in habits:
        elapsed = habit_streak_seconds(h)
        max_days = max(max_days, elapsed // 86400)
        relapses += h["relapses"]
        if h["cost_per_day"] and h["cost_per_day"] > 0:
            saved += int(elapsed / 86400 * h["cost_per_day"])
    return {
        "max_days": max_days,
        "saved": saved,
        "relapses": relapses,
        "cravings": user["cravings_survived"] if user else 0,
        "quest_streak": user["quest_streak"] if user else 0,
    }


async def check_and_unlock(user_id: int):
    """Проверяет условия, разблокирует новые ачивки. Возвращает список новых."""
    stats = await gather_stats(user_id)
    unlocked = await db.get_achievements(user_id)
    newly = []
    for code, emoji, title, desc, cond in ACHIEVEMENTS:
        if code in unlocked:
            continue
        try:
            if cond(stats):
                if await db.unlock_achievement(user_id, code):
                    await db.add_xp(user_id, XP_PER_ACHIEVEMENT)
                    newly.append((emoji, title, desc))
        except Exception:  # noqa: BLE001
            continue
    return newly


def format_new(newly: list) -> str:
    lines = ["🎉 <b>Новое достижение!</b>", ""]
    for emoji, title, desc in newly:
        lines.append(f"{emoji} <b>{title}</b> — {desc} (+{XP_PER_ACHIEVEMENT} XP)")
    return "\n".join(lines)
