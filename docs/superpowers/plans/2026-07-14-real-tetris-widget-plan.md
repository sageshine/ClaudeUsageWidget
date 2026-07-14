# 진짜 테트로미노 위젯 UI Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 현재 위젯(단일 열에 사각 블록만 쌓이는 v1)을 진짜 테트로미노 7종(I·O·T·S·Z·J·L)이 5x10 보드 위에서 떨어져 쌓이는 형태로 다시 만든다.

**Architecture:** 보드/조각 시뮬레이션(빈 보드, 착지 위치 계산, 조각 배치, 배치 후보 선택)은 `tetris_pieces.py`에 순수 함수로 분리해 Tkinter 없이 테스트한다. `tetris_logic.py`는 더 이상 쓰이지 않는 v1의 `filled_row_count`/`row_color`를 제거하고 `is_game_over`만 남긴다. `widget.py`는 이 두 모듈을 써서 캔버스에 5x10 셀 그리드를 그리고 조각 낙하 애니메이션을 담당한다. `CharacterWidget`의 생성자/`.apply_state(state, thresholds)` 시그니처와 `.WIDTH`/`.HEIGHT` 클래스 변수는 그대로 유지되므로(값만 바뀜), **`app.py`는 이번 작업에서 전혀 수정하지 않는다.**

**Tech Stack:** 기존과 동일 — Python 3.11+, stdlib `tkinter`, `random`, `pytest`. 새 의존성 없음.

## Global Constraints

- 보드는 5칸(가로) x 10칸(세로), 칸 크기 18px → 위젯 90x180px.
- 조각 모양은 고정 방향만 사용한다 (회전 없음).
- 조각 색상은 종류별 클래식 테트리스 색: I=`#22D3EE`, O=`#FACC15`, T=`#A855F7`, S=`#22C55E`, Z=`#EF4444`, J=`#3B82F6`, L=`#F97316`.
- 새 조각이 떨어질 열은 **가장 깊이(낮게) 착지하는 열들 중에서만** 무작위로 고른다 — 완전 무작위 선택 금지.
- `headline_percent`(0~100 클램프) → `target_filled_cells = round(percent / 100 * 50)`. 목표가 늘면 조각을 스폰해 채우고, 줄면(리셋) 애니메이션 없이 즉시 비운다. 첫 `apply_state` 호출도 애니메이션 없이 즉시 채운다.
- **GAME OVER는 오직 `headline_percent >= 100`일 때만** 뜬다 — 조각 배치 실패(보드 topping-out)로 인한 GAME OVER는 없다.
- 조각 낙하 중 새 `apply_state`가 호출되면, 낙하 중이던 조각을 즉시 착지 위치로 스냅해 보드에 반영한 뒤 새 목표를 향해 이어간다.
- `CharacterWidget(root, initial_pos, on_move, on_right_click)` 생성자 시그니처, `.apply_state(state: WidgetState, thresholds: dict) -> None`, `.top`, 드래그/우클릭/호버 툴팁 동작은 그대로 유지한다.
- `app.py`, `widget_state.py`는 이번 작업에서 수정하지 않는다.

---

## Task 1: 테트로미노 보드/조각 시뮬레이션 (`tetris_pieces.py`) + `tetris_logic.py` 정리

**Files:**
- Create: `src/claude_usage_widget/tetris_pieces.py`
- Test: `tests/test_tetris_pieces.py`
- Modify: `src/claude_usage_widget/tetris_logic.py` (v1 전용 함수 제거)
- Modify: `tests/test_tetris_logic.py` (남은 `is_game_over` 테스트만 유지)

**Interfaces:**
- Produces: `ROWS=10`, `COLS=5`, `TOTAL_CELLS=50`, `SHAPES: dict[str, tuple[tuple[int,int],...]]`, `SHAPE_COLORS: dict[str,str]`, `empty_board() -> Board`(`Board = tuple[tuple[str|None,...],...]`), `filled_cell_count(board) -> int`, `find_landing_row(board, shape_id, start_col) -> int | None`, `place_piece(board, shape_id, start_col, row_offset) -> Board`, `choose_placement(board, shape_id, rng: random.Random) -> tuple[int,int] | None`, `choose_shape(rng: random.Random) -> str`
- `tetris_logic.py`가 계속 제공: `is_game_over(headline_percent: int) -> bool` (변경 없음)

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_tetris_pieces.py`**

```python
import random

from claude_usage_widget.tetris_pieces import (
    COLS,
    ROWS,
    SHAPES,
    TOTAL_CELLS,
    choose_placement,
    choose_shape,
    empty_board,
    filled_cell_count,
    find_landing_row,
    place_piece,
)


