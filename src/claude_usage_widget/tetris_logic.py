import math

from .widget_state import MOOD_COLORS, Mood

TOTAL_ROWS = 10


def filled_row_count(headline_percent: int) -> int:
    clamped = max(0, min(100, headline_percent))
    return math.ceil(clamped / 10)


def row_color(row_index: int, thresholds: dict) -> str:
    row_upper_percent = row_index * 10
    if row_upper_percent >= thresholds["danger"]:
        return MOOD_COLORS[Mood.DANGER]
    if row_upper_percent >= thresholds["warning"]:
        return MOOD_COLORS[Mood.WARNING]
    return MOOD_COLORS[Mood.CALM]


def is_game_over(headline_percent: int) -> bool:
    return headline_percent >= 100
