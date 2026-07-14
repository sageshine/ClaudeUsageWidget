import random
import tkinter as tk

from .tetris_logic import is_game_over
from .tetris_pieces import (
    COLS,
    ROWS,
    SHAPES,
    SHAPE_COLORS,
    choose_shape_and_placement,
    empty_board,
    filled_cell_count,
    place_piece,
)
from .widget_state import WidgetState

_TRANSPARENT_KEY = "magenta"
_BORDER_BASE = "#8B93A1"
_CELL_SIZE = 12
_BEVEL = 2
_FALL_STEP_MS = 150
_SPAWN_GAP_MS = 400
_DECORATIVE_LINGER_MS = 500


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _lighten(hex_color, amount=0.45):
    r, g, b = _hex_to_rgb(hex_color)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02X}{g:02X}{b:02X}"


def _darken(hex_color, amount=0.45):
    r, g, b = _hex_to_rgb(hex_color)
    r = int(r * (1 - amount))
    g = int(g * (1 - amount))
    b = int(b * (1 - amount))
    return f"#{r:02X}{g:02X}{b:02X}"


class CharacterWidget:
    WIDTH = (COLS + 2) * _CELL_SIZE
    HEIGHT = (ROWS + 2) * _CELL_SIZE

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

        self._draw_border()

        self._cell_items = []
        for row in range(ROWS):
            row_items = []
            for col in range(COLS):
                x1 = (col + 1) * _CELL_SIZE
                y1 = (row + 1) * _CELL_SIZE
                row_items.append(self._create_beveled_cell(x1, y1))
            self._cell_items.append(row_items)

        interior_x1, interior_y1 = _CELL_SIZE, _CELL_SIZE
        interior_x2, interior_y2 = _CELL_SIZE + COLS * _CELL_SIZE, _CELL_SIZE + ROWS * _CELL_SIZE
        self._game_over_bg = self.canvas.create_rectangle(
            interior_x1, interior_y1, interior_x2, interior_y2,
            fill="#000000", stipple="gray50", outline="", state="hidden",
        )
        self._game_over_text = self.canvas.create_text(
            (interior_x1 + interior_x2) / 2,
            (interior_y1 + interior_y2) / 2,
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
        self._target = 0
        # {"shape_id", "col", "row_offset", "landing_row", "decorative"} 또는 None.
        # "decorative"인 조각은 착지해도 보드에 합쳐지지 않고 잠시 머물다 사라진다 --
        # target에 이미 도달한 상태에서도 계속 조각이 떨어지는 느낌을 주기 위한 장식용.
        self._current_piece = None
        self._drop_after_id = None
        self._rng = random.Random()

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._do_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", lambda event: self._on_right_click())
        self.canvas.bind("<Enter>", self._show_tooltip)
        self.canvas.bind("<Leave>", self._hide_tooltip)

        self._schedule_next_drop(_SPAWN_GAP_MS)

    def _create_beveled_cell(self, x1, y1):
        x2, y2 = x1 + _CELL_SIZE, y1 + _CELL_SIZE
        base = self.canvas.create_rectangle(x1, y1, x2, y2, fill=_TRANSPARENT_KEY, outline="", state="hidden")
        highlight = self.canvas.create_line(
            x1, y2, x1, y1, x2, y1, width=_BEVEL, fill=_TRANSPARENT_KEY, joinstyle="miter", state="hidden"
        )
        shadow = self.canvas.create_line(
            x1, y2, x2, y2, x2, y1, width=_BEVEL, fill=_TRANSPARENT_KEY, joinstyle="miter", state="hidden"
        )
        return {"base": base, "highlight": highlight, "shadow": shadow}

    def _draw_border(self):
        total_cols, total_rows = COLS + 2, ROWS + 2
        for row in range(total_rows):
            for col in range(total_cols):
                if 0 < row < total_rows - 1 and 0 < col < total_cols - 1:
                    continue  # interior -- not part of the border
                x1, y1 = col * _CELL_SIZE, row * _CELL_SIZE
                items = self._create_beveled_cell(x1, y1)
                self._paint_beveled_cell(items, _BORDER_BASE)
                for item_id in items.values():
                    self.canvas.itemconfig(item_id, state="normal")

    def _paint_beveled_cell(self, items, base_color):
        self.canvas.itemconfig(items["base"], fill=base_color)
        self.canvas.itemconfig(items["highlight"], fill=_lighten(base_color))
        self.canvas.itemconfig(items["shadow"], fill=_darken(base_color))

    def apply_state(self, state: WidgetState, thresholds: dict) -> None:
        """target만 갱신한다 -- 실제로 조각을 몇 개 채울지는 계속 돌아가는 낙하 루프
        (_spawn_piece 이하)가 알아서 target을 향해 조금씩 쌓아간다. 유일한 예외는
        한도가 리셋되어 target이 현재 채워진 칸 수보다 작아지는 경우로, 이때는
        보드를 즉시 비운다(리셋은 순간적 이벤트라 애니메이션이 필요 없음)."""
        self._tooltip_text = state.tooltip
        clamped = max(0, min(100, state.headline_percent))
        new_target = round(clamped / 100 * (ROWS * COLS))

        if new_target < filled_cell_count(self._board):
            if self._drop_after_id is not None:
                self.canvas.after_cancel(self._drop_after_id)
                self._drop_after_id = None
            self._current_piece = None
            self._board = empty_board()
            self._redraw()
            self._schedule_next_drop(_SPAWN_GAP_MS)

        self._target = new_target
        self._redraw()
        self._set_game_over_visible(is_game_over(state.headline_percent))

    def _schedule_next_drop(self, delay_ms):
        self._drop_after_id = self.canvas.after(delay_ms, self._spawn_piece)

    def _spawn_piece(self):
        result = choose_shape_and_placement(self._board, self._rng)
        if result is None:
            # 지금 당장 놓을 자리가 없다 -- 이번 낙하는 건너뛰고 다음 시도를 예약한다.
            self._schedule_next_drop(_SPAWN_GAP_MS)
            return
        shape_id, col, landing_row = result
        decorative = filled_cell_count(self._board) >= self._target
        self._current_piece = {
            "shape_id": shape_id,
            "col": col,
            "row_offset": 0,
            "landing_row": landing_row,
            "decorative": decorative,
        }
        self._redraw()
        self._drop_after_id = self.canvas.after(_FALL_STEP_MS, self._animate_drop_step)

    def _animate_drop_step(self):
        piece = self._current_piece
        if piece["row_offset"] >= piece["landing_row"]:
            if piece["decorative"]:
                self._redraw()
                self._drop_after_id = self.canvas.after(_DECORATIVE_LINGER_MS, self._dissolve_decorative_piece)
            else:
                self._board = place_piece(self._board, piece["shape_id"], piece["col"], piece["landing_row"])
                self._current_piece = None
                self._redraw()
                self._schedule_next_drop(_SPAWN_GAP_MS)
            return
        piece["row_offset"] += 1
        self._redraw()
        self._drop_after_id = self.canvas.after(_FALL_STEP_MS, self._animate_drop_step)

    def _dissolve_decorative_piece(self):
        self._current_piece = None
        self._redraw()
        self._schedule_next_drop(_SPAWN_GAP_MS)

    def _redraw(self):
        for row in range(ROWS):
            for col in range(COLS):
                items = self._cell_items[row][col]
                color = self._cell_color(row, col)
                if color is None:
                    for item_id in items.values():
                        self.canvas.itemconfig(item_id, state="hidden")
                else:
                    self._paint_beveled_cell(items, color)
                    for item_id in items.values():
                        self.canvas.itemconfig(item_id, state="normal")

    def _cell_color(self, row, col):
        if self._current_piece is not None:
            piece = self._current_piece
            for dr, dc in SHAPES[piece["shape_id"]]:
                if piece["row_offset"] + dr == row and piece["col"] + dc == col:
                    return SHAPE_COLORS[piece["shape_id"]]
        cell = self._board[row][col]
        if cell is not None:
            return SHAPE_COLORS[cell]
        return None

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
