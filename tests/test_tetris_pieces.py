import random

from claude_usage_widget.tetris_pieces import (
    COLS,
    ROWS,
    SHAPES,
    TOTAL_CELLS,
    choose_placement,
    choose_shape,
    empty_board,
    filled_cell_count,
    find_landing_row,
    place_piece,
)


def test_empty_board_has_correct_dimensions_and_all_cells_none():
    board = empty_board()
    assert len(board) == ROWS
    assert all(len(row) == COLS for row in board)
    assert all(cell is None for row in board for cell in row)


def test_total_cells_matches_rows_times_cols():
    assert TOTAL_CELLS == ROWS * COLS


def test_filled_cell_count_counts_non_none_cells():
    board = place_piece(empty_board(), "O", 0, ROWS - 2)
    assert filled_cell_count(board) == 4


def test_place_piece_returns_new_board_without_mutating_original():
    board = empty_board()
    new_board = place_piece(board, "O", 0, ROWS - 2)
    assert filled_cell_count(board) == 0
    assert filled_cell_count(new_board) == 4


def test_find_landing_row_on_empty_board_lands_i_piece_at_floor():
    landing = find_landing_row(empty_board(), "I", 0)
    assert landing == ROWS - 1


def test_find_landing_row_rests_on_top_of_existing_stack():
    board = place_piece(empty_board(), "O", 0, ROWS - 2)
    landing = find_landing_row(board, "O", 0)
    assert landing == ROWS - 4


def test_find_landing_row_returns_none_when_top_of_column_is_blocked():
    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(ROWS):
        grid[row][0] = "I"
    board = tuple(tuple(row) for row in grid)
    assert find_landing_row(board, "O", 0) is None


def test_choose_placement_lands_at_floor_when_all_candidate_columns_are_empty():
    grid = [[None] * COLS for _ in range(ROWS)]
    grid[ROWS - 1][4] = "I"
    board = tuple(tuple(row) for row in grid)

    rng = random.Random(0)
    col, landing_row = choose_placement(board, "O", rng)

    assert landing_row == ROWS - 2
    assert col in range(0, COLS - 1)


def test_choose_placement_avoids_shallow_column_when_a_deeper_one_exists():
    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(ROWS - 1, ROWS - 5, -1):
        grid[row][0] = "I"
        grid[row][1] = "I"
    board = tuple(tuple(row) for row in grid)

    rng = random.Random(0)
    for _ in range(20):
        col, landing_row = choose_placement(board, "O", rng)
        assert col in (2, 3)
        assert landing_row == ROWS - 2


def test_choose_placement_returns_none_when_no_column_fits():
    grid = [["I"] * COLS for _ in range(ROWS)]
    board = tuple(tuple(row) for row in grid)
    rng = random.Random(0)
    assert choose_placement(board, "O", rng) is None


def test_choose_shape_returns_a_valid_shape_id():
    rng = random.Random(0)
    for _ in range(20):
        assert choose_shape(rng) in SHAPES
