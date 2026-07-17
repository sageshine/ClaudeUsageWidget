import tkinter as tk
from tkinter import messagebox, ttk

WIDGET_STYLE_LABELS = {"tetris": "테트리스", "hourglass": "모래시계", "number": "숫자"}
_WIDGET_STYLE_BY_LABEL = {label: value for value, label in WIDGET_STYLE_LABELS.items()}

HEADLINE_METRIC_LABELS = {
    "max": "세션/주간 중 높은 쪽",
    "session": "현재 세션",
    "weekly": "주간 한도",
}
_HEADLINE_METRIC_BY_LABEL = {label: value for value, label in HEADLINE_METRIC_LABELS.items()}


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
        widget_style = config.get("widget_style", "tetris")
        self.widget_style_var = tk.StringVar(value=WIDGET_STYLE_LABELS.get(widget_style, WIDGET_STYLE_LABELS["tetris"]))
        headline_metric = config.get("headline_metric", "max")
        self.headline_metric_var = tk.StringVar(
            value=HEADLINE_METRIC_LABELS.get(headline_metric, HEADLINE_METRIC_LABELS["max"])
        )

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

        ttk.Label(self.top, text="위젯에 표시할 사용량").grid(row=5, column=0, sticky="w", **pad)
        ttk.Combobox(
            self.top,
            textvariable=self.headline_metric_var,
            values=list(HEADLINE_METRIC_LABELS.values()),
            state="readonly",
            width=18,
        ).grid(row=5, column=1, sticky="w", **pad)

        ttk.Label(self.top, text="위젯 모양").grid(row=6, column=0, sticky="w", **pad)
        ttk.Combobox(
            self.top,
            textvariable=self.widget_style_var,
            values=list(WIDGET_STYLE_LABELS.values()),
            state="readonly",
            width=12,
        ).grid(row=6, column=1, sticky="w", **pad)

        ttk.Checkbutton(self.top, text="사용 크레딧 표시", variable=self.credit_var).grid(row=7, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(self.top, text="PC 시작 시 자동 실행", variable=self.autostart_var).grid(row=8, column=0, columnspan=2, sticky="w", **pad)

        ttk.Button(self.top, text="저장", command=self._save).grid(row=9, column=0, columnspan=2, pady=10)

    def show(self) -> None:
        self.top.deiconify()
        self.top.lift()

    def _save(self):
        try:
            interval = self.interval_var.get()
            warning = self.warning_var.get()
            danger = self.danger_var.get()
        except (tk.TclError, ValueError):
            # IntVar.get() raises tk.TclError when the Spinbox contains text the user typed by
            # hand instead of picked with the arrows (e.g. "abc"). Without this, a --windowed
            # build swallows the exception silently and 저장 appears to do nothing.
            messagebox.showerror("설정 오류", "숫자만 입력해주세요.")
            return

        if warning >= danger:
            messagebox.showerror("설정 오류", "주의 임계값은 위험 임계값보다 작아야 해요.")
            return

        result = {
            "session_key": self.session_key_var.get().strip() or None,
            "org_id": self.org_id_var.get().strip() or None,
            "refresh_interval_seconds": max(60, interval),
            "thresholds": {"warning": warning, "danger": danger},
            "show_credit": self.credit_var.get(),
            "autostart_enabled": self.autostart_var.get(),
            "widget_style": _WIDGET_STYLE_BY_LABEL.get(self.widget_style_var.get(), "tetris"),
            "headline_metric": _HEADLINE_METRIC_BY_LABEL.get(self.headline_metric_var.get(), "max"),
        }
        self._on_save(result)
        self.top.withdraw()
