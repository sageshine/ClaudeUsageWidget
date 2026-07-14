from datetime import datetime, timezone

from claude_usage_widget.api_client import AuthError, TransientError
from claude_usage_widget.models import CreditInfo, LimitInfo, ScopedLimit, UsageSnapshot
from claude_usage_widget.widget_state import Mood, compute_widget_state, resolve_state

THRESHOLDS = {"warning": 60, "danger": 85}


def _snapshot(session_pct, weekly_pct, credit_enabled=False):
    now = datetime.now(timezone.utc)
    return UsageSnapshot(
        session=LimitInfo(percent=session_pct, resets_at=now),
        weekly_all=LimitInfo(percent=weekly_pct, resets_at=now),
        weekly_scoped=[ScopedLimit(model_name="Fable", percent=19, resets_at=now)],
        credit=CreditInfo(enabled=credit_enabled, percent=10, used_dollars=1.5, limit_dollars=None),
        fetched_at=now,
    )


def test_compute_widget_state_calm_below_warning_threshold():
    state = compute_widget_state(_snapshot(9, 17), THRESHOLDS, True)
    assert state.mood == Mood.CALM
    assert state.headline_percent == 17


def test_compute_widget_state_warning_at_threshold():
    state = compute_widget_state(_snapshot(60, 10), THRESHOLDS, True)
    assert state.mood == Mood.WARNING


def test_compute_widget_state_danger_at_threshold():
    state = compute_widget_state(_snapshot(10, 85), THRESHOLDS, True)
    assert state.mood == Mood.DANGER


def test_compute_widget_state_includes_scoped_and_credit_rows_when_enabled():
    state = compute_widget_state(_snapshot(9, 17, credit_enabled=True), THRESHOLDS, True)
    labels = [row[0] for row in state.detail_rows]
    assert any("Fable" in label for label in labels)
    assert any("크레딧" in label for label in labels)


def test_compute_widget_state_omits_credit_row_when_disabled():
    state = compute_widget_state(_snapshot(9, 17, credit_enabled=False), THRESHOLDS, True)
    labels = [row[0] for row in state.detail_rows]
    assert not any("크레딧" in label for label in labels)


def test_compute_widget_state_includes_credit_row_when_api_enabled_and_show_credit_true():
    state = compute_widget_state(_snapshot(9, 17, credit_enabled=True), THRESHOLDS, show_credit=True)
    labels = [row[0] for row in state.detail_rows]
    assert any("크레딧" in label for label in labels)


def test_compute_widget_state_omits_credit_row_when_api_enabled_but_show_credit_false():
    state = compute_widget_state(_snapshot(9, 17, credit_enabled=True), THRESHOLDS, show_credit=False)
    labels = [row[0] for row in state.detail_rows]
    assert not any("크레딧" in label for label in labels)


def test_resolve_state_setup_needed_when_result_is_none():
    state = resolve_state(None, THRESHOLDS, True)
    assert state.mood == Mood.SETUP_NEEDED


def test_resolve_state_auth_error_when_result_is_auth_error():
    state = resolve_state(AuthError("expired"), THRESHOLDS, True)
    assert state.mood == Mood.AUTH_ERROR


def test_resolve_state_warning_when_result_is_other_exception():
    state = resolve_state(TransientError("network"), THRESHOLDS, True)
    assert state.mood == Mood.WARNING


def test_resolve_state_delegates_to_compute_widget_state_for_snapshot():
    state = resolve_state(_snapshot(9, 17), THRESHOLDS, True)
    assert state.mood == Mood.CALM
    assert state.headline_percent == 17


def test_resolve_state_respects_show_credit_false_for_snapshot_result():
    state = resolve_state(_snapshot(9, 17, credit_enabled=True), THRESHOLDS, False)
    labels = [row[0] for row in state.detail_rows]
    assert not any("크레딧" in label for label in labels)


def test_compute_widget_state_tooltip_includes_session_reset_countdown_with_hours():
    now = datetime(2026, 7, 14, 10, 0, 0, tzinfo=timezone.utc)
    snapshot = _snapshot(9, 17)
    snapshot.session.resets_at = datetime(2026, 7, 14, 14, 37, 0, tzinfo=timezone.utc)

    state = compute_widget_state(snapshot, THRESHOLDS, True, now=now)

    assert "4시간 37분 후 재설정" in state.tooltip


def test_compute_widget_state_tooltip_shows_minutes_only_under_one_hour():
    now = datetime(2026, 7, 14, 10, 0, 0, tzinfo=timezone.utc)
    snapshot = _snapshot(9, 17)
    snapshot.session.resets_at = datetime(2026, 7, 14, 10, 25, 0, tzinfo=timezone.utc)

    state = compute_widget_state(snapshot, THRESHOLDS, True, now=now)

    assert "25분 후 재설정" in state.tooltip
    assert "시간" not in state.tooltip


def test_compute_widget_state_tooltip_shows_waiting_message_when_reset_time_already_passed():
    now = datetime(2026, 7, 14, 10, 0, 0, tzinfo=timezone.utc)
    snapshot = _snapshot(9, 17)
    snapshot.session.resets_at = datetime(2026, 7, 14, 9, 0, 0, tzinfo=timezone.utc)

    state = compute_widget_state(snapshot, THRESHOLDS, True, now=now)

    assert "재설정 대기 중" in state.tooltip
