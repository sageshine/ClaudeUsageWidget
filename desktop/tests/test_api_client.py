from unittest.mock import patch, MagicMock

from claude_usage_widget.api_client import fetch_usage, parse_usage_response, AuthError, TransientError, fetch_usage_with_retry

# 실제 claude.ai 응답은 utilization/percent를 소수로 내려준다 -- 예전엔 이 픽스처가
# 정수라서, 소수를 그대로 흘려보내던 버그(위젯에 "10.4"가 그려져 앞자리가 잘림)를
# 테스트가 잡지 못했다.
SAMPLE_RESPONSE = {
    "five_hour": {"utilization": 9.4, "resets_at": "2026-07-14T09:00:00.491813+00:00"},
    "seven_day": {"utilization": 17.0, "resets_at": "2026-07-19T02:00:00.491842+00:00"},
    "limits": [
        {"kind": "session", "percent": 9.4, "resets_at": "2026-07-14T09:00:00.491813+00:00"},
        {"kind": "weekly_all", "percent": 17.0, "resets_at": "2026-07-19T02:00:00.491842+00:00"},
        {
            "kind": "weekly_scoped",
            "percent": 18.6,
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


def test_parse_usage_response_rounds_fractional_percents_to_int():
    """위젯은 정수 자릿수에 맞춰 그려서 "10.4" 같은 값은 창 밖으로 잘린다.
    소수는 파싱 경계에서 정수로 정리돼야 한다."""
    snapshot = parse_usage_response(SAMPLE_RESPONSE)
    for value in (
        snapshot.session.percent,
        snapshot.weekly_all.percent,
        snapshot.weekly_scoped[0].percent,
        snapshot.credit.percent,
    ):
        assert isinstance(value, int)
    assert snapshot.session.percent == 9  # 9.4 -> 9
    assert snapshot.weekly_scoped[0].percent == 19  # 18.6 -> 19


def test_parse_usage_response_tolerates_null_resets_at():
    """claude.ai는 아직 한 번도 안 쓴 weekly_scoped 한도의 resets_at을 null로
    내려준다(2026-08-03부터 실사용자 로그에서 관찰됨). 예전 코드는 이때
    value.replace(...)에서 AttributeError로 죽었는데, TransientError가 아니라서
    fetch_usage_with_retry의 재시도도 안 타고 매 새로고침마다 즉시 실패했다."""
    data = dict(SAMPLE_RESPONSE)
    data["limits"] = list(SAMPLE_RESPONSE["limits"])
    data["limits"][-1] = {
        "kind": "weekly_scoped",
        "percent": 0,
        "resets_at": None,
        "scope": {"model": {"display_name": "Fable"}},
    }
    snapshot = parse_usage_response(data)
    assert snapshot.weekly_scoped[0].resets_at is None
    assert snapshot.weekly_scoped[0].percent == 0


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
