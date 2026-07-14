import random
from types import SimpleNamespace
import tkinter as tk

import pytest

from claude_usage_widget.tetris_pieces import COLS, ROWS, TOTAL_CELLS, filled_cell_count
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


def test_in_flight_piece_is_discarded_cleanly_when_percent_decreases_mid_fall(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(10), THRESHOLDS)
    widget.apply_state(_state(80), THRESHOLDS)
    assert widget._current_piece is not None
    assert widget._animation_after_id is not None

    # A decrease arrives while a piece is still mid-flight (10 -> 80 -> 5). The in-flight
    # piece gets snapped into the board first (per the interrupt-snap logic), but the
    # decrease branch then wipes the board and rebuilds instantly at the new lower
    # target -- so no leaked cells and no leftover animation state should remain.
    widget.apply_state(_state(5), THRESHOLDS)

    target = _target_cells(5)
    filled = filled_cell_count(widget._board)
    assert widget._current_piece is None
    assert widget._animation_after_id is None
    assert target <= filled < target + 4
    widget.top.destroy()


def test_choose_placement_failure_does_not_crash_or_spawn_piece(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    # Top the board out: fill the very top row across every column. find_landing_row
    # computes offset_limit = first_filled - 1 - dr for each occupied column, and every
    # shape has a cell with dr == 0, so with first_filled == 0 that limit is -1 for every
    # column and every shape -- choose_placement can never find a landing spot anywhere,
    # mirroring the "board topped out" grid built in test_tetris_pieces.py.
    grid = [[None] * COLS for _ in range(ROWS)]
    for col in range(COLS):
        grid[0][col] = "I"
    widget._board = tuple(tuple(row) for row in grid)
    widget._initialized = True

    # target(25) exceeds the current filled count (5), so apply_state takes the
    # "increase" path and attempts to spawn a piece via choose_placement, which must
    # fail silently instead of raising.
    widget.apply_state(_state(50), THRESHOLDS)

    assert widget._current_piece is None
    assert widget._animation_after_id is None
    # GAME OVER visibility must be driven only by headline_percent, never by the board
    # being unable to reach its target.
    assert widget.canvas.itemcget(widget._game_over_text, "state") == "hidden"
    widget.top.destroy()


def test_fill_instantly_reaches_target_when_only_narrow_shapes_fit(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    # Block column 2 top-to-bottom so I (width 4) and every width-3 shape
    # (T, S, Z, J, L) can never land anywhere on the board -- only O (width 2) can
    # still be placed, in the untouched column pairs (0,1) and (3,4). This mirrors
    # the regression the reviewer found: picking a single random shape and giving up
    # when it doesn't fit stalls the fill well before the target; trying multiple
    # shapes must not.
    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(ROWS):
        grid[row][2] = "I"
    blocked_board = tuple(tuple(row) for row in grid)

    # Target 35 cells (70%) is reachable using O alone: up to 40 non-blocked cells
    # remain (columns 0, 1, 3, 4 across all 10 rows).
    for seed in range(10):
        widget._board = blocked_board
        widget._rng = random.Random(seed)
        widget._fill_instantly(35)
        assert filled_cell_count(widget._board) >= 35

    widget.top.destroy()


def test_spawn_next_piece_succeeds_when_only_narrow_shapes_fit(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget._initialized = True

    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(ROWS):
        grid[row][2] = "I"
    blocked_board = tuple(tuple(row) for row in grid)

    for seed in range(10):
        widget._board = blocked_board
        widget._current_piece = None
        if widget._animation_after_id is not None:
            widget.canvas.after_cancel(widget._animation_after_id)
            widget._animation_after_id = None
        widget._rng = random.Random(seed)

        # target(30, i.e. 60%) exceeds the current filled count (10), so apply_state
        # takes the "increase" path and spawns a piece via choose_shape_and_placement.
        # Under the old "one shape, give up" logic this would fail on most seeds even
        # though O always fits; it must now succeed every time.
        widget.apply_state(_state(60), THRESHOLDS)

        assert widget._current_piece is not None
        assert widget._current_piece["shape_id"] == "O"

    if widget._animation_after_id is not None:
        widget.canvas.after_cancel(widget._animation_after_id)
        widget._animation_after_id = None
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
