import tkinter as tk

from .widget_state import Mood, MOOD_COLORS, WidgetState

_TRANSPARENT_KEY = "magenta"
_FONT = ("Segoe UI", 15, "bold")


class NumberWidget:
    """CharacterWidget(테트리스)/HourglassWidget과 같은 인터페이스를 구현하는
    가장 단순한 디자인 -- 배경 없이 큰 숫자(%)만 보여준다. 임계값에 따라
    글자 색만 파랑/노랑/빨강으로 바뀐다."""

    WIDTH = 52
    HEIGHT = 28

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

        self._text = self.canvas.create_text(
            self.WIDTH / 2, self.HEIGHT / 2, text="0%", fill=MOOD_COLORS[Mood.CALM], font=_FONT
        )

        self._on_move = on_move
        self._on_right_click = on_right_click
        self._drag_start = None
        self._tooltip_win = None
        self._tooltip_text = ""

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._do_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", lambda event: self._on_right_click())
        self.canvas.bind("<Enter>", self._show_tooltip)
        self.canvas.bind("<Leave>", self._hide_tooltip)

    def apply_state(self, state: WidgetState, thresholds: dict) -> None:
        self._tooltip_text = state.tooltip
        clamped = max(0, min(100, state.headline_percent))

        if clamped >= thresholds["danger"]:
            color = MOOD_COLORS[Mood.DANGER]
        elif clamped >= thresholds["warning"]:
            color = MOOD_COLORS[Mood.WARNING]
        else:
            color = MOOD_COLORS[Mood.CALM]

        self.canvas.itemconfig(self._text, text=f"{clamped}%", fill=color)

    # ---- 드래그 / 툴팁 (CharacterWidget과 동일한 인터페이스) ----

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
