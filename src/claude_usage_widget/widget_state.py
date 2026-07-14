from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .api_client import AuthError
from .models import UsageSnapshot


class Mood(str, Enum):
    CALM = "calm"
    WARNING = "warning"
    DANGER = "danger"
    AUTH_ERROR = "auth_error"
    SETUP_NEEDED = "setup_needed"


MOOD_COLORS = {
    Mood.CALM: "#3B82F6",
    Mood.WARNING: "#F59E0B",
    Mood.DANGER: "#EF4444",
    Mood.AUTH_ERROR: "#EF4444",
    Mood.SETUP_NEEDED: "#9CA3AF",
}

MOOD_FACES = {
    Mood.CALM: "\U0001F642",
    Mood.WARNING: "\U0001F610",
    Mood.DANGER: "\U0001F630",
    Mood.AUTH_ERROR: "⚠",
    Mood.SETUP_NEEDED: "?",
}


@dataclass
class WidgetState:
    mood: Mood
    headline_percent: int
    tooltip: str
    detail_rows: list


def _format_reset_countdown(resets_at: datetime, now: datetime) -> str:
    total_seconds = int((resets_at - now).total_seconds())
    if total_seconds <= 0:
        return "재설정 대기 중"
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if hours > 0:
        return f"{hours}시간 {minutes}분 후 재설정"
    return f"{minutes}분 후 재설정"


def compute_widget_state(
    snapshot: UsageSnapshot, thresholds: dict, show_credit: bool, now: datetime | None = None
) -> WidgetState:
    if now is None:
        now = datetime.now(timezone.utc)

    headline = max(snapshot.session.percent, snapshot.weekly_all.percent)
    if headline >= thresholds["danger"]:
        mood = Mood.DANGER
    elif headline >= thresholds["warning"]:
        mood = Mood.WARNING
    else:
        mood = Mood.CALM

    session_countdown = _format_reset_countdown(snapshot.session.resets_at, now)
    tooltip = f"세션 {snapshot.session.percent}% ({session_countdown}) · 주간 {snapshot.weekly_all.percent}%"

    rows = [
        ("현재 세션", snapshot.session.percent),
        ("주간 한도 (전체 모델)", snapshot.weekly_all.percent),
    ]
    for scoped in snapshot.weekly_scoped:
        rows.append((f"주간 한도 ({scoped.model_name})", scoped.percent))
    if snapshot.credit.enabled and show_credit:
        rows.append((f"사용 크레딧 (${snapshot.credit.used_dollars:.2f})", snapshot.credit.percent))

    return WidgetState(mood=mood, headline_percent=headline, tooltip=tooltip, detail_rows=rows)


def resolve_state(result, thresholds: dict, show_credit: bool, now: datetime | None = None) -> WidgetState:
    if result is None:
        return WidgetState(
            mood=Mood.SETUP_NEEDED,
            headline_percent=0,
            tooltip="설정에서 로그인 정보를 입력하세요",
            detail_rows=[("sessionKey / Organization ID가 설정되지 않았어요.", None)],
        )
    if isinstance(result, AuthError):
        return WidgetState(
            mood=Mood.AUTH_ERROR,
            headline_percent=0,
            tooltip="재로그인이 필요해요",
            detail_rows=[
                ("sessionKey가 만료되었거나 유효하지 않아요.", None),
                ("설정에서 다시 입력해주세요.", None),
            ],
        )
    if isinstance(result, Exception):
        return WidgetState(
            mood=Mood.WARNING,
            headline_percent=0,
            tooltip="일시적으로 갱신에 실패했어요 (마지막 값 유지)",
            detail_rows=[("네트워크 오류로 최신 값을 가져오지 못했어요.", None)],
        )
    return compute_widget_state(result, thresholds, show_credit, now)
