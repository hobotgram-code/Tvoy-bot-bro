"""Формирование текстовых карточек прогресса."""
from content import HABITS
from utils import (
    now_utc,
    from_iso,
    format_duration,
    level_info,
    progress_bar,
    milestones_status,
)

DIVIDER = "━━━━━━━━━━━━━━━"


def habit_streak_seconds(habit: dict) -> int:
    return int((now_utc() - from_iso(habit["started_at"])).total_seconds())


def habit_card(habit: dict) -> str:
    meta = HABITS.get(habit["htype"], HABITS["custom"])
    title = habit["title"] or meta["name"]
    elapsed = habit_streak_seconds(habit)
    days = elapsed // 86400

    lines = [f"{meta['emoji']} <b>{title}</b>"]
    lines.append(f"🔥 Стрик: <b>{format_duration(elapsed)}</b>")

    cur_level, nxt_level = level_info(days)
    lines.append(f"🏅 Уровень: {cur_level[1]}")
    if nxt_level:
        target_days = nxt_level[0]
        bar = progress_bar(days, target_days)
        left = target_days * 86400 - elapsed
        pct = int(min(days / target_days, 1) * 100) if target_days else 100
        lines.append(
            f"📈 До «{nxt_level[1]}»: {bar} {pct}%\n"
            f"    ещё {format_duration(max(left, 0))}"
        )
    else:
        lines.append("📈 Максимальный уровень достигнут! 👑")

    # Деньги + мечта-цель
    if habit["cost_per_day"] and habit["cost_per_day"] > 0:
        saved = int(elapsed / 86400 * habit["cost_per_day"])
        lines.append(f"💰 Сэкономлено: <b>{saved:,} ₽</b>".replace(",", " "))
        goal = habit.get("goal")
        goal_cost = habit.get("goal_cost") or 0
        if goal and goal_cost > 0:
            pct = int(min(saved / goal_cost, 1) * 100)
            bar = progress_bar(saved, goal_cost)
            lines.append(f"🎁 На «{goal}»: {bar} {pct}%")

    # Личное «зачем»
    if habit.get("why"):
        lines.append(f"❤️ Ради: <i>{habit['why']}</i>")

    # Вехи восстановления
    reached, upcoming = milestones_status(elapsed, habit["htype"])
    if reached:
        last = reached[-1]
        lines.append(f"✅ Достигнуто: {last[1]}")
    if upcoming:
        left = upcoming[0] - elapsed
        lines.append(f"🎯 Впереди ({format_duration(left)}): {upcoming[1]}")

    # Статистика
    best = max(habit["best_streak"], elapsed)
    lines.append(f"🏆 Рекорд: {format_duration(best)}  •  💥 Срывов: {habit['relapses']}")

    return "\n".join(lines)


def progress_message(habits: list) -> str:
    if not habits:
        return (
            "📊 <b>У тебя пока нет трекеров.</b>\n\n"
            "Нажми «➕ Трекер», чтобы начать отслеживать первую цель. "
            "Каждый день без зависимости — это победа. Начни прямо сейчас! 💪"
        )
    total_saved = 0
    total_days = 0
    for h in habits:
        elapsed = habit_streak_seconds(h)
        total_days += elapsed // 86400
        if h["cost_per_day"] and h["cost_per_day"] > 0:
            total_saved += int(elapsed / 86400 * h["cost_per_day"])

    cards = [habit_card(h) for h in habits]
    header = "📊 <b>ТВОЙ ПРОГРЕСС</b>\n" + DIVIDER
    footer = DIVIDER + f"\n🔥 Всего чистых дней: <b>{total_days}</b>"
    if total_saved > 0:
        footer += f"\n💰 Всего сэкономлено: <b>{total_saved:,} ₽</b>".replace(",", " ")
    body = ("\n\n" + DIVIDER + "\n\n").join(cards)
    return f"{header}\n\n{body}\n\n{footer}"


def levels_message() -> str:
    from content import LEVELS
    from utils import plural_ru

    lines = ["🏆 <b>СИСТЕМА УРОВНЕЙ</b>", DIVIDER]
    for threshold, name in LEVELS:
        if threshold == 0:
            when = "старт"
        else:
            when = f"{threshold} {plural_ru(threshold, ('день', 'дня', 'дней'))}"
        lines.append(f"{name} — <i>{when}</i>")
    lines.append(DIVIDER)
    lines.append("Уровни считаются отдельно для каждого трекера. Держи стрик — расти! 🚀")
    return "\n".join(lines)


