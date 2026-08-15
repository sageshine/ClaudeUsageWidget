import random
from types import SimpleNamespace
import tkinter as tk

import pytest

from claude_usage_widget.tetris_pieces import COLS, ROWS, SHAPE_COLORS, TOTAL_CELLS, filled_cell_count
from claude_usage_widget.widget import _BOUNCE_FRAMES, _SPAWN_GAP_MS, CharacterWidget
from claude_usage_widget.widget_state import Mood, MOOD_COLORS, WidgetState

THRESHOLDS = {"warning": 60, "danger": 85}


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def _state(percent, mood=Mood.CALM, tooltip="t"):
    return WidgetState(mood=mood, headline_percent=percent, tooltip=tooltip, detail_rows=[])


def _target_cells(percent):
    return round(max(0, min(100, percent)) / 100 * TOTAL_CELLS)


def _run_piece_to_landing(widget):
    """현재 낙하 중인 조각이 착지 + 바운스 애니메이션까지 모두 마칠 때까지
    내부 스텝 메서드를 직접 호출해서 실시간 대기 없이 건너뛴다."""
    piece = widget._current_piece
    widget._release_piece()  # 스폰 직후의 움츠림(anticipation) 해제
    while piece["row_offset"] < piece["landing_row"]:
        widget._animate_drop_step()
    widget._animate_drop_step()  # landing_row 도달 -> 바운스 시작
    for frame in range(len(_BOUNCE_FRAMES) + 1):
        widget._play_landing_bounce(piece, frame)


def test_widget_starts_with_empty_board_and_zero_target(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    assert filled_cell_count(widget._board) == 0
    assert widget._target == 0
    widget.destroy()


def test_apply_state_updates_target_without_immediately_changing_board(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)
    assert widget._target == _target_cells(50)
    assert filled_cell_count(widget._board) == 0  # 아직 아무 조각도 착지하지 않음 -- 낙하는 점진적
    widget.destroy()


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
    widget.destroy()


def test_spawn_piece_merges_into_board_when_below_target(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget._target = 40  # 아직 한참 남음

    widget._spawn_piece()
    assert widget._current_piece is not None
    assert widget._current_piece["decorative"] is False

    _run_piece_to_landing(widget)

    assert widget._current_piece is None
    assert filled_cell_count(widget._board) == 4  # 조각 하나(4칸)가 보드에 합쳐짐
    widget.destroy()


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
    widget.destroy()


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
    assert widget.canvas.itemcget(widget._game_over_bg, "state") == "hidden"
    widget.destroy()


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

    widget.destroy()


def test_game_over_overlay_shown_at_100_percent(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(100), THRESHOLDS)
    for item in widget._game_over_items:
        assert widget.canvas.itemcget(item, "state") == "normal"
    widget.destroy()


def test_game_over_overlay_hidden_below_100_percent(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)
    for item in widget._game_over_items:
        assert widget.canvas.itemcget(item, "state") == "hidden"
    widget.destroy()


def test_jar_outline_follows_mood(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(10, Mood.CALM), THRESHOLDS)
    assert widget.canvas.itemcget(widget._jar, "outline") == MOOD_COLORS[Mood.CALM]

    widget.apply_state(_state(65, Mood.WARNING), THRESHOLDS)
    assert widget.canvas.itemcget(widget._jar, "outline") == MOOD_COLORS[Mood.WARNING]

    widget.apply_state(_state(90, Mood.DANGER), THRESHOLDS)
    assert widget.canvas.itemcget(widget._jar, "outline") == MOOD_COLORS[Mood.DANGER]
    widget.destroy()


def test_jar_thickens_at_warning(root):
    """색조만으론 44px 위젯에서 약하다 -- 위험 신호는 '굵기'로도 나타나야
    색을 못 가려도 프레임이 두꺼워진 건 보인다."""
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(10, Mood.CALM), THRESHOLDS)
    calm_width = float(widget.canvas.itemcget(widget._jar, "width"))

    widget.apply_state(_state(65, Mood.WARNING), THRESHOLDS)
    assert float(widget.canvas.itemcget(widget._jar, "width")) > calm_width
    widget.destroy()


def test_danger_jar_pulses_but_calm_jar_does_not(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(90, Mood.DANGER), THRESHOLDS)
    widths = set()
    for _ in range(12):
        widget._on_pulse()
        widths.add(widget.canvas.itemcget(widget._jar, "width"))
    assert len(widths) > 1  # 굵기가 오간다 = 맥박

    widget.apply_state(_state(10, Mood.CALM), THRESHOLDS)
    calm_widths = set()
    for _ in range(12):
        widget._on_pulse()
        calm_widths.add(widget.canvas.itemcget(widget._jar, "width"))
    assert len(calm_widths) == 1  # 평온할 땐 가만히 있는다
    widget.destroy()


def test_only_one_shine_per_fused_blob(root):
    """붙어서 한 덩어리가 된 젤리에 광택이 여러 개면 전부 눈처럼 보여서,
    정작 떨어지는 조각의 진짜 얼굴이 묻힌다."""
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    grid = [[None] * COLS for _ in range(ROWS)]
    grid[ROWS - 1][0] = "O"
    grid[ROWS - 1][1] = "O"  # 같은 색 두 칸 -> 한 덩어리
    widget._board = tuple(tuple(row) for row in grid)
    widget._redraw()

    shines = [
        widget.canvas.itemcget(widget._blob_shines[ROWS - 1][col], "state") for col in (0, 1)
    ]
    assert shines == ["normal", "hidden"]  # 왼쪽 위 칸에만
    widget.destroy()


def test_falling_piece_takes_no_shine(root):
    """떨어지는 조각 자리는 얼굴이 쓴다 -- 광택까지 겹치면 뭉갠다."""
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget._target = 40
    widget._spawn_piece()

    for row, col in widget._piece_cells(widget._current_piece):
        assert widget.canvas.itemcget(widget._blob_shines[row][col], "state") == "hidden"
    widget.destroy()


def test_auth_error_mood_is_not_rendered_as_a_calm_jar(root):
    """AUTH_ERROR/SETUP_NEEDED는 headline_percent가 0이라, 퍼센트만 보고 색을
    정하던 예전 코드에선 '차분한 파란 병'으로 보였다."""
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(0, Mood.SETUP_NEEDED), THRESHOLDS)

    assert widget.canvas.itemcget(widget._jar, "outline") == MOOD_COLORS[Mood.SETUP_NEEDED]
    assert widget.canvas.itemcget(widget._jar, "outline") != MOOD_COLORS[Mood.CALM]
    widget.destroy()


