from types import SimpleNamespace
import tkinter as tk

import pytest

from claude_usage_widget.hourglass_widget import HourglassWidget
from claude_usage_widget.widget_state import Mood, MOOD_COLORS, WidgetState

THRESHOLDS = {"warning": 60, "danger": 85}


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def _state(percent, mood=Mood.CALM, tooltip="t"):
    return WidgetState(mood=mood, headline_percent=percent, tooltip=tooltip, detail_rows=[])


def _settle(widget):
    """애니메이션은 33ms마다 돌지만 모래는 4틱에 한 번만 흐른다 -- 100%를
    다 흘리려면 400틱이 필요하다."""
    for _ in range(450):
        widget._on_tick()


def test_widget_starts_empty(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    assert widget._displayed_fraction == 0.0
    assert widget._target_fraction == 0.0
    widget.destroy()


def test_apply_state_sets_target_without_instantly_moving_displayed_fraction(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)
    assert widget._target_fraction == 0.5
    assert widget._displayed_fraction == 0.0  # 아직 한 번도 tick이 안 돌아 그대로
    widget.destroy()


def test_tick_drains_displayed_fraction_toward_target_gradually(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)

    for _ in range(4):  # 모래는 4틱에 한 번 흐른다
        widget._on_tick()
    first = widget._displayed_fraction
    assert 0.0 < first <= 0.5

    _settle(widget)
    assert widget._displayed_fraction == 0.5
    widget.destroy()


def test_reset_lower_target_triggers_flip_and_resets_displayed_fraction(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(80), THRESHOLDS)
    _settle(widget)
    assert widget._displayed_fraction == 0.8

    widget.apply_state(_state(5), THRESHOLDS)

    assert widget._flipping is True
    widget.destroy()


def test_sand_color_follows_mood(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(10, Mood.CALM), THRESHOLDS)
    assert widget._color == MOOD_COLORS[Mood.CALM]

    widget.apply_state(_state(65, Mood.WARNING), THRESHOLDS)
    assert widget._color == MOOD_COLORS[Mood.WARNING]

    widget.apply_state(_state(90, Mood.DANGER), THRESHOLDS)
    assert widget._color == MOOD_COLORS[Mood.DANGER]
    widget.destroy()


def test_mood_tints_the_whole_body_not_just_the_sand(root):
    """40px 위젯에선 모래 높이보다 전체 색조가 곁눈질에 먼저 읽힌다."""
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    calm_glass = widget.canvas.itemcget(widget._glass_body, "fill")

    widget.apply_state(_state(90, Mood.DANGER), THRESHOLDS)

    assert widget.canvas.itemcget(widget._glass_body, "fill") != calm_glass
    assert widget.canvas.itemcget(widget._glass_outline, "outline") == "#B03A3A"
    widget.destroy()


def test_auth_error_mood_is_not_rendered_as_a_calm_hourglass(root):
    """AUTH_ERROR/SETUP_NEEDED는 headline_percent가 0이라, 퍼센트만 보고 색을
    정하던 예전 코드에선 '차분한 파란 모래시계'로 보였다."""
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(0, Mood.SETUP_NEEDED), THRESHOLDS)

    assert widget._color == MOOD_COLORS[Mood.SETUP_NEEDED]
    assert widget._color != MOOD_COLORS[Mood.CALM]
    widget.destroy()


def test_face_shows_alarm_only_when_in_danger(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(10, Mood.CALM), THRESHOLDS)
    widget._on_tick()
    assert widget.canvas.itemcget(widget._mouth_open, "state") == "hidden"
    assert widget.canvas.itemcget(widget._brow_l, "state") == "hidden"

    widget.apply_state(_state(90, Mood.DANGER), THRESHOLDS)
    widget._on_tick()
    assert widget.canvas.itemcget(widget._mouth_open, "state") == "normal"
    assert widget.canvas.itemcget(widget._brow_l, "state") == "normal"
    widget.destroy()


def test_danger_mood_hops_more_often_than_calm(root):
    """작은 위젯에선 색보다 리듬이 먼저 읽힌다 -- 위험할수록 자주 움직여야 한다."""
    from claude_usage_widget.hourglass_widget import _IDLE_CYCLE

    assert _IDLE_CYCLE[Mood.DANGER] < _IDLE_CYCLE[Mood.WARNING] < _IDLE_CYCLE[Mood.CALM]


def test_hop_transform_lifts_and_squashes_within_the_window(root):
    """점프해도 창 밖으로 잘리면 안 된다 -- 위쪽 _HOP_HEADROOM 안에서만 뜬다."""
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget._mood = Mood.CALM

    lifted = False
    for _ in range(200):
        widget._on_tick()
        scale_x, scale_y, dy = widget._hop_transform()
        assert widget._squashed(widget._top_y - 5, scale_y, dy) >= 0  # 스티커 테두리 위쪽 끝
        if dy < -1:
            lifted = True
            # 세로로 늘어난 만큼 가로는 얇아져야 부피가 보존돼 보인다
            assert scale_x < 1.0 if scale_y > 1.0 else scale_x > 1.0
    assert lifted
    widget.destroy()


def test_game_over_overlay_shown_at_100_percent(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(100), THRESHOLDS)
    assert widget.canvas.itemcget(widget._game_over_text, "state") == "normal"
    widget.destroy()


def test_game_over_overlay_hidden_below_100_percent(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)
    assert widget.canvas.itemcget(widget._game_over_text, "state") == "hidden"
    widget.destroy()


def test_drag_reports_new_position_via_on_move(root):
    moves = []
    widget = HourglassWidget(root, (10, 10), on_move=moves.append, on_right_click=lambda: None)

    widget._start_drag(SimpleNamespace(x=5, y=5))
    widget._do_drag(SimpleNamespace(x=15, y=20))
    widget._end_drag(SimpleNamespace(x=15, y=20))

    assert len(moves) == 1
    assert isinstance(moves[0][0], int)
    assert isinstance(moves[0][1], int)
    widget.destroy()


def test_right_click_invokes_callback(root):
    clicks = []
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: clicks.append(1))

    widget.top.update()
    widget.canvas.event_generate("<Button-3>")
    root.update()

    assert clicks == [1]
    widget.destroy()


def test_destroy_cancels_the_tick_loop(root):
    widget = HourglassWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    assert widget._tick_after_id is not None

    widget.destroy()

    assert widget._tick_after_id is None