def xp_rank(xp: int):
    from content import XP_RANKS
    cur = XP_RANKS[0]
    nxt = None
    for threshold, name in XP_RANKS:
        if xp >= threshold:
            cur = (threshold, name)
        else:
            nxt = (threshold, name)
            break
    return cur, nxt


def profile_message(user: dict, unlocked: set, rank: int, total_users: int) -> str:
    from achievements import ACHIEVEMENTS
    from utils import plural_ru

    xp = user.get("xp", 0)
    cur, nxt = xp_rank(xp)
    lines = ["🎖 <b>ТВОЙ ПРОФИЛЬ</b>", DIVIDER]
    lines.append(f"⭐ Ранг: {cur[1]}")
    lines.append(f"✨ Опыт: <b>{xp} XP</b>")
    if nxt:
        left = nxt[0] - xp
        lines.append(f"📈 До «{nxt[1]}»: {progress_bar(xp, nxt[0])} (ещё {left} XP)")
    lines.append(f"🔥 Пережито тяг: {user.get('cravings_survived', 0)}")
    if user.get("quest_streak", 0):
        qs = user["quest_streak"]
        lines.append(f"🎯 Серия квестов: {qs} {plural_ru(qs, ('день', 'дня', 'дней'))}")
    if total_users > 1 and rank:
        lines.append(f"🏆 Рейтинг по стрику: <b>#{rank}</b> из {total_users}")

    lines.append(DIVIDER)
    lines.append(f"🏅 <b>Достижения ({len(unlocked)}/{len(ACHIEVEMENTS)})</b>")
    for code, emoji, title, desc, _ in ACHIEVEMENTS:
        mark = f"{emoji} <b>{title}</b> — {desc}" if code in unlocked else f"🔒 <i>{title}</i>"
        lines.append(mark)
    return "\n".join(lines)


def diary_message(relapses: list) -> str:
    from content import TRIGGERS_MAP
    from collections import Counter

    lines = ["📔 <b>ДНЕВНИК СРЫВОВ</b>", DIVIDER]
    if not relapses:
        lines.append("Срывов не зафиксировано. Так держать! 💪")
        lines.append("\n<i>Когда отмечаешь срыв, я спрашиваю триггер и настроение — "
                     "потом покажу здесь твои паттерны.</i>")
        return "\n".join(lines)

    total = len(relapses)
    lines.append(f"Всего срывов: <b>{total}</b>")

    triggers = Counter(r["trigger"] for r in relapses if r.get("trigger"))
    if triggers:
        lines.append("\n🎯 <b>Частые триггеры:</b>")
        for trg, cnt in triggers.most_common(5):
            label = TRIGGERS_MAP.get(trg, trg)
            pct = int(cnt / total * 100)
            lines.append(f"  {label}: {cnt} ({pct}%)")

    moods = [r["mood"] for r in relapses if r.get("mood")]
    if moods:
        avg = sum(moods) / len(moods)
        lines.append(f"\n😐 Среднее настроение при срыве: <b>{avg:.1f}/5</b>")

    lines.append(DIVIDER)
    top = triggers.most_common(1)
    if top:
        label = TRIGGERS_MAP.get(top[0][0], top[0][0])
        lines.append(f"💡 Главный враг — <b>{label}</b>. Придумай план на этот случай заранее.")
    return "\n".join(lines)


def reward_for(saved: int):
    from content import REWARDS
    pick = None
    for threshold, text in REWARDS:
        if saved >= threshold:
            pick = (threshold, text)
    return pick


