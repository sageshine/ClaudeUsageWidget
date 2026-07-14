from unittest.mock import patch, MagicMock

from claude_usage_widget.api_client import fetch_usage, parse_usage_response, AuthError, TransientError, fetch_usage_with_retry

SAMPLE_RESPONSE = {
    "five_hour": {"utilization": 9, "resets_at": "2026-07-14T09:00:00.491813+00:00"},
    "seven_day": {"utilization": 17, "resets_at": "2026-07-19T02:00:00.491842+00:00"},
    "limits": [
        {"kind": "session", "percent": 9, "resets_at": "2026-07-14T09:00:00.491813+00:00"},
        {"kind": "weekly_all", "percent": 17, "resets_at": "2026-07-19T02:00:00.491842+00:00"},
        {
            "kind": "weekly_scoped",
            "percent": 19,
            "resets_at": "2026-07-19T02:00:00.492150+00:00",
            "scope": {"model": {"display_name": "Fable"}},
        },
    ],
    "spend": {
        "enabled": False,
        "percent": 0,
        "used": {"amount_minor": 0, "currency": "USD", "exponent": 2},
        "limit": None,
    },
}


def test_parse_usage_response_extracts_session_and_weekly():
    snapshot = parse_usage_response(SAMPLE_RESPONSE)
    assert snapshot.session.percent == 9
    assert snapshot.weekly_all.percent == 17
    assert len(snapshot.weekly_scoped) == 1
    assert snapshot.weekly_scoped[0].model_name == "Fable"
    assert snapshot.weekly_scoped[0].percent == 19
    assert snapshot.credit.enabled is False
    assert snapshot.credit.used_dollars == 0.0


def test_parse_usage_response_converts_credit_minor_amount():
    data = dict(SAMPLE_RESPONSE)
    data["spend"] = {
        "enabled": True,
        "percent": 108,
        "used": {"amount_minor": 324, "currency": "USD", "exponent": 2},
        "limit": {"amount_minor": 300, "currency": "USD", "exponent": 2},
    }
    snapshot = parse_usage_response(data)
    assert snapshot.credit.enabled is True
    assert snapshot.credit.used_dollars == 3.24
    assert snapshot.credit.limit_dollars == 3.0


@patch("claude_usage_widget.api_client.requests.get")
def test_fetch_usage_returns_snapshot_on_200(mock_get):
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_get.return_value = mock_resp

    snapshot = fetch_usage("session-key-value", "org-123")

    assert snapshot.session.percent == 9
    called_headers = mock_get.call_args.kwargs["headers"]
    assert called_headers["Cookie"] == "sessionKey=session-key-value"
    called_url = mock_get.call_args.args[0]
    assert called_url == "https://claude.ai/api/organizations/org-123/usage"


@patch("claude_usage_widget.api_client.requests.get")
def test_fetch_usage_raises_auth_error_on_401(mock_get):
    mock_get.return_value = MagicMock(status_code=401)
    try:
        fetch_usage("bad-key", "org-123")
        assert False, "expected AuthError"
    except AuthError:
        pass


@patch("claude_usage_widget.api_client.requests.get")
def test_fetch_usage_raises_transient_error_on_500(mock_get):
    mock_get.return_value = MagicMock(status_code=500)
    try:
        fetch_usage("key", "org-123")
        assert False, "expected TransientError"
    except TransientError:
        pass


@patch("claude_usage_widget.api_client.requests.get")
def test_fetch_usage_raises_transient_error_on_malformed_json(mock_get):
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.side_effect = ValueError("bad json")
    mock_get.return_value = mock_resp
    try:
        fetch_usage("key", "org-123")
        assert False, "expected TransientError"
    except TransientError as exc:
        assert "JSON" in str(exc)


def test_fetch_usage_with_retry_raises_auth_error_immediately_without_retry():
    calls = []

    def fake_fetch(session_key, org_id):
        calls.append(1)
        raise AuthError("expired")

    try:
        fetch_usage_with_retry(
            "key", "org-123", fetch_fn=fake_fetch, sleep_fn=lambda s: None
        )
        assert False, "expected AuthError"
    except AuthError:
        pass
    assert len(calls) == 1


def test_fetch_usage_with_retry_retries_transient_errors_then_succeeds():
    calls = []
    sleeps = []

    def fake_fetch(session_key, org_id):
        calls.append(1)
        if len(calls) < 3:
            raise TransientError("network blip")
        return "snapshot-ok"

    result = fetch_usage_with_retry(
        "key", "org-123", fetch_fn=fake_fetch, sleep_fn=lambda s: sleeps.append(s), base_delay=1.0
    )

    assert result == "snapshot-ok"
    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_fetch_usage_with_retry_raises_after_max_attempts():
    def fake_fetch(session_key, org_id):
        raise TransientError("still down")

    try:
        fetch_usage_with_retry(
            "key", "org-123", fetch_fn=fake_fetch, sleep_fn=lambda s: None, max_attempts=3, base_delay=1.0
        )
        assert False, "expected TransientError"
    except TransientError:
        pass
