"""Планировщик: утренняя мотивация, вечерний чек-ин, умные напоминания."""
import logging
import random
from collections import Counter
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

import database as db
from config import MORNING_HOUR, EVENING_HOUR
from content import MORNING_LINES, EVENING_LINES
from cards import progress_message
import keyboards as kb
from utils import now_utc, from_iso

log = logging.getLogger(__name__)

RISK_HOUR = 18  # час для превентивного напоминания в опасный день недели


async def hourly_check(bot: Bot):
    """Раз в час подбирает пользователей, у кого сейчас утро, вечер или зона риска."""
    now = now_utc()
    users = await db.users_to_notify()
    for user in users:
        local = now + timedelta(hours=user["tz_offset"])
        local_hour = local.hour
        try:
            if local_hour == MORNING_HOUR:
                await _send_morning(bot, user)
            elif local_hour == EVENING_HOUR:
                await _send_evening(bot, user)
            elif local_hour == RISK_HOUR:
                await _maybe_send_risk(bot, user, local.weekday())
        except (TelegramForbiddenError, TelegramBadRequest):
            await db.set_notify(user["user_id"], 0)
        except Exception as exc:  # noqa: BLE001
            log.warning("Уведомление %s не отправлено: %s", user["user_id"], exc)


async def _send_morning(bot: Bot, user: dict):
    habits = await db.get_habits(user["user_id"])
    line = random.choice(MORNING_LINES)
    if habits:
        text = f"{line}\n\n{progress_message(habits)}"
    else:
        text = f"{line}\n\nДобавь первый трекер через «➕ Трекер» и начни путь к свободе. 💪"
    await bot.send_message(user["user_id"], text)


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
