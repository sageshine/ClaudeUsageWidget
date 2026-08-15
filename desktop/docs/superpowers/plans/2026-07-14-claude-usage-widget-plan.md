# Claude 사용량 위젯 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** claude.ai(Pro/Max) 세션/주간 사용량과 크레딧을 항상 떠있는 작은 캐릭터 위젯으로 보여주는 Windows 데스크톱 앱을 만든다.

**Architecture:** Python 3.11 단일 프로세스. Tkinter로 떠다니는 캐릭터 위젯과 상세 패널/설정창을 그리고, pystray로 트레이 아이콘을 띄운다. 백그라운드 타이머가 claude.ai 내부 사용량 API(`GET /api/organizations/{org_id}/usage`)를 주기적으로 호출해 상태를 갱신한다. PyInstaller로 `.exe` 하나로 패키징한다.

**Tech Stack:** Python 3.11+, `requests`, `keyring` (Windows Credential Manager 백엔드), `pystray` + `Pillow` (트레이 아이콘), stdlib `tkinter`/`winreg`/`json`/`logging`, `pytest` (테스트), `PyInstaller` (패키징)

## Global Constraints

- Windows 전용 (winreg, Windows Credential Manager 사용) — 다른 OS 지원 불필요
- `sessionKey` 쿠키 값은 평문 파일에 절대 저장하지 않는다 — 반드시 `keyring`을 통해 Windows Credential Manager에만 저장
- 새로고침 주기는 최소 60초 (설정 UI에서 강제)
- 비공식 API를 사용한다는 점을 최초 실행 시 사용자에게 고지한다 (설계 문서 "보안 고지" 참고)
- 최종 산출물은 `PyInstaller --onefile --windowed`로 만든 단일 `ClaudeUsageWidget.exe`
- 확정된 API 계약(설계 문서 참고): `GET https://claude.ai/api/organizations/{org_id}/usage`, 요청 헤더 `Cookie: sessionKey=<값>`, 응답의 `five_hour.utilization`(세션 %), `seven_day.utilization`(주간 전체 %), `limits[kind=weekly_scoped]`(모델별 주간 %), `spend`(크레딧)
- 모든 사용자 대면 텍스트는 한국어

---

## Task 1: 프로젝트 스캐폴딩 + 설정(config) 모듈

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `conftest.py`
- Create: `src/claude_usage_widget/__init__.py`
- Create: `src/claude_usage_widget/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.DEFAULT_CONFIG: dict`, `config.config_dir() -> pathlib.Path`, `config.config_path() -> pathlib.Path`, `config.load_config() -> dict`, `config.save_config(config: dict) -> None`

- [ ] **Step 1: 프로젝트 뼈대 파일 작성**

`requirements.txt`:
```
requests>=2.31
keyring>=24.0
pystray>=0.19
Pillow>=10.0
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=7.4
pyinstaller>=6.0
```

`.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
build/
dist/
*.spec
.venv/
```

`conftest.py` (루트, `src/` 레이아웃을 pytest에서 임포트 가능하게 함):
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
```

`src/claude_usage_widget/__init__.py`:
```python
```
(빈 파일)

- [ ] **Step 2: config 모듈의 실패하는 테스트 작성**

`tests/test_config.py`:
```python
from claude_usage_widget import config


def test_load_config_returns_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    result = config.load_config()
    assert result["refresh_interval_seconds"] == 180
    assert result["thresholds"] == {"warning": 60, "danger": 85}
    assert result["autostart_enabled"] is False


