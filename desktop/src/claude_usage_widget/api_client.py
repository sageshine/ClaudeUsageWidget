import time
from datetime import datetime, timezone

import requests

from .models import CreditInfo, LimitInfo, ScopedLimit, UsageSnapshot

USAGE_URL_TEMPLATE = "https://claude.ai/api/organizations/{org_id}/usage"


class AuthError(Exception):
    pass


class TransientError(Exception):
    pass


def fetch_usage(session_key: str, org_id: str, timeout: float = 10.0) -> UsageSnapshot:
    url = USAGE_URL_TEMPLATE.format(org_id=org_id)
    headers = {"Cookie": f"sessionKey={session_key}"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise TransientError(str(exc)) from exc

    if resp.status_code in (401, 403):
        raise AuthError(f"claude.ai returned {resp.status_code}")
    if resp.status_code != 200:
        raise TransientError(f"unexpected status {resp.status_code}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise TransientError(f"failed to parse response body as JSON: {exc}") from exc

    return parse_usage_response(data)


def _percent(value) -> int:
    """claude.ai는 utilization을 10.4처럼 소수로 내려준다. 모델은 int로 선언돼
    있고 위젯도 정수 자릿수에 맞춰 그리므로(50px 창에 "10.4"는 안 들어가서 앞
    글자가 잘렸다) 파싱 경계에서 한 번만 정리한다."""
    if value is None:
        return 0
    return int(round(float(value)))


def parse_usage_response(data: dict) -> UsageSnapshot:
    session = LimitInfo(
        percent=_percent(data["five_hour"]["utilization"]),
        resets_at=_parse_dt(data["five_hour"]["resets_at"]),
    )
    weekly_all = LimitInfo(
        percent=_percent(data["seven_day"]["utilization"]),
        resets_at=_parse_dt(data["seven_day"]["resets_at"]),
    )
    weekly_scoped = [
        ScopedLimit(
            model_name=item["scope"]["model"]["display_name"],
            percent=_percent(item["percent"]),
            resets_at=_parse_dt(item["resets_at"]),
        )
        for item in data.get("limits", [])
        if item.get("kind") == "weekly_scoped" and item.get("scope", {}).get("model")
    ]
    spend = data.get("spend") or {}
    used = spend.get("used") or {}
    limit = spend.get("limit")
    credit = CreditInfo(
        enabled=bool(spend.get("enabled")),
        percent=_percent(spend.get("percent")),
        used_dollars=_minor_to_dollars(used),
        limit_dollars=_minor_to_dollars(limit) if limit else None,
    )
    return UsageSnapshot(
        session=session,
        weekly_all=weekly_all,
        weekly_scoped=weekly_scoped,
        credit=credit,
        fetched_at=datetime.now(timezone.utc),
    )


def _parse_dt(value: str | None) -> datetime | None:
    """claude.ai가 아직 한 번도 안 쓴 weekly_scoped 한도에는 resets_at을
    null로 내려준다 (2026-08-03부터 관찰됨) -- 그걸 그대로 .replace()에
    넘기면 매 요청마다 AttributeError로 죽고, 이건 TransientError가 아니라서
    fetch_usage_with_retry의 재시도/백오프도 안 타고 즉시 실패한다."""
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _minor_to_dollars(amount) -> float:
    if not amount:
        return 0.0
    return amount["amount_minor"] / (10 ** amount.get("exponent", 2))


def fetch_usage_with_retry(
    session_key: str,
    org_id: str,
    max_attempts: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 900.0,
    sleep_fn=time.sleep,
    fetch_fn=fetch_usage,
) -> UsageSnapshot:
    delay = base_delay
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fetch_fn(session_key, org_id)
        except AuthError:
            raise
        except TransientError as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            sleep_fn(min(delay, max_delay))
            delay *= 2
    raise last_error
