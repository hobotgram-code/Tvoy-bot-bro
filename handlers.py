"""Обработчики сообщений и колбэков."""
import asyncio
import random

from aiogram import Router, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, BufferedInputFile

import database as db
import achievements
import charts
from content import (
    HABITS, TIPS, BREATHING_STEPS, BREATHING_CYCLES, DISTRACTIONS, QUESTS,
    TRIGGERS_MAP,
)
from cards import (
    progress_message, levels_message, habit_streak_seconds,
    profile_message, diary_message, replacements_message,
)
from utils import now_utc, format_duration
import keyboards as kb

router = Router()


class Form(StatesGroup):
    cost = State()
    custom_title = State()
    why = State()
    goal_name = State()
    goal_cost = State()


# ---------------------------------------------------------------------------
# Общий помощник: объявить новые достижения
# ---------------------------------------------------------------------------
async def announce_achievements(bot, user_id: int):
    newly = await achievements.check_and_unlock(user_id)
    if newly:
        try:
            await bot.send_message(user_id, achievements.format_new(newly))
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Старт и помощь
# ---------------------------------------------------------------------------
WELCOME = (
    "👋 <b>Привет, боец! Я — Твой Бот-Бро.</b>\n\n"
    "Помогу бросить то, что тянет вниз: 🚬 курение, 🍺 алкоголь, "
    "🧠 порно/онанизм, 🍔 плохое питание — или любую свою цель.\n\n"
    "Что я умею:\n"
    "• ⏱ Считаю стрик до минуты и даю уровни\n"
    "• 🆘 <b>Паника</b> — спасаю в момент тяги\n"
    "• 🩺 Показываю восстановление организма\n"
    "• 💰 Считаю сэкономленные деньги и веду к мечте\n"
    "• 🏆 Ачивки, XP, квесты и рейтинг\n"
    "• 📔 Дневник срывов и умные напоминания\n"
    "• 🤝 Режим напарника для поддержки\n\n"
    "Жми <b>➕ Трекер</b> и добавь первую цель. Погнали! 🚀"
)


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    await db.ensure_user(message.from_user.id, message.from_user.username or "")
    payload = command.args or ""
    if payload.startswith("partner"):
        await _link_partner(message, payload)
        return
    await message.answer(WELCOME, reply_markup=kb.main_menu())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.ensure_user(message.from_user.id, message.from_user.username or "")
    await message.answer(WELCOME, reply_markup=kb.main_menu())


async def _link_partner(message: Message, payload: str):
    try:
        inviter_id = int(payload.replace("partner", ""))
    except ValueError:
        await message.answer("Неверная ссылка приглашения.", reply_markup=kb.main_menu())
        return
    me_id = message.from_user.id
    if inviter_id == me_id:
        await message.answer(
            "Нельзя стать напарником самому себе 🙂 Перешли ссылку другу.",
            reply_markup=kb.main_menu(),
        )
        return
    inviter = await db.get_user(inviter_id)
    if not inviter:
        await message.answer("Пригласивший не найден.", reply_markup=kb.main_menu())
        return
    await db.set_partner(me_id, inviter_id)
    await db.set_partner(inviter_id, me_id)
    await message.answer(
        "🤝 Готово! Вы с напарником связаны. Теперь он узнает о твоих срывах "
        "и сможет поддержать. Держитесь вместе! 💪",
        reply_markup=kb.main_menu(),
    )
    try:
        name = "@" + (message.from_user.username or "") if message.from_user.username else "Твой друг"
        await message.bot.send_message(
            inviter_id,
            f"🤝 {name} присоединился как твой напарник! Теперь вы поддерживаете друг друга.",
        )
    except Exception:  # noqa: BLE001
        pass


@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Кнопки меню</b>\n\n"
        "📊 Прогресс — трекеры, стрики, вехи, график\n"
        "🆘 Паника — экстренная помощь в момент тяги\n"
        "➕ Трекер — добавить цель\n"
        "💥 Срыв — честно отметить срыв (+ дневник)\n"
        "🎯 Квест — задание дня\n"
        "🏆 Профиль — XP, ранг, ачивки, рейтинг\n"
        "📔 Дневник — аналитика твоих срывов\n"
        "💡 Совет — мотивация и техники\n"
        "⚙️ Настройки — уведомления, пояс, напарник, цели\n\n"
        "Помни: срыв — не конец, а урок. Главное — вернуться. 💪",
        reply_markup=kb.main_menu(),
    )


