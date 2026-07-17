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
    choose_shape_and_placement,
    empty_board,
    filled_cell_count,
    place_piece,
)
from .widget_state import Mood, MOOD_COLORS, WidgetState

_TRANSPARENT_KEY = "magenta"
_BORDER_THICKNESS = 2
_CELL_SIZE = 8

# smooth=True인 폴리곤은 스플라인이 조절점 안쪽으로 당겨지므로, 실제로 보이는
# 반경보다 크게 넣어야 원하는 만큼 둥글어진다.
_JAR_RADIUS = 7
_BLOB_RADIUS = 2.4
# 테두리가 맥박치며 굵어질 때 창 밖으로 잘리지 않게 안쪽으로 조금 들여 그린다
_JAR_INSET = 2.0

_BLOB_INSET = 0.5
_OUTLINE_GROW = 1.0  # 어두운 뒷판이 삐져나오는 폭 = 스티커 외곽선 두께
_OUTLINE_DARKEN = 0.55
_SHINE_LIGHTEN = 0.72
# 같은 색 이웃 쪽으로 이만큼 부풀려서 서로 겹치게 만든다 -> 젤리처럼 녹아 붙는다
_FUSE = 1.5

_INK = "#1F2937"
_GAME_OVER_SCRIM = "#7F1D1D"

_FALL_BASE_MS = 170
_FALL_FLOOR_MS = 85
_FALL_ACCEL_MS = 10
_DECORATIVE_LINGER_MS = 500
_PREHOP_LIFT = 2.0
_PREHOP_UP_MS = 90
_PREHOP_DOWN_MS = 60
_PULSE_MS = 120
_PULSE_STEPS = 10

# 무드별 병 테두리 굵기. 색만으로는 44px에서 약해서 굵기까지 같이 바뀐다 --
# 색을 못 가려도 '프레임이 두꺼워졌다'는 건 보인다. DANGER에선 이 굵기가
# _JAR_PULSE_WIDTH와 번갈아가며 맥박친다.
_JAR_WIDTH = {
    Mood.CALM: 2,
    Mood.WARNING: 3,
    Mood.DANGER: 3,
    Mood.AUTH_ERROR: 3,
    Mood.SETUP_NEEDED: 2,
}
_JAR_PULSE_WIDTH = 4.5

# 착지 바운스: (눌림 정도, 다음 프레임까지 ms). 진폭도 간격도 같이 줄어들어야
# 한 번 쿵 하고 마는 게 아니라 실제로 감쇠 진동하는 것처럼 보인다.
_BOUNCE_FRAMES = ((0.40, 60), (-0.18, 50), (0.10, 40), (-0.04, 35), (0.00, 30))

# 무드별 조각이 새로 떨어지는 간격. 짧을수록 조급해 보인다 -- 모래시계의 점프
# 주기, 숫자의 홉 주기와 같은 신호를 테트리스 방식으로 말한 것.
_SPAWN_GAP_MS = {
    Mood.CALM: 400,
    Mood.WARNING: 260,
    Mood.DANGER: 150,
    Mood.AUTH_ERROR: 150,
    Mood.SETUP_NEEDED: 600,
}
_ALARMED_MOODS = (Mood.DANGER, Mood.AUTH_ERROR)


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


def _rounded_pts(x1, y1, x2, y2, r):
    """모서리마다 '변 끝점 -> 진짜 모서리 -> 변 시작점' 순으로 찍는다. smooth=True와
    함께 쓰면 변은 곧게 남고 모서리만 둥글어진다."""
    return [
        x1 + r, y1, x2 - r, y1, x2, y1,
        x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2,
        x1, y2 - r, x1, y1 + r, x1, y1,
    ]


