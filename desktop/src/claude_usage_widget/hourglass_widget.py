import math
import tkinter as tk

from .widget_state import Mood, MOOD_COLORS, WidgetState

_TRANSPARENT_KEY = "magenta"
_STICKER_WHITE = "#FFFFFF"
_STICKER_OFFSET = 3
_GLASS_STROKE_WIDTH = 2

_MARGIN = 3
_CAP_RY = 5
_BULB_HALF_WIDTH = 17
_NECK_HALF_WIDTH = 5
_HOP_HEADROOM = 5  # 점프할 때 머리가 잘리지 않도록 위쪽에 비워두는 공간
_CURVE_STEPS = 9

# 무드가 바뀌면 모래 색만이 아니라 몸 전체가 물든다. 40px짜리 위젯에선
# 모래 '높이'보다 전체 색조 변화가 곁눈질에도 먼저 읽힌다.
#
# face는 ink보다 훨씬 진하다: 얼굴은 윗구슬 유리 위에 있지만, 남은 양이 많을 땐
# 그 뒤가 모래로 꽉 차 있다. 유리(밝음)와 모래(중간) 둘 다에서 읽히려면
# 테두리용 ink 정도로는 모자라 모래에 묻혀 사라진다.
_PALETTE = {
    Mood.CALM: {
        "glass": "#BFE0F7", "ink": "#4A7FB0", "face": "#173350", "sand": "#3B82F6",
        "sand_light": "#7FA9FB", "cap": "#FFEDD0", "blush": "#F9A8C4",
    },
    Mood.WARNING: {
        "glass": "#FCE7C0", "ink": "#B4780E", "face": "#4A2F02", "sand": "#F59E0B",
        "sand_light": "#F8C86A", "cap": "#FFF6E2", "blush": "#F48FA8",
    },
    Mood.DANGER: {
        "glass": "#FBD3D3", "ink": "#B03A3A", "face": "#5C1212", "sand": "#EF4444",
        "sand_light": "#F58585", "cap": "#FFE6E6", "blush": "#E8607F",
    },
    Mood.SETUP_NEEDED: {
        "glass": "#E5E7EB", "ink": "#6B7280", "face": "#2F3540", "sand": "#9CA3AF",
        "sand_light": "#C3C9D2", "cap": "#F5F5F5", "blush": "#D8B4C4",
    },
}
_PALETTE[Mood.AUTH_ERROR] = _PALETTE[Mood.DANGER]
_MOUTH_OPEN_FILL = "#C0392B"

_WAIST = 1.5  # 클수록 목이 더 오래 잘록하게 남는다

_TICK_MS = 33
_DRAIN_EVERY = 4  # 4틱(=132ms)마다 한 번만 모래를 흘린다
_DRAIN_STEP = 0.01
_FLIP_FRAME_MS = 90
_FLIP_FRAMES = 4
_TRICKLE_STEPS = 10
_TRICKLE_RADIUS = 1.2