# ---------------------------------------------------------------------------
# Прогресс / График / Уровни / Совет
# ---------------------------------------------------------------------------
@router.message(F.text == "📊 Прогресс")
async def show_progress(message: Message):
    habits = await db.get_habits(message.from_user.id)
    markup = kb.progress_kb() if habits else kb.main_menu()
    await message.answer(progress_message(habits), reply_markup=markup)


@router.callback_query(F.data == "chart")
async def send_chart(callback: CallbackQuery):
    await callback.answer("Рисую график…")
    user = await db.get_user(callback.from_user.id)
    habits = await db.get_habits(callback.from_user.id)
    if not habits:
        await callback.message.answer("Сначала добавь трекер.")
        return
    ts_list = await db.all_relapse_days(callback.from_user.id)
    try:
        png = charts.heatmap_png(user, habits, ts_list)
        await callback.message.answer_photo(
            BufferedInputFile(png, filename="progress.png"),
            caption="📈 Твой календарь чистых дней. Зелёное — держался, красное — срыв.",
        )
    except Exception as exc:  # noqa: BLE001
        await callback.message.answer(f"Не удалось построить график: {exc}")


@router.message(F.text == "🏆 Уровни")
async def show_levels(message: Message):
    await message.answer(levels_message())


@router.message(F.text == "💡 Совет")
async def show_tip(message: Message):
    await message.answer(f"💡 <b>Совет</b>\n\n{random.choice(TIPS)}")


# ---------------------------------------------------------------------------
# Профиль / Дневник
# ---------------------------------------------------------------------------
@router.message(F.text == "🏆 Профиль")
async def show_profile(message: Message):
    user = await db.get_user(message.from_user.id)
    unlocked = await db.get_achievements(message.from_user.id)
    rank, total = await _leaderboard_rank(message.from_user.id)
    await message.answer(profile_message(user, unlocked, rank, total))


@router.message(F.text == "📔 Дневник")
async def show_diary(message: Message):
    relapses = await db.relapse_stats(message.from_user.id)
    await message.answer(diary_message(relapses))


async def _leaderboard_rank(user_id: int):
    rows = await db.leaderboard_data()
    best = {}
    for r in rows:
        secs = int((now_utc() - _parse(r["started_at"])).total_seconds())
        best[r["user_id"]] = max(best.get(r["user_id"], 0), secs)
    if not best:
        return None, 0
    ranking = sorted(best.items(), key=lambda x: x[1], reverse=True)
    total = len(ranking)
    for i, (uid, _) in enumerate(ranking, 1):
        if uid == user_id:
            return i, total
    return None, total


def _parse(s):
    from utils import from_iso
    return from_iso(s)


# ---------------------------------------------------------------------------
# Квест дня
# ---------------------------------------------------------------------------
@router.message(F.text == "🎯 Квест")
async def show_quest(message: Message):
    user = await db.get_user(message.from_user.id)
    today = _local_date(user)
    if user.get("quest_date") != today:
        quest = random.choice(QUESTS)
        await db.set_quest(message.from_user.id, today, quest)
        done = False
    else:
        quest = user.get("quest_text") or random.choice(QUESTS)
        done = bool(user.get("quest_done"))
    streak = user.get("quest_streak", 0)
    status = "✅ Выполнен! Молодец!" if done else "⏳ Ещё не выполнен"
    await message.answer(
        f"🎯 <b>КВЕСТ ДНЯ</b>\n\n{quest}\n\n"
        f"Статус: {status}\n🔥 Серия квестов: {streak}\n\n"
        f"<i>Маленькое действие каждый день — большая перемена за год.</i>",
        reply_markup=kb.quest_kb(done),
    )