def test_empty_board_has_correct_dimensions_and_all_cells_none():
    board = empty_board()
    assert len(board) == ROWS
    assert all(len(row) == COLS for row in board)
    assert all(cell is None for row in board for cell in row)


def test_total_cells_matches_rows_times_cols():
    assert TOTAL_CELLS == ROWS * COLS


def test_filled_cell_count_counts_non_none_cells():
    board = place_piece(empty_board(), "O", 0, ROWS - 2)
    assert filled_cell_count(board) == 4


def test_place_piece_returns_new_board_without_mutating_original():
    board = empty_board()
    new_board = place_piece(board, "O", 0, ROWS - 2)
    assert filled_cell_count(board) == 0
    assert filled_cell_count(new_board) == 4


def test_find_landing_row_on_empty_board_lands_i_piece_at_floor():
    landing = find_landing_row(empty_board(), "I", 0)
    assert landing == ROWS - 1


def test_find_landing_row_rests_on_top_of_existing_stack():
    board = place_piece(empty_board(), "O", 0, ROWS - 2)
    landing = find_landing_row(board, "O", 0)
    assert landing == ROWS - 4


def test_find_landing_row_returns_none_when_top_of_column_is_blocked():
    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(ROWS):
        grid[row][0] = "I"
    board = tuple(tuple(row) for row in grid)
    assert find_landing_row(board, "O", 0) is None


def test_choose_placement_lands_at_floor_when_all_candidate_columns_are_empty():
    grid = [[None] * COLS for _ in range(ROWS)]
    grid[ROWS - 1][4] = "I"
    board = tuple(tuple(row) for row in grid)

    rng = random.Random(0)
    col, landing_row = choose_placement(board, "O", rng)

    assert landing_row == ROWS - 2
    assert col in range(0, COLS - 1)


def test_choose_placement_avoids_shallow_column_when_a_deeper_one_exists():
    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(ROWS - 1, ROWS - 5, -1):
        grid[row][0] = "I"
        grid[row][1] = "I"
    board = tuple(tuple(row) for row in grid)

    rng = random.Random(0)
    for _ in range(20):
        col, landing_row = choose_placement(board, "O", rng)
        assert col in (2, 3)
        assert landing_row == ROWS - 2


def test_choose_placement_returns_none_when_no_column_fits():
    grid = [["I"] * COLS for _ in range(ROWS)]
    board = tuple(tuple(row) for row in grid)
    rng = random.Random(0)
    assert choose_placement(board, "O", rng) is None


def test_choose_shape_returns_a_valid_shape_id():
    rng = random.Random(0)
    for _ in range(20):
        assert choose_shape(rng) in SHAPES
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_tetris_pieces.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.tetris_pieces'`

- [ ] **Step 3: `tetris_pieces.py` 구현**

`src/claude_usage_widget/tetris_pieces.py`:
```python
import random

ROWS = 10
COLS = 5
TOTAL_CELLS = ROWS * COLS

SHAPES = {
    "I": ((0, 0), (0, 1), (0, 2), (0, 3)),
    "O": ((0, 0), (0, 1), (1, 0), (1, 1)),
    "T": ((0, 0), (0, 1), (0, 2), (1, 1)),
    "S": ((0, 1), (0, 2), (1, 0), (1, 1)),
    "Z": ((0, 0), (0, 1), (1, 1), (1, 2)),
    "J": ((0, 0), (1, 0), (1, 1), (1, 2)),
    "L": ((0, 2), (1, 0), (1, 1), (1, 2)),
}

SHAPE_COLORS = {
    "I": "#22D3EE",
    "O": "#FACC15",
    "T": "#A855F7",
    "S": "#22C55E",
    "Z": "#EF4444",
    "J": "#3B82F6",
    "L": "#F97316",
}


def empty_board():
    return tuple(tuple(None for _ in range(COLS)) for _ in range(ROWS))


def filled_cell_count(board) -> int:
    return sum(1 for row in board for cell in row if cell is not None)


def _piece_width(shape_id: str) -> int:
    return max(dc for _, dc in SHAPES[shape_id]) + 1


def find_landing_row(board, shape_id: str, start_col: int):
    cells = SHAPES[shape_id]
    width = _piece_width(shape_id)
    if start_col < 0 or start_col + width > COLS:
        return None

    best_offset = ROWS
    for dr, dc in cells:
        col = start_col + dc
        first_filled = next((r for r in range(ROWS) if board[r][col] is not None), ROWS)
        offset_limit = first_filled - 1 - dr
        best_offset = min(best_offset, offset_limit)

    if best_offset < 0:
        return None
    return best_offset


def place_piece(board, shape_id: str, start_col: int, row_offset: int):
    grid = [list(row) for row in board]
    for dr, dc in SHAPES[shape_id]:
        grid[row_offset + dr][start_col + dc] = shape_id
    return tuple(tuple(row) for row in grid)


def choose_placement(board, shape_id: str, rng: random.Random):
    width = _piece_width(shape_id)
    candidates = []
    for start_col in range(COLS - width + 1):
        landing = find_landing_row(board, shape_id, start_col)
        if landing is not None:
            candidates.append((start_col, landing))

    if not candidates:
        return None

    deepest = max(landing for _, landing in candidates)
    best = [c for c in candidates if c[1] == deepest]
    return rng.choice(best)


def choose_shape(rng: random.Random) -> str:
    return rng.choice(list(SHAPES.keys()))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_tetris_pieces.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: `tetris_logic.py`에서 v1 전용 함수 제거**

`src/claude_usage_widget/tetris_logic.py` 전체를 아래로 교체:
```python
def is_game_over(headline_percent: int) -> bool:
    return headline_percent >= 100
