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