def test_save_then_load_round_trips_values(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    data = config.load_config()
    data["org_id"] = "org-123"
    data["refresh_interval_seconds"] = 300
    config.save_config(data)

    reloaded = config.load_config()
    assert reloaded["org_id"] == "org-123"
    assert reloaded["refresh_interval_seconds"] == 300


def test_load_config_recovers_from_corrupt_file(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    config.config_dir()  # ensures dir exists
    config.config_path().write_text("{not valid json", encoding="utf-8")

    result = config.load_config()
    assert result["refresh_interval_seconds"] == 180
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.config'` (또는 `config` 미정의 관련 오류)

- [ ] **Step 4: config.py 구현**

`src/claude_usage_widget/config.py`:
```python
import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "refresh_interval_seconds": 180,
    "widget_position": None,
    "thresholds": {"warning": 60, "danger": 85},
    "show_credit": False,
    "autostart_enabled": False,
    "org_id": None,
}


def config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    d = base / "ClaudeUsageWidget"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save_config(config: dict) -> None:
    path = config_path()
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: 커밋**

```bash
git add requirements.txt requirements-dev.txt .gitignore conftest.py src/claude_usage_widget/__init__.py src/claude_usage_widget/config.py tests/test_config.py
git commit -m "Add project scaffolding and config module"
```

---

## Task 2: 로깅 모듈

**Files:**
- Create: `src/claude_usage_widget/logging_setup.py`
- Test: `tests/test_logging_setup.py`

**Interfaces:**
- Consumes: `config.config_dir() -> pathlib.Path` (Task 1)
- Produces: `logging_setup.get_logger() -> logging.Logger`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_logging_setup.py`:
```python
from claude_usage_widget import logging_setup, config


def test_get_logger_writes_to_appdata_log_file(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # 모듈이 이미 핸들러를 캐싱하지 않도록 로거 이름을 초기화
    logging_setup._reset_for_tests()

    logger = logging_setup.get_logger()
    logger.info("hello widget")
    for handler in logger.handlers:
        handler.flush()

    log_file = config.config_dir() / "log.txt"
    assert log_file.exists()
    assert "hello widget" in log_file.read_text(encoding="utf-8")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_logging_setup.py -v`
Expected: FAIL with `ModuleNotFoundError` 또는 `AttributeError: module has no attribute 'get_logger'`

- [ ] **Step 3: logging_setup.py 구현**

`src/claude_usage_widget/logging_setup.py`:
```python
import logging

from .config import config_dir

_LOGGER_NAME = "claude_usage_widget"


def get_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_path = config_dir() / "log.txt"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def _reset_for_tests() -> None:
    logger = logging.getLogger(_LOGGER_NAME)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_logging_setup.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/claude_usage_widget/logging_setup.py tests/test_logging_setup.py
git commit -m "Add file-based logging setup"
```

---

## Task 3: 자격 증명 저장소 (Windows Credential Manager 연동)

**Files:**
- Create: `src/claude_usage_widget/credential_store.py`
- Test: `tests/test_credential_store.py`

**Interfaces:**
- Produces: `credential_store.save_session_key(value: str) -> None`, `credential_store.load_session_key() -> str | None`, `credential_store.delete_session_key() -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_credential_store.py`:
```python
from claude_usage_widget import credential_store


class _FakeKeyring:
    def __init__(self):
        self._store = {}

    def set_password(self, service, username, value):
        self._store[(service, username)] = value

    def get_password(self, service, username):
        return self._store.get((service, username))

    def delete_password(self, service, username):
        del self._store[(service, username)]


def test_save_and_load_session_key(monkeypatch):
    fake = _FakeKeyring()
    monkeypatch.setattr(credential_store.keyring, "set_password", fake.set_password)
    monkeypatch.setattr(credential_store.keyring, "get_password", fake.get_password)

    credential_store.save_session_key("abc123")
    assert credential_store.load_session_key() == "abc123"


def test_load_session_key_returns_none_when_missing(monkeypatch):
    fake = _FakeKeyring()
    monkeypatch.setattr(credential_store.keyring, "get_password", fake.get_password)

    assert credential_store.load_session_key() is None


def test_delete_session_key_is_safe_when_missing(monkeypatch):
    fake = _FakeKeyring()

    class _Errors:
        class PasswordDeleteError(Exception):
            pass

    def fake_delete(service, username):
        raise _Errors.PasswordDeleteError()

    monkeypatch.setattr(credential_store.keyring, "delete_password", fake_delete)
    monkeypatch.setattr(credential_store.keyring.errors, "PasswordDeleteError", _Errors.PasswordDeleteError)

    credential_store.delete_session_key()  # 예외가 밖으로 새어나오지 않아야 함
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_credential_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.credential_store'`

- [ ] **Step 3: credential_store.py 구현**

`src/claude_usage_widget/credential_store.py`:
```python
import keyring
import keyring.errors

SERVICE_NAME = "ClaudeUsageWidget"
SESSION_KEY_USERNAME = "sessionKey"


def save_session_key(value: str) -> None:
    keyring.set_password(SERVICE_NAME, SESSION_KEY_USERNAME, value)


def load_session_key() -> str | None:
    return keyring.get_password(SERVICE_NAME, SESSION_KEY_USERNAME)


def delete_session_key() -> None:
    try:
        keyring.delete_password(SERVICE_NAME, SESSION_KEY_USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_credential_store.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/claude_usage_widget/credential_store.py tests/test_credential_store.py
git commit -m "Add Windows Credential Manager-backed session key storage"
```

---

## Task 4: 데이터 모델 + API 클라이언트 (정상 경로)

**Files:**
- Create: `src/claude_usage_widget/models.py`
- Create: `src/claude_usage_widget/api_client.py`
- Test: `tests/test_api_client.py`

**Interfaces:**
- Produces (models.py): `LimitInfo(percent: int, resets_at: datetime)`, `ScopedLimit(model_name: str, percent: int, resets_at: datetime)`, `CreditInfo(enabled: bool, percent: int, used_dollars: float, limit_dollars: float | None)`, `UsageSnapshot(session: LimitInfo, weekly_all: LimitInfo, weekly_scoped: list[ScopedLimit], credit: CreditInfo, fetched_at: datetime)`
- Produces (api_client.py): `AuthError(Exception)`, `TransientError(Exception)`, `fetch_usage(session_key: str, org_id: str, timeout: float = 10.0) -> UsageSnapshot`, `parse_usage_response(data: dict) -> UsageSnapshot`

- [ ] **Step 1: models.py 작성**

`src/claude_usage_widget/models.py`:
```python
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LimitInfo:
    percent: int
    resets_at: datetime


@dataclass
class ScopedLimit:
    model_name: str
    percent: int
    resets_at: datetime


@dataclass
class CreditInfo:
    enabled: bool
    percent: int
    used_dollars: float
    limit_dollars: float | None


@dataclass
class UsageSnapshot:
    session: LimitInfo
    weekly_all: LimitInfo
    weekly_scoped: list
    credit: CreditInfo
    fetched_at: datetime
```

- [ ] **Step 2: 실패하는 테스트 작성 (파싱 + 정상 요청)**

`tests/test_api_client.py`:
```python
from unittest.mock import patch, MagicMock

from claude_usage_widget.api_client import fetch_usage, parse_usage_response, AuthError, TransientError

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
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python -m pytest tests/test_api_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.api_client'`

- [ ] **Step 4: api_client.py 구현 (정상 경로 + 상태코드 분기)**

`src/claude_usage_widget/api_client.py`:
```python
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_api_client.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: 커밋**

```bash
git add src/claude_usage_widget/models.py src/claude_usage_widget/api_client.py tests/test_api_client.py
git commit -m "Add usage models and claude.ai usage API client"
```

---

## Task 5: API 재시도/백오프 로직

**Files:**
- Modify: `src/claude_usage_widget/api_client.py`
- Modify: `tests/test_api_client.py`

**Interfaces:**
- Consumes: `fetch_usage`, `AuthError`, `TransientError` (Task 4)
- Produces: `fetch_usage_with_retry(session_key: str, org_id: str, max_attempts: int = 5, base_delay: float = 2.0, max_delay: float = 900.0, sleep_fn=time.sleep) -> UsageSnapshot`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_api_client.py`에 추가:
```python
from claude_usage_widget.api_client import fetch_usage_with_retry


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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_api_client.py -v`
Expected: FAIL with `ImportError: cannot import name 'fetch_usage_with_retry'`

- [ ] **Step 3: fetch_usage_with_retry 구현**

`src/claude_usage_widget/api_client.py`의 끝에 추가:
```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_api_client.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/claude_usage_widget/api_client.py tests/test_api_client.py
git commit -m "Add exponential backoff retry wrapper for usage fetch"
```

---

## Task 6: 위젯 상태 로직 (순수 함수)

**Files:**
- Create: `src/claude_usage_widget/widget_state.py`
- Test: `tests/test_widget_state.py`

**Interfaces:**
- Consumes: `UsageSnapshot`, `LimitInfo`, `ScopedLimit`, `CreditInfo` (Task 4), `AuthError` (Task 4)
- Produces: `Mood(str, Enum)` with values `CALM, WARNING, DANGER, AUTH_ERROR, SETUP_NEEDED`, `MOOD_COLORS: dict[Mood, str]`, `MOOD_FACES: dict[Mood, str]`, `WidgetState(mood, headline_percent, tooltip, detail_rows)` where `detail_rows: list[tuple[str, int | None]]`, `compute_widget_state(snapshot: UsageSnapshot, thresholds: dict) -> WidgetState`, `resolve_state(result, thresholds: dict) -> WidgetState` (`result`은 `UsageSnapshot | Exception | None`)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_widget_state.py`:
```python
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
    state = compute_widget_state(_snapshot(9, 17), THRESHOLDS)
    assert state.mood == Mood.CALM
    assert state.headline_percent == 17


def test_compute_widget_state_warning_at_threshold():
    state = compute_widget_state(_snapshot(60, 10), THRESHOLDS)
    assert state.mood == Mood.WARNING


def test_compute_widget_state_danger_at_threshold():
    state = compute_widget_state(_snapshot(10, 85), THRESHOLDS)
    assert state.mood == Mood.DANGER


def test_compute_widget_state_includes_scoped_and_credit_rows_when_enabled():
    state = compute_widget_state(_snapshot(9, 17, credit_enabled=True), THRESHOLDS)
    labels = [row[0] for row in state.detail_rows]
    assert any("Fable" in label for label in labels)
    assert any("크레딧" in label for label in labels)


def test_compute_widget_state_omits_credit_row_when_disabled():
    state = compute_widget_state(_snapshot(9, 17, credit_enabled=False), THRESHOLDS)
    labels = [row[0] for row in state.detail_rows]
    assert not any("크레딧" in label for label in labels)


def test_resolve_state_setup_needed_when_result_is_none():
    state = resolve_state(None, THRESHOLDS)
    assert state.mood == Mood.SETUP_NEEDED


def test_resolve_state_auth_error_when_result_is_auth_error():
    state = resolve_state(AuthError("expired"), THRESHOLDS)
    assert state.mood == Mood.AUTH_ERROR


def test_resolve_state_warning_when_result_is_other_exception():
    state = resolve_state(TransientError("network"), THRESHOLDS)
    assert state.mood == Mood.WARNING


def test_resolve_state_delegates_to_compute_widget_state_for_snapshot():
    state = resolve_state(_snapshot(9, 17), THRESHOLDS)
    assert state.mood == Mood.CALM
    assert state.headline_percent == 17
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_widget_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.widget_state'`

- [ ] **Step 3: widget_state.py 구현**

`src/claude_usage_widget/widget_state.py`:
```python
from dataclasses import dataclass
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


def compute_widget_state(snapshot: UsageSnapshot, thresholds: dict) -> WidgetState:
    headline = max(snapshot.session.percent, snapshot.weekly_all.percent)
    if headline >= thresholds["danger"]:
        mood = Mood.DANGER
    elif headline >= thresholds["warning"]:
        mood = Mood.WARNING
    else:
        mood = Mood.CALM

    tooltip = f"세션 {snapshot.session.percent}% · 주간 {snapshot.weekly_all.percent}%"

    rows = [
        ("현재 세션", snapshot.session.percent),
        ("주간 한도 (전체 모델)", snapshot.weekly_all.percent),
    ]
    for scoped in snapshot.weekly_scoped:
        rows.append((f"주간 한도 ({scoped.model_name})", scoped.percent))
    if snapshot.credit.enabled:
        rows.append((f"사용 크레딧 (${snapshot.credit.used_dollars:.2f})", snapshot.credit.percent))

    return WidgetState(mood=mood, headline_percent=headline, tooltip=tooltip, detail_rows=rows)


def resolve_state(result, thresholds: dict) -> WidgetState:
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
    return compute_widget_state(result, thresholds)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_widget_state.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/claude_usage_widget/widget_state.py tests/test_widget_state.py
git commit -m "Add pure widget-state derivation logic"
```

---

## Task 7: 떠다니는 캐릭터 위젯 (Tkinter)

**Files:**
- Create: `src/claude_usage_widget/widget.py`
- Test: `tests/test_widget.py`

**Interfaces:**
- Consumes: `WidgetState`, `Mood`, `MOOD_COLORS`, `MOOD_FACES` (Task 6)
- Produces: `CharacterWidget(root, initial_pos: tuple[int, int], on_move, on_right_click)` with `.SIZE: int` (클래스 변수), `.top: tk.Toplevel`, `.apply_state(state: WidgetState) -> None`

> 이 태스크의 테스트는 실제 화면(디스플레이)이 있는 Windows 데스크톱 세션에서 실행해야 한다. 짧게 작은 창이 화면에 나타났다 사라질 수 있다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_widget.py`:
```python
from types import SimpleNamespace
import tkinter as tk

import pytest

from claude_usage_widget.widget import CharacterWidget
from claude_usage_widget.widget_state import Mood, MOOD_COLORS, MOOD_FACES, WidgetState


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_apply_state_updates_color_and_face(root):
    moves = []
    clicks = []
    widget = CharacterWidget(root, (10, 10), on_move=moves.append, on_right_click=lambda: clicks.append(1))

    state = WidgetState(mood=Mood.DANGER, headline_percent=90, tooltip="t", detail_rows=[])
    widget.apply_state(state)

    assert widget.canvas.itemcget(widget._circle, "fill") == MOOD_COLORS[Mood.DANGER]
    assert widget.canvas.itemcget(widget._face, "text") == MOOD_FACES[Mood.DANGER]
    widget.top.destroy()


def test_drag_reports_new_position_via_on_move(root):
    moves = []
    widget = CharacterWidget(root, (10, 10), on_move=moves.append, on_right_click=lambda: None)

    widget._start_drag(SimpleNamespace(x=5, y=5))
    widget._do_drag(SimpleNamespace(x=15, y=20))
    widget._end_drag(SimpleNamespace(x=15, y=20))

    assert len(moves) == 1
    assert isinstance(moves[0][0], int)
    assert isinstance(moves[0][1], int)
    widget.top.destroy()


def test_right_click_invokes_callback(root):
    clicks = []
    widget = CharacterWidget(root, (10, 10), on_move=lambda pos: None, on_right_click=lambda: clicks.append(1))

    widget.canvas.event_generate("<Button-3>")
    root.update()

    assert clicks == [1]
    widget.top.destroy()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_widget.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.widget'`

- [ ] **Step 3: widget.py 구현**

`src/claude_usage_widget/widget.py`:
```python
import tkinter as tk

from .widget_state import MOOD_COLORS, MOOD_FACES, WidgetState

_TRANSPARENT_KEY = "magenta"


class CharacterWidget:
    SIZE = 56

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
        self.top.geometry(f"{self.SIZE}x{self.SIZE}+{x}+{y}")

        self.canvas = tk.Canvas(
            self.top, width=self.SIZE, height=self.SIZE, bg=_TRANSPARENT_KEY, highlightthickness=0
        )
        self.canvas.pack()
        first_mood = next(iter(MOOD_COLORS))
        self._circle = self.canvas.create_oval(2, 2, self.SIZE - 2, self.SIZE - 2, fill=MOOD_COLORS[first_mood], outline="")
        self._face = self.canvas.create_text(self.SIZE / 2, self.SIZE / 2, text="", font=("Segoe UI", 16))

        self._on_move = on_move
        self._on_right_click = on_right_click
        self._drag_start = None
        self._tooltip_win = None
        self._tooltip_text = ""

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._do_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", lambda event: self._on_right_click())
        self.canvas.bind("<Enter>", self._show_tooltip)
        self.canvas.bind("<Leave>", self._hide_tooltip)

    def apply_state(self, state: WidgetState) -> None:
        self.canvas.itemconfig(self._circle, fill=MOOD_COLORS[state.mood])
        self.canvas.itemconfig(self._face, text=MOOD_FACES[state.mood])
        self._tooltip_text = state.tooltip

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
        x = self.top.winfo_x() + self.SIZE + 5
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_widget.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/claude_usage_widget/widget.py tests/test_widget.py
git commit -m "Add draggable floating character widget"
```

---

## Task 8: 상세 패널 팝업

**Files:**
- Create: `src/claude_usage_widget/detail_panel.py`
- Test: `tests/test_detail_panel.py`

**Interfaces:**
- Produces: `DetailPanel(root, on_refresh, on_open_settings, on_quit)` with `.show_at(x: int, y: int) -> None`, `.hide() -> None`, `.render(rows: list[tuple[str, int | None]], updated_text: str) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_detail_panel.py`:
```python
import tkinter as tk

import pytest

from claude_usage_widget.detail_panel import DetailPanel


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_render_creates_one_row_per_entry_and_sets_updated_label(root):
    panel = DetailPanel(root, on_refresh=lambda: None, on_open_settings=lambda: None, on_quit=lambda: None)

    panel.render(
        rows=[("현재 세션", 9), ("주간 한도 (전체 모델)", 17), ("재로그인 필요 안내", None)],
        updated_text="마지막 업데이트: 방금",
    )

    assert len(panel._row_widgets) == 3
    assert panel.updated_label.cget("text") == "마지막 업데이트: 방금"
    panel.top.destroy()


def test_render_replaces_previous_rows(root):
    panel = DetailPanel(root, on_refresh=lambda: None, on_open_settings=lambda: None, on_quit=lambda: None)

    panel.render(rows=[("a", 1), ("b", 2)], updated_text="t1")
    panel.render(rows=[("c", 3)], updated_text="t2")

    assert len(panel._row_widgets) == 1
    panel.top.destroy()


def test_refresh_button_invokes_callback(root):
    calls = []
    panel = DetailPanel(root, on_refresh=lambda: calls.append(1), on_open_settings=lambda: None, on_quit=lambda: None)
    panel._refresh_button.invoke()
    assert calls == [1]
    panel.top.destroy()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_detail_panel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.detail_panel'`

- [ ] **Step 3: detail_panel.py 구현**

`src/claude_usage_widget/detail_panel.py`:
```python
import tkinter as tk
from tkinter import ttk


class DetailPanel:
    def __init__(self, root, on_refresh, on_open_settings, on_quit):
        self.top = tk.Toplevel(root)
        self.top.title("Claude 사용량")
        self.top.attributes("-topmost", True)
        self.top.resizable(False, False)

        self.updated_label = ttk.Label(self.top, text="마지막 업데이트: -")
        self.updated_label.pack(anchor="w", padx=10, pady=(10, 0))

        self.rows_frame = ttk.Frame(self.top)
        self.rows_frame.pack(fill="x", padx=10, pady=10)
        self._row_widgets = []

        btns = ttk.Frame(self.top)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        self._refresh_button = ttk.Button(btns, text="새로고침", command=on_refresh)
        self._refresh_button.pack(side="left")
        ttk.Button(btns, text="설정", command=on_open_settings).pack(side="left", padx=5)
        ttk.Button(btns, text="종료", command=on_quit).pack(side="right")

        self.top.withdraw()

    def show_at(self, x: int, y: int) -> None:
        self.top.geometry(f"+{x}+{y}")
        self.top.deiconify()
        self.top.lift()

    def hide(self) -> None:
        self.top.withdraw()

    def render(self, rows, updated_text: str) -> None:
        for widget in self._row_widgets:
            widget.destroy()
        self._row_widgets = []
        self.updated_label.config(text=updated_text)

        for label_text, percent in rows:
            row = ttk.Frame(self.rows_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label_text, anchor="w").pack(side="left", fill="x", expand=True)
            if percent is not None:
                bar = ttk.Progressbar(row, length=140, maximum=100, value=min(percent, 100))
                bar.pack(side="left", padx=5)
                ttk.Label(row, text=f"{percent}%").pack(side="left")
            self._row_widgets.append(row)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_detail_panel.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/claude_usage_widget/detail_panel.py tests/test_detail_panel.py
git commit -m "Add usage detail panel mirroring claude.ai usage screen"
```

---

## Task 9: 트레이 아이콘

**Files:**
- Create: `src/claude_usage_widget/tray.py`
- Test: `tests/test_tray.py`

**Interfaces:**
- Consumes: `Mood`, `MOOD_COLORS` (Task 6)
- Produces: `make_icon_image(mood: Mood) -> PIL.Image.Image`, `build_tray_icon(initial_mood: Mood, on_toggle_widget, on_open_settings, on_quit) -> pystray.Icon`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_tray.py`:
```python
from claude_usage_widget.tray import make_icon_image, _hex_to_rgb
from claude_usage_widget.widget_state import Mood, MOOD_COLORS


def test_make_icon_image_size_and_mode():
    img = make_icon_image(Mood.CALM)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_make_icon_image_center_pixel_matches_mood_color():
    img = make_icon_image(Mood.DANGER)
    r, g, b, a = img.getpixel((32, 32))
    expected = _hex_to_rgb(MOOD_COLORS[Mood.DANGER])
    assert (r, g, b) == expected
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_tray.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.tray'`

- [ ] **Step 3: tray.py 구현**

`src/claude_usage_widget/tray.py`:
```python
import pystray
from PIL import Image, ImageDraw

from .widget_state import Mood, MOOD_COLORS


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def make_icon_image(mood: Mood) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, size - 2, size - 2), fill=MOOD_COLORS[mood])
    return img


def build_tray_icon(initial_mood: Mood, on_toggle_widget, on_open_settings, on_quit):
    menu = pystray.Menu(
        pystray.MenuItem("위젯 표시/숨김", lambda icon, item: on_toggle_widget()),
        pystray.MenuItem("설정", lambda icon, item: on_open_settings()),
        pystray.MenuItem("종료", lambda icon, item: on_quit()),
    )
    return pystray.Icon("claude_usage_widget", make_icon_image(initial_mood), "Claude 사용량", menu)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_tray.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/claude_usage_widget/tray.py tests/test_tray.py
git commit -m "Add system tray icon rendering"
```

---

## Task 10: 설정 화면

**Files:**
- Create: `src/claude_usage_widget/settings_ui.py`
- Test: `tests/test_settings_ui.py`

**Interfaces:**
- Consumes: `config.DEFAULT_CONFIG` 형태의 `config: dict` (Task 1)
- Produces: `SettingsDialog(root, config: dict, on_save)` with `.show() -> None`. `on_save`는 `{"session_key": str | None, "org_id": str | None, "refresh_interval_seconds": int, "thresholds": {"warning": int, "danger": int}, "show_credit": bool, "autostart_enabled": bool}` dict 하나를 인자로 호출됨

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_settings_ui.py`:
```python
import tkinter as tk

import pytest

from claude_usage_widget import settings_ui
from claude_usage_widget.config import DEFAULT_CONFIG


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_save_calls_on_save_with_expected_values(root, monkeypatch):
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda *a, **k: None)
    saved = []
    dialog = settings_ui.SettingsDialog(root, dict(DEFAULT_CONFIG), on_save=saved.append)

    dialog.session_key_var.set("  secret-token  ")
    dialog.org_id_var.set("org-1")
    dialog.interval_var.set(120)
    dialog.warning_var.set(50)
    dialog.danger_var.set(80)
    dialog.credit_var.set(True)
    dialog.autostart_var.set(True)

    dialog._save()

    assert len(saved) == 1
    result = saved[0]
    assert result["session_key"] == "secret-token"
    assert result["org_id"] == "org-1"
    assert result["refresh_interval_seconds"] == 120
    assert result["thresholds"] == {"warning": 50, "danger": 80}
    assert result["show_credit"] is True
    assert result["autostart_enabled"] is True
    dialog.top.destroy()


def test_save_rejects_warning_threshold_greater_than_or_equal_danger(root, monkeypatch):
    errors = []
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda title, msg: errors.append(msg))
    saved = []
    dialog = settings_ui.SettingsDialog(root, dict(DEFAULT_CONFIG), on_save=saved.append)

    dialog.warning_var.set(90)
    dialog.danger_var.set(80)
    dialog._save()

    assert saved == []
    assert len(errors) == 1
    dialog.top.destroy()


