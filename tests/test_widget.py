from types import SimpleNamespace
import tkinter as tk

import pytest

from claude_usage_widget.widget import CharacterWidget
from claude_usage_widget.widget_state import Mood, MOOD_COLORS, MOOD_FACES, WidgetState


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_apply_state_updates_color_and_face(root):
    moves = []
    clicks = []
    widget = CharacterWidget(root, (10, 10), on_move=moves.append, on_right_click=lambda: clicks.append(1))

    state = WidgetState(mood=Mood.DANGER, headline_percent=90, tooltip="t", detail_rows=[])
    widget.apply_state(state)

    assert widget.canvas.itemcget(widget._circle, "fill") == MOOD_COLORS[Mood.DANGER]
    assert widget.canvas.itemcget(widget._face, "text") == MOOD_FACES[Mood.DANGER]
    widget.top.destroy()


def test_drag_reports_new_position_via_on_move(root):
    moves = []
    widget = CharacterWidget(root, (10, 10), on_move=moves.append, on_right_click=lambda: None)

    widget._start_drag(SimpleNamespace(x=5, y=5))
    widget._do_drag(SimpleNamespace(x=15, y=20))
    widget._end_drag(SimpleNamespace(x=15, y=20))

    assert len(moves) == 1
    assert isinstance(moves[0][0], int)
    assert isinstance(moves[0][1], int)
    widget.top.destroy()


def test_right_click_invokes_callback(root):
    clicks = []
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: clicks.append(1))

    # Ensure Toplevel is ready for event processing before generating synthetic events
    widget.top.update()
    widget.canvas.event_generate("<Button-3>")
    root.update()

    assert clicks == [1]
    widget.top.destroy()
