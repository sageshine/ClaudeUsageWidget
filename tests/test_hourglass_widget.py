from types import SimpleNamespace
import tkinter as tk

import pytest

from claude_usage_widget.hourglass_widget import HourglassWidget
from claude_usage_widget.widget_state import Mood, MOOD_COLORS, WidgetState

THRESHOLDS = {"warning": 60, "danger": 85}


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def _state(percent, tooltip="t"):
    return WidgetState(mood=Mood.CALM, headline_percent=percent, tooltip=tooltip, detail_rows=[])


def test_widget_starts_empty(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    assert widget._displayed_fraction == 0.0
    assert widget._target_fraction == 0.0
    widget.top.destroy()


def test_apply_state_sets_target_without_instantly_moving_displayed_fraction(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)
    assert widget._target_fraction == 0.5
    assert widget._displayed_fraction == 0.0  # 아직 한 번도 tick이 안 돌아 그대로
    widget.top.destroy()


def test_tick_drains_displayed_fraction_toward_target_gradually(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)

    widget._on_tick()
    first = widget._displayed_fraction
    assert 0.0 < first <= 0.5

    for _ in range(200):  # 넉넉히 반복하면 결국 target에 도달해야 함
        widget._on_tick()
    assert widget._displayed_fraction == 0.5
    widget.top.destroy()


def test_reset_lower_target_triggers_flip_and_resets_displayed_fraction(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(80), THRESHOLDS)
    for _ in range(200):
        widget._on_tick()
    assert widget._displayed_fraction == 0.8

    widget.apply_state(_state(5), THRESHOLDS)

    assert widget._flipping is True
    widget.top.destroy()


def test_color_reflects_thresholds(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(10), THRESHOLDS)
    assert widget._color == MOOD_COLORS[Mood.CALM]

    widget.apply_state(_state(65), THRESHOLDS)
    assert widget._color == MOOD_COLORS[Mood.WARNING]

    widget.apply_state(_state(90), THRESHOLDS)
    assert widget._color == MOOD_COLORS[Mood.DANGER]
    widget.top.destroy()


def test_game_over_overlay_shown_at_100_percent(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(100), THRESHOLDS)
    assert widget.canvas.itemcget(widget._game_over_text, "state") == "normal"
    widget.top.destroy()


def test_game_over_overlay_hidden_below_100_percent(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)
    assert widget.canvas.itemcget(widget._game_over_text, "state") == "hidden"
    widget.top.destroy()


def test_drag_reports_new_position_via_on_move(root):
    moves = []
    widget = HourglassWidget(root, (10, 10), on_move=moves.append, on_right_click=lambda: None)

    widget._start_drag(SimpleNamespace(x=5, y=5))
    widget._do_drag(SimpleNamespace(x=15, y=20))
    widget._end_drag(SimpleNamespace(x=15, y=20))

    assert len(moves) == 1
    assert isinstance(moves[0][0], int)
    assert isinstance(moves[0][1], int)
    widget.top.destroy()


def test_right_click_invokes_callback(root):
    clicks = []
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: clicks.append(1))

    widget.top.update()
    widget.canvas.event_generate("<Button-3>")
    root.update()

    assert clicks == [1]
    widget.top.destroy()
