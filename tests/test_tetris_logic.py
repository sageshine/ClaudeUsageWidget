from claude_usage_widget.tetris_logic import filled_row_count, is_game_over, row_color
from claude_usage_widget.widget_state import MOOD_COLORS, Mood

THRESHOLDS = {"warning": 60, "danger": 85}


def test_filled_row_count_rounds_up_to_nearest_row():
    assert filled_row_count(0) == 0
    assert filled_row_count(1) == 1
    assert filled_row_count(9) == 1
    assert filled_row_count(10) == 1
    assert filled_row_count(11) == 2
    assert filled_row_count(65) == 7
    assert filled_row_count(100) == 10


def test_filled_row_count_clamps_above_100():
    assert filled_row_count(108) == 10


def test_filled_row_count_clamps_below_0():
    assert filled_row_count(-5) == 0


def test_row_color_below_warning_threshold_is_calm():
    assert row_color(1, THRESHOLDS) == MOOD_COLORS[Mood.CALM]
    assert row_color(5, THRESHOLDS) == MOOD_COLORS[Mood.CALM]


def test_row_color_between_warning_and_danger_is_warning():
    assert row_color(6, THRESHOLDS) == MOOD_COLORS[Mood.WARNING]
    assert row_color(8, THRESHOLDS) == MOOD_COLORS[Mood.WARNING]


def test_row_color_at_or_above_danger_is_danger():
    assert row_color(9, THRESHOLDS) == MOOD_COLORS[Mood.DANGER]
    assert row_color(10, THRESHOLDS) == MOOD_COLORS[Mood.DANGER]


def test_is_game_over_true_at_100_percent_and_above():
    assert is_game_over(100) is True
    assert is_game_over(108) is True


def test_is_game_over_false_below_100_percent():
    assert is_game_over(99) is False
    assert is_game_over(0) is False
