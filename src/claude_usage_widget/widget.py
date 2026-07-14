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