```

- [ ] **Step 6: `tests/test_tetris_logic.py`도 `is_game_over` 테스트만 남기고 교체**

`tests/test_tetris_logic.py` 전체를 아래로 교체:
```python
from claude_usage_widget.tetris_logic import is_game_over


def test_is_game_over_true_at_100_percent_and_above():
    assert is_game_over(100) is True
    assert is_game_over(108) is True


def test_is_game_over_false_below_100_percent():
    assert is_game_over(99) is False
    assert is_game_over(0) is False
```

- [ ] **Step 7: 전체 테스트 스위트 통과 확인**

Run: `python -m pytest -v`
Expected: 전체 PASS. (`widget.py`는 아직 v1 코드 그대로라 `from .tetris_logic import ... filled_row_count, row_color`를 계속 임포트하고 있으므로, 이 시점에는 `ImportError`가 나는 게 정상이다 — Task 2에서 `widget.py`를 재작성하면서 해결된다. 이 스텝은 `tests/test_tetris_pieces.py`와 `tests/test_tetris_logic.py`만 우선 확인하고, 전체 스위트 실패는 Task 2 완료 후 다시 확인한다.)

Run 대신: `python -m pytest tests/test_tetris_pieces.py tests/test_tetris_logic.py -v`
Expected: PASS (13 passed)

- [ ] **Step 8: 커밋**

```bash
git add src/claude_usage_widget/tetris_pieces.py src/claude_usage_widget/tetris_logic.py tests/test_tetris_pieces.py tests/test_tetris_logic.py
git commit -m "Add tetromino board/piece simulation, drop v1's row-based tetris_logic helpers"
```

---

## Task 2: 테트로미노 위젯 재작성 (`widget.py`)

**Files:**
- Modify: `src/claude_usage_widget/widget.py` (전체 재작성)
- Modify: `tests/test_widget.py` (전체 재작성)

**Interfaces:**
- Consumes: `ROWS`, `COLS`, `SHAPES`, `SHAPE_COLORS`, `empty_board`, `filled_cell_count`, `find_landing_row`(간접), `place_piece`, `choose_placement`, `choose_shape` (Task 1의 `tetris_pieces.py`), `is_game_over` (`tetris_logic.py`), `WidgetState` (기존 `widget_state.py`)
- Produces: `CharacterWidget(root, initial_pos, on_move, on_right_click)` — `.WIDTH: int`(=90), `.HEIGHT: int`(=180), `.top: tk.Toplevel`, `.apply_state(state: WidgetState, thresholds: dict) -> None` — **시그니처는 v1과 동일하므로 `app.py`는 수정하지 않는다.**

> 이 태스크의 테스트는 실제 화면(디스플레이)이 있는 Windows 데스크톱 세션에서 실행해야 한다. 짧게 작은 창이 화면에 나타났다 사라질 수 있다.

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_widget.py` 전체 교체)**

`tests/test_widget.py` (기존 파일 내용을 아래로 완전히 대체):
```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_widget.py -v`
Expected: FAIL — 기존 `widget.py`가 아직 v1 API(`_filled_rows` 등)를 쓰고 있어 `AttributeError` 발생

- [ ] **Step 3: `widget.py` 전체 재작성**

