import math
import tkinter as tk

from .widget_state import Mood, MOOD_COLORS, WidgetState

_TRANSPARENT_KEY = "magenta"
_GLASS_OUTLINE = "#CBD5E1"
_GLASS_SHINE = "#FFFFFF"
_WOOD_BASE = "#92400E"
_MARGIN = 4
_CAP_HEIGHT = 7
_POST_WIDTH = 5
_BULB_HALF_WIDTH = 24
_NECK_HALF_WIDTH = 3
_CURVE_STEPS = 5
_TICK_MS = 120
_DRAIN_STEP = 0.01
_FLIP_FRAME_MS = 90
_FLIP_FRAMES = 4
_TRICKLE_STEPS = 10
_TRICKLE_RADIUS = 1.5


def _lerp(a, b, t):
    return a + (b - a) * t


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _lighten(hex_color, amount=0.4):
    r, g, b = _hex_to_rgb(hex_color)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02X}{g:02X}{b:02X}"


def _darken(hex_color, amount=0.4):
    r, g, b = _hex_to_rgb(hex_color)
    r = int(r * (1 - amount))
    g = int(g * (1 - amount))
    b = int(b * (1 - amount))
    return f"#{r:02X}{g:02X}{b:02X}"


class HourglassWidget:
    """CharacterWidget(테트리스)과 같은 인터페이스를 구현하는 대체 디자인.
    남은 사용량이 위 유리구에, 사용한 만큼 아래 유리구에 모래로 쌓인다.
    나무 프레임(위아래 마개 + 좌우 기둥)과 완만하게 잘록해지는 유리구 곡선으로
    실제 모래시계 실루엣에 가깝게 그린다. 한도가 다 차면(100%) 위가 완전히
    비고, 리셋되면 좌우로 접혔다 펴지며 다시 채워진다."""

    WIDTH = 2 * (_BULB_HALF_WIDTH + _POST_WIDTH) + 2 * _MARGIN
    HEIGHT = 150

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
        self._top_y = _MARGIN + _CAP_HEIGHT
        self._bottom_y = self.HEIGHT - _MARGIN - _CAP_HEIGHT

        self._wood_items = [
            self._create_bevel_rect(),  # top cap
            self._create_bevel_rect(),  # bottom cap
            self._create_bevel_rect(),  # left post
            self._create_bevel_rect(),  # right post
        ]
        self._paint_wood()

        initial_color = MOOD_COLORS[Mood.CALM]
        self._top_sand = self.canvas.create_polygon(0, 0, 0, 0, fill=initial_color, outline="")
        self._bottom_sand = self.canvas.create_polygon(0, 0, 0, 0, fill=initial_color, outline="")
        self._trickle = self.canvas.create_oval(0, 0, 0, 0, fill=initial_color, outline="", state="hidden")
        self._outline = self.canvas.create_polygon(*self._outline_points(1.0), fill="", outline=_GLASS_OUTLINE, width=1)
        self._shine_top = self.canvas.create_line(0, 0, 0, 0, width=2, fill=_GLASS_SHINE, stipple="gray25")
        self._shine_bottom = self.canvas.create_line(0, 0, 0, 0, width=2, fill=_GLASS_SHINE, stipple="gray25")

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

    # ---- 나무 프레임 (위아래 마개 + 좌우 기둥) ----

    def _create_bevel_rect(self):
        base = self.canvas.create_rectangle(0, 0, 0, 0, fill=_WOOD_BASE, outline="")
        highlight = self.canvas.create_line(0, 0, 0, 0, 0, 0, width=1, fill=_lighten(_WOOD_BASE))
        shadow = self.canvas.create_line(0, 0, 0, 0, 0, 0, width=1, fill=_darken(_WOOD_BASE))
        return {"base": base, "highlight": highlight, "shadow": shadow}

    def _set_bevel_rect(self, items, x1, y1, x2, y2):
        self.canvas.coords(items["base"], x1, y1, x2, y2)
        self.canvas.coords(items["highlight"], x1, y2, x1, y1, x2, y1)
        self.canvas.coords(items["shadow"], x1, y2, x2, y2, x2, y1)

    def _paint_wood(self, scale_x=1.0):
        cx = self._center_x
        outer_hw = _BULB_HALF_WIDTH + _POST_WIDTH
        x_left = self._scaled(cx - outer_hw, scale_x)
        x_right = self._scaled(cx + outer_hw, scale_x)
        top_cap, bottom_cap, left_post, right_post = self._wood_items
        self._set_bevel_rect(top_cap, x_left, _MARGIN, x_right, self._top_y)
        self._set_bevel_rect(bottom_cap, x_left, self._bottom_y, x_right, self.HEIGHT - _MARGIN)
        post_left_x1 = self._scaled(cx - outer_hw, scale_x)
        post_left_x2 = self._scaled(cx - _BULB_HALF_WIDTH, scale_x)
        self._set_bevel_rect(left_post, post_left_x1, self._top_y, post_left_x2, self._bottom_y)
        post_right_x1 = self._scaled(cx + _BULB_HALF_WIDTH, scale_x)
        post_right_x2 = self._scaled(cx + outer_hw, scale_x)
        self._set_bevel_rect(right_post, post_right_x1, self._top_y, post_right_x2, self._bottom_y)

    # ---- 유리구 곡선 계산 ----

    def _top_bulb_half_width(self, y):
        span = self._neck_y - self._top_y
        t = 0.0 if span == 0 else max(0.0, min(1.0, (y - self._top_y) / span))
        s = 1 - t  # 1: 넓은 쪽(위), 0: 목
        return _NECK_HALF_WIDTH + (_BULB_HALF_WIDTH - _NECK_HALF_WIDTH) * math.sin(s * math.pi / 2)

    def _bottom_bulb_half_width(self, y):
        span = self._bottom_y - self._neck_y
        t = 0.0 if span == 0 else max(0.0, min(1.0, (y - self._neck_y) / span))
        s = t  # 0: 목, 1: 넓은 쪽(아래)
        return _NECK_HALF_WIDTH + (_BULB_HALF_WIDTH - _NECK_HALF_WIDTH) * math.sin(s * math.pi / 2)

    def _curve_points(self, y_from, y_to, half_width_fn, steps=_CURVE_STEPS):
        return [(_lerp(y_from, y_to, i / steps), half_width_fn(_lerp(y_from, y_to, i / steps))) for i in range(steps + 1)]

    def _scaled(self, x, scale_x):
        return self._center_x + (x - self._center_x) * scale_x

    def _mirrored_polygon(self, left_pts, scale_x):
        cx = self._center_x
        right_pts = [(2 * cx - px, py) for px, py in reversed(left_pts)]
        all_pts = left_pts + right_pts
        return [coord for px, py in all_pts for coord in (self._scaled(px, scale_x), py)]

    def _outline_points(self, scale_x):
        cx = self._center_x
        left_pts = [(cx - hw, y) for y, hw in self._curve_points(self._top_y, self._neck_y, self._top_bulb_half_width)]
        left_pts += [(cx - hw, y) for y, hw in self._curve_points(self._neck_y, self._bottom_y, self._bottom_bulb_half_width)]
        return self._mirrored_polygon(left_pts, scale_x)

    def _top_sand_points(self, fraction_remaining, scale_x):
        cx = self._center_x
        fill_top_y = self._neck_y - fraction_remaining * (self._neck_y - self._top_y)
        left_pts = [(cx - hw, y) for y, hw in self._curve_points(fill_top_y, self._neck_y, self._top_bulb_half_width)]
        return self._mirrored_polygon(left_pts, scale_x)

    def _bottom_sand_points(self, fraction_filled, scale_x):
        cx = self._center_x
        fill_top_y = self._bottom_y - fraction_filled * (self._bottom_y - self._neck_y)
        left_pts = [(cx - hw, y) for y, hw in self._curve_points(fill_top_y, self._bottom_y, self._bottom_bulb_half_width)]
        return self._mirrored_polygon(left_pts, scale_x)

    def _redraw(self, scale_x=1.0):
        remaining = 1.0 - self._displayed_fraction
        self.canvas.coords(self._top_sand, *self._top_sand_points(remaining, scale_x))
        self.canvas.coords(self._bottom_sand, *self._bottom_sand_points(self._displayed_fraction, scale_x))
        self.canvas.coords(self._outline, *self._outline_points(scale_x))
        self.canvas.itemconfig(self._top_sand, fill=self._color)
        self.canvas.itemconfig(self._bottom_sand, fill=self._color)
        self._paint_wood(scale_x)
        self._redraw_shine(scale_x)
        self._redraw_trickle(scale_x)

    def _redraw_shine(self, scale_x):
        cx = self._center_x
        top_x = self._scaled(cx - _BULB_HALF_WIDTH * 0.45, scale_x)
        self.canvas.coords(self._shine_top, top_x, self._top_y + 6, top_x, self._neck_y - 8)
        bottom_x = self._scaled(cx - _BULB_HALF_WIDTH * 0.45, scale_x)
        self.canvas.coords(self._shine_bottom, bottom_x, self._neck_y + 8, bottom_x, self._bottom_y - 6)

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