def test_enforces_minimum_refresh_interval_of_60_seconds(root, monkeypatch):
    monkeypatch.setattr(settings_ui.messagebox, "showerror", lambda *a, **k: None)
    saved = []
    dialog = settings_ui.SettingsDialog(root, dict(DEFAULT_CONFIG), on_save=saved.append)

    dialog.interval_var.set(10)
    dialog._save()

    assert saved[0]["refresh_interval_seconds"] == 60
    dialog.top.destroy()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_settings_ui.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.settings_ui'`

- [ ] **Step 3: settings_ui.py 구현**

`src/claude_usage_widget/settings_ui.py`:
```python
import tkinter as tk
from tkinter import messagebox, ttk


class SettingsDialog:
    def __init__(self, root, config: dict, on_save):
        self.top = tk.Toplevel(root)
        self.top.title("설정")
        self.top.resizable(False, False)
        self._on_save = on_save

        self.session_key_var = tk.StringVar()
        self.org_id_var = tk.StringVar(value=config.get("org_id") or "")
        self.interval_var = tk.IntVar(value=config["refresh_interval_seconds"])
        self.warning_var = tk.IntVar(value=config["thresholds"]["warning"])
        self.danger_var = tk.IntVar(value=config["thresholds"]["danger"])
        self.credit_var = tk.BooleanVar(value=config["show_credit"])
        self.autostart_var = tk.BooleanVar(value=config["autostart_enabled"])

        self._build_form()
        self.top.withdraw()

    def _build_form(self):
        pad = {"padx": 10, "pady": 4}
        ttk.Label(self.top, text="sessionKey 쿠키 값").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(self.top, textvariable=self.session_key_var, width=40, show="*").grid(row=0, column=1, **pad)

        ttk.Label(self.top, text="Organization ID").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(self.top, textvariable=self.org_id_var, width=40).grid(row=1, column=1, **pad)

        ttk.Label(self.top, text="새로고침 주기(초, 최소 60)").grid(row=2, column=0, sticky="w", **pad)
        ttk.Spinbox(self.top, from_=60, to=3600, textvariable=self.interval_var, width=10).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(self.top, text="주의 임계값(%)").grid(row=3, column=0, sticky="w", **pad)
        ttk.Spinbox(self.top, from_=1, to=99, textvariable=self.warning_var, width=10).grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(self.top, text="위험 임계값(%)").grid(row=4, column=0, sticky="w", **pad)
        ttk.Spinbox(self.top, from_=1, to=100, textvariable=self.danger_var, width=10).grid(row=4, column=1, sticky="w", **pad)

        ttk.Checkbutton(self.top, text="사용 크레딧 표시", variable=self.credit_var).grid(row=5, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(self.top, text="PC 시작 시 자동 실행", variable=self.autostart_var).grid(row=6, column=0, columnspan=2, sticky="w", **pad)

        ttk.Button(self.top, text="저장", command=self._save).grid(row=7, column=0, columnspan=2, pady=10)

    def show(self) -> None:
        self.top.deiconify()
        self.top.lift()

    def _save(self):
        if self.warning_var.get() >= self.danger_var.get():
            messagebox.showerror("설정 오류", "주의 임계값은 위험 임계값보다 작아야 해요.")
            return

        result = {
            "session_key": self.session_key_var.get().strip() or None,
            "org_id": self.org_id_var.get().strip() or None,
            "refresh_interval_seconds": max(60, self.interval_var.get()),
            "thresholds": {"warning": self.warning_var.get(), "danger": self.danger_var.get()},
            "show_credit": self.credit_var.get(),
            "autostart_enabled": self.autostart_var.get(),
        }
        self._on_save(result)
        self.top.withdraw()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_settings_ui.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/claude_usage_widget/settings_ui.py tests/test_settings_ui.py
git commit -m "Add settings dialog"
```

