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
