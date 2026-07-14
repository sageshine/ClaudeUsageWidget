# 테트리스 위젯 UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 둥근 캐릭터 위젯을 세로 10칸짜리 테트리스 보드로 완전히 교체한다. 사용량이 오르면 블록이 떨어져 쌓이고, 100%에 도달하면 GAME OVER가 뜬다.

**Architecture:** 색상 밴딩/칸 수 계산/게임오버 판정은 `tetris_logic.py`에 순수 함수로 분리해 Tkinter 없이 테스트한다. `widget.py`의 `CharacterWidget`은 이 순수 함수들을 써서 캔버스에 10개의 행 사각형을 그리고, 애니메이션(after 스케줄링)과 드래그/우클릭/툴팁은 기존 구조를 재사용한다. `app.py`는 두 줄만 수정한다(`CharacterWidget.SIZE`→`HEIGHT`, `apply_state` 호출에 `thresholds` 인자 추가).

**Tech Stack:** 기존 프로젝트와 동일 — Python 3.11+, stdlib `tkinter`, `pytest`. 새 의존성 없음.

## Global Constraints

- 기존 `CharacterWidget(root, initial_pos, on_move, on_right_click)` 생성자 시그니처는 그대로 유지한다.
- `apply_state`는 `apply_state(state: WidgetState, thresholds: dict) -> None`으로 시그니처가 바뀐다 (기존 `apply_state(state)`에서 인자 하나 추가).
- `CharacterWidget.SIZE`(정사각형 가정)는 제거하고 `WIDTH = 40`, `HEIGHT = 100`으로 분리한다.
- 보드는 세로 10칸, 1칸 = 10%. `headline_percent`는 0~100으로 클램프해서 칸 수를 계산한다.
- 칸 색상은 `widget_state.py`의 `MOOD_COLORS`(`Mood.CALM`/`Mood.WARNING`/`Mood.DANGER`)를 그대로 재사용한다 — 새 색상 상수를 만들지 않는다.
- 사용량 증가 시에만 애니메이션(칸당 400ms 지연으로 순차 표시), 감소(리셋) 시에는 애니메이션 없이 즉시 다시 그린다. 위젯 생성 후 첫 `apply_state` 호출도 애니메이션 없이 즉시 그린다.
- GAME OVER는 `headline_percent >= 100`일 때만 표시하고, 텍스트는 영어 그대로 "GAME OVER"를 쓴다 (사용자가 직접 이 표현을 제안함).
- 드래그로 위치 이동, 우클릭 시 콜백 호출, 호버 시 툴팁 표시 동작은 기존과 동일하게 유지한다.
- `widget_state.py`와 `app.py`의 사용량 계산/스레드 안전성 로직(재시도, generation token, timer lock 등)은 건드리지 않는다.

---

## Task 1: 테트리스 순수 로직 (`tetris_logic.py`)

**Files:**
- Create: `src/claude_usage_widget/tetris_logic.py`
- Test: `tests/test_tetris_logic.py`

**Interfaces:**
- Consumes: `MOOD_COLORS: dict[Mood, str]`, `Mood` (from `widget_state.py`, 이미 존재)
- Produces: `TOTAL_ROWS: int` (=10), `filled_row_count(headline_percent: int) -> int`, `row_color(row_index: int, thresholds: dict) -> str` (`row_index`는 1=맨 아래 칸 ~ `TOTAL_ROWS`=맨 위 칸), `is_game_over(headline_percent: int) -> bool`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_tetris_logic.py`:
```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_tetris_logic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.tetris_logic'`

- [ ] **Step 3: tetris_logic.py 구현**

`src/claude_usage_widget/tetris_logic.py`:
```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_tetris_logic.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/claude_usage_widget/tetris_logic.py tests/test_tetris_logic.py
git commit -m "Add pure Tetris board logic (row count, row color, game-over check)"
```

---

## Task 2: 테트리스 보드 위젯 (`widget.py` 교체 + `app.py` 배선)

**Files:**
- Modify: `src/claude_usage_widget/widget.py` (전체 재작성)
- Modify: `tests/test_widget.py` (전체 재작성 — 기존 원형/표정 관련 테스트는 더 이상 유효하지 않음)
- Modify: `src/claude_usage_widget/app.py:229` (`CharacterWidget.SIZE` → `CharacterWidget.HEIGHT`)
- Modify: `src/claude_usage_widget/app.py:206` (`self.widget.apply_state(state)` → `self.widget.apply_state(state, self.config["thresholds"])`)
- Modify: `tests/test_app.py:10-12` (`_FakeWidget.apply_state`가 `thresholds` 인자도 받도록 시그니처 수정)

