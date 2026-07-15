"""Обработчики сообщений и колбэков."""
import random

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import database as db
from content import HABITS, TIPS
from cards import progress_message, levels_message, habit_card, habit_streak_seconds
import keyboards as kb

router = Router()


class Form(StatesGroup):
    cost = State()
    custom_title = State()


# ---------------------------------------------------------------------------
# Старт и помощь
# ---------------------------------------------------------------------------
WELCOME = (
    "👋 <b>Привет, боец! Я — Твой Бот-Бро.</b>\n\n"
    "Я помогу тебе бросить то, что тянет вниз: 🚬 курение, 🍺 алкоголь, "
    "🧠 порно/онанизм, 🍔 плохое питание — или любую свою цель.\n\n"
    "Что я умею:\n"
    "• ⏱ Считаю твой стрик до минуты\n"
    "• 🏅 Даю уровни за силу воли\n"
    "• 🩺 Показываю, как восстанавливается твой организм\n"
    "• 💰 Считаю сэкономленные деньги\n"
    "• 🔔 Присылаю утреннюю мотивацию и вечерний чек-ин\n"
    "• 💡 Даю советы, когда тяжело\n\n"
    "Жми <b>➕ Трекер</b> и добавь первую цель. Погнали! 🚀"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.ensure_user(message.from_user.id, message.from_user.username or "")
    await message.answer(WELCOME, reply_markup=kb.main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Команды и кнопки</b>\n\n"
        "📊 Прогресс — все твои трекеры, стрики и вехи\n"
        "➕ Трекер — добавить новую цель\n"
        "💥 Срыв — честно отметить срыв (стрик начнётся заново)\n"
        "💡 Совет — мотивация и техника, когда тяжело\n"
        "🏆 Уровни — таблица уровней\n"
        "⚙️ Настройки — уведомления, часовой пояс, цена привычки\n\n"
        "Помни: срыв — не конец, а урок. Главное — вернуться. 💪",
        reply_markup=kb.main_menu(),
    )


# ---------------------------------------------------------------------------
# Прогресс / Уровни / Совет
# ---------------------------------------------------------------------------
@router.message(F.text == "📊 Прогресс")
async def show_progress(message: Message):
    habits = await db.get_habits(message.from_user.id)
    await message.answer(progress_message(habits), reply_markup=kb.main_menu())


@router.message(F.text == "🏆 Уровни")
async def show_levels(message: Message):
    await message.answer(levels_message())


@router.message(F.text == "💡 Совет")
async def show_tip(message: Message):
    tip = random.choice(TIPS)
    await message.answer(f"💡 <b>Совет</b>\n\n{tip}")


# ---------------------------------------------------------------------------
# Добавление трекера
# ---------------------------------------------------------------------------
@router.message(F.text == "➕ Трекер")
async def add_menu(message: Message):
    habits = await db.get_habits(message.from_user.id)
    existing = {h["htype"] for h in habits if h["htype"] != "custom"}
    await message.answer(
        "Что берём под контроль? Выбери трекер 👇\n"
        "<i>Стрик пойдёт с этого момента.</i>",
        reply_markup=kb.add_habit_kb(existing),
    )


@router.callback_query(F.data.startswith("add:"))
async def add_habit_cb(callback: CallbackQuery, state: FSMContext):
    htype = callback.data.split(":", 1)[1]
    meta = HABITS.get(htype)
    if not meta:
        await callback.answer("Неизвестный тип")
        return

    if htype == "custom":
        await state.set_state(Form.custom_title)
        await callback.message.edit_text(
            "🎯 Напиши коротко, от чего отказываешься.\n"
            "<i>Например: «Энергетики», «Ставки», «Прокрастинация».</i>"
        )
        await callback.answer()
        return

    await db.add_habit(callback.from_user.id, htype, meta["name"], meta["default_cost"])
    await callback.message.edit_text(
        f"{meta['emoji']} <b>{meta['name']}</b> — трекер запущен! ⏱\n\n"
        f"<i>{meta['motto']}</i>\n\n"
        "Стрик пошёл с этой секунды. Загляни в 📊 Прогресс в любой момент. 💪"
    )
    await callback.answer("Трекер добавлен ✅")


@router.message(Form.custom_title)
async def custom_title_input(message: Message, state: FSMContext):
    title = (message.text or "").strip()[:40]
    if not title:
        await message.answer("Пустое название не подойдёт. Напиши ещё раз 🙂")
        return
    await db.add_habit(message.from_user.id, "custom", title, 0)
    await state.clear()
    await message.answer(
        f"🎯 <b>{title}</b> — трекер запущен! ⏱\n\n"
        "Стрик пошёл. Ты справишься! 💪",
        reply_markup=kb.main_menu(),
    )


# ---------------------------------------------------------------------------
# Срыв
# ---------------------------------------------------------------------------
@router.message(F.text == "💥 Срыв")
async def relapse_menu(message: Message):
    habits = await db.get_habits(message.from_user.id)
    if not habits:
        await message.answer("У тебя пока нет трекеров. Добавь через «➕ Трекер».")
        return
    await message.answer(
        "По какому трекеру был срыв? Отметь честно — это не поражение, "
        "а точка, из которой ты снова растёшь. 🌱",
        reply_markup=kb.relapse_kb(habits),
    )


@router.callback_query(F.data.startswith("rl:"))
async def relapse_pick(callback: CallbackQuery):
    habit_id = int(callback.data.split(":", 1)[1])
    habit = await db.get_habit(habit_id)
    if not habit:
        await callback.answer("Трекер не найден")
        return
    meta = HABITS.get(habit["htype"], HABITS["custom"])
    title = habit["title"] or meta["name"]
    await callback.message.edit_text(
        f"Подтверди срыв по «{meta['emoji']} {title}».\n"
        "Текущий стрик обнулится, но рекорд сохранится.",
        reply_markup=kb.relapse_confirm_kb(habit_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rlc:"))
async def relapse_confirm(callback: CallbackQuery):
    habit_id = int(callback.data.split(":", 1)[1])
    habit = await db.get_habit(habit_id)
    if not habit:
        await callback.answer("Трекер не найден")
        return
    streak = habit_streak_seconds(habit)
    await db.relapse(habit_id, streak)
    meta = HABITS.get(habit["htype"], HABITS["custom"])
    title = habit["title"] or meta["name"]
    await callback.message.edit_text(
        f"🌱 Стрик по «{meta['emoji']} {title}» начат заново.\n\n"
        "Срыв — это не «всё пропало». Это данные: что стало триггером? "
        "Убери его — и следующий заход будет сильнее.\n\n"
        "<b>Ты уже знаешь, что можешь держаться. Начинаем снова. 💪</b>"
    )
    await callback.answer("Начинаем заново 🌱")


# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------
@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    user = await db.get_user(message.from_user.id)
    habits = await db.get_habits(message.from_user.id)
    await message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Здесь можно включить/выключить уведомления, задать часовой пояс "
        "и цену привычки (для подсчёта денег).",
        reply_markup=kb.settings_kb(user, habits),
    )


@router.callback_query(F.data == "st:notify")
async def toggle_notify(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    new_val = 0 if user["notify"] else 1
    await db.set_notify(callback.from_user.id, new_val)
    user["notify"] = new_val
    habits = await db.get_habits(callback.from_user.id)
    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>\n\nУведомления " + ("включены 🔔" if new_val else "выключены 🔕"),
        reply_markup=kb.settings_kb(user, habits),
    )
    await callback.answer()


@router.callback_query(F.data == "st:tz")
async def tz_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🕒 Выбери свой часовой пояс — по нему буду присылать уведомления:",
        reply_markup=kb.tz_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tz:"))
async def tz_set(callback: CallbackQuery):
    offset = int(callback.data.split(":", 1)[1])
    await db.set_tz(callback.from_user.id, offset)
    user = await db.get_user(callback.from_user.id)
    habits = await db.get_habits(callback.from_user.id)
    await callback.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\nЧасовой пояс: UTC+{offset} ✅",
        reply_markup=kb.settings_kb(user, habits),
    )
    await callback.answer("Сохранено")


@router.callback_query(F.data.startswith("cost:"))
async def cost_start(callback: CallbackQuery, state: FSMContext):
    habit_id = int(callback.data.split(":", 1)[1])
    await state.set_state(Form.cost)
    await state.update_data(habit_id=habit_id)
    await callback.message.edit_text(
        "💰 Сколько денег в день уходило на эту привычку?\n"
        "Напиши число в рублях (например, <code>200</code>). "
        "Я буду считать, сколько ты экономишь."
    )
    await callback.answer()


@router.message(Form.cost)
async def cost_input(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", ".").strip()
    try:
        cost = float(text)
        if cost < 0 or cost > 1_000_000:
            raise ValueError
    except ValueError:
        await message.answer("Нужно число от 0 до 1 000 000. Попробуй ещё раз.")
        return
    data = await state.get_data()
    await db.set_cost(data["habit_id"], cost)
    await state.clear()
    await message.answer(
        f"💰 Готово! Считаю экономию по {cost:.0f} ₽/день. "
        "Смотри итог в 📊 Прогресс.",
        reply_markup=kb.main_menu(),
    )


@router.callback_query(F.data.startswith("rm:"))
async def remove_start(callback: CallbackQuery):
    habit_id = int(callback.data.split(":", 1)[1])
    habit = await db.get_habit(habit_id)
    if not habit:
        await callback.answer("Не найдено")
        return
    meta = HABITS.get(habit["htype"], HABITS["custom"])
    title = habit["title"] or meta["name"]
    await callback.message.edit_text(
        f"🗑 Удалить трекер «{meta['emoji']} {title}» вместе со всей статистикой?",
        reply_markup=kb.remove_confirm_kb(habit_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rmc:"))
async def remove_confirm(callback: CallbackQuery):
    habit_id = int(callback.data.split(":", 1)[1])
    await db.remove_habit(habit_id)
    await callback.message.edit_text("🗑 Трекер удалён.")
    await callback.answer("Удалено")


# ---------------------------------------------------------------------------
# Вечерний чек-ин (из уведомления)
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "checkin:ok")
async def checkin_ok(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔥 Красавчик! Ещё один чистый день в копилку. Так держать! 💪"
    )
    await callback.answer("Гордимся тобой!")


@router.callback_query(F.data == "checkin:relapse")
async def checkin_relapse(callback: CallbackQuery):
    habits = await db.get_habits(callback.from_user.id)
    if not habits:
        await callback.message.edit_text("У тебя нет активных трекеров.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "Бывает. Отметь, по какому трекеру был срыв — и идём дальше. 🌱",
        reply_markup=kb.relapse_kb(habits),
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Общие
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "cancel")
async def cancel_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменено. Возвращайся в меню 👇")
    await callback.answer()


@router.message()
async def fallback(message: Message):
    await message.answer(
        "Не понял 🤔 Пользуйся кнопками меню внизу или /help.",
        reply_markup=kb.main_menu(),
    )
