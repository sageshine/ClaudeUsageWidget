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

    return parse_usage_response(resp.json())


def parse_usage_response(data: dict) -> UsageSnapshot:
    session = LimitInfo(
        percent=data["five_hour"]["utilization"],
        resets_at=_parse_dt(data["five_hour"]["resets_at"]),
    )
    weekly_all = LimitInfo(
        percent=data["seven_day"]["utilization"],
        resets_at=_parse_dt(data["seven_day"]["resets_at"]),
    )
    weekly_scoped = [
        ScopedLimit(
            model_name=item["scope"]["model"]["display_name"],
            percent=item["percent"],
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
        percent=spend.get("percent") or 0,
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


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _minor_to_dollars(amount) -> float:
    if not amount:
        return 0.0
    return amount["amount_minor"] / (10 ** amount.get("exponent", 2))