**Interfaces:**
- Consumes: `TOTAL_ROWS`, `filled_row_count`, `row_color`, `is_game_over` (Task 1의 `tetris_logic.py`), `WidgetState` (기존 `widget_state.py`)
- Produces: `CharacterWidget(root, initial_pos, on_move, on_right_click)` — `.WIDTH: int`(=40), `.HEIGHT: int`(=100), `.top: tk.Toplevel`, `.apply_state(state: WidgetState, thresholds: dict) -> None`

> 이 태스크의 테스트는 실제 화면(디스플레이)이 있는 Windows 데스크톱 세션에서 실행해야 한다. 짧게 작은 창이 화면에 나타났다 사라질 수 있다.

- [ ] **Step 1: 실패하는 테스트 작성 (`tests/test_widget.py` 전체 교체)**

`tests/test_widget.py` (기존 파일 내용을 아래로 완전히 대체):
```python
from types import SimpleNamespace
import tkinter as tk

import pytest

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


def test_first_apply_state_fills_rows_immediately_without_animation(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(65), THRESHOLDS)
    assert widget._filled_rows == 7
    assert widget._animation_after_id is None
    widget.top.destroy()


def test_increasing_percent_animates_filling_rows_over_time(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(20), THRESHOLDS)
    assert widget._filled_rows == 2

    widget.apply_state(_state(50), THRESHOLDS)
    assert widget._filled_rows == 3  # 한 칸만 즉시 채워지고 나머지는 예약됨
    assert widget._animation_after_id is not None
    widget.top.destroy()


def test_decreasing_percent_resets_immediately_without_animation(root):
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(80), THRESHOLDS)
    assert widget._filled_rows == 8

    widget.apply_state(_state(10), THRESHOLDS)
    assert widget._filled_rows == 1
    assert widget._animation_after_id is None
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
Expected: FAIL — 기존 `widget.py`에는 `_filled_rows`, `_animation_after_id`, `_game_over_text` 등이 없고 `apply_state`가 인자 하나만 받으므로 `AttributeError` 또는 `TypeError` 발생

- [ ] **Step 3: `widget.py` 전체 재작성**

`src/claude_usage_widget/widget.py` (기존 파일 내용을 아래로 완전히 대체):
```python
import tkinter as tk

from .tetris_logic import TOTAL_ROWS, filled_row_count, is_game_over, row_color
from .widget_state import WidgetState

_TRANSPARENT_KEY = "magenta"
_EMPTY_ROW_COLOR = "#D1D5DB"
_BORDER_COLOR = "#374151"
_ANIMATION_DELAY_MS = 400


class CharacterWidget:
    WIDTH = 40
    HEIGHT = 100
    _ROW_HEIGHT = HEIGHT / TOTAL_ROWS

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

        self._row_rects = []
        for row_index in range(1, TOTAL_ROWS + 1):
            y1 = self.HEIGHT - row_index * self._ROW_HEIGHT
            y2 = self.HEIGHT - (row_index - 1) * self._ROW_HEIGHT
            rect = self.canvas.create_rectangle(
                2, y1 + 1, self.WIDTH - 2, y2 - 1, fill=_EMPTY_ROW_COLOR, outline=_BORDER_COLOR
            )
            self._row_rects.append(rect)

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

        self._filled_rows = None  # None이면 아직 첫 apply_state가 호출되지 않은 상태
        self._animation_after_id = None

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._do_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", lambda event: self._on_right_click())
        self.canvas.bind("<Enter>", self._show_tooltip)
        self.canvas.bind("<Leave>", self._hide_tooltip)

    def apply_state(self, state: WidgetState, thresholds: dict) -> None:
        self._tooltip_text = state.tooltip
        target = filled_row_count(state.headline_percent)

        if self._animation_after_id is not None:
            self.canvas.after_cancel(self._animation_after_id)
            self._animation_after_id = None

        if self._filled_rows is None or target < self._filled_rows:
            self._filled_rows = target
            self._redraw(thresholds)
        elif target > self._filled_rows:
            self._animate_fill_step(target, thresholds)
        else:
            self._redraw(thresholds)

        self._set_game_over_visible(is_game_over(state.headline_percent))

    def _animate_fill_step(self, target, thresholds):
        if self._filled_rows >= target:
            return
        self._filled_rows += 1
        self._redraw(thresholds)
        if self._filled_rows < target:
            self._animation_after_id = self.canvas.after(
                _ANIMATION_DELAY_MS, self._animate_fill_step, target, thresholds
            )
        else:
            self._animation_after_id = None

    def _redraw(self, thresholds):
        for row_index, rect in enumerate(self._row_rects, start=1):
            if row_index <= self._filled_rows:
                self.canvas.itemconfig(rect, fill=row_color(row_index, thresholds))
            else:
                self.canvas.itemconfig(rect, fill=_EMPTY_ROW_COLOR)

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

