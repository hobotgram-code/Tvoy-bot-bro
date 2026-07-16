"""Планировщик: утренняя мотивация, вечерний чек-ин, умные напоминания."""
import logging
import random
from collections import Counter
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

import database as db
from config import (
    MORNING_HOUR, EVENING_HOUR, VITAMIN_HOUR, WORKOUT_HOUR, WORKOUT_DAYS,
    PHOTO_HOUR, PHOTO_WEEKDAY, BACKUP_HOUR, BACKUP_WEEKDAY,
)
from aiogram.types import BufferedInputFile
from content import MORNING_LINES, EVENING_LINES, WORKOUT_LINES, VITAMIN_LINES
from cards import progress_message
import keyboards as kb
from utils import now_utc, from_iso

log = logging.getLogger(__name__)

RISK_HOUR = 18  # час для превентивного напоминания в опасный день недели


async def hourly_check(bot: Bot):
    """Раз в час подбирает пользователей по локальному времени и дню недели."""
    now = now_utc()
    users = await db.users_to_notify()
    for user in users:
        local = now + timedelta(hours=user["tz_offset"])
        hour = local.hour
        weekday = local.weekday()
        today = local.date().isoformat()
        morning = _hour(user, "morning_hour", MORNING_HOUR)
        evening = _hour(user, "evening_hour", EVENING_HOUR)
        workout = _hour(user, "workout_hour", WORKOUT_HOUR)
        try:
            if hour == morning:
                await _send_morning(bot, user, weekday)
            elif hour == VITAMIN_HOUR:
                await _maybe_send_vitamins(bot, user, today)
            elif hour == PHOTO_HOUR and weekday == PHOTO_WEEKDAY:
                await _send_photo_reminder(bot, user)
            elif hour == BACKUP_HOUR and weekday == BACKUP_WEEKDAY:
                await _send_backup(bot, user)
            elif hour == workout and weekday in WORKOUT_DAYS:
                await _maybe_send_workout(bot, user, today)
            elif hour == RISK_HOUR:
                await _maybe_send_risk(bot, user, weekday)
            elif hour == evening:
                await _send_evening(bot, user)
        except (TelegramForbiddenError, TelegramBadRequest):
            await db.set_notify(user["user_id"], 0)
        except Exception as exc:  # noqa: BLE001
            log.warning("Уведомление %s не отправлено: %s", user["user_id"], exc)


async def _maybe_send_vitamins(bot: Bot, user: dict, today: str):
    if user.get("vitamins_done_date") == today:
        return
    await bot.send_message(user["user_id"], random.choice(VITAMIN_LINES))


async def _maybe_send_workout(bot: Bot, user: dict, today: str):
    if user.get("workout_done_date") == today:
        return
    await db.ensure_workouts(user["user_id"])
    workouts = await db.get_workouts(user["user_id"])
    from cards import workout_message
    text = random.choice(WORKOUT_LINES) + "\n\n" + workout_message(workouts, False)
    await bot.send_message(user["user_id"], text, reply_markup=kb.workout_kb(False))


async def _send_backup(bot: Bot, user: dict):
    """Еженедельный бэкап личных данных пользователю в виде JSON-файла."""
    import json
    habits = await db.get_habits(user["user_id"])
    if not habits:
        return
    data = await db.export_data(user["user_id"])
    payload = json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    await bot.send_document(
        user["user_id"],
        BufferedInputFile(payload, filename="tvoy-bot-bro-backup.json"),
        caption="☁️ Еженедельный бэкап твоих данных. Сохрани файл — на случай, "
                "если что-то пойдёт не так. 🔐",
    )


async def _send_photo_reminder(bot: Bot, user: dict):
    last = await db.latest_photo(user["user_id"])
    caption = (
        "📸 <b>Прошла неделя!</b> Время сделать новое прогресс-фото.\n"
        "Пришли снимок — сравним с прошлым. Изменения копятся незаметно, "
        "а на фото — видны. 💪"
    )
    if last:
        await bot.send_photo(user["user_id"], last["file_id"],
                             caption="👆 Твоё прошлое фото.\n\n" + caption)
    else:
        await bot.send_message(user["user_id"], caption)


def _hour(user: dict, field: str, default: int) -> int:
    val = user.get(field)
    return val if val is not None else default


async def _send_morning(bot: Bot, user: dict, weekday: int = 0):
    habits = await db.get_habits(user["user_id"])
    line = random.choice(MORNING_LINES)
    affs = await db.get_affirmations(user["user_id"])
    aff_line = f"\n\n💬 <i>{random.choice(affs)['text']}</i>" if affs else ""
    if habits:
        text = f"{line}{aff_line}\n\n{progress_message(habits)}"
    else:
        text = f"{line}\n\nДобавь первый трекер через «➕ Трекер» и начни путь к свободе. 💪"
    await bot.send_message(user["user_id"], text)
    if weekday == 0 and habits:  # понедельник — недельный отчёт
        await _send_weekly_report(bot, user)


async def _send_weekly_report(bot: Bot, user: dict):
    from cards import report_message, habit_streak_seconds
    from utils import to_iso
    habits = await db.get_habits(user["user_id"])
    max_secs = 0
    saved = 0
    for h in habits:
        secs = habit_streak_seconds(h)
        max_secs = max(max_secs, secs)
        if h["cost_per_day"] and h["cost_per_day"] > 0:
            saved += int(secs / 86400 * h["cost_per_day"])
    week_ago = to_iso(now_utc() - timedelta(days=7))
    workouts = await db.get_workouts(user["user_id"])
    data = {
        "habits": len(habits), "max_secs": max_secs, "saved": saved,
        "relapses_week": await db.relapses_since(user["user_id"], week_ago),
        "workouts": max((w["sessions"] for w in workouts), default=0),
        "quest_streak": user.get("quest_streak", 0), "xp": user.get("xp", 0),
        "achievements": len(await db.get_achievements(user["user_id"])),
    }
    await bot.send_message(user["user_id"], report_message(data))


async def _send_evening(bot: Bot, user: dict):
    habits = await db.get_habits(user["user_id"])
    if not habits:
        return
    await bot.send_message(user["user_id"], random.choice(EVENING_LINES),
                           reply_markup=kb.evening_kb())


async def _maybe_send_risk(bot: Bot, user: dict, weekday: int):
    """Если сегодня — статистически опасный день недели, шлём превентив."""
    habits = await db.get_habits(user["user_id"])
    if not habits:
        return
    rows = await db.all_relapse_days(user["user_id"])
    if len(rows) < 3:
        return
    tz = user["tz_offset"]
    weekdays = Counter((from_iso(ts) + timedelta(hours=tz)).weekday() for ts in rows)
    top_day, top_count = weekdays.most_common(1)[0]
    # Нужен явный «пик»: не меньше 2 срывов и это самый частый день
    if weekday == top_day and top_count >= 2:
        names = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
        await bot.send_message(
            user["user_id"],
            f"⚠️ <b>Внимание, зона риска.</b>\n\n"
            f"Раньше срывы часто случались в {names[weekday]}. "
            "Будь начеку: убери триггеры, займи вечер делом. "
            "Если накатит — жми 🆘 <b>Паника</b>. Ты сильнее! 💪",
        )


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(hourly_check, "cron", minute=0, args=[bot], misfire_grace_time=300)
    return scheduler
