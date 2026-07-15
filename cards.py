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

    # Деньги
    if habit["cost_per_day"] and habit["cost_per_day"] > 0:
        saved = int(elapsed / 86400 * habit["cost_per_day"])
        lines.append(f"💰 Сэкономлено: <b>{saved:,} ₽</b>".replace(",", " "))

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