def report_message(data: dict) -> str:
    """Недельный отчёт. data — заранее собранная статистика."""
    lines = ["📅 <b>ОТЧЁТ ЗА НЕДЕЛЮ</b>", DIVIDER]
    lines.append(f"🔥 Активных трекеров: {data['habits']}")
    lines.append(f"⏱ Лучший текущий стрик: <b>{format_duration(data['max_secs'])}</b>")
    if data["saved"] > 0:
        lines.append(f"💰 Всего сэкономлено: <b>{data['saved']:,} ₽</b>".replace(",", " "))
    lines.append(f"💥 Срывов за неделю: {data['relapses_week']}")
    lines.append(f"🏋️ Тренировок пройдено: {data['workouts']}")
    if data.get("quest_streak"):
        lines.append(f"🎯 Серия квестов: {data['quest_streak']}")
    lines.append(f"✨ Опыт: <b>{data['xp']} XP</b>  •  🏅 Ачивок: {data['achievements']}")
    lines.append(DIVIDER)
    if data["relapses_week"] == 0 and data["habits"] > 0:
        lines.append("🏆 Неделя без срывов — ты машина! Так держать! 💪")
    else:
        lines.append("Каждая неделя — шанс стать сильнее. Вперёд! 🚀")
    reward = reward_for(data["saved"])
    if reward:
        lines.append(f"\n🎁 Ты уже заслужил: <b>{reward[1]}</b>")
    return "\n".join(lines)


def metrics_message(weights: list, wellbeing: list) -> str:
    lines = ["📈 <b>ЗАМЕРЫ</b>", DIVIDER]
    if weights:
        first = weights[0]["value"]
        last = weights[-1]["value"]
        diff = last - first
        sign = "▼" if diff < 0 else ("▲" if diff > 0 else "=")
        lines.append(f"⚖️ Вес: <b>{last:g} кг</b> (старт {first:g} кг, {sign} {abs(diff):g} кг)")
    else:
        lines.append("⚖️ Вес: нет записей")
    if wellbeing:
        avg = sum(w["value"] for w in wellbeing) / len(wellbeing)
        lines.append(f"😊 Самочувствие: последнее {wellbeing[-1]['value']:g}/10, "
                     f"среднее {avg:.1f}/10")
    else:
        lines.append("😊 Самочувствие: нет записей")
    lines.append(DIVIDER)
    lines.append("Записывай регулярно — динамику увидишь на графике. 📊")
    return "\n".join(lines)


def workout_message(workouts: list, done_today: bool) -> str:
    from content import EXERCISES_MAP, WORKOUT_SETS

    lines = ["💪 <b>ТРЕНИРОВКА НА СЕГОДНЯ</b>", DIVIDER]
    total_sessions = 0
    for w in workouts:
        name, emoji, _start, _step = EXERCISES_MAP.get(
            w["exercise"], (w["exercise"], "🏋️", 0, 1)
        )
        total_sessions = max(total_sessions, w["sessions"])
        lines.append(f"{emoji} <b>{name}</b>: {WORKOUT_SETS} × {w['target']} раз")
    lines.append(DIVIDER)
    if done_today:
        lines.append("✅ Сегодня уже выполнено — красавчик! Отдыхай. 🔥")
    else:
        lines.append("Выполнил — и цель подрастёт на следующий раз. Прогресс! 📈")
    lines.append(f"🏋️ Тренировок пройдено: {total_sessions}")
    return "\n".join(lines)


def supplements_message(habits: list) -> str:
    from content import SUPPLEMENTS, SUPPLEMENTS_DISCLAIMER

    types = [h["htype"] for h in habits] if habits else []
    keys = [t for t in ("alcohol", "junk", "smoking", "nofap") if t in types]
    if not keys:
        keys = ["general"]
    lines = ["🌿 <b>ВИТАМИНЫ И ДОБАВКИ</b>", DIVIDER]
    for k in keys:
        block = SUPPLEMENTS[k]
        lines.append(f"\n<b>{block['title']}</b>")
        lines.extend(block["items"])
    lines.append("")
    lines.append(SUPPLEMENTS_DISCLAIMER)
    return "\n".join(lines)


def replacements_message(habits: list) -> str:
    from content import REPLACEMENTS, HABITS as H

    lines = ["💊 <b>ЗДОРОВЫЕ ЗАМЕНЫ</b>", DIVIDER]
    if not habits:
        types = ["custom"]
    else:
        types = list(dict.fromkeys(h["htype"] for h in habits))
    for t in types:
        meta = H.get(t, H["custom"])
        lines.append(f"\n{meta['emoji']} <b>{meta['name']}</b>")
        for item in REPLACEMENTS.get(t, REPLACEMENTS["custom"]):
            lines.append(f"  • {item}")
    return "\n".join(lines)
