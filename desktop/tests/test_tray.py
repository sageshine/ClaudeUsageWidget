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
