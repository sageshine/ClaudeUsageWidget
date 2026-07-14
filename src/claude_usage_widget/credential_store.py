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
