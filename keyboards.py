"""Клавиатуры бота."""
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from content import HABITS, TRIGGERS, MOODS


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Прогресс"), KeyboardButton(text="🆘 Паника")],
            [KeyboardButton(text="➕ Трекер"), KeyboardButton(text="💥 Срыв")],
            [KeyboardButton(text="💪 Тренировка"), KeyboardButton(text="📸 Фото")],
            [KeyboardButton(text="🌿 Витамины"), KeyboardButton(text="🎯 Квест")],
            [KeyboardButton(text="🏆 Профиль"), KeyboardButton(text="📔 Дневник")],
            [KeyboardButton(text="🧰 Ещё"), KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие…",
    )


def hub_kb(ai_on: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🧘 Техники", callback_data="hub:tech")
    kb.button(text="📅 Отчёт за неделю", callback_data="hub:report")
    kb.button(text="💬 Аффирмации", callback_data="hub:aff")
    kb.button(text="📈 Замеры (вес)", callback_data="hub:metrics")
    if ai_on:
        kb.button(text="🤖 Поговорить с ИИ-бро", callback_data="hub:ai")
    kb.button(text="📤 Экспорт данных", callback_data="hub:export")
    kb.button(text="💡 Совет", callback_data="hub:tip")
    kb.button(text="❓ Помощь", callback_data="hub:help")
    kb.adjust(1)
    return kb.as_markup()


def techniques_kb() -> InlineKeyboardMarkup:
    from content import TECHNIQUES
    kb = InlineKeyboardBuilder()
    for i, (title, _text) in enumerate(TECHNIQUES):
        kb.button(text=title, callback_data=f"tech:{i}")
    kb.adjust(1)
    return kb.as_markup()


def affirmations_kb(has_any: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить свою", callback_data="aff:add")
    if has_any:
        kb.button(text="🎲 Случайная", callback_data="aff:rand")
    kb.adjust(1)
    return kb.as_markup()


def metrics_kb(has_weight: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚖️ Записать вес", callback_data="m:weight")
    kb.button(text="😊 Записать самочувствие", callback_data="m:mood")
    if has_weight:
        kb.button(text="📈 График веса", callback_data="m:chart")
    kb.adjust(1)
    return kb.as_markup()


def ai_exit_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🚪 Выйти из чата с ИИ", callback_data="ai:exit")
    kb.adjust(1)
    return kb.as_markup()


def hours_kb(field: str) -> InlineKeyboardMarkup:
    """Выбор часа для конкретного уведомления."""
    kb = InlineKeyboardBuilder()
    hours = {
        "morning_hour": [6, 7, 8, 9, 10, 11],
        "evening_hour": [18, 19, 20, 21, 22, 23],
        "workout_hour": [12, 15, 17, 18, 19, 20],
    }.get(field, [8, 9, 10])
    for h in hours:
        kb.button(text=f"{h}:00", callback_data=f"seth:{field}:{h}")
    kb.button(text="↩️ Назад", callback_data="st:hours")
    kb.adjust(3)
    return kb.as_markup()


def hours_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🌅 Утро", callback_data="hsel:morning_hour")
    kb.button(text="🌙 Вечер", callback_data="hsel:evening_hour")
    kb.button(text="💪 Тренировка", callback_data="hsel:workout_hour")
    kb.button(text="↩️ Назад", callback_data="back:settings")
    kb.adjust(1)
    return kb.as_markup()


def workout_kb(done_today: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not done_today:
        kb.button(text="✅ Выполнил", callback_data="wo:done")
        kb.button(text="⏭ Пропустил", callback_data="wo:skip")
    kb.adjust(2)
    return kb.as_markup()


def vitamins_kb(done_today: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not done_today:
        kb.button(text="✅ Принял витамины", callback_data="vit:done")
    kb.adjust(1)
    return kb.as_markup()


def add_habit_kb(existing_types: set) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, data in HABITS.items():
        if key == "custom" or key in existing_types:
            continue
        kb.button(text=f"{data['emoji']} {data['name']}", callback_data=f"add:{key}")
    kb.button(text="🎯 Своя цель", callback_data="add:custom")
    kb.adjust(1)
    return kb.as_markup()


def after_add_kb(habit_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❤️ Указать «зачем» и мечту", callback_data=f"goal:{habit_id}")
    kb.adjust(1)
    return kb.as_markup()


def progress_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📈 Календарь-график", callback_data="chart")
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


def relapse_confirm_kb(habit_id: int, freeze_left: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, был срыв", callback_data=f"rlc:{habit_id}")
    if freeze_left > 0:
        kb.button(text=f"❄️ Заморозка — спасти стрик ({freeze_left})",
                  callback_data=f"frz:{habit_id}")
    kb.button(text="↩️ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def panic_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Отпустило!", callback_data="pn:calm")
    kb.button(text="💊 Замены", callback_data="pn:repl")
    kb.button(text="💥 Всё же сорвался", callback_data="pn:relapse")
    kb.adjust(1)
    return kb.as_markup()


def quest_kb(done: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not done:
        kb.button(text="✅ Выполнил!", callback_data="quest:done")
    kb.adjust(1)
    return kb.as_markup()


def trigger_kb(log_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, label in TRIGGERS:
        kb.button(text=label, callback_data=f"trg:{log_id}:{code}")
    kb.button(text="⏭ Пропустить", callback_data=f"trg:{log_id}:skip")
    kb.adjust(2)
    return kb.as_markup()


def mood_kb(log_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for val, label in MOODS:
        kb.button(text=label, callback_data=f"mood:{log_id}:{val}")
    kb.adjust(5)
    return kb.as_markup()


def settings_kb(user: dict, habits: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    notify_label = "🔔 Уведомления: ВКЛ" if user["notify"] else "🔕 Уведомления: ВЫКЛ"
    kb.button(text=notify_label, callback_data="st:notify")
    kb.button(text=f"🕒 Пояс: UTC+{user['tz_offset']}", callback_data="st:tz")
    partner_label = "🤝 Напарник: подключён" if user.get("partner_id") else "🤝 Пригласить напарника"
    kb.button(text=partner_label, callback_data="st:partner")
    kb.button(text="⏰ Время уведомлений", callback_data="st:hours")
    for h in habits:
        meta = HABITS.get(h["htype"], HABITS["custom"])
        title = h["title"] or meta["name"]
        kb.button(text=f"⚙️ {meta['emoji']} {title}", callback_data=f"hs:{h['id']}")
    kb.adjust(1)
    return kb.as_markup()


def habit_settings_kb(habit: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Цена привычки", callback_data=f"cost:{habit['id']}")
    kb.button(text="❤️ «Зачем» и мечта", callback_data=f"goal:{habit['id']}")
    kb.button(text="🗑 Удалить трекер", callback_data=f"rm:{habit['id']}")
    kb.button(text="↩️ Назад", callback_data="back:settings")
    kb.adjust(1)
    return kb.as_markup()


def tz_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    zones = [
        ("Калининград +2", 2), ("Москва +3", 3), ("Самара +4", 4),
        ("Екатеринбург +5", 5), ("Омск +6", 6), ("Красноярск +7", 7),
        ("Иркутск +8", 8), ("Владивосток +10", 10),
    ]
    for label, off in zones:
        kb.button(text=label, callback_data=f"tz:{off}")
    kb.adjust(2)
    return kb.as_markup()


def partner_kb(user: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if user.get("partner_id"):
        kb.button(text="👀 Стрик напарника", callback_data="partner:view")
        kb.button(text="❌ Отвязать напарника", callback_data="partner:unlink")
    kb.button(text="↩️ Назад", callback_data="back:settings")
    kb.adjust(1)
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