- [ ] **Step 4: `app.py` 배선 수정 (2곳)**

`src/claude_usage_widget/app.py`의 `_on_widget_right_click` 메서드에서:
```python
    def _on_widget_right_click(self):
        x = self.widget.top.winfo_x()
        y = self.widget.top.winfo_y() + CharacterWidget.SIZE
        self.detail_panel.show_at(x, y)
```
를 아래로 수정:
```python
    def _on_widget_right_click(self):
        x = self.widget.top.winfo_x()
        y = self.widget.top.winfo_y() + CharacterWidget.HEIGHT
        self.detail_panel.show_at(x, y)
```

`src/claude_usage_widget/app.py`의 `_apply_state` 메서드에서:
```python
    def _apply_state(self, state):
        self.widget.apply_state(state)
```
를 아래로 수정:
```python
    def _apply_state(self, state):
        self.widget.apply_state(state, self.config["thresholds"])
```

- [ ] **Step 5: `tests/test_app.py`의 `_FakeWidget` 시그니처 수정**

`tests/test_app.py`에서:
```python
class _FakeWidget:
    def apply_state(self, state):
        pass
```
를 아래로 수정:
```python
class _FakeWidget:
    def apply_state(self, state, thresholds):
        pass
```

- [ ] **Step 6: 위젯 테스트 통과 확인**

Run: `python -m pytest tests/test_widget.py -v`
Expected: PASS (7 passed)

- [ ] **Step 7: 전체 테스트 스위트 통과 확인 (app.py 배선 변경이 기존 테스트를 깨지 않았는지 확인)**

Run: `python -m pytest -v`
Expected: 전체 PASS (Task 1~2에서 추가/수정한 테스트 포함, 기존 회귀 없음)

- [ ] **Step 8: 커밋**

```bash
git add src/claude_usage_widget/widget.py src/claude_usage_widget/app.py tests/test_widget.py tests/test_app.py
git commit -m "Replace circular character widget with animated Tetris board"
```

- [ ] **Step 9: PyInstaller로 재빌드 (선택 사항이지만 권장 — 기존 .exe는 구 버전 위젯을 담고 있음)**

Run: `pyinstaller --onefile --windowed --name ClaudeUsageWidget --paths src run.py`
Expected: `dist/ClaudeUsageWidget.exe`가 새 코드로 재생성됨. `dist/`, `build/`, `*.spec`는 여전히 커밋하지 않는다.

---

## Self-Review 메모

- **스펙 커버리지**: 보드 규격/칸 색상/애니메이션/GAME OVER/인터페이스 변경 사항(설계 문서의 모든 절)이 Task 1(순수 로직)과 Task 2(위젯+배선)에 각각 매핑됨.
- **타입 일관성**: `apply_state(state, thresholds)` 시그니처가 `widget.py`, `app.py`(호출부 2곳), `tests/test_app.py`(`_FakeWidget`), `tests/test_widget.py`(테스트 호출) 전체에서 동일하게 맞춰짐. `CharacterWidget.HEIGHT`가 `widget.py`와 `app.py` 양쪽에서 같은 이름으로 참조됨.
- **플레이스홀더 없음**: 모든 스텝에 실행 가능한 실제 코드/명령어 포함.
- **회귀 방지**: Task 2 Step 7에서 전체 스위트를 돌려 `app.py`의 두 줄 수정이 `test_app.py`의 다른 기존 테스트(제너레이션 토큰, 재시도, 첫 실행 안내 등)를 깨지 않는지 확인하도록 명시함.
