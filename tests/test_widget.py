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


def _run_piece_to_landing(widget):
    """현재 낙하 중인 조각이 착지할 때까지 _animate_drop_step을 직접 호출해서
    (칸당 150ms) 애니메이션을 실시간으로 기다리지 않고 건너뛴다. 착지 순간의
    분기(합치기 또는 decorative 잔류)까지 정확히 한 번만 트리거한다."""
    piece = widget._current_piece
    while piece["row_offset"] < piece["landing_row"]:
        widget._animate_drop_step()
    widget._animate_drop_step()


def test_widget_starts_with_empty_board_and_zero_target(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    assert filled_cell_count(widget._board) == 0
    assert widget._target == 0
    widget.top.destroy()


def test_apply_state_updates_target_without_immediately_changing_board(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)
    assert widget._target == _target_cells(50)
    assert filled_cell_count(widget._board) == 0  # 아직 아무 조각도 착지하지 않음 -- 낙하는 점진적
    widget.top.destroy()


def test_apply_state_with_lower_target_clears_board_immediately(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget._target = 40
    # 두 줄(10칸)을 직접 채워서, 10%(target=5)로 낮아졌을 때 확실히 "감소" 분기를 타도록 함
    grid = [[None] * COLS for _ in range(ROWS)]
    grid[ROWS - 1] = ["O", "O", "O", "O", "O"]
    grid[ROWS - 2] = ["O", "O", "O", "O", "O"]
    widget._board = tuple(tuple(row) for row in grid)
    assert filled_cell_count(widget._board) == 10

    widget.apply_state(_state(10), THRESHOLDS)

    assert filled_cell_count(widget._board) == 0
    assert widget._target == _target_cells(10)
    assert widget._current_piece is None
    widget.top.destroy()


def test_spawn_piece_merges_into_board_when_below_target(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget._target = 40  # 아직 한참 남음

    widget._spawn_piece()
    assert widget._current_piece is not None
    assert widget._current_piece["decorative"] is False

    _run_piece_to_landing(widget)

    assert widget._current_piece is None
    assert filled_cell_count(widget._board) == 4  # 조각 하나(4칸)가 보드에 합쳐짐
    widget.top.destroy()


def test_spawn_piece_is_decorative_and_does_not_merge_when_target_already_reached(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget._target = 0  # 빈 보드 기준으로 이미 목표 달성 상태

    widget._spawn_piece()
    assert widget._current_piece is not None
    assert widget._current_piece["decorative"] is True

    _run_piece_to_landing(widget)

    # decorative 조각은 착지해도 곧바로 사라지지 않고 잠깐 머문다(잔류 타이머 대기 중)
    assert widget._current_piece is not None
    assert filled_cell_count(widget._board) == 0  # 보드에는 절대 합쳐지지 않음

    widget._dissolve_decorative_piece()
    assert widget._current_piece is None
    assert filled_cell_count(widget._board) == 0
    widget.top.destroy()


def test_spawn_piece_does_not_crash_when_board_fully_blocked(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    # Top the board out: fill the very top row across every column, so no shape can
    # ever land anywhere (mirrors the "board topped out" grid in test_tetris_pieces.py).
    grid = [[None] * COLS for _ in range(ROWS)]
    for col in range(COLS):
        grid[0][col] = "I"
    widget._board = tuple(tuple(row) for row in grid)
    widget._target = 40

    widget._spawn_piece()

    assert widget._current_piece is None
    assert widget._drop_after_id is not None  # 다음 낙하 시도가 예약되어야 함(포기하지 않음)
    # GAME OVER 표시는 오직 headline_percent로만 결정되어야 하고, 보드가 막힌 것과는 무관해야 함
    widget.apply_state(_state(50), THRESHOLDS)
    assert widget.canvas.itemcget(widget._game_over_text, "state") == "hidden"
    widget.top.destroy()


def test_spawn_piece_finds_narrow_shape_when_wide_shapes_blocked(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    # Block column 2 top-to-bottom so I (width 4) and every width-3 shape
    # (T, S, Z, J, L) can never land anywhere on the board -- only O (width 2) can
    # still be placed, in the untouched column pairs (0,1) and (3,4). This is the
    # regression the multi-shape choose_shape_and_placement fallback protects against.
    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(ROWS):
        grid[row][2] = "I"
    blocked_board = tuple(tuple(row) for row in grid)

    for seed in range(10):
        widget._board = blocked_board
        widget._current_piece = None
        widget._target = 40
        widget._rng = random.Random(seed)

        widget._spawn_piece()

        assert widget._current_piece is not None
        assert widget._current_piece["shape_id"] == "O"

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
