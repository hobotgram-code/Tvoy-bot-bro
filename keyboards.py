"""Клавиатуры бота."""
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from content import HABITS


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Прогресс"), KeyboardButton(text="➕ Трекер")],
            [KeyboardButton(text="💥 Срыв"), KeyboardButton(text="💡 Совет")],
            [KeyboardButton(text="🏆 Уровни"), KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие…",
    )


def add_habit_kb(existing_types: set) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, data in HABITS.items():
        if key == "custom":
            continue
        if key in existing_types:
            continue
        kb.button(text=f"{data['emoji']} {data['name']}", callback_data=f"add:{key}")
    kb.button(text="🎯 Своя цель", callback_data="add:custom")
    kb.adjust(1)
    return kb.as_markup()


def relapse_kb(habits: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for h in habits:
        meta = HABITS.get(h["htype"], HABITS["custom"])
        title = h["title"] or meta["name"]
        kb.button(text=f"{meta['emoji']} {title}", callback_data=f"rl:{h['id']}")
    kb.adjust(1)
    return kb.as_markup()


def relapse_confirm_kb(habit_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, был срыв", callback_data=f"rlc:{habit_id}")
    kb.button(text="↩️ Отмена", callback_data="cancel")
    kb.adjust(2)
    return kb.as_markup()


def settings_kb(user: dict, habits: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    notify_label = "🔔 Уведомления: ВКЛ" if user["notify"] else "🔕 Уведомления: ВЫКЛ"
    kb.button(text=notify_label, callback_data="st:notify")
    kb.button(text=f"🕒 Часовой пояс: UTC+{user['tz_offset']}", callback_data="st:tz")
    for h in habits:
        meta = HABITS.get(h["htype"], HABITS["custom"])
        title = h["title"] or meta["name"]
        kb.button(text=f"💰 Цена: {meta['emoji']} {title}", callback_data=f"cost:{h['id']}")
        kb.button(text=f"🗑 Удалить: {meta['emoji']} {title}", callback_data=f"rm:{h['id']}")
    kb.adjust(1)
    return kb.as_markup()


def tz_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    zones = [
        ("Калининград UTC+2", 2),
        ("Москва UTC+3", 3),
        ("Самара UTC+4", 4),
        ("Екатеринбург UTC+5", 5),
        ("Омск UTC+6", 6),
        ("Красноярск UTC+7", 7),
        ("Иркутск UTC+8", 8),
        ("Владивосток UTC+10", 10),
    ]
    for label, off in zones:
        kb.button(text=label, callback_data=f"tz:{off}")
    kb.adjust(2)
    return kb.as_markup()


def evening_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Держусь!", callback_data="checkin:ok")
    kb.button(text="💥 Был срыв", callback_data="checkin:relapse")
    kb.adjust(2)
    return kb.as_markup()


def remove_confirm_kb(habit_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Да, удалить", callback_data=f"rmc:{habit_id}")
    kb.button(text="↩️ Отмена", callback_data="cancel")
    kb.adjust(2)
    return kb.as_markup()