---

## Task 11: 자동 시작 (Windows 레지스트리)

**Files:**
- Create: `src/claude_usage_widget/autostart.py`
- Test: `tests/test_autostart.py`

**Interfaces:**
- Produces: `enable_autostart(exe_path: str | None = None) -> None`, `disable_autostart() -> None`, `is_autostart_enabled() -> bool`

> 이 태스크의 테스트는 `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`에 실제로 값을 썼다가 지운다 (관리자 권한 불필요, 사용자 본인 하이브). 테스트는 `finally`로 항상 정리한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_autostart.py`:
```python
from claude_usage_widget import autostart


def test_enable_then_disable_autostart_round_trip():
    fake_exe = r"C:\fake\path\ClaudeUsageWidget.exe"
    try:
        assert autostart.is_autostart_enabled() is False
        autostart.enable_autostart(fake_exe)
        assert autostart.is_autostart_enabled() is True
    finally:
        autostart.disable_autostart()
    assert autostart.is_autostart_enabled() is False


def test_disable_autostart_is_safe_when_not_set():
    autostart.disable_autostart()  # 예외 없이 통과해야 함
    assert autostart.is_autostart_enabled() is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_autostart.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.autostart'`

- [ ] **Step 3: autostart.py 구현**

`src/claude_usage_widget/autostart.py`:
```python
import sys
import winreg

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ClaudeUsageWidget"


def _executable_path() -> str:
    return sys.executable if getattr(sys, "frozen", False) else sys.argv[0]


def enable_autostart(exe_path: str | None = None) -> None:
    path = exe_path or _executable_path()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, f'"{path}"')


def disable_autostart() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass


def is_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except FileNotFoundError:
        return False
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_autostart.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/claude_usage_widget/autostart.py tests/test_autostart.py
git commit -m "Add Windows Run-key based autostart toggle"
```

