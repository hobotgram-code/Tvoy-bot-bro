"""Генерация графиков прогресса (PNG) через matplotlib."""
import io
from datetime import timedelta

import matplotlib
matplotlib.use("Agg")  # без дисплея
import matplotlib.pyplot as plt
import numpy as np

from utils import now_utc, from_iso

WEEKS = 12  # сколько недель показываем в календаре


def _local_date(user: dict):
    return (now_utc() + timedelta(hours=user.get("tz_offset", 3))).date()


def heatmap_png(user: dict, habits: list, relapse_ts: list) -> bytes:
    """GitHub-подобный календарь чистых дней за последние ~12 недель."""
    today = _local_date(user)
    tz = user.get("tz_offset", 3)

    # Даты срывов (в локальном времени пользователя)
    relapse_days = set()
    for ts in relapse_ts:
        d = (from_iso(ts) + timedelta(hours=tz)).date()
        relapse_days.add(d)

    # С какого дня считаем «отслеживание начато»
    if habits:
        start_track = min(
            (from_iso(h["created_at"] or h["started_at"]) + timedelta(hours=tz)).date()
            for h in habits
        )
    else:
        start_track = today

    # Сетка: колонки — недели, строки — дни недели (Пн..Вс)
    end = today
    # Начало сетки — понедельник самой ранней недели
    start_grid = end - timedelta(days=WEEKS * 7 - 1)
    start_grid -= timedelta(days=start_grid.weekday())
    total_days = (end - start_grid).days + 1
    n_weeks = (total_days + 6) // 7

    # RGB массив: строки=7, колонки=n_weeks
    grid = np.ones((7, n_weeks, 3))  # белый фон
    C_CLEAN = np.array([0.20, 0.72, 0.35])   # зелёный
    C_RELAPSE = np.array([0.90, 0.30, 0.24])  # красный
    C_NONE = np.array([0.90, 0.90, 0.90])     # серый (вне отслеживания)

    d = start_grid
    while d <= end:
        col = (d - start_grid).days // 7
        row = d.weekday()
        if d < start_track:
            grid[row, col] = C_NONE
        elif d in relapse_days:
            grid[row, col] = C_RELAPSE
        else:
            grid[row, col] = C_CLEAN
        d += timedelta(days=1)

    fig, ax = plt.subplots(figsize=(max(6, n_weeks * 0.5), 3.2))
    ax.imshow(grid, aspect="equal")

    # Границы клеток
    ax.set_xticks(np.arange(-0.5, n_weeks, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 7, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)

    ax.set_yticks(range(7))
    ax.set_yticklabels(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"], fontsize=8)
    ax.set_xticks([])

    clean = sum(
        1 for x in range((end - start_track).days + 1)
        if (start_track + timedelta(days=x)) not in relapse_days
    ) if end >= start_track else 0
    ax.set_title(
        f"Календарь чистых дней · {clean} чистых · {len(relapse_days)} срывов",
        fontsize=11, fontweight="bold",
    )
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