# 손으로 찍은 18프레임 점프. 0-2 웅크림 / 3-9 도약 / 10-12 착지 눌림 / 13-17 잔진동.
_HOP_DY = [0.0, 0.0, 0.0, -1.0, -3.0, -4.0, -4.5, -4.0, -3.0, -1.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
_HOP_SY = [0.88, 0.84, 0.90, 1.06, 1.08, 1.06, 1.02, 1.02, 1.04, 1.06, 0.86, 0.82, 0.90, 0.97, 1.03, 1.01, 0.99, 1.00]
_HOP_FRAMES = len(_HOP_DY)
_SQUASH_VOLUME = 0.65  # 세로로 눌린 만큼 가로로 퍼져야 부피가 보존돼 보인다

# 무드별 점프 주기(틱). 짧을수록 조급해 보인다 -- 색과 별개로 작동하는 위험 신호.
_IDLE_CYCLE = {
    Mood.CALM: 72,
    Mood.WARNING: 45,
    Mood.DANGER: 24,
    Mood.AUTH_ERROR: 24,
    Mood.SETUP_NEEDED: 96,
}
_FLIP_CELEBRATION_HOPS = 3
_DRAG_SQUASH = 0.92


def _lerp(a, b, t):
    return a + (b - a) * t


class HourglassWidget:
    """CharacterWidget(테트리스)과 같은 인터페이스를 구현하는 대체 디자인.
    남은 사용량이 위 유리구에, 사용한 만큼 아래 유리구에 모래로 쌓인다.

    윗구슬에 얼굴이 있는 작은 캐릭터로 그린다 -- 모래가 빠질수록 이 친구가
    비어가며 표정이 굳어가고, 한도가 찰수록 더 자주 조급하게 통통 뛴다.
    한도가 리셋되면 좌우로 접혔다 펴지며 신나서 세 번 뛴다."""

    WIDTH = 2 * _BULB_HALF_WIDTH + 2 * _MARGIN
    HEIGHT = 58

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
        self._top_y = _MARGIN + _CAP_RY + _HOP_HEADROOM
        self._bottom_y = self.HEIGHT - _MARGIN - _CAP_RY
        # 목은 몸통 한가운데 -- 창 한가운데가 아니다(위에 점프 공간을 뒀으므로).
        self._neck_y = (self._top_y + self._bottom_y) / 2

        palette = _PALETTE[Mood.CALM]

        # 흰 스티커 테두리(맨 뒤) -- 본체보다 살짝 크게 그려서 컷아웃 느낌을 냄
        self._sticker_backer = self.canvas.create_polygon(
            0, 0, 0, 0, fill=_STICKER_WHITE, outline="", smooth=True
        )
        self._sticker_top_cap = self.canvas.create_oval(0, 0, 0, 0, fill=_STICKER_WHITE, outline="")
        self._sticker_bottom_cap = self.canvas.create_oval(0, 0, 0, 0, fill=_STICKER_WHITE, outline="")

        # 유리 본체 + 크림색 뚜껑
        self._glass_body = self.canvas.create_polygon(
            0, 0, 0, 0, fill=palette["glass"], outline="", smooth=True
        )
        self._glass_top_cap = self.canvas.create_oval(
            0, 0, 0, 0, fill=palette["cap"], outline=palette["ink"], width=_GLASS_STROKE_WIDTH
        )
        self._glass_bottom_cap = self.canvas.create_oval(
            0, 0, 0, 0, fill=palette["cap"], outline=palette["ink"], width=_GLASS_STROKE_WIDTH
        )

        # 모래. 윗모래엔 유리색 타원을 얹어 오목한 깔때기를, 아랫모래엔 밝은
        # 타원을 얹어 볼록한 더미를 만든다 (그라데이션 대용).
        self._top_sand = self.canvas.create_polygon(0, 0, 0, 0, fill=palette["sand"], outline="")
        self._top_dip = self.canvas.create_oval(0, 0, 0, 0, fill=palette["glass"], outline="")
        self._bottom_sand = self.canvas.create_polygon(0, 0, 0, 0, fill=palette["sand"], outline="")
        self._bottom_mound = self.canvas.create_oval(0, 0, 0, 0, fill=palette["sand_light"], outline="")
        self._trickle = self.canvas.create_oval(0, 0, 0, 0, fill=palette["sand"], outline="", state="hidden")

        # 몸통 테두리 선 (모래 위에 그려서 유리벽이 모래를 감싸는 것처럼 보이게 함)
        self._glass_outline = self.canvas.create_polygon(
            0, 0, 0, 0, fill="", outline=palette["ink"], width=_GLASS_STROKE_WIDTH, smooth=True
        )

        # 몸통 광택은 넣지 않는다: 40px에서 stipple 타원은 유리에 난 흰 생채기처럼
        # 보이면서 얼굴과 싸운다. 광택은 흰 스티커 테두리와 눈동자 흰 점이 낸다.

        # 얼굴
        self._blush_l = self.canvas.create_oval(0, 0, 0, 0, fill=palette["blush"], outline="", stipple="gray50")
        self._blush_r = self.canvas.create_oval(0, 0, 0, 0, fill=palette["blush"], outline="", stipple="gray50")
        self._brow_l = self.canvas.create_line(
            0, 0, 0, 0, fill=palette["face"], width=1.4, capstyle="round", state="hidden"
        )
        self._brow_r = self.canvas.create_line(
            0, 0, 0, 0, fill=palette["face"], width=1.4, capstyle="round", state="hidden"
        )
        self._eye_l = self.canvas.create_oval(0, 0, 0, 0, fill=palette["face"], outline="")
        self._eye_r = self.canvas.create_oval(0, 0, 0, 0, fill=palette["face"], outline="")
        # 눈 속 흰 점 -- 이거 하나로 '귀엽다'와 '죽어있다'가 갈린다.
        self._eye_shine_l = self.canvas.create_oval(0, 0, 0, 0, fill=_STICKER_WHITE, outline="")
        self._eye_shine_r = self.canvas.create_oval(0, 0, 0, 0, fill=_STICKER_WHITE, outline="")
        self._mouth = self.canvas.create_line(
            0, 0, 0, 0, fill=palette["face"], width=1.4, smooth=True, capstyle="round"
        )
        self._mouth_open = self.canvas.create_oval(
            0, 0, 0, 0, fill=_MOUTH_OPEN_FILL, outline=palette["face"], width=1, state="hidden"
        )

        self._game_over_bg = self.canvas.create_rectangle(
            0, 0, self.WIDTH, self.HEIGHT, fill="#000000", stipple="gray50", outline="", state="hidden"
        )
        self._game_over_text = self.canvas.create_text(
            self.WIDTH / 2,
            self.HEIGHT / 2,
            text="GAME\nOVER",
            fill="white",
            font=("Segoe UI", 6, "bold"),
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
        self._mood = Mood.CALM
        self._color = palette["sand"]
        self._tick_after_id = None
        self._flip_after_id = None
        self._flipping = False
        self._trickle_phase = 0
        self._phase = 0
        self._hop_burst = 0

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._do_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", lambda event: self._on_right_click())
        self.canvas.bind("<Enter>", self._show_tooltip)
        self.canvas.bind("<Leave>", self._hide_tooltip)

        self._apply_palette()
        self._redraw()
        self._schedule_tick()

    # ---- 유리구 곡선 계산 ----

    def _flare(self, s):
        """s=0(목) ~ 1(어깨)에서 몸통이 벌어지는 정도(0~1).

        sin은 어깨를 통통하게 둥글려 주지만 그것만 쓰면 목에서 곧바로 벌어져
        눈사람이 된다. 지수를 1보다 크게 먹여 목 쪽을 눌러 허리를 만든다.
        (smoothstep은 반대로 목이 너무 오래 가늘어 와인잔이 된다.)"""
        return math.sin(s * math.pi / 2) ** _WAIST

    def _top_bulb_half_width(self, y, offset=0.0):
        span = self._neck_y - self._top_y
        t = 0.0 if span == 0 else max(0.0, min(1.0, (y - self._top_y) / span))
        return offset + _NECK_HALF_WIDTH + (_BULB_HALF_WIDTH - _NECK_HALF_WIDTH) * self._flare(1 - t)

    def _bottom_bulb_half_width(self, y, offset=0.0):
        span = self._bottom_y - self._neck_y
        t = 0.0 if span == 0 else max(0.0, min(1.0, (y - self._neck_y) / span))
        return offset + _NECK_HALF_WIDTH + (_BULB_HALF_WIDTH - _NECK_HALF_WIDTH) * self._flare(t)

    def _sample_ys(self, y_from, y_to, steps=_CURVE_STEPS):
        return [_lerp(y_from, y_to, i / steps) for i in range(steps + 1)]

    # ---- 좌표 변환 (가로 접기 = 뒤집기, 세로 눌림 = 점프) ----

    def _scaled(self, x, scale_x):
        return self._center_x + (x - self._center_x) * scale_x

    def _squashed(self, y, scale_y, dy):
        """바닥(_bottom_y)을 기준으로 눌린다 -- 가운데가 아니라 바닥 고정이라야
        땅에 착지해 찌그러지는 것처럼 보인다."""
        return self._bottom_y + (y - self._bottom_y) * scale_y + dy

    def _mirrored_polygon(self, left_pts, scale_x, scale_y, dy):
        cx = self._center_x
        right_pts = [(2 * cx - px, py) for px, py in reversed(left_pts)]
        return [
            coord
            for px, py in left_pts + right_pts
            for coord in (self._scaled(px, scale_x), self._squashed(py, scale_y, dy))
        ]

    def _body_points(self, scale_x, scale_y, dy, offset=0.0):
        cx = self._center_x
        left_pts = [
            (cx - self._top_bulb_half_width(y, offset), y)
            for y in self._sample_ys(self._top_y, self._neck_y)
        ]
        left_pts += [
            (cx - self._bottom_bulb_half_width(y, offset), y)
            for y in self._sample_ys(self._neck_y, self._bottom_y)
        ]
        return self._mirrored_polygon(left_pts, scale_x, scale_y, dy)

    def _top_sand_points(self, fraction_remaining, scale_x, scale_y, dy):
        cx = self._center_x
        fill_top_y = self._neck_y - fraction_remaining * (self._neck_y - self._top_y)
        left_pts = [(cx - self._top_bulb_half_width(y), y) for y in self._sample_ys(fill_top_y, self._neck_y)]
        return self._mirrored_polygon(left_pts, scale_x, scale_y, dy)

    def _bottom_sand_points(self, fraction_filled, scale_x, scale_y, dy):
        cx = self._center_x
        fill_top_y = self._bottom_y - fraction_filled * (self._bottom_y - self._neck_y)
        left_pts = [
            (cx - self._bottom_bulb_half_width(y), y) for y in self._sample_ys(fill_top_y, self._bottom_y)
        ]
        return self._mirrored_polygon(left_pts, scale_x, scale_y, dy)

    def _place_oval(self, item_id, cx_pos, cy, rx, ry, scale_x, scale_y, dy):
        self.canvas.coords(
            item_id,
            self._scaled(cx_pos - rx, scale_x),
            self._squashed(cy - ry, scale_y, dy),
            self._scaled(cx_pos + rx, scale_x),
            self._squashed(cy + ry, scale_y, dy),
        )

    def _place_line(self, item_id, points, scale_x, scale_y, dy):
        flat = [
            coord
            for px, py in points
            for coord in (self._scaled(px, scale_x), self._squashed(py, scale_y, dy))
        ]
        self.canvas.coords(item_id, *flat)

    # ---- 그리기 ----

    def _redraw(self, scale_x=1.0, scale_y=1.0, dy=0.0):
        remaining = 1.0 - self._displayed_fraction
        cx = self._center_x

        self.canvas.coords(self._sticker_backer, *self._body_points(scale_x, scale_y, dy, offset=_STICKER_OFFSET))
        self._place_oval(
            self._sticker_top_cap, cx, self._top_y,
            _BULB_HALF_WIDTH + _STICKER_OFFSET, _CAP_RY + _STICKER_OFFSET, scale_x, scale_y, dy,
        )
        self._place_oval(
            self._sticker_bottom_cap, cx, self._bottom_y,
            _BULB_HALF_WIDTH + _STICKER_OFFSET, _CAP_RY + _STICKER_OFFSET, scale_x, scale_y, dy,
        )

        self.canvas.coords(self._glass_body, *self._body_points(scale_x, scale_y, dy))
        self._place_oval(self._glass_top_cap, cx, self._top_y, _BULB_HALF_WIDTH, _CAP_RY, scale_x, scale_y, dy)
        self._place_oval(
            self._glass_bottom_cap, cx, self._bottom_y, _BULB_HALF_WIDTH, _CAP_RY, scale_x, scale_y, dy
        )

        self.canvas.coords(self._top_sand, *self._top_sand_points(remaining, scale_x, scale_y, dy))
        self.canvas.coords(
            self._bottom_sand, *self._bottom_sand_points(self._displayed_fraction, scale_x, scale_y, dy)
        )
        self._redraw_sand_surfaces(remaining, scale_x, scale_y, dy)

        self.canvas.coords(self._glass_outline, *self._body_points(scale_x, scale_y, dy))

        self._redraw_face(scale_x, scale_y, dy)
        self._redraw_trickle(scale_x, scale_y, dy)

    def _redraw_sand_surfaces(self, remaining, scale_x, scale_y, dy):
        cx = self._center_x

        top_fill_y = self._neck_y - remaining * (self._neck_y - self._top_y)
        if remaining < 0.06:
            self.canvas.itemconfig(self._top_dip, state="hidden")
        else:
            half = self._top_bulb_half_width(top_fill_y)
            self.canvas.itemconfig(self._top_dip, state="normal")
            self._place_oval(self._top_dip, cx, top_fill_y, half, 2, scale_x, scale_y, dy)

        bottom_fill_y = self._bottom_y - self._displayed_fraction * (self._bottom_y - self._neck_y)
        if self._displayed_fraction < 0.04:
            self.canvas.itemconfig(self._bottom_mound, state="hidden")
        else:
            half = self._bottom_bulb_half_width(bottom_fill_y)
            self.canvas.itemconfig(self._bottom_mound, state="normal")
            self._place_oval(self._bottom_mound, cx, bottom_fill_y, half, 2.5, scale_x, scale_y, dy)

    def _redraw_face(self, scale_x, scale_y, dy):
        cx = self._center_x
        alarmed = self._mood in (Mood.DANGER, Mood.AUTH_ERROR)
        worried = self._mood == Mood.WARNING

        if alarmed:
            eye_rx, eye_ry, eye_dx = 2.2, 2.9, 0.4  # 눈이 커진다
        elif worried:
            eye_rx, eye_ry, eye_dx = 2.4, 1.7, 0.0  # 찡그린다
        else:
            eye_rx, eye_ry, eye_dx = 2.0, 2.4, 0.0

        for item, shine, side in ((self._eye_l, self._eye_shine_l, -1), (self._eye_r, self._eye_shine_r, 1)):
            ex = cx + side * (5.5 - eye_dx)
            self._place_oval(item, ex, 20, eye_rx, eye_ry, scale_x, scale_y, dy)
            self._place_oval(shine, ex - 0.6, 18.9, 0.6, 0.65, scale_x, scale_y, dy)

        self._place_oval(self._blush_l, cx - 10.5, 24, 2.5, 1.5, scale_x, scale_y, dy)
        self._place_oval(self._blush_r, cx + 10.5, 24, 2.5, 1.5, scale_x, scale_y, dy)

        if alarmed:
            brows = ((-8.5, 15, -3, 17), (8.5, 15, 3, 17))
        elif worried:
            brows = ((-8, 15.5, -3.5, 16.5), (8, 15.5, 3.5, 16.5))
        else:
            brows = None

        if brows is None:
            self.canvas.itemconfig(self._brow_l, state="hidden")
            self.canvas.itemconfig(self._brow_r, state="hidden")
        else:
            for item, (x1, y1, x2, y2) in ((self._brow_l, brows[0]), (self._brow_r, brows[1])):
                self.canvas.itemconfig(item, state="normal")
                self._place_line(item, [(cx + x1, y1), (cx + x2, y2)], scale_x, scale_y, dy)

        if alarmed:
            # 비명 -- 입이 벌어진다
            self.canvas.itemconfig(self._mouth, state="hidden")
            self.canvas.itemconfig(self._mouth_open, state="normal")
            self._place_oval(self._mouth_open, cx, 27, 2.5, 2, scale_x, scale_y, dy)
        else:
            self.canvas.itemconfig(self._mouth_open, state="hidden")
            self.canvas.itemconfig(self._mouth, state="normal")
            if worried:
                pts = [(cx - 3.5, 26.5), (cx - 1.75, 25.4), (cx, 26.5), (cx + 1.75, 25.4), (cx + 3.5, 26.5)]
            else:
                pts = [(cx - 3.5, 25), (cx - 1.75, 26.6), (cx, 27), (cx + 1.75, 26.6), (cx + 3.5, 25)]
            self._place_line(self._mouth, pts, scale_x, scale_y, dy)

    def _redraw_trickle(self, scale_x, scale_y, dy):
        active = self._displayed_fraction < 1.0 and not self._flipping
        if not active:
            self.canvas.itemconfig(self._trickle, state="hidden")
            return
        self._trickle_phase = (self._trickle_phase + 1) % _TRICKLE_STEPS
        t = self._trickle_phase / _TRICKLE_STEPS
        y = _lerp(self._neck_y - 3, self._neck_y + 3, t)
        self._place_oval(self._trickle, self._center_x, y, _TRICKLE_RADIUS, _TRICKLE_RADIUS, scale_x, scale_y, dy)
        self.canvas.itemconfig(self._trickle, state="normal")

    def _apply_palette(self):
        palette = _PALETTE.get(self._mood, _PALETTE[Mood.CALM])
        self._color = palette["sand"]
        self.canvas.itemconfig(self._glass_body, fill=palette["glass"])
        self.canvas.itemconfig(self._top_dip, fill=palette["glass"])
        for cap in (self._glass_top_cap, self._glass_bottom_cap):
            self.canvas.itemconfig(cap, fill=palette["cap"], outline=palette["ink"])
        for sand in (self._top_sand, self._bottom_sand, self._trickle):
            self.canvas.itemconfig(sand, fill=palette["sand"])
        self.canvas.itemconfig(self._bottom_mound, fill=palette["sand_light"])
        self.canvas.itemconfig(self._glass_outline, outline=palette["ink"])
        for face_item in (self._eye_l, self._eye_r, self._mouth, self._brow_l, self._brow_r):
            self.canvas.itemconfig(face_item, fill=palette["face"])
        self.canvas.itemconfig(self._mouth_open, outline=palette["face"])
        for blush in (self._blush_l, self._blush_r):
            self.canvas.itemconfig(blush, fill=palette["blush"])

    # ---- 상태 갱신 ----

    def apply_state(self, state: WidgetState, thresholds: dict) -> None:
        self._tooltip_text = state.tooltip
        clamped = max(0, min(100, state.headline_percent))
        new_fraction = clamped / 100

        # state.mood는 compute_widget_state가 이미 같은 thresholds로 계산해둔 값이고,
        # 임계값만으론 알 수 없는 AUTH_ERROR/SETUP_NEEDED까지 담고 있다.
        if state.mood != self._mood:
            self._mood = state.mood
            self._apply_palette()

        if new_fraction < self._target_fraction - 0.001 and not self._flipping:
            self._start_flip()

        self._target_fraction = new_fraction
        self._set_game_over_visible(clamped >= 100)

    def _schedule_tick(self):
        self._tick_after_id = self.canvas.after(_TICK_MS, self._on_tick)

    def _on_tick(self):
        if not self._flipping:
            self._phase += 1

            if self._phase % _DRAIN_EVERY == 0:
                if self._displayed_fraction < self._target_fraction:
                    self._displayed_fraction = min(
                        self._target_fraction, self._displayed_fraction + _DRAIN_STEP
                    )
                elif self._displayed_fraction > self._target_fraction:
                    self._displayed_fraction = self._target_fraction

            self._redraw(*self._hop_transform())
        self._schedule_tick()

    def _hop_transform(self):
        """지금 프레임의 (scale_x, scale_y, dy). 무드가 급할수록 점프 주기가 짧다."""
        if self._drag_start is not None:
            scale_y = _DRAG_SQUASH  # 집어 올리면 손가락 밑에서 눌린다
            return 1.0 + (1.0 - scale_y) * _SQUASH_VOLUME, scale_y, 0.0

        cycle = _HOP_FRAMES if self._hop_burst > 0 else _IDLE_CYCLE.get(self._mood, 72)
        frame = self._phase % cycle
        if self._hop_burst > 0 and frame == 0:
            self._hop_burst -= 1

        if frame < _HOP_FRAMES:
            dy, scale_y = _HOP_DY[frame], _HOP_SY[frame]
        else:
            dy, scale_y = 0.0, 1.0
        return 1.0 + (1.0 - scale_y) * _SQUASH_VOLUME, scale_y, dy

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
                # 한도가 풀렸으니 신나서 몇 번 뛴다.
                self._phase = 0
                self._hop_burst = _FLIP_CELEBRATION_HOPS
                self._redraw()
            return

        next_frame = frame + 1
        self._flip_after_id = self.canvas.after(_FLIP_FRAME_MS, lambda: self._flip_step(next_frame, collapsing))

    def _set_game_over_visible(self, visible):
        state = "normal" if visible else "hidden"
        self.canvas.itemconfig(self._game_over_bg, state=state)
        self.canvas.itemconfig(self._game_over_text, state=state)

    def destroy(self):
        """설정에서 위젯 모양을 바꿀 때 app.py가 부른다 -- 예약된 tick을 취소하지
        않고 캔버스를 없애면, 남은 콜백이 사라진 캔버스를 건드리며 터진다."""
        for after_id in (self._tick_after_id, self._flip_after_id):
            if after_id is not None:
                self.canvas.after_cancel(after_id)
        self._tick_after_id = None
        self._flip_after_id = None
        self._hide_tooltip(None)
        self.top.destroy()

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
        self._phase = 0  # 내려놓으면 통 하고 착지
        pos = (self.top.winfo_x(), self.top.winfo_y())
        self._on_move(pos)

    def _show_tooltip(self, event):
        self._phase = 0  # 커서가 오면 반갑다고 폴짝
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
