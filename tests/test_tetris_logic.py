from claude_usage_widget.tetris_logic import is_game_over


def test_is_game_over_true_at_100_percent_and_above():
    assert is_game_over(100) is True
    assert is_game_over(108) is True


def test_is_game_over_false_below_100_percent():
    assert is_game_over(99) is False
    assert is_game_over(0) is False
