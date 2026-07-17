import tkinter as tk

from .widget_state import Mood, MOOD_COLORS, WidgetState

_STICKER_WHITE = "#FFFFFF"
_INVERT_RING = "#EF4444"

# 투명 처리용 색. 다른 스킨들은 magenta를 쓰지만 여기선 쓸 수 없다 --
# -transparentcolor는 '정확히 그 색'인 픽셀만 지우는데, 윈도우는 글자를
# 안티에일리어싱해서 가장자리에 흰색과 배경색이 섞인 중간 픽셀을 만든다.
# 배경이 magenta면 그 중간 픽셀이 분홍색 테두리로 남아 지저분해진다.
# 배경을 흰색 바로 옆 색으로 두면 '흰색 <-> 거의 흰색' 사이를 오가므로
# 남는 픽셀도 거의 흰색이라 스티커 테두리에 묻혀 보이지 않는다.
# (도형만 쓰는 다른 스킨들은 Tk가 안티에일리어싱을 안 해서 이 문제가 없다.)
_TRANSPARENT_KEY = "#FEFEFE"

_FONT_NUM = ("Segoe UI Black", 16)
_FONT_NUM_POP = ("Segoe UI Black", 18)
_FONT_PCT = ("Segoe UI Black", 10)

# 숫자는 오른쪽 끝(_PIVOT_X)에 고정해서 왼쪽으로 자란다 -- 9% -> 51% -> 100%로
# 자릿수가 바뀌어도 % 기호가 흔들리지 않는다.
_PIVOT_X = 34
_NUM_CY = 17
# %는 숫자와 거의 같은 높이에 둔다. 배지처럼 위로 띄우면 흰 키라인이 숫자
# 쪽과 안 붙어서, 스티커 하나가 아니라 별개의 흰 상자 두 개로 보인다.
_PCT_X = 34
_PCT_CY = 16

# 그림자 퍽은 숫자 스티커와 확실히 떨어져 있어야 한다 -- 붙으면 글자에서
# 뻗어나온 혓바닥처럼 보이지, 바닥에 드리운 그림자로 안 읽힌다.
_GROUND_CY = 33
_PUCK_CX = 24
_PUCK_RX = 9.0
_PUCK_RY = 2.5
_PUCK_BACKER_PAD = 1.5

# 글자를 8방향으로 복사해 흰 테두리(다이컷 스티커 키라인)를 흉내낸다.
# Tk에는 글자 외곽선 기능이 없다.
_RING_OFFSETS = ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (-2, 2), (2, -2), (2, 2))
# %는 글자가 작아서 2px로 두르면 속이 메워져 흰 덩어리가 된다.
_PCT_RING_OFFSETS = tuple((ox * 0.75, oy * 0.75) for ox, oy in _RING_OFFSETS)

_TICK_MS = 40
_HOP_REF_HEIGHT = 5.0

# 무드별 (가만히 있는 프레임 수, 1차 점프 높이). 쉬는 시간이 짧아질수록
# 조급해 보인다 -- 작은 위젯에선 색보다 이 리듬이 먼저 눈에 띈다.
_IDLE_TEMPO = {
    Mood.CALM: (60, 5.0),
    Mood.WARNING: (30, 5.0),
    Mood.DANGER: (15, 7.0),
    Mood.AUTH_ERROR: (15, 7.0),
    Mood.SETUP_NEEDED: (90, 3.0),
}
_ALARMED_MOODS = (Mood.DANGER, Mood.AUTH_ERROR)
_SHAKE_DXS = (2.0, -2.0, 2.0, -1.0, 1.0, 0.0)

_ROLL_FRAMES = 12
_ROLL_THRESHOLD = 5


def _hop_dys(height, frames):
    """포물선 점프: dy = -H * 4t(1-t). 첫/마지막 프레임은 dy=0(바닥)."""
    return [-height * 4 * (i / (frames - 1)) * (1 - i / (frames - 1)) for i in range(frames)]


