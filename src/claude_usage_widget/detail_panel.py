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

    def render(self, rows: list[tuple[str, int | None]], updated_text: str) -> None:
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