`src/claude_usage_widget/widget.py` (기존 파일 내용을 아래로 완전히 대체):
```python
import random
import tkinter as tk

from .tetris_logic import is_game_over
from .tetris_pieces import (
    COLS,
    ROWS,
    SHAPES,
    SHAPE_COLORS,
    choose_placement,
    choose_shape,
    empty_board,
    filled_cell_count,
    place_piece,
)
from .widget_state import WidgetState

_TRANSPARENT_KEY = "magenta"
_EMPTY_CELL_COLOR = "#D1D5DB"
_BORDER_COLOR = "#374151"
_CELL_SIZE = 18
_ANIMATION_DELAY_MS = 300


class CharacterWidget:
    WIDTH = COLS * _CELL_SIZE
    HEIGHT = ROWS * _CELL_SIZE

    def __init__(self, root, initial_pos, on_move, on_right_click):
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(bg=_TRANSPARENT_KEY)
        try:
            self.top.attributes("-transparentcolor", _TRANSPARENT_KEY)
        except tk.TclError:
            pass  # 일부 환경(테스트 등)에서는 지원하지 않을 수 있음

        x, y = initial_pos
        self.top.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        self.canvas = tk.Canvas(
            self.top, width=self.WIDTH, height=self.HEIGHT, bg=_TRANSPARENT_KEY, highlightthickness=0
        )
        self.canvas.pack()

        self._cell_rects = []
        for row in range(ROWS):
            row_rects = []
            for col in range(COLS):
                x1 = col * _CELL_SIZE
                y1 = row * _CELL_SIZE
                rect = self.canvas.create_rectangle(
                    x1 + 1,
                    y1 + 1,
                    x1 + _CELL_SIZE - 1,
                    y1 + _CELL_SIZE - 1,
                    fill=_EMPTY_CELL_COLOR,
                    outline=_BORDER_COLOR,
                )
                row_rects.append(rect)
            self._cell_rects.append(row_rects)

        self._game_over_bg = self.canvas.create_rectangle(
            0, 0, self.WIDTH, self.HEIGHT, fill="#000000", stipple="gray50", outline="", state="hidden"
        )
        self._game_over_text = self.canvas.create_text(
            self.WIDTH / 2,
            self.HEIGHT / 2,
            text="GAME\nOVER",
            fill="white",
            font=("Segoe UI", 9, "bold"),
            justify="center",
            state="hidden",
        )

        self._on_move = on_move
        self._on_right_click = on_right_click
        self._drag_start = None
        self._tooltip_win = None
        self._tooltip_text = ""

        self._board = empty_board()
        self._current_piece = None  # {"shape_id", "col", "row_offset", "landing_row"} 또는 None
        self._pending_target = 0
        self._animation_after_id = None
        self._initialized = False
        self._rng = random.Random()

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._do_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", lambda event: self._on_right_click())
        self.canvas.bind("<Enter>", self._show_tooltip)
        self.canvas.bind("<Leave>", self._hide_tooltip)

    def apply_state(self, state: WidgetState, thresholds: dict) -> None:
        self._tooltip_text = state.tooltip
        clamped = max(0, min(100, state.headline_percent))
        target = round(clamped / 100 * (ROWS * COLS))

        if self._animation_after_id is not None:
            self.canvas.after_cancel(self._animation_after_id)
            self._animation_after_id = None

        if self._current_piece is not None:
            piece = self._current_piece
            self._board = place_piece(self._board, piece["shape_id"], piece["col"], piece["landing_row"])
            self._current_piece = None

        current_filled = filled_cell_count(self._board)

        if not self._initialized or target < current_filled:
            self._board = empty_board()
            self._fill_instantly(target)
            self._initialized = True
        elif target > current_filled:
            self._pending_target = target
            self._spawn_next_piece()

        self._redraw()
        self._set_game_over_visible(is_game_over(state.headline_percent))

    def _fill_instantly(self, target):
        while filled_cell_count(self._board) < target:
            shape_id = choose_shape(self._rng)
            placement = choose_placement(self._board, shape_id, self._rng)
            if placement is None:
                break
            col, landing_row = placement
            self._board = place_piece(self._board, shape_id, col, landing_row)

    def _spawn_next_piece(self):
        if filled_cell_count(self._board) >= self._pending_target:
            return
        shape_id = choose_shape(self._rng)
        placement = choose_placement(self._board, shape_id, self._rng)
        if placement is None:
            return
        col, landing_row = placement
        self._current_piece = {"shape_id": shape_id, "col": col, "row_offset": 0, "landing_row": landing_row}
        self._redraw()
        self._animation_after_id = self.canvas.after(_ANIMATION_DELAY_MS, self._animate_piece_fall_step)

    def _animate_piece_fall_step(self):
        piece = self._current_piece
        if piece["row_offset"] >= piece["landing_row"]:
            self._board = place_piece(self._board, piece["shape_id"], piece["col"], piece["landing_row"])
            self._current_piece = None
            self._redraw()
            self._spawn_next_piece()
            return
        piece["row_offset"] += 1
        self._redraw()
        self._animation_after_id = self.canvas.after(_ANIMATION_DELAY_MS, self._animate_piece_fall_step)

    def _redraw(self):
        for row in range(ROWS):
            for col in range(COLS):
                self.canvas.itemconfig(self._cell_rects[row][col], fill=self._cell_color(row, col))

    def _cell_color(self, row, col):
        if self._current_piece is not None:
            piece = self._current_piece
            for dr, dc in SHAPES[piece["shape_id"]]:
                if piece["row_offset"] + dr == row and piece["col"] + dc == col:
                    return SHAPE_COLORS[piece["shape_id"]]
        cell = self._board[row][col]
        if cell is not None:
            return SHAPE_COLORS[cell]
        return _EMPTY_CELL_COLOR

    def _set_game_over_visible(self, visible):
        state = "normal" if visible else "hidden"
        self.canvas.itemconfig(self._game_over_bg, state=state)
        self.canvas.itemconfig(self._game_over_text, state=state)

    def _start_drag(self, event):
        self._drag_start = (event.x, event.y)

    def _do_drag(self, event):
        if self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        x = self.top.winfo_x() + dx
        y = self.top.winfo_y() + dy
        self.top.geometry(f"+{x}+{y}")

    def _end_drag(self, event):
        self._drag_start = None
        pos = (self.top.winfo_x(), self.top.winfo_y())
        self._on_move(pos)

    def _show_tooltip(self, event):
        if self._tooltip_win is not None:
            return
        x = self.top.winfo_x() + self.WIDTH + 5
        y = self.top.winfo_y()
        self._tooltip_win = tk.Toplevel(self.top)
        self._tooltip_win.overrideredirect(True)
        self._tooltip_win.attributes("-topmost", True)
        self._tooltip_win.geometry(f"+{x}+{y}")
        tk.Label(self._tooltip_win, text=self._tooltip_text, bg="#333333", fg="white", padx=6, pady=3).pack()

    def _hide_tooltip(self, event):
        if self._tooltip_win is not None:
            self._tooltip_win.destroy()
            self._tooltip_win = None
```