---

## Task 12: 앱 오케스트레이션 (app.py + 실행 진입점)

**Files:**
- Create: `src/claude_usage_widget/app.py`
- Create: `run.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: 모든 이전 태스크의 모듈 (`config`, `logging_setup`, `credential_store`, `api_client.fetch_usage_with_retry`, `widget_state.resolve_state`/`Mood`, `widget.CharacterWidget`, `detail_panel.DetailPanel`, `settings_ui.SettingsDialog`, `tray.build_tray_icon`/`make_icon_image`, `autostart.enable_autostart`/`disable_autostart`)
- Produces: `App` 클래스 (`.run()`), `main() -> None`

- [ ] **Step 1: 실패하는 테스트 작성 (GUI 생성 없이 순수 오케스트레이션 로직만 검증)**

`tests/test_app.py`:
```python
from claude_usage_widget import app as app_module
from claude_usage_widget import config as config_module


def test_on_settings_saved_persists_config_and_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    saved = {}
    monkeypatch.setattr(app_module.credential_store, "save_session_key", lambda v: saved.setdefault("session_key", v))
    monkeypatch.setattr(app_module, "enable_autostart", lambda: saved.setdefault("autostart", "enabled"))
    monkeypatch.setattr(app_module, "disable_autostart", lambda: saved.setdefault("autostart", "disabled"))

    instance = app_module.App.__new__(app_module.App)
    instance.config = config_module.load_config()
    instance._timer = None
    instance._notified_auth_error = False
    instance._refresh_and_reschedule_cancel_old = lambda: saved.setdefault("rescheduled", True)

    instance._on_settings_saved({
        "session_key": "secret-token",
        "org_id": "org-42",
        "refresh_interval_seconds": 120,
        "thresholds": {"warning": 50, "danger": 80},
        "show_credit": True,
        "autostart_enabled": True,
    })

    assert saved["session_key"] == "secret-token"
    assert saved["autostart"] == "enabled"
    assert saved["rescheduled"] is True
    assert instance.config["org_id"] == "org-42"
    assert instance.config["thresholds"] == {"warning": 50, "danger": 80}

    reloaded = config_module.load_config()
    assert reloaded["org_id"] == "org-42"