@router.callback_query(F.data == "quest:done")
async def quest_done(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    today = _local_date(user)
    if user.get("quest_date") != today:
        await callback.answer("Квест уже неактуален, открой заново.")
        return
    if user.get("quest_done"):
        await callback.answer("Уже выполнено ✅")
        return
    await db.complete_quest(callback.from_user.id)
    await db.add_xp(callback.from_user.id, 15)
    await callback.message.edit_text(
        f"🎯 <b>КВЕСТ ВЫПОЛНЕН!</b> +15 XP 🔥\n\n"
        f"{user.get('quest_text', '')}\n\nВозвращайся завтра за новым. 💪"
    )
    await callback.answer("+15 XP")
    await announce_achievements(callback.bot, callback.from_user.id)


def _local_date(user: dict) -> str:
    from datetime import timedelta
    d = (now_utc() + timedelta(hours=user.get("tz_offset", 3))).date()
    return d.isoformat()


# ---------------------------------------------------------------------------
# Паника — экстренная помощь
# ---------------------------------------------------------------------------
@router.message(F.text == "🆘 Паника")
async def panic_start(message: Message):
    habits = await db.get_habits(message.from_user.id)
    whys = [h["why"] for h in habits if h.get("why")]
    losses = []
    for h in habits:
        meta = HABITS.get(h["htype"], HABITS["custom"])
        secs = habit_streak_seconds(h)
        if secs >= 3600:
            losses.append(f"{meta['emoji']} {format_duration(secs)}")

    await message.answer(
        "🆘 <b>Держись. Тяга — это волна, она пройдёт за 3–5 минут.</b>\n\n"
        "Давай подышим вместе. Следуй за подсказками 👇"
    )
    # Дыхательная техника
    breathing = await message.answer("Приготовься… 🫁")
    try:
        for _ in range(BREATHING_CYCLES):
            for text, emoji, secs in BREATHING_STEPS:
                await breathing.edit_text(f"{emoji} <b>{text}</b> — {secs} сек")
                await asyncio.sleep(secs)
        await breathing.edit_text("🌬 <b>Отлично. Ты уже спокойнее.</b>")
    except Exception:  # noqa: BLE001
        pass

    parts = []
    if losses:
        parts.append("💔 <b>Сорвёшься — потеряешь:</b>\n" + "\n".join(losses))
    if whys:
        parts.append("❤️ <b>Вспомни, ради чего:</b>\n" + "\n".join(f"• {w}" for w in whys))
    parts.append("🎯 <b>Сделай прямо сейчас:</b>\n" + random.choice(DISTRACTIONS))
    parts.append("\nТы сильнее этой тяги. Что дальше?")

    await message.answer("\n\n".join(parts), reply_markup=kb.panic_kb())


@router.callback_query(F.data == "pn:calm")
async def panic_calm(callback: CallbackQuery):
    await db.inc_cravings(callback.from_user.id)
    await db.add_xp(callback.from_user.id, 10)
    await callback.message.edit_text(
        "🏆 <b>ТЫ ПОБЕДИЛ ТЯГУ!</b> +10 XP\n\n"
        "Каждая пережитая волна делает тебя сильнее — мозг учится, "
        "что тяга проходит и без срыва. Гордись собой! 💪"
    )
    await callback.answer("Красавчик! 🔥")
    await announce_achievements(callback.bot, callback.from_user.id)


@router.callback_query(F.data == "pn:repl")
async def panic_repl(callback: CallbackQuery):
    habits = await db.get_habits(callback.from_user.id)
    await callback.message.answer(replacements_message(habits))
    await callback.answer()


@router.callback_query(F.data == "pn:relapse")
async def panic_relapse(callback: CallbackQuery):
    habits = await db.get_habits(callback.from_user.id)
    if not habits:
        await callback.message.edit_text("У тебя нет активных трекеров.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "Бывает. Отметь честно, по какому трекеру — и идём дальше. 🌱",
        reply_markup=kb.relapse_kb(habits),
    )
    await callback.answer()


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
    hid = await db.add_habit(callback.from_user.id, htype, meta["name"], meta["default_cost"])
    await callback.message.edit_text(
        f"{meta['emoji']} <b>{meta['name']}</b> — трекер запущен! ⏱\n\n"
        f"<i>{meta['motto']}</i>\n\nСтрик пошёл. Загляни в 📊 Прогресс в любой момент.",
        reply_markup=kb.after_add_kb(hid),
    )
    await callback.answer("Трекер добавлен ✅")
    await announce_achievements(callback.bot, callback.from_user.id)


@router.message(Form.custom_title)
async def custom_title_input(message: Message, state: FSMContext):
    title = (message.text or "").strip()[:40]
    if not title:
        await message.answer("Пустое название не подойдёт. Напиши ещё раз 🙂")
        return
    hid = await db.add_habit(message.from_user.id, "custom", title, 0)
    await state.clear()
    await message.answer(
        f"🎯 <b>{title}</b> — трекер запущен! ⏱\nСтрик пошёл. Ты справишься! 💪",
        reply_markup=kb.after_add_kb(hid),
    )


# ---------------------------------------------------------------------------
# «Зачем» и мечта-цель
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("goal:"))
async def goal_start(callback: CallbackQuery, state: FSMContext):
    habit_id = int(callback.data.split(":", 1)[1])
    await state.set_state(Form.why)
    await state.update_data(habit_id=habit_id)
    await callback.message.answer(
        "❤️ Напиши одной фразой, <b>ради чего</b> ты бросаешь.\n"
        "<i>Например: «Ради здоровья и детей», «Хочу уважать себя».</i>\n\n"
        "Я покажу это в момент тяги."
    )
    await callback.answer()