- [ ] **Step 4: 위젯 테스트 통과 확인**

Run: `python -m pytest tests/test_widget.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 전체 테스트 스위트 통과 확인**

Run: `python -m pytest -v`
Expected: 전체 PASS. `app.py`/`tests/test_app.py`는 이번 작업에서 건드리지 않았으므로 그대로 통과해야 한다.

- [ ] **Step 6: 커밋**

```bash
git add src/claude_usage_widget/widget.py tests/test_widget.py
git commit -m "Replace single-column block widget with real falling-tetromino board"
```

- [ ] **Step 7: PyInstaller로 재빌드 (선택 사항이지만 권장)**

Run: `pyinstaller --onefile --windowed --name ClaudeUsageWidget --paths src run.py`
Expected: `dist/ClaudeUsageWidget.exe`가 새 코드로 재생성됨. 빌드 전에 기존 `dist/ClaudeUsageWidget.exe`가 실행 중이면 파일이 잠겨 있어 빌드가 실패할 수 있으니, 필요하면 먼저 종료한다.

---

## Self-Review 메모

- **스펙 커버리지**: 설계 문서(v2)의 보드 규격/색상/배치 휴리스틱/채우기 목표/애니메이션/낙하 중 스냅/GAME OVER 조건이 Task 1(순수 시뮬레이션)과 Task 2(위젯+애니메이션)에 각각 매핑됨.
- **타입 일관성**: `CharacterWidget.apply_state(state, thresholds)` 시그니처가 v1과 동일하게 유지되어 `app.py`가 이번 계획에서 전혀 등장하지 않음(수정 대상 아님)을 명시함. `tetris_pieces.py`의 `Board` 표현(`tuple[tuple[str|None,...],...]`)이 `widget.py`의 `_board`/`place_piece`/`filled_cell_count`/`choose_placement` 호출 전체에서 일관되게 쓰임.
- **플레이스홀더 없음**: 모든 스텝에 실행 가능한 실제 코드/명령어 포함.
- **회귀 방지**: Task 1 Step 7에서 `widget.py`가 아직 안 바뀐 상태이므로 전체 스위트가 아니라 Task 1이 만든 두 테스트 파일만 우선 확인하도록 명시(오해로 인한 불필요한 디버깅 방지). Task 2 Step 5에서 전체 스위트를 돌려 `app.py` 쪽 기존 테스트가 이번 변경으로 깨지지 않았는지 최종 확인.