class NumberWidget:
    """CharacterWidget(테트리스)/HourglassWidget과 같은 인터페이스를 구현하는
    가장 단순한 디자인 -- 퍼센트 숫자만 보여준다. 불투명한 배경판 없이,
    흰 키라인으로 오려낸 스티커처럼 그리고 바닥 그림자 위에서 통통 튄다."""

    WIDTH = 50
    HEIGHT = 39

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

        initial_color = MOOD_COLORS[Mood.CALM]

        # 바닥 그림자 퍽 -- 점프할 때 같이 줄었다 늘었다 해야 진짜 튀는 것처럼 보인다.
        # (글자 자체는 Tk에서 부드럽게 확대/축소가 안 되지만 타원은 된다.)
        self._puck_backer = self.canvas.create_oval(0, 0, 0, 0, fill=_STICKER_WHITE, outline="")
        self._puck = self.canvas.create_oval(0, 0, 0, 0, fill=initial_color, outline="")

        self._num_items = self._create_text_run(
            _PIVOT_X, _NUM_CY, "0", _FONT_NUM, "e", initial_color, _RING_OFFSETS
        )
        self._pct_items = self._create_text_run(
            _PCT_X, _PCT_CY, "%", _FONT_PCT, "w", initial_color, _PCT_RING_OFFSETS
        )

        self._on_move = on_move
        self._on_right_click = on_right_click
        self._drag_start = None
        self._tooltip_win = None
        self._tooltip_text = ""

        self._mood = Mood.CALM
        self._displayed_value = 0
        self._target_value = 0
        self._roll_step = 0
        self._queue = []
        self._shake_next = False
        self._popped = False
        self._tick_after_id = None

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._do_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", lambda event: self._on_right_click())
        self.canvas.bind("<Enter>", self._show_tooltip)
        self.canvas.bind("<Leave>", self._hide_tooltip)

        self._render(0.0, 0.0, landed=False, pop=False)
        self._schedule_tick()

    def _create_text_run(self, base_x, base_y, text, font, anchor, color, ring_offsets):
        """흰 키라인 8장 + 그 위에 색 글자 1장. 리스트로 돌려주되 맨 마지막이
        색 글자(= 색을 바꿀 대상)다."""
        items = []
        for ox, oy in ring_offsets:
            item = self.canvas.create_text(
                base_x + ox, base_y + oy, text=text, fill=_STICKER_WHITE, font=font, anchor=anchor
            )
            items.append((item, ox, oy))
        fill_item = self.canvas.create_text(base_x, base_y, text=text, fill=color, font=font, anchor=anchor)
        items.append((fill_item, 0, 0))
        return {"items": items, "base": (base_x, base_y), "font": font}

    # ---- 그리기 ----

    def _render(self, dx, dy, landed, pop, held=False):
        for run in (self._num_items, self._pct_items):
            base_x, base_y = run["base"]
            for item, ox, oy in run["items"]:
                self.canvas.coords(item, base_x + ox + dx, base_y + oy + dy)

        if held:
            rx, ry = 5.5, 2.0
        elif landed:
            rx, ry = 10.5, 2.2  # 착지 순간 반대로 넓게 눌린다
        else:
            lift = min(1.0, max(0.0, -dy / _HOP_REF_HEIGHT))
            rx = _PUCK_RX - 3.5 * lift
            ry = _PUCK_RY - 0.7 * lift

        self.canvas.coords(self._puck, _PUCK_CX - rx, _GROUND_CY - ry, _PUCK_CX + rx, _GROUND_CY + ry)
        self.canvas.coords(
            self._puck_backer,
            _PUCK_CX - rx - _PUCK_BACKER_PAD,
            _GROUND_CY - ry - _PUCK_BACKER_PAD,
            _PUCK_CX + rx + _PUCK_BACKER_PAD,
            _GROUND_CY + ry + _PUCK_BACKER_PAD,
        )

        if pop != self._popped:
            font = _FONT_NUM_POP if pop else _FONT_NUM
            for item, _, _ in self._num_items["items"]:
                self.canvas.itemconfig(item, font=font)
            self._popped = pop

    def _set_text(self, value):
        text = "—" if self._mood == Mood.SETUP_NEEDED else str(value)
        for item, _, _ in self._num_items["items"]:
            self.canvas.itemconfig(item, text=text)

    def _paint(self, color):
        """100%일 땐 색을 뒤집어 -- 흰 글자 + 빨간 키라인 -- 가장 강한 대비를 만든다."""
        inverted = self._mood != Mood.SETUP_NEEDED and self._target_value >= 100
        fill = _STICKER_WHITE if inverted else color
        ring = _INVERT_RING if inverted else _STICKER_WHITE

        for run in (self._num_items, self._pct_items):
            items = run["items"]
            for item, _, _ in items[:-1]:
                self.canvas.itemconfig(item, fill=ring)
            self.canvas.itemconfig(items[-1][0], fill=fill)
        self.canvas.itemconfig(self._puck, fill=color)

    # ---- 애니메이션 ----

    def _idle_cycle(self):
        rest_frames, hop_height = _IDLE_TEMPO.get(self._mood, _IDLE_TEMPO[Mood.CALM])
        frames = [(0.0, 0.0, False, False)] * rest_frames

        if self._mood in _ALARMED_MOODS and self._shake_next:
            # 위험할 땐 한 번 걸러 점프 대신 부르르 떤다.
            frames += [(shake_dx, 0.0, False, False) for shake_dx in _SHAKE_DXS]
        else:
            frames += [(0.0, dy, False, False) for dy in _hop_dys(hop_height, 8)]
            frames += [(0.0, dy, False, False) for dy in _hop_dys(hop_height * 0.5, 8)]
            frames += [(0.0, 0.0, True, False), (0.0, 0.0, True, False)]
        self._shake_next = not self._shake_next
        return frames

    def _reaction_frames(self, celebrate):
        """숫자가 바뀌면 반응해서 튄다. 한도가 리셋되면(큰 폭 하락) 신나서 3연속."""
        hops = ((9.0, 10), (6.0, 8), (3.0, 6)) if celebrate else ((9.0, 10),)
        frames = []
        for index, (height, count) in enumerate(hops):
            for frame, dy in enumerate(_hop_dys(height, count)):
                frames.append((0.0, dy, False, index == 0 and frame < count // 2))
        frames += [(0.0, 0.0, True, False), (0.0, 0.0, True, False)]
        return frames

    def _schedule_tick(self):
        self._tick_after_id = self.canvas.after(_TICK_MS, self._on_tick)

    def _on_tick(self):
        if self._roll_step and self._displayed_value != self._target_value:
            remaining = self._target_value - self._displayed_value
            if abs(remaining) <= abs(self._roll_step):
                self._displayed_value = self._target_value
                self._roll_step = 0
            else:
                self._displayed_value += self._roll_step
            self._set_text(self._displayed_value)

        if self._drag_start is not None:
            self._render(0.0, -4.0, landed=False, pop=False, held=True)
        else:
            if not self._queue:
                self._queue = self._idle_cycle()
            dx, dy, landed, pop = self._queue.pop(0)
            self._render(dx, dy, landed, pop)

        self._schedule_tick()

    # ---- 상태 갱신 ----

    def apply_state(self, state: WidgetState, thresholds: dict) -> None:
        self._tooltip_text = state.tooltip
        clamped = max(0, min(100, state.headline_percent))

        # state.mood는 compute_widget_state가 이미 같은 thresholds로 계산해둔 값이고,
        # 여기엔 임계값만으론 알 수 없는 AUTH_ERROR/SETUP_NEEDED까지 담겨 있다.
        # (예전엔 퍼센트만 보고 색을 다시 계산하느라 로그인 만료 상태가 그냥
        # 파란 0%로 보였다.)
        self._mood = state.mood
        previous = self._target_value
        self._target_value = clamped
        delta = clamped - previous

        if abs(delta) >= _ROLL_THRESHOLD:
            # 큰 폭으로 바뀌면 숫자가 또르르 굴러간다.
            step = -(-abs(delta) // _ROLL_FRAMES)
            self._roll_step = step if delta > 0 else -step
        else:
            self._roll_step = 0
            self._displayed_value = clamped

        self._set_text(self._displayed_value)
        self._paint(MOOD_COLORS[self._mood])

        if delta != 0:
            self._queue = self._reaction_frames(celebrate=delta <= -_ROLL_THRESHOLD)

    def destroy(self):
        """설정에서 위젯 모양을 바꿀 때 app.py가 부른다 -- 예약된 tick을 취소하지
        않고 캔버스를 없애면, 남은 콜백이 사라진 캔버스를 건드리며 터진다."""
        if self._tick_after_id is not None:
            self.canvas.after_cancel(self._tick_after_id)
            self._tick_after_id = None
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
        self._queue = [(0.0, dy, False, False) for dy in _hop_dys(4.0, 6)]
        self._queue += [(0.0, 0.0, True, False)]
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