@router.message(Form.why)
async def why_input(message: Message, state: FSMContext):
    why = (message.text or "").strip()[:120]
    await state.update_data(why=why)
    await state.set_state(Form.goal_name)
    await message.answer(
        "🎁 О чём мечтаешь купить на сэкономленные деньги?\n"
        "<i>Например: «Новый телефон», «Поездка к морю».</i>\n"
        "Отправь «-», чтобы пропустить."
    )


@router.message(Form.goal_name)
async def goal_name_input(message: Message, state: FSMContext):
    goal = (message.text or "").strip()[:60]
    if goal == "-":
        data = await state.get_data()
        await db.set_why_goal(data["habit_id"], data.get("why", ""), "", 0)
        await state.clear()
        await message.answer("❤️ Записал твоё «зачем». Оно поддержит в трудный момент.",
                             reply_markup=kb.main_menu())
        return
    await state.update_data(goal=goal)
    await state.set_state(Form.goal_cost)
    await message.answer(f"💰 Сколько стоит «{goal}»? Напиши число в рублях.")


@router.message(Form.goal_cost)
async def goal_cost_input(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", ".").strip()
    try:
        cost = float(text)
        if cost < 0 or cost > 100_000_000:
            raise ValueError
    except ValueError:
        await message.answer("Нужно число. Попробуй ещё раз.")
        return
    data = await state.get_data()
    await db.set_why_goal(data["habit_id"], data.get("why", ""), data.get("goal", ""), cost)
    await state.clear()
    await message.answer(
        "🎯 Готово! Теперь в прогрессе видно, насколько ты близок к мечте. 🚀",
        reply_markup=kb.main_menu(),
    )


# ---------------------------------------------------------------------------
# Срыв + дневник (триггер, настроение)
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
    log_id = await db.relapse(callback.from_user.id, habit_id, streak)
    meta = HABITS.get(habit["htype"], HABITS["custom"])
    title = habit["title"] or meta["name"]
    await callback.message.edit_text(
        f"🌱 Стрик по «{meta['emoji']} {title}» начат заново.\n\n"
        "Срыв — это данные. Давай зафиксируем триггер, чтобы в следующий раз "
        "быть готовым. <b>Что стало причиной?</b>",
        reply_markup=kb.trigger_kb(log_id),
    )
    await callback.answer("Начинаем заново 🌱")
    # Уведомить напарника
    await _notify_partner_relapse(callback, title, meta, streak)


async def _notify_partner_relapse(callback, title, meta, streak):
    user = await db.get_user(callback.from_user.id)
    if not user or not user.get("partner_id"):
        return
    name = "@" + user["username"] if user.get("username") else "Твой напарник"
    try:
        await callback.bot.send_message(
            user["partner_id"],
            f"🤝 {name} сорвался по «{meta['emoji']} {title}» "
            f"(стрик был {format_duration(streak)}).\n"
            "Напиши ему пару тёплых слов — поддержка сейчас важна. 💪",
        )
    except Exception:  # noqa: BLE001
        pass


@router.callback_query(F.data.startswith("trg:"))
async def relapse_trigger(callback: CallbackQuery):
    _, log_id, code = callback.data.split(":")
    log_id = int(log_id)
    if code != "skip":
        await db.set_relapse_details(log_id, trigger=code)
    await callback.message.edit_text(
        "Понял. И последнее: <b>как настроение сейчас?</b> (1 — плохо, 5 — отлично)",
        reply_markup=kb.mood_kb(log_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mood:"))
async def relapse_mood(callback: CallbackQuery):
    _, log_id, val = callback.data.split(":")
    await db.set_relapse_details(int(log_id), mood=int(val))
    await callback.message.edit_text(
        "🌱 Записал. Ты честен с собой — это уже сила.\n\n"
        "<b>Ты знаешь, что можешь держаться. Начинаем снова. 💪</b>\n"
        "<i>Посмотри свои паттерны в 📔 Дневнике.</i>"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------
@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    user = await db.get_user(message.from_user.id)
    habits = await db.get_habits(message.from_user.id)
    await message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Уведомления, часовой пояс, напарник и настройка каждого трекера "
        "(цена, «зачем», удаление).",
        reply_markup=kb.settings_kb(user, habits),
    )


async def _render_settings(callback, header="⚙️ <b>Настройки</b>"):
    user = await db.get_user(callback.from_user.id)
    habits = await db.get_habits(callback.from_user.id)
    await callback.message.edit_text(header, reply_markup=kb.settings_kb(user, habits))


@router.callback_query(F.data == "back:settings")
async def back_settings(callback: CallbackQuery):
    await _render_settings(callback)
    await callback.answer()


@router.callback_query(F.data == "st:notify")
async def toggle_notify(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    new_val = 0 if user["notify"] else 1
    await db.set_notify(callback.from_user.id, new_val)
    await _render_settings(
        callback,
        "⚙️ <b>Настройки</b>\n\nУведомления " + ("включены 🔔" if new_val else "выключены 🔕"),
    )
    await callback.answer()


@router.callback_query(F.data == "st:tz")
async def tz_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🕒 Выбери часовой пояс — по нему буду слать уведомления:",
        reply_markup=kb.tz_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tz:"))
async def tz_set(callback: CallbackQuery):
    offset = int(callback.data.split(":", 1)[1])
    await db.set_tz(callback.from_user.id, offset)
    await _render_settings(callback, f"⚙️ <b>Настройки</b>\n\nЧасовой пояс: UTC+{offset} ✅")
    await callback.answer("Сохранено")


# --- Напарник
@router.callback_query(F.data == "st:partner")
async def partner_menu(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    me = await callback.bot.get_me()
    link = f"https://t.me/{me.username}?start=partner{callback.from_user.id}"
    if user.get("partner_id"):
        text = (
            "🤝 <b>Напарник</b>\n\nУ тебя есть напарник — он получает сигнал о срывах "
            "и может поддержать.\n\nХочешь позвать ещё кого-то? Отправь ссылку:\n"
            f"<code>{link}</code>"
        )
    else:
        text = (
            "🤝 <b>Режим напарника</b>\n\n"
            "Отправь эту ссылку другу, которому доверяешь. Когда он её откроет — "
            "вы станете напарниками: он будет видеть твой стрик и получать сигнал "
            "о срывах, чтобы поддержать. Публичная ответственность работает!\n\n"
            f"🔗 <code>{link}</code>"
        )
    await callback.message.edit_text(text, reply_markup=kb.partner_kb(user))
    await callback.answer()


@router.callback_query(F.data == "partner:view")
async def partner_view(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    pid = user.get("partner_id")
    if not pid:
        await callback.answer("Напарник не подключён")
        return
    habits = await db.get_habits(pid)
    partner = await db.get_user(pid)
    name = "@" + partner["username"] if partner and partner.get("username") else "Напарник"
    await callback.message.answer(f"👀 <b>Прогресс: {name}</b>\n\n{progress_message(habits)}")
    await callback.answer()


@router.callback_query(F.data == "partner:unlink")
async def partner_unlink(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    pid = user.get("partner_id")
    await db.set_partner(callback.from_user.id, None)
    if pid:
        await db.set_partner(pid, None)
    await _render_settings(callback, "⚙️ <b>Настройки</b>\n\nНапарник отвязан.")
    await callback.answer("Отвязано")


# --- Настройки конкретного трекера
@router.callback_query(F.data.startswith("hs:"))
async def habit_settings(callback: CallbackQuery):
    habit_id = int(callback.data.split(":", 1)[1])
    habit = await db.get_habit(habit_id)
    if not habit:
        await callback.answer("Не найдено")
        return
    meta = HABITS.get(habit["htype"], HABITS["custom"])
    title = habit["title"] or meta["name"]
    await callback.message.edit_text(
        f"⚙️ <b>{meta['emoji']} {title}</b>\nЧто настроить?",
        reply_markup=kb.habit_settings_kb(habit),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cost:"))
async def cost_start(callback: CallbackQuery, state: FSMContext):
    habit_id = int(callback.data.split(":", 1)[1])
    await state.set_state(Form.cost)
    await state.update_data(habit_id=habit_id)
    await callback.message.answer(
        "💰 Сколько денег в день уходило на эту привычку?\n"
        "Напиши число в рублях (например, <code>200</code>)."
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
        f"💰 Готово! Считаю экономию по {cost:.0f} ₽/день. Смотри итог в 📊 Прогресс.",
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
        f"🗑 Удалить трекер «{meta['emoji']} {title}» со всей статистикой?",
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
# Вечерний чек-ин
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "checkin:ok")
async def checkin_ok(callback: CallbackQuery):
    await db.add_xp(callback.from_user.id, 5)
    await callback.message.edit_text(
        "🔥 Красавчик! Ещё один чистый день в копилку. +5 XP 💪"
    )
    await callback.answer("Гордимся тобой!")
    await announce_achievements(callback.bot, callback.from_user.id)


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
