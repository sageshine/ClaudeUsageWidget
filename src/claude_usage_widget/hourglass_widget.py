import tkinter as tk

from .widget_state import Mood, MOOD_COLORS, WidgetState

_TRANSPARENT_KEY = "magenta"
_GLASS_COLOR = "#9CA3AF"
_MARGIN = 8
_BULB_HALF_WIDTH = 27
_NECK_HALF_WIDTH = 3
_TICK_MS = 120
_DRAIN_STEP = 0.01
_FLIP_FRAME_MS = 90
_FLIP_FRAMES = 4
_TRICKLE_STEPS = 10
_TRICKLE_RADIUS = 1.5


def _lerp(a, b, t):
    return a + (b - a) * t


class HourglassWidget:
    """CharacterWidget(테트리스)과 같은 인터페이스를 구현하는 대체 디자인.
    남은 사용량이 위 유리구에, 사용한 만큼 아래 유리구에 모래로 쌓인다.
    한도가 다 차면(100%) 위가 완전히 비고, 리셋되면 뒤집히며 다시 채워진다."""

    WIDTH = 70
    HEIGHT = 140

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

        self._center_x = self.WIDTH / 2
        self._neck_y = self.HEIGHT / 2

        initial_color = MOOD_COLORS[Mood.CALM]
        self._top_sand = self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill=initial_color, outline="")
        self._bottom_sand = self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0, fill=initial_color, outline="")
        self._trickle = self.canvas.create_oval(0, 0, 0, 0, fill=initial_color, outline="", state="hidden")
        self._outline = self.canvas.create_polygon(*self._outline_points(1.0), fill="", outline=_GLASS_COLOR, width=2)

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

        self._displayed_fraction = 0.0  # 지금 화면에 그려진 "사용된 비율" (0~1)
        self._target_fraction = 0.0  # apply_state가 마지막으로 알려준 실제 비율
        self._color = initial_color
        self._tick_after_id = None
        self._flip_after_id = None
        self._flipping = False
        self._trickle_phase = 0

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._do_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", lambda event: self._on_right_click())
        self.canvas.bind("<Enter>", self._show_tooltip)
        self.canvas.bind("<Leave>", self._hide_tooltip)

        self._redraw(1.0)
        self._schedule_tick()

    # ---- 도형 계산 ----

    def _half_width_at(self, y, y0, hw0, y1, hw1):
        if y1 == y0:
            return hw0
        t = max(0.0, min(1.0, (y - y0) / (y1 - y0)))
        return _lerp(hw0, hw1, t)

    def _top_bulb_half_width(self, y):
        return self._half_width_at(y, _MARGIN, _BULB_HALF_WIDTH, self._neck_y, _NECK_HALF_WIDTH)

    def _bottom_bulb_half_width(self, y):
        return self._half_width_at(y, self._neck_y, _NECK_HALF_WIDTH, self.HEIGHT - _MARGIN, _BULB_HALF_WIDTH)

    def _scaled(self, x, scale_x):
        return self._center_x + (x - self._center_x) * scale_x

    def _outline_points(self, scale_x):
        cx = self._center_x
        pts = [
            (cx - _BULB_HALF_WIDTH, _MARGIN),
            (cx + _BULB_HALF_WIDTH, _MARGIN),
            (cx + _NECK_HALF_WIDTH, self._neck_y),
            (cx + _BULB_HALF_WIDTH, self.HEIGHT - _MARGIN),
            (cx - _BULB_HALF_WIDTH, self.HEIGHT - _MARGIN),
            (cx - _NECK_HALF_WIDTH, self._neck_y),
        ]
        return [coord for px, py in pts for coord in (self._scaled(px, scale_x), py)]

    def _top_sand_points(self, fraction_remaining, scale_x):
        cx = self._center_x
        fill_top_y = self._neck_y - fraction_remaining * (self._neck_y - _MARGIN)
        hw = self._top_bulb_half_width(fill_top_y)
        pts = [
            (cx - _NECK_HALF_WIDTH, self._neck_y),
            (cx - hw, fill_top_y),
            (cx + hw, fill_top_y),
            (cx + _NECK_HALF_WIDTH, self._neck_y),
        ]
        return [coord for px, py in pts for coord in (self._scaled(px, scale_x), py)]

    def _bottom_sand_points(self, fraction_filled, scale_x):
        cx = self._center_x
        bottom_y = self.HEIGHT - _MARGIN
        fill_top_y = bottom_y - fraction_filled * (bottom_y - self._neck_y)
        hw = self._bottom_bulb_half_width(fill_top_y)
        pts = [
            (cx - hw, fill_top_y),
            (cx - _BULB_HALF_WIDTH, bottom_y),
            (cx + _BULB_HALF_WIDTH, bottom_y),
            (cx + hw, fill_top_y),
        ]
        return [coord for px, py in pts for coord in (self._scaled(px, scale_x), py)]

    def _redraw(self, scale_x=1.0):
        remaining = 1.0 - self._displayed_fraction
        self.canvas.coords(self._top_sand, *self._top_sand_points(remaining, scale_x))
        self.canvas.coords(self._bottom_sand, *self._bottom_sand_points(self._displayed_fraction, scale_x))
        self.canvas.coords(self._outline, *self._outline_points(scale_x))
        self.canvas.itemconfig(self._top_sand, fill=self._color)
        self.canvas.itemconfig(self._bottom_sand, fill=self._color)
        self._redraw_trickle(scale_x)

    def _redraw_trickle(self, scale_x):
        active = self._displayed_fraction < 1.0 and not self._flipping
        if not active:
            self.canvas.itemconfig(self._trickle, state="hidden")
            return
        self._trickle_phase = (self._trickle_phase + 1) % _TRICKLE_STEPS
        t = self._trickle_phase / _TRICKLE_STEPS
        y = _lerp(self._neck_y - 6, self._neck_y + 6, t)
        cx = self._center_x
        x1 = self._scaled(cx - _TRICKLE_RADIUS, scale_x)
        x2 = self._scaled(cx + _TRICKLE_RADIUS, scale_x)
        self.canvas.coords(self._trickle, x1, y - _TRICKLE_RADIUS, x2, y + _TRICKLE_RADIUS)
        self.canvas.itemconfig(self._trickle, state="normal", fill=self._color)

    # ---- 상태 갱신 ----

    def apply_state(self, state: WidgetState, thresholds: dict) -> None:
        self._tooltip_text = state.tooltip
        clamped = max(0, min(100, state.headline_percent))
        new_fraction = clamped / 100

        if clamped >= thresholds["danger"]:
            self._color = MOOD_COLORS[Mood.DANGER]
        elif clamped >= thresholds["warning"]:
            self._color = MOOD_COLORS[Mood.WARNING]
        else:
            self._color = MOOD_COLORS[Mood.CALM]

        if new_fraction < self._target_fraction - 0.001 and not self._flipping:
            self._start_flip()

        self._target_fraction = new_fraction
        self._set_game_over_visible(clamped >= 100)

    def _schedule_tick(self):
        self._tick_after_id = self.canvas.after(_TICK_MS, self._on_tick)

    def _on_tick(self):
        if not self._flipping:
            if self._displayed_fraction < self._target_fraction:
                self._displayed_fraction = min(self._target_fraction, self._displayed_fraction + _DRAIN_STEP)
            elif self._displayed_fraction > self._target_fraction:
                self._displayed_fraction = self._target_fraction
            self._redraw(1.0)
        self._schedule_tick()

    def _start_flip(self):
        """한도가 실제로 리셋되면 모래시계를 뒤집는다. 진짜 회전 대신, 가로 폭을
        얇게 접었다가('철컵') 다시 펼치는 카드 뒤집기 방식으로 흉내낸다 -- 접힌
        순간에 내용물을 리셋해서 다시 펼쳐질 땐 위가 가득 찬 새 모래시계로
        보이게 한다."""
        self._flipping = True
        self._flip_step(0, collapsing=True)

    def _flip_step(self, frame, collapsing):
        scale = _lerp(1.0, 0.05, frame / _FLIP_FRAMES) if collapsing else _lerp(0.05, 1.0, frame / _FLIP_FRAMES)
        self._redraw(scale)

        if frame >= _FLIP_FRAMES:
            if collapsing:
                self._displayed_fraction = 0.0
                self._flip_after_id = self.canvas.after(_FLIP_FRAME_MS, lambda: self._flip_step(0, collapsing=False))
            else:
                self._flipping = False
                self._redraw(1.0)
            return

        next_frame = frame + 1
        self._flip_after_id = self.canvas.after(_FLIP_FRAME_MS, lambda: self._flip_step(next_frame, collapsing))

    def _set_game_over_visible(self, visible):
        state = "normal" if visible else "hidden"
        self.canvas.itemconfig(self._game_over_bg, state=state)
        self.canvas.itemconfig(self._game_over_text, state=state)

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
