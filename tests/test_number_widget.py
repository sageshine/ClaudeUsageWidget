from types import SimpleNamespace
import tkinter as tk

import pytest

from claude_usage_widget.number_widget import NumberWidget
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


def _number_text(widget):
    """숫자는 흰 키라인 8장 + 색 글자 1장으로 그려진다. 맨 뒤가 색 글자."""
    item = widget._num_items["items"][-1][0]
    return widget.canvas.itemcget(item, "text")


def _number_fill(widget):
    item = widget._num_items["items"][-1][0]
    return widget.canvas.itemcget(item, "fill")


def _settle(widget):
    """숫자가 굴러가는 연출을 끝까지 돌려 최종값을 확정시킨다."""
    for _ in range(40):
        widget._on_tick()


def test_widget_starts_at_zero(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    assert _number_text(widget) == "0"
    widget.destroy()


def test_apply_state_shows_headline_percent(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(51), THRESHOLDS)
    _settle(widget)
    assert _number_text(widget) == "51"
    widget.destroy()


def test_apply_state_clamps_percent_to_0_100_range(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(140), THRESHOLDS)
    _settle(widget)
    assert _number_text(widget) == "100"
    widget.destroy()


def test_large_change_rolls_the_number_gradually(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(90), THRESHOLDS)
    _settle(widget)

    widget.apply_state(_state(2), THRESHOLDS)  # 한도 리셋
    assert _number_text(widget) == "90"  # 아직 안 굴렀다

    widget._on_tick()
    mid = int(_number_text(widget))
    assert 2 < mid < 90  # 중간값을 거쳐 간다

    _settle(widget)
    assert _number_text(widget) == "2"
    widget.destroy()


def test_small_change_snaps_without_rolling(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(50), THRESHOLDS)
    _settle(widget)

    widget.apply_state(_state(52), THRESHOLDS)
    assert _number_text(widget) == "52"  # tick 없이도 바로
    widget.destroy()


def test_color_follows_mood(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(10, Mood.CALM), THRESHOLDS)
    assert _number_fill(widget) == MOOD_COLORS[Mood.CALM]

    widget.apply_state(_state(65, Mood.WARNING), THRESHOLDS)
    assert _number_fill(widget) == MOOD_COLORS[Mood.WARNING]

    widget.apply_state(_state(90, Mood.DANGER), THRESHOLDS)
    assert _number_fill(widget) == MOOD_COLORS[Mood.DANGER]
    widget.destroy()


def test_auth_error_mood_is_not_rendered_as_a_calm_zero(root):
    """AUTH_ERROR/SETUP_NEEDED는 headline_percent가 0이라, 퍼센트만 보고 색을
    정하던 예전 코드에선 '차분한 파란 0%'로 보였다."""
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget.apply_state(_state(0, Mood.AUTH_ERROR), THRESHOLDS)
    assert _number_fill(widget) == MOOD_COLORS[Mood.AUTH_ERROR]
    assert _number_fill(widget) != MOOD_COLORS[Mood.CALM]
    widget.destroy()


def test_setup_needed_shows_a_dash_instead_of_a_number(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(0, Mood.SETUP_NEEDED), THRESHOLDS)
    assert _number_text(widget) == "—"
    widget.destroy()


def test_full_usage_inverts_the_sticker_colors(root):
    """100%에선 흰 글자 + 빨간 키라인으로 뒤집혀 가장 세게 눈에 띈다."""
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    widget.apply_state(_state(100, Mood.DANGER), THRESHOLDS)

    ring_item = widget._num_items["items"][0][0]
    assert _number_fill(widget) == "#FFFFFF"
    assert widget.canvas.itemcget(ring_item, "fill") == "#EF4444"
    widget.destroy()


def test_idle_hop_moves_the_number_then_returns_to_rest(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    fill_item = widget._num_items["items"][-1][0]
    rest_y = widget.canvas.coords(fill_item)[1]

    lifted = False
    for _ in range(300):  # 한 사이클(쉬는 시간 + 점프)을 충분히 덮는다
        widget._on_tick()
        if widget.canvas.coords(fill_item)[1] < rest_y - 1:
            lifted = True
            break
    assert lifted

    widget.destroy()


def test_danger_mood_hops_more_often_than_calm(root):
    """작은 위젯에선 색보다 리듬이 먼저 읽힌다 -- 위험할수록 자주 움직여야 한다."""
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)

    widget._mood = Mood.CALM
    calm_cycle = len(widget._idle_cycle())

    widget._mood = Mood.DANGER
    danger_cycle = len(widget._idle_cycle())

    assert danger_cycle < calm_cycle
    widget.destroy()


def test_drag_reports_new_position_via_on_move(root):
    moves = []
    widget = NumberWidget(root, (10, 10), on_move=moves.append, on_right_click=lambda: None)

    widget._start_drag(SimpleNamespace(x=5, y=5))
    widget._do_drag(SimpleNamespace(x=15, y=20))
    widget._end_drag(SimpleNamespace(x=15, y=20))

    assert len(moves) == 1
    assert isinstance(moves[0][0], int)
    assert isinstance(moves[0][1], int)
    widget.destroy()


def test_right_click_invokes_callback(root):
    clicks = []
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: clicks.append(1))

    widget.top.update()
    widget.canvas.event_generate("<Button-3>")
    root.update()

    assert clicks == [1]
    widget.destroy()


def test_destroy_cancels_the_tick_loop(root):
    widget = NumberWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: None)
    assert widget._tick_after_id is not None

    widget.destroy()

    assert widget._tick_after_id is None
