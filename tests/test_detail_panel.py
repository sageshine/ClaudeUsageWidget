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