def test_danger_mood_drops_pieces_more_often_than_calm(root):
    """작은 위젯에선 색보다 리듬이 먼저 읽힌다 -- 위험할수록 자주 움직여야 한다."""
    assert _SPAWN_GAP_MS[Mood.DANGER] < _SPAWN_GAP_MS[Mood.WARNING] < _SPAWN_GAP_MS[Mood.CALM]


def test_same_colored_neighbours_fuse_into_one_blob(root):
    """같은 색끼리 서로 부풀어 겹쳐야 젤리 한 덩어리로 보인다. 겹치지 않으면
    칸마다 따로 노는 사각형으로 읽힌다."""
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    grid = [[None] * COLS for _ in range(ROWS)]
    grid[ROWS - 1][0] = "O"
    grid[ROWS - 1][1] = "O"  # 오른쪽 이웃, 같은 색
    grid[ROWS - 1][3] = "I"  # 떨어진 곳의 다른 색 -- 붙을 이웃이 없다
    widget._board = tuple(tuple(row) for row in grid)

    left = widget._blob_rect(ROWS - 1, 0)
    right = widget._blob_rect(ROWS - 1, 1)
    lone = widget._blob_rect(ROWS - 1, 3)

    assert left[2] > right[0]  # 서로 파고들어 겹친다
    assert lone[2] - lone[0] < left[2] - left[0]  # 이웃 없는 칸은 부풀지 않는다
    widget.destroy()


def test_different_colored_neighbours_do_not_fuse(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    grid = [[None] * COLS for _ in range(ROWS)]
    grid[ROWS - 1][0] = "O"
    grid[ROWS - 1][1] = "I"  # 붙어 있지만 다른 색
    widget._board = tuple(tuple(row) for row in grid)
    assert SHAPE_COLORS["O"] != SHAPE_COLORS["I"]

    left = widget._blob_rect(ROWS - 1, 0)
    right = widget._blob_rect(ROWS - 1, 1)

    assert left[2] < right[0]  # 사이에 어두운 외곽선이 지나갈 틈이 남는다
    widget.destroy()


def test_cell_color_out_of_bounds_returns_none(root):
    """이웃을 볼 때 음수 인덱스가 반대편 칸으로 감기면 엉뚱한 칸끼리 붙는다."""
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    grid = [[None] * COLS for _ in range(ROWS)]
    grid[ROWS - 1][COLS - 1] = "O"
    widget._board = tuple(tuple(row) for row in grid)

    assert widget._cell_color(-1, 0) is None
    assert widget._cell_color(0, -1) is None
    assert widget._cell_color(ROWS, 0) is None
    assert widget._cell_color(0, COLS) is None
    widget.destroy()


def test_pieces_accelerate_as_they_fall(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    assert widget._fall_delay(0) > widget._fall_delay(5) >= widget._fall_delay(9)
    widget.destroy()


def test_falling_piece_has_a_face_and_the_stack_does_not(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget._target = 40
    widget._spawn_piece()

    assert widget.canvas.itemcget(widget._eye_l, "state") == "normal"

    _run_piece_to_landing(widget)  # 보드에 합쳐지면 조각은 사라진다

    assert widget._current_piece is None
    assert widget.canvas.itemcget(widget._eye_l, "state") == "hidden"
    widget.destroy()


def test_drag_reports_new_position_via_on_move(root):
    moves = []
    widget = CharacterWidget(root, (10, 10), on_move=moves.append, on_right_click=lambda: None)

    widget._start_drag(SimpleNamespace(x=5, y=5))
    widget._do_drag(SimpleNamespace(x=15, y=20))
    widget._end_drag(SimpleNamespace(x=15, y=20))

    assert len(moves) == 1
    assert isinstance(moves[0][0], int)
    assert isinstance(moves[0][1], int)
    widget.destroy()


def test_right_click_invokes_callback(root):
    clicks = []
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: clicks.append(1))

    widget.top.update()
    widget.canvas.event_generate("<Button-3>")
    root.update()

    assert clicks == [1]
    widget.destroy()


def test_destroy_cancels_pending_callbacks(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    assert widget._drop_after_id is not None
    assert widget._pulse_after_id is not None

    widget.destroy()

    assert widget._drop_after_id is None
    assert widget._pulse_after_id is None
