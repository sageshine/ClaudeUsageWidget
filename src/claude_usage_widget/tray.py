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
