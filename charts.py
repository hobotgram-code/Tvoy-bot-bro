"""Генерация графиков прогресса (PNG) через matplotlib."""
import io
from datetime import timedelta

import matplotlib
matplotlib.use("Agg")  # без дисплея
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

from utils import now_utc, from_iso, plural_ru


def share_card_png(name: str, days: int, level_text: str, saved: int, accent: str) -> bytes:
    """Красивая карточка-достижение для шеринга друзьям."""
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    bg = "#12141c"
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    # Рамка со скруглением в цвет привычки
    ax.add_patch(FancyBboxPatch(
        (0.07, 0.07), 0.86, 0.86,
        boxstyle="round,pad=0.0,rounding_size=0.04",
        fill=False, edgecolor=accent, linewidth=5,
    ))

    ax.text(0.5, 0.865, "ТВОЙ БОТ-БРО", ha="center", va="center",
            color="#7c8296", fontsize=20, weight="bold")
    ax.text(0.5, 0.785, name.upper(), ha="center", va="center",
            color=accent, fontsize=30, weight="bold")

    num_size = 155 if days < 100 else 115
    ax.text(0.5, 0.55, str(days), ha="center", va="center",
            color="#ffffff", fontsize=num_size, weight="bold")

    d_word = plural_ru(days, ("день", "дня", "дней"))
    ax.text(0.5, 0.375, f"{d_word} держусь", ha="center", va="center",
            color="#ffffff", fontsize=32)

    if level_text:
        ax.text(0.5, 0.29, level_text, ha="center", va="center",
                color="#c4cad8", fontsize=22)
    if saved and saved > 0:
        s = f"сэкономлено {saved:,} ₽".replace(",", " ")
        ax.text(0.5, 0.21, s, ha="center", va="center",
                color="#51cf66", fontsize=22, weight="bold")

    ax.text(0.5, 0.12, "и не сдаюсь 💪".replace(" 💪", ""), ha="center", va="center",
            color="#7c8296", fontsize=18, style="italic")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, facecolor=bg, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

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


def weight_chart_png(user: dict, metrics: list) -> bytes:
    """Линейный график динамики веса."""
    tz = user.get("tz_offset", 3)
    dates = [(from_iso(m["ts"]) + timedelta(hours=tz)).date() for m in metrics]
    values = [m["value"] for m in metrics]
    # Если все записи в один день — раскладываем по индексу, чтобы линия читалась
    same_day = len(set(dates)) <= 1
    xs = list(range(len(values))) if same_day else dates

    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.plot(xs, values, marker="o", color="#2f8fed", linewidth=2)
    ax.fill_between(xs, values, min(values), alpha=0.12, color="#2f8fed")
    for x, y in zip(xs, values):
        ax.annotate(f"{y:g}", (x, y), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=8)
    ax.set_title("Динамика веса, кг", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.25)
    if same_day:
        ax.set_xticks(xs)
        ax.set_xticklabels([f"#{i+1}" for i in xs], fontsize=8)
    else:
        fig.autofmt_xdate(rotation=30)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