def test_on_settings_saved_disables_autostart_when_unchecked(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    saved = {}
    monkeypatch.setattr(app_module.credential_store, "save_session_key", lambda v: None)
    monkeypatch.setattr(app_module, "enable_autostart", lambda: saved.setdefault("autostart", "enabled"))
    monkeypatch.setattr(app_module, "disable_autostart", lambda: saved.setdefault("autostart", "disabled"))

    instance = app_module.App.__new__(app_module.App)
    instance.config = config_module.load_config()
    instance._timer = None
    instance._notified_auth_error = False
    instance._refresh_and_reschedule_cancel_old = lambda: None

    instance._on_settings_saved({
        "session_key": None,
        "org_id": "org-42",
        "refresh_interval_seconds": 120,
        "thresholds": {"warning": 50, "danger": 80},
        "show_credit": False,
        "autostart_enabled": False,
    })

    assert saved["autostart"] == "disabled"


def test_fetch_result_returns_none_when_credentials_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(app_module.credential_store, "load_session_key", lambda: None)

    instance = app_module.App.__new__(app_module.App)
    instance.config = {"org_id": None}

    assert instance._fetch_result() is None


def test_fetch_result_returns_exception_when_fetch_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(app_module.credential_store, "load_session_key", lambda: "key")

    def raise_error(session_key, org_id):
        raise app_module.AuthError("expired")

    monkeypatch.setattr(app_module, "fetch_usage_with_retry", raise_error)

    instance = app_module.App.__new__(app_module.App)
    instance.config = {"org_id": "org-1"}

    result = instance._fetch_result()
    assert isinstance(result, app_module.AuthError)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'claude_usage_widget.app'`

- [ ] **Step 3: app.py 구현**

`src/claude_usage_widget/app.py`:
```python
import threading
import tkinter as tk
from datetime import datetime

from . import config as config_module
from . import credential_store
from .api_client import AuthError, fetch_usage_with_retry
from .autostart import disable_autostart, enable_autostart
from .detail_panel import DetailPanel
from .logging_setup import get_logger
from .settings_ui import SettingsDialog
from .tray import build_tray_icon, make_icon_image
from .widget import CharacterWidget
from .widget_state import Mood, resolve_state

logger = get_logger()


class App:
    def __init__(self):
        self.config = config_module.load_config()
        self._first_run = not config_module.config_path().exists()

        self.root = tk.Tk()
        self.root.withdraw()

        pos = tuple(self.config.get("widget_position") or [100, 100])
        self.widget = CharacterWidget(self.root, pos, self._on_widget_move, self._on_widget_right_click)
        self.detail_panel = DetailPanel(self.root, self._manual_refresh, self._open_settings, self.quit)
        self.settings_dialog = SettingsDialog(self.root, self.config, self._on_settings_saved)
        self.tray_icon = build_tray_icon(Mood.SETUP_NEEDED, self._toggle_widget, self._open_settings, self.quit)

        self._notified_auth_error = False
        self._timer = None

        if self._first_run:
            self._open_settings()

        self._refresh_and_reschedule()

    def _fetch_result(self):
        session_key = credential_store.load_session_key()
        org_id = self.config.get("org_id")
        if not session_key or not org_id:
            return None
        try:
            return fetch_usage_with_retry(session_key, org_id)
        except Exception as exc:  # AuthError 또는 재시도 소진 후 TransientError
            logger.error("usage fetch failed: %s", exc)
            return exc

    def _refresh_and_reschedule(self):
        result = self._fetch_result()
        state = resolve_state(result, self.config["thresholds"])
        self._apply_state(state)
        self._schedule_next_refresh()

    def _refresh_and_reschedule_cancel_old(self):
        if self._timer is not None:
            self._timer.cancel()
        self._refresh_and_reschedule()

    def _schedule_next_refresh(self):
        interval = self.config.get("refresh_interval_seconds", 180)
        self._timer = threading.Timer(interval, self._background_refresh)
        self._timer.daemon = True
        self._timer.start()

    def _background_refresh(self):
        result = self._fetch_result()
        state = resolve_state(result, self.config["thresholds"])
        self.root.after(0, self._apply_state, state)
        self._schedule_next_refresh()

    def _manual_refresh(self):
        self._refresh_and_reschedule_cancel_old()

    def _apply_state(self, state):
        self.widget.apply_state(state)
        now_text = f"마지막 업데이트: {datetime.now().strftime('%H:%M')}"
        self.detail_panel.render(state.detail_rows, now_text)
        self.tray_icon.icon = make_icon_image(state.mood)

        if state.mood == Mood.AUTH_ERROR and not self._notified_auth_error:
            self._notify("재로그인이 필요해요. 설정에서 sessionKey를 다시 입력해주세요.")
            self._notified_auth_error = True
        elif state.mood != Mood.AUTH_ERROR:
            self._notified_auth_error = False

    def _notify(self, message: str):
        try:
            self.tray_icon.notify(message)
        except NotImplementedError:
            logger.info("tray notifications not supported on this platform: %s", message)

    def _on_widget_move(self, pos):
        self.config["widget_position"] = list(pos)
        config_module.save_config(self.config)

    def _on_widget_right_click(self):
        x = self.widget.top.winfo_x()
        y = self.widget.top.winfo_y() + CharacterWidget.SIZE
        self.detail_panel.show_at(x, y)

    def _open_settings(self):
        self.settings_dialog.show()

    def _on_settings_saved(self, values):
        if values["session_key"]:
            credential_store.save_session_key(values["session_key"])
        self.config["org_id"] = values["org_id"]
        self.config["refresh_interval_seconds"] = values["refresh_interval_seconds"]
        self.config["thresholds"] = values["thresholds"]
        self.config["show_credit"] = values["show_credit"]
        self.config["autostart_enabled"] = values["autostart_enabled"]
        config_module.save_config(self.config)

        if values["autostart_enabled"]:
            enable_autostart()
        else:
            disable_autostart()

        self._refresh_and_reschedule_cancel_old()

    def _toggle_widget(self):
        if self.widget.top.state() == "withdrawn":
            self.widget.top.deiconify()
        else:
            self.widget.top.withdraw()

    def quit(self):
        if self._timer is not None:
            self._timer.cancel()
        self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self.root.mainloop()


def main():
    app = App()
    app.run()
```

`run.py` (프로젝트 루트, PyInstaller 진입점):
```python
from claude_usage_widget.app import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 전체 테스트 스위트 통과 확인**

Run: `python -m pytest -v`
Expected: 모든 테스트 PASS (Task 1~12에서 작성한 테스트 전체)

- [ ] **Step 6: 커밋**

```bash
git add src/claude_usage_widget/app.py run.py tests/test_app.py
git commit -m "Wire modules together into the App orchestrator and entry point"
```

---

## Task 13: PyInstaller 패키징 + README

**Files:**
- Create: `README.md`
- Manual: PyInstaller 빌드 및 실행 확인 (자동화 테스트 없음)

**Interfaces:**
- Consumes: `run.py` (Task 12)

- [ ] **Step 1: README 작성**

`README.md`:
```markdown
# Claude 사용량 위젯

claude.ai(Pro/Max) 세션/주간 사용량과 크레딧을 화면에 항상 떠있는 작은 캐릭터로 보여주는 Windows 데스크톱 위젯입니다.

## ⚠ 중요 안내

이 프로그램은 Anthropic이 공식적으로 지원하지 않는 방식(claude.ai가 내부적으로 쓰는 비공식 API)을 사용합니다.

- Anthropic이 내부 구조를 바꾸면 언제든 동작이 멈출 수 있습니다.
- 로그인 세션 쿠키(`sessionKey`)를 사용하는데, 이 값은 사실상 로그인 자체와 동급으로 민감한 정보입니다. 이 앱은 해당 값을 Windows Credential Manager에 암호화 저장하고 오직 `claude.ai`로만 요청을 보내며, 어떤 외부 서버로도 전송하지 않습니다. 그래도 본인 책임하에 사용해주세요.

## sessionKey 쿠키 가져오는 법

1. Chrome에서 claude.ai에 로그인
2. F12 → Application 탭 → Cookies → `https://claude.ai`
3. `sessionKey` 값을 복사 (Organization ID는 `lastActiveOrg` 값)
4. 위젯 우클릭 → 설정에 붙여넣기

## 개발 환경에서 실행

```bash
pip install -r requirements-dev.txt
python -m pytest
python run.py
```

## 실행파일(.exe) 빌드

```bash
pyinstaller --onefile --windowed --name ClaudeUsageWidget --paths src run.py
```

빌드 결과물은 `dist/ClaudeUsageWidget.exe`.
```

- [ ] **Step 2: 실행파일 빌드**

Run: `pyinstaller --onefile --windowed --name ClaudeUsageWidget --paths src run.py`
Expected: `dist/ClaudeUsageWidget.exe` 생성, 콘솔에 오류 없음

- [ ] **Step 3: 수동 검증**

`dist/ClaudeUsageWidget.exe`를 더블클릭 실행 후 확인:
1. 첫 실행이므로 설정 창이 자동으로 뜬다
2. sessionKey / Organization ID를 입력하고 저장하면 창이 닫힌다
3. 화면 구석에 캐릭터 위젯이 나타나고, 몇 초 안에 실제 세션/주간 % 반영해서 표정·색이 바뀐다
4. 위젯을 드래그하면 위치가 바뀌고, 프로그램을 재시작해도 그 위치를 기억한다
5. 위젯 우클릭 → 상세 패널에 세션/주간(전체)/주간(모델별) 막대가 뜬다
6. 트레이 아이콘 우클릭 → "위젯 표시/숨김"으로 위젯이 사라졌다 나타난다
7. 설정에서 "PC 시작 시 자동 실행" 체크 → `Win+R` → `regedit` → `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`에 `ClaudeUsageWidget` 값이 생겼는지 확인
8. `%APPDATA%\ClaudeUsageWidget\config.json`과 `log.txt`가 생성되었는지 확인
9. 트레이 메뉴 "종료"로 완전히 종료되는지 확인 (작업 관리자에 프로세스가 남지 않아야 함)

- [ ] **Step 4: 커밋**

```bash
git add README.md
git commit -m "Add README with setup, risk disclaimer, and build instructions"
```

---

## Self-Review 메모

- **스펙 커버리지**: 설계 문서의 API 계약(Task 4), 캐릭터 위젯(Task 7), 상세 패널(Task 8), 트레이(Task 9), 설정 화면(Task 10), 자격증명 암호화 저장(Task 3), 에러 처리/재시도(Task 5, resolve_state의 AUTH_ERROR/WARNING 분기), 자동 시작(Task 11), 패키징(Task 13), 보안 고지(Task 13 README) 모두 태스크로 매핑됨. Admin API·로컬 토큰 로그 분석은 설계 문서에서 명시적으로 범위 제외됨.
- **타입 일관성**: `WidgetState.detail_rows`가 Task 6에서 `list[tuple[str, int | None]]`로 정의되고, Task 8 `DetailPanel.render`와 Task 12 `App._apply_state`가 동일한 타입을 그대로 소비하도록 맞춤. `CharacterWidget.SIZE`, `.top`, `.apply_state` 등 Task 7에서 정의한 이름을 Task 12에서 그대로 사용.
- **플레이스홀더 없음**: 모든 스텝에 실행 가능한 실제 코드/명령어를 포함시킴.
