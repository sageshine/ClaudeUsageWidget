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
