"""Вспомогательные функции: время, склонения, уровни, прогресс-бары."""
from datetime import datetime, timezone

from content import LEVELS, HABITS


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def from_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def plural_ru(n: int, forms: tuple) -> str:
    """forms = (день, дня, дней)."""
    n = abs(n) % 100
    n1 = n % 10
    if 10 < n < 20:
        return forms[2]
    if 1 < n1 < 5:
        return forms[1]
    if n1 == 1:
        return forms[0]
    return forms[2]


def format_duration(seconds: float) -> str:
    """Человекочитаемая длительность: «3 дня 5 часов»."""
    seconds = int(seconds)
    if seconds < 60:
        return "меньше минуты"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    parts = []
    if days:
        parts.append(f"{days} {plural_ru(days, ('день', 'дня', 'дней'))}")
    if hours:
        parts.append(f"{hours} {plural_ru(hours, ('час', 'часа', 'часов'))}")
    if minutes and not days:
        parts.append(f"{minutes} {plural_ru(minutes, ('минута', 'минуты', 'минут'))}")
    return " ".join(parts) if parts else "меньше минуты"


def level_info(days: int):
    """Возвращает (текущий_уровень, следующий_уровень|None, порог_следующего|None)."""
    current = LEVELS[0]
    nxt = None
    for threshold, name in LEVELS:
        if days >= threshold:
            current = (threshold, name)
        else:
            nxt = (threshold, name)
            break
    return current, nxt


def progress_bar(current: float, target: float, length: int = 10) -> str:
    if target <= 0:
        ratio = 1.0
    else:
        ratio = max(0.0, min(current / target, 1.0))
    filled = int(round(ratio * length))
    return "█" * filled + "░" * (length - filled)


def milestones_status(elapsed: float, htype: str):
    """Возвращает (список_достигнутых, следующая|None) по вехам восстановления."""
    milestones = HABITS[htype]["milestones"]
    reached = [m for m in milestones if elapsed >= m[0]]
    upcoming = next((m for m in milestones if elapsed < m[0]), None)
    return reached, upcoming