class CharacterWidget:
    """사용량이 차오르는 만큼 젤리 스티커가 유리병에 쌓인다.

    같은 색끼리는 서로 녹아 붙어서 한 덩어리로 보이고, 떨어지는 조각에는 얼굴이
    있다. 병 테두리 색이 무드를 알리고, 위험할수록 조각이 더 자주 쏟아진다."""

    WIDTH = COLS * _CELL_SIZE + 2 * _BORDER_THICKNESS
    HEIGHT = ROWS * _CELL_SIZE + 2 * _BORDER_THICKNESS

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

        self._piece_lift = 0.0
        self._mood = Mood.CALM
        self._game_over = False

        # 젤리는 3겹으로 그린다. 어두운 뒷판을 전부 먼저 깔고, 그 위에 색 채움을
        # 전부 덮는다 -- 뒷판이 1px씩만 비어져 나와 '합쳐진 덩어리 전체'를 두르는
        # 외곽선이 된다. (칸마다 outline을 주면 붙어버린 이웃 위로 선이 지나간다.)
        self._blob_backs = self._create_cell_layer(fill=_INK)
        self._blob_fills = self._create_cell_layer(fill=_INK)
        self._blob_shines = [
            [self.canvas.create_oval(0, 0, 0, 0, fill=_INK, outline="", state="hidden") for _ in range(COLS)]
            for _ in range(ROWS)
        ]

        # 떨어지는 조각의 얼굴 (쌓인 것들엔 안 붙인다 -- 40개면 뭉갠다)
        self._eye_l = self.canvas.create_oval(0, 0, 0, 0, fill=_INK, outline="", state="hidden")
        self._eye_r = self.canvas.create_oval(0, 0, 0, 0, fill=_INK, outline="", state="hidden")
        self._mouth = self.canvas.create_line(
            0, 0, 0, 0, fill=_INK, width=1, smooth=True, capstyle="round", state="hidden"
        )

        # 병 -- 칸보다 위에 그려서, 둥근 어깨 밖으로 삐져나온 모서리 칸을 덮는다.
        self._jar = self.canvas.create_polygon(
            *self._jar_pts(0.0), fill="", outline=MOOD_COLORS[Mood.CALM], width=_JAR_WIDTH[Mood.CALM], smooth=True
        )

        self._game_over_bg = self.canvas.create_polygon(
            *_rounded_pts(
                _BORDER_THICKNESS, _BORDER_THICKNESS,
                self.WIDTH - _BORDER_THICKNESS, self.HEIGHT - _BORDER_THICKNESS, _JAR_RADIUS,
            ),
            fill=_GAME_OVER_SCRIM, outline="", smooth=True, stipple="gray50", state="hidden",
        )
        # 6pt "GAME OVER"는 40px 폭에선 그냥 얼룩이다. ×_× 얼굴이 글자보다 읽힌다.
        self._game_over_items = [self._game_over_bg]
        for x1, y1, x2, y2 in ((17, 36, 21, 40), (21, 36, 17, 40), (23, 36, 27, 40), (27, 36, 23, 40)):
            self._game_over_items.append(
                self.canvas.create_line(x1, y1, x2, y2, fill="#FFFFFF", width=2, capstyle="round", state="hidden")
            )
        self._game_over_items.append(
            self.canvas.create_line(
                17, 50, 20, 47, 23, 50, 26, 47, 29, 50,
                fill="#FFFFFF", width=2, smooth=True, capstyle="round", state="hidden",
            )
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
        self._pulse_after_id = None
        self._pulse_phase = 0
        self._rng = random.Random()

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._do_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", lambda event: self._on_right_click())
        self.canvas.bind("<Enter>", self._show_tooltip)
        self.canvas.bind("<Leave>", self._hide_tooltip)

        self._redraw()
        self._schedule_next_drop(self._spawn_gap())
        self._schedule_pulse()

    def _create_cell_layer(self, fill):
        return [
            [
                self.canvas.create_polygon(0, 0, 0, 0, fill=fill, outline="", smooth=True, state="hidden")
                for _ in range(COLS)
            ]
            for _ in range(ROWS)
        ]

    def _jar_pts(self, squash):
        """squash > 0이면 바닥은 그대로 두고 위쪽만 눌러 병 전체를 움찔하게 한다."""
        inset = _JAR_INSET
        return _rounded_pts(inset, inset + squash, self.WIDTH - inset, self.HEIGHT - inset, _JAR_RADIUS)

    # ---- 무드 ----

    def _mood_color(self):
        if self._game_over:
            return MOOD_COLORS[Mood.DANGER]
        return MOOD_COLORS.get(self._mood, MOOD_COLORS[Mood.CALM])

    def _is_alarmed(self):
        return self._game_over or self._mood in _ALARMED_MOODS

    def _jar_width(self):
        if self._game_over:
            return _JAR_WIDTH[Mood.DANGER]
        return _JAR_WIDTH.get(self._mood, _JAR_WIDTH[Mood.CALM])

    def _refresh_jar_style(self):
        self.canvas.itemconfig(self._jar, outline=self._mood_color(), width=self._jar_width())

    def _schedule_pulse(self):
        self._pulse_after_id = self.canvas.after(_PULSE_MS, self._on_pulse)

    def _on_pulse(self):
        """위험할 때만 병 테두리가 굵어졌다 얇아졌다 한다. 44px짜리가 화면 구석에
        있을 땐 색조보다 '움직임'이 먼저 눈에 걸린다.

        (따로 후광 링을 두는 대신 병 자체를 쓴다 -- 병이 이미 창 가장자리에
        붙어 있어서, 그 바깥에 그린 링은 창 밖으로 잘려 아예 보이지 않았다.)"""
        if self._is_alarmed():
            self._pulse_phase = (self._pulse_phase + 1) % _PULSE_STEPS
            strong = self._pulse_phase < _PULSE_STEPS // 2
            self.canvas.itemconfig(self._jar, width=_JAR_PULSE_WIDTH if strong else self._jar_width())
        self._schedule_pulse()

    def _spawn_gap(self):
        return _SPAWN_GAP_MS.get(self._mood, _SPAWN_GAP_MS[Mood.CALM])

    # ---- 상태 갱신 ----

    def apply_state(self, state: WidgetState, thresholds: dict) -> None:
        """target만 갱신한다 -- 실제로 조각을 몇 개 채울지는 계속 돌아가는 낙하 루프
        (_spawn_piece 이하)가 알아서 target을 향해 조금씩 쌓아간다. 유일한 예외는
        한도가 리셋되어 target이 현재 채워진 칸 수보다 작아지는 경우로, 이때는
        보드를 즉시 비운다(리셋은 순간적 이벤트라 애니메이션이 필요 없음)."""
        self._tooltip_text = state.tooltip
        clamped = max(0, min(100, state.headline_percent))
        new_target = round(clamped / 100 * (ROWS * COLS))

        # state.mood는 compute_widget_state가 이미 같은 thresholds로 계산해둔 값이고,
        # 임계값만으론 알 수 없는 AUTH_ERROR/SETUP_NEEDED까지 담고 있다.
        self._mood = state.mood
        self._game_over = is_game_over(state.headline_percent)
        self._refresh_jar_style()
        self._set_game_over_visible(self._game_over)

        if new_target < filled_cell_count(self._board):
            if self._drop_after_id is not None:
                self.canvas.after_cancel(self._drop_after_id)
                self._drop_after_id = None
            self._current_piece = None
            self._board = empty_board()
            self._redraw()
            self._schedule_next_drop(self._spawn_gap())

        self._target = new_target
        self._redraw()

    def _schedule_next_drop(self, delay_ms):
        self._drop_after_id = self.canvas.after(delay_ms, self._spawn_piece)

    def _choose_piece_placement(self):
        """알록달록하고 비정형적인 느낌을 위해 항상 완전히 무작위로 모양을 먼저
        고르고, 그 모양이 놓일 수 있는 자리를 찾는다 (쌓이는 조각·장식용 조각
        모두 동일하게). choose_shape_and_placement(가장 깊이 착지하는 조각만
        고르는 방식)는 목표%까지 더 정확하게 채우지만 매번 비슷한 모양(특히 I)만
        골라서 단조로워 보인다 -- 다양성을 우선하기로 하고, 하필 고른 모양이
        지금 보드엔 하나도 안 들어갈 때만 정확도 우선 방식으로 폴백한다."""
        shape_id = choose_shape(self._rng)
        placement = choose_placement(self._board, shape_id, self._rng)
        if placement is not None:
            col, landing_row = placement
            return shape_id, col, landing_row
        return choose_shape_and_placement(self._board, self._rng)

    def _spawn_piece(self):
        decorative = filled_cell_count(self._board) >= self._target
        result = self._choose_piece_placement()
        if result is None:
            # 지금 당장 놓을 자리가 없다 -- 이번 낙하는 건너뛰고 다음 시도를 예약한다.
            self._schedule_next_drop(self._spawn_gap())
            return
        shape_id, col, landing_row = result
        self._current_piece = {
            "shape_id": shape_id,
            "col": col,
            "row_offset": 0,
            "landing_row": landing_row,
            "decorative": decorative,
        }
        # 떨어지기 직전에 살짝 위로 움츠렸다가 간다 (anticipation)
        self._piece_lift = _PREHOP_LIFT
        self._redraw()
        self._drop_after_id = self.canvas.after(_PREHOP_UP_MS, self._release_piece)

    def _release_piece(self):
        self._piece_lift = 0.0
        self._redraw()
        self._drop_after_id = self.canvas.after(_PREHOP_DOWN_MS, self._animate_drop_step)

    def _fall_delay(self, row_offset):
        """아래로 갈수록 빨라진다 -- 등속 낙하는 무게가 없어 보인다."""
        return max(_FALL_FLOOR_MS, _FALL_BASE_MS - row_offset * _FALL_ACCEL_MS)

    def _animate_drop_step(self):
        piece = self._current_piece
        if piece["row_offset"] >= piece["landing_row"]:
            self._play_landing_bounce(piece)
            return
        piece["row_offset"] += 1
        self._redraw()
        self._drop_after_id = self.canvas.after(self._fall_delay(piece["row_offset"]), self._animate_drop_step)

    def _piece_cells(self, piece):
        return [(piece["row_offset"] + dr, piece["col"] + dc) for dr, dc in SHAPES[piece["shape_id"]]]

    def _is_current_piece_cell(self, row, col):
        if self._current_piece is None:
            return False
        return (row, col) in self._piece_cells(self._current_piece)

    def _play_landing_bounce(self, piece, frame=0):
        """착지 순간 눌렸다가 튕겨 오르길 반복하며 잦아든다. 진폭과 간격이 함께
        줄어드는 감쇠 진동이라, 한 번 쿵 하고 마는 것과는 감이 다르다."""
        if frame >= len(_BOUNCE_FRAMES):
            self.canvas.coords(self._jar, *self._jar_pts(0.0))
            self._finish_landing(piece)
            return

        squash, delay = _BOUNCE_FRAMES[frame]
        self._redraw()
        for row, col in self._piece_cells(piece):
            self._set_cell_geometry(row, col, squash=squash)
        # 첫 프레임엔 병까지 같이 움찔한다 -- 조각만 눌리면 충격이 안 전해진다
        self.canvas.coords(self._jar, *self._jar_pts(1.0 if frame == 0 else 0.0))
        self._drop_after_id = self.canvas.after(delay, lambda: self._play_landing_bounce(piece, frame + 1))

    def _finish_landing(self, piece):
        if piece["decorative"]:
            self._redraw()
            self._drop_after_id = self.canvas.after(_DECORATIVE_LINGER_MS, self._dissolve_decorative_piece)
        else:
            self._board = place_piece(self._board, piece["shape_id"], piece["col"], piece["landing_row"])
            self._current_piece = None
            self._redraw()
            self._schedule_next_drop(self._spawn_gap())

    def _dissolve_decorative_piece(self):
        self._current_piece = None
        self._redraw()
        self._schedule_next_drop(self._spawn_gap())

    # ---- 그리기 ----

    def _cell_color(self, row, col):
        if not (0 <= row < ROWS and 0 <= col < COLS):
            return None  # 범위 밖 -- 음수 인덱스가 반대편으로 감기지 않게 막는다
        if self._current_piece is not None:
            piece = self._current_piece
            for dr, dc in SHAPES[piece["shape_id"]]:
                if piece["row_offset"] + dr == row and piece["col"] + dc == col:
                    return SHAPE_COLORS[piece["shape_id"]]
        cell = self._board[row][col]
        if cell is not None:
            return SHAPE_COLORS[cell]
        return None

    def _blob_rect(self, row, col, squash=0.0):
        """같은 색 이웃이 있는 변마다 부풀린다. 겹친 채움끼리는 색이 같아 이음매가
        사라지고, 뒤에 깔린 어두운 판만 바깥 실루엣을 두른다."""
        x1 = _BORDER_THICKNESS + col * _CELL_SIZE + _BLOB_INSET
        y1 = _BORDER_THICKNESS + row * _CELL_SIZE + _BLOB_INSET
        x2 = x1 + _CELL_SIZE - 2 * _BLOB_INSET
        y2 = y1 + _CELL_SIZE - 2 * _BLOB_INSET

        color = self._cell_color(row, col)
        if color is not None:
            if self._cell_color(row - 1, col) == color:
                y1 -= _FUSE
            if self._cell_color(row + 1, col) == color:
                y2 += _FUSE
            if self._cell_color(row, col - 1) == color:
                x1 -= _FUSE
            if self._cell_color(row, col + 1) == color:
                x2 += _FUSE

        if self._is_current_piece_cell(row, col) and self._piece_lift:
            y1 -= self._piece_lift
            y2 -= self._piece_lift

        # squash > 0: 눌린 모습(높이 감소, 폭 증가, 바닥 고정). < 0: 튕겨 늘어난 모습.
        dy = _CELL_SIZE * squash
        dx = _CELL_SIZE * squash * 0.5
        return x1 - dx, y1 + dy, x2 + dx, y2

    def _set_cell_geometry(self, row, col, squash=0.0):
        x1, y1, x2, y2 = self._blob_rect(row, col, squash)
        self.canvas.coords(
            self._blob_backs[row][col],
            *_rounded_pts(
                x1 - _OUTLINE_GROW, y1 - _OUTLINE_GROW, x2 + _OUTLINE_GROW, y2 + _OUTLINE_GROW,
                _BLOB_RADIUS + _OUTLINE_GROW,
            ),
        )
        self.canvas.coords(self._blob_fills[row][col], *_rounded_pts(x1, y1, x2, y2, _BLOB_RADIUS))
        self.canvas.coords(self._blob_shines[row][col], x1 + 1.5, y1 + 1, x1 + 4.5, y1 + 2.5)

    def _paint_cell(self, row, col, color):
        self.canvas.itemconfig(self._blob_backs[row][col], fill=_darken(color, _OUTLINE_DARKEN), state="normal")
        self.canvas.itemconfig(self._blob_fills[row][col], fill=color, state="normal")
        self.canvas.itemconfig(
            self._blob_shines[row][col],
            fill=_lighten(color, _SHINE_LIGHTEN),
            state="normal" if self._takes_shine(row, col, color) else "hidden",
        )

    def _takes_shine(self, row, col, color):
        """붙어서 한 덩어리가 된 젤리에는 광택을 딱 하나만 -- 덩어리의 왼쪽 위
        칸에만 준다. 칸마다 주면 두 칸짜리 블록마다 흰 점이 둘씩 박혀서 전부
        눈처럼 보이고, 정작 떨어지는 조각의 진짜 얼굴이 묻힌다."""
        if self._is_current_piece_cell(row, col):
            return False  # 떨어지는 조각 자리는 얼굴이 쓴다
        if self._cell_color(row - 1, col) == color:
            return False  # 덩어리 위쪽이 아니다
        return self._cell_color(row, col - 1) != color  # 덩어리 왼쪽 끝만

    def _hide_cell(self, row, col):
        for layer in (self._blob_backs, self._blob_fills, self._blob_shines):
            self.canvas.itemconfig(layer[row][col], state="hidden")

    def _redraw(self):
        for row in range(ROWS):
            for col in range(COLS):
                color = self._cell_color(row, col)
                if color is None:
                    self._hide_cell(row, col)
                    continue
                self._set_cell_geometry(row, col)  # 매번 기본 모양으로 되돌린 뒤 다시 그림
                self._paint_cell(row, col, color)
        self._redraw_face()

    def _redraw_face(self):
        piece = self._current_piece
        if piece is None:
            for item in (self._eye_l, self._eye_r, self._mouth):
                self.canvas.itemconfig(item, state="hidden")
            return

        # 얼굴은 한 칸이 아니라 조각 전체의 한가운데에 놓는다 -- 8px 칸 하나에
        # 우겨넣으면 눈·입이 뭉개져 그냥 얼룩으로 보인다. 조각 전체를 쓰면
        # 이목구비를 띄울 만큼 자리가 난다.
        cells = self._piece_cells(piece)
        rows = [row for row, _ in cells]
        cols = [col for _, col in cells]
        cx = _BORDER_THICKNESS + (min(cols) + max(cols) + 1) * _CELL_SIZE / 2
        cy = _BORDER_THICKNESS + (min(rows) + max(rows) + 1) * _CELL_SIZE / 2 - self._piece_lift

        self.canvas.coords(self._eye_l, cx - 3.4, cy - 2.2, cx - 1.4, cy + 0.3)
        self.canvas.coords(self._eye_r, cx + 1.4, cy - 2.2, cx + 3.4, cy + 0.3)
        if self._is_alarmed():
            mouth = (cx - 2, cy + 3.4, cx, cy + 2, cx + 2, cy + 3.4)  # 찌푸림
        elif self._mood == Mood.WARNING:
            mouth = (cx - 2, cy + 2.8, cx, cy + 2.8, cx + 2, cy + 2.8)  # 굳은 일자
        else:
            mouth = (cx - 2, cy + 2, cx, cy + 3.6, cx + 2, cy + 2)  # 미소
        self.canvas.coords(self._mouth, *mouth)
        for item in (self._eye_l, self._eye_r, self._mouth):
            self.canvas.itemconfig(item, state="normal")

    def _set_game_over_visible(self, visible):
        state = "normal" if visible else "hidden"
        for item in self._game_over_items:
            self.canvas.itemconfig(item, state=state)

    def destroy(self):
        """설정에서 위젯 모양을 바꿀 때 app.py가 부른다 -- 예약된 콜백을 취소하지
        않고 캔버스를 없애면, 남은 콜백이 사라진 캔버스를 건드리며 터진다."""
        for after_id in (self._drop_after_id, self._pulse_after_id):
            if after_id is not None:
                self.canvas.after_cancel(after_id)
        self._drop_after_id = None
        self._pulse_after_id = None
        self._hide_tooltip(None)
        self.top.destroy()

    # ---- 드래그 / 툴팁 ----

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
