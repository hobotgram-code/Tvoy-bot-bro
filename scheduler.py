"""Планировщик уведомлений: утренняя мотивация и вечерний чек-ин."""
import logging
import random

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

import database as db
from config import MORNING_HOUR, EVENING_HOUR
from content import MORNING_LINES, EVENING_LINES
from cards import progress_message
import keyboards as kb
from utils import now_utc

log = logging.getLogger(__name__)


async def hourly_check(bot: Bot):
    """Раз в час: подбирает пользователей, у кого сейчас утро или вечер по локали."""
    utc_hour = now_utc().hour
    users = await db.users_to_notify()
    for user in users:
        local_hour = (utc_hour + user["tz_offset"]) % 24
        try:
            if local_hour == MORNING_HOUR:
                await _send_morning(bot, user)
            elif local_hour == EVENING_HOUR:
                await _send_evening(bot, user)
        except (TelegramForbiddenError, TelegramBadRequest):
            # Пользователь заблокировал бота — тихо выключаем уведомления.
            await db.set_notify(user["user_id"], 0)
        except Exception as exc:  # noqa: BLE001
            log.warning("Не удалось отправить уведомление %s: %s", user["user_id"], exc)


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
    line = random.choice(EVENING_LINES)
    await bot.send_message(user["user_id"], line, reply_markup=kb.evening_kb())


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(hourly_check, "cron", minute=0, args=[bot], misfire_grace_time=300)
    return scheduler
