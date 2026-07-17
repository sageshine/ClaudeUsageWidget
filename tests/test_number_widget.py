from types import SimpleNamespace
import tkinter as tk

import pytest

from claude_usage_widget.number_widget import NumberWidget
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


def test_widget_starts_at_zero_percent(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    assert widget.canvas.itemcget(widget._text, "text") == "0%"
    widget.top.destroy()


def test_apply_state_shows_headline_percent(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(51), THRESHOLDS)
    assert widget.canvas.itemcget(widget._text, "text") == "51%"
    widget.top.destroy()


def test_apply_state_clamps_percent_to_0_100_range(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(140), THRESHOLDS)
    assert widget.canvas.itemcget(widget._text, "text") == "100%"
    widget.top.destroy()


def test_color_reflects_thresholds(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(10), THRESHOLDS)
    assert widget.canvas.itemcget(widget._text, "fill") == MOOD_COLORS[Mood.CALM]

    widget.apply_state(_state(65), THRESHOLDS)
    assert widget.canvas.itemcget(widget._text, "fill") == MOOD_COLORS[Mood.WARNING]

    widget.apply_state(_state(90), THRESHOLDS)
    assert widget.canvas.itemcget(widget._text, "fill") == MOOD_COLORS[Mood.DANGER]
    widget.top.destroy()


def test_drag_reports_new_position_via_on_move(root):
    moves = []
    widget = NumberWidget(root, (10, 10), on_move=moves.append, on_right_click=lambda: None)

    widget._start_drag(SimpleNamespace(x=5, y=5))
    widget._do_drag(SimpleNamespace(x=15, y=20))
    widget._end_drag(SimpleNamespace(x=15, y=20))

    assert len(moves) == 1
    assert isinstance(moves[0][0], int)
    assert isinstance(moves[0][1], int)
    widget.top.destroy()


def test_right_click_invokes_callback(root):
    clicks = []
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: clicks.append(1))

    widget.top.update()
    widget.canvas.event_generate("<Button-3>")
    root.update()

    assert clicks == [1]
    widget.top.destroy()
