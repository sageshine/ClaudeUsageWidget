from types import SimpleNamespace
import tkinter as tk

import pytest

from claude_usage_widget.tetris_pieces import TOTAL_CELLS, filled_cell_count
from claude_usage_widget.widget import CharacterWidget
from claude_usage_widget.widget_state import Mood, WidgetState

THRESHOLDS = {"warning": 60, "danger": 85}


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def _state(percent, tooltip="t"):
    return WidgetState(mood=Mood.CALM, headline_percent=percent, tooltip=tooltip, detail_rows=[])


def _target_cells(percent):
    return round(max(0, min(100, percent)) / 100 * TOTAL_CELLS)


def test_first_apply_state_fills_board_immediately_without_animation(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)

    target = _target_cells(50)
    filled = filled_cell_count(widget._board)
    assert target <= filled < target + 4
    assert widget._animation_after_id is None
    assert widget._current_piece is None
    widget.top.destroy()


def test_increasing_percent_spawns_a_falling_piece_without_immediately_filling_board(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(10), THRESHOLDS)
    filled_after_first = filled_cell_count(widget._board)

    widget.apply_state(_state(80), THRESHOLDS)

    assert widget._current_piece is not None
    assert widget._animation_after_id is not None
    assert filled_cell_count(widget._board) == filled_after_first
    widget.top.destroy()


def test_decreasing_percent_clears_board_immediately_without_animation(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(80), THRESHOLDS)
    assert filled_cell_count(widget._board) > 0

    widget.apply_state(_state(10), THRESHOLDS)

    target = _target_cells(10)
    filled = filled_cell_count(widget._board)
    assert target <= filled < target + 4
    assert widget._animation_after_id is None
    assert widget._current_piece is None
    widget.top.destroy()


def test_in_flight_piece_is_snapped_into_board_when_new_state_arrives(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(10), THRESHOLDS)
    widget.apply_state(_state(80), THRESHOLDS)
    assert widget._current_piece is not None
    filled_before = filled_cell_count(widget._board)

    widget.apply_state(_state(90), THRESHOLDS)

    # the piece that was mid-flight must have been merged into the board (4 more cells),
    # not discarded -- filled count only ever grows across these calls.
    assert filled_cell_count(widget._board) >= filled_before + 4
    widget.top.destroy()


def test_game_over_overlay_shown_at_100_percent(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(100), THRESHOLDS)
    assert widget.canvas.itemcget(widget._game_over_text, "state") == "normal"
    widget.top.destroy()


def test_game_over_overlay_hidden_below_100_percent(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)
    assert widget.canvas.itemcget(widget._game_over_text, "state") == "hidden"
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

    widget.top.update()
    widget.canvas.event_generate("<Button-3>")
    root.update()

    assert clicks == [1]
    widget.top.destroy()
