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


def test_find_landing_row_t_piece_lands_on_staggered_stack_with_left_and_right_columns_filled():
    # T piece cells: ((0,0),(0,1),(0,2),(1,1)) at start_col=0
    # col0 filled rows 8-9 (first_filled=8) -> offset_limit = 8-1-0 = 7
    # col1 empty (first_filled=10)          -> offset_limit = 10-1-0 = 9 (top), 10-1-1 = 8 (bottom notch)
    # col2 filled rows 6-9 (first_filled=6) -> offset_limit = 6-1-0 = 5   <- binding constraint
    # best_offset = min(7, 9, 5, 8) = 5
    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(8, ROWS):
        grid[row][0] = "I"
    for row in range(6, ROWS):
        grid[row][2] = "I"
    board = tuple(tuple(row) for row in grid)
    assert find_landing_row(board, "T", 0) == 5


def test_find_landing_row_s_piece_lands_on_staggered_stack_with_single_filled_cell():
    # S piece cells: ((0,1),(0,2),(1,0),(1,1)) at start_col=0
    # col0 filled at row 9 only (first_filled=9) -> bottom-left cell (1,0): offset_limit = 9-1-1 = 7  <- binding
    # col1, col2 empty (first_filled=10)         -> offset_limit = 9 (top cells), 10-1-1 = 8 (bottom-right cell)
    # best_offset = min(9, 9, 7, 8) = 7
    grid = [[None] * COLS for _ in range(ROWS)]
    grid[9][0] = "I"
    board = tuple(tuple(row) for row in grid)
    assert find_landing_row(board, "S", 0) == 7


def test_find_landing_row_l_piece_lands_on_staggered_stack_with_left_column_filled():
    # L piece cells: ((0,2),(1,0),(1,1),(1,2)) at start_col=0
    # col0 filled rows 7-9 (first_filled=7) -> bottom-left cell (1,0): offset_limit = 7-1-1 = 5   <- binding
    # col1, col2 empty (first_filled=10)    -> offset_limit = 9 (top-right cell), 10-1-1 = 8 (other bottom cells)
    # best_offset = min(9, 5, 8, 8) = 5
    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(7, ROWS):
        grid[row][0] = "I"
    board = tuple(tuple(row) for row in grid)
    assert find_landing_row(board, "L", 0) == 5


def test_choose_placement_with_t_piece_avoids_shallow_middle_column_on_staggered_stack():
    # T piece width = 3, so candidate start_col values are 0, 1, 2.
    # Column 2 is filled rows 6-9 (a 4-tall stack, same as the existing O-piece test).
    # start_col=0 (cols 0,1,2): cells land on empty col0/col1 (offset_limit 9/9/8) and
    #   filled col2 via the top-right cell (offset_limit 6-1-0=5)      -> best_offset = 5
    # start_col=1 (cols 1,2,3): the filled col2 now hits the piece's notch cell (1,1)
    #   (offset_limit 6-1-1=4), which is shallower than start_col 0/2  -> best_offset = 4
    # start_col=2 (cols 2,3,4): filled col2 hits the top-left cell (0,0) (offset_limit 5) -> best_offset = 5
    # Deepest landing is 5, achieved only by start_col 0 and 2; start_col 1 (landing 4) must never be chosen.
    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(ROWS - 1, ROWS - 5, -1):
        grid[row][2] = "I"
    board = tuple(tuple(row) for row in grid)

    rng = random.Random(0)
    for _ in range(20):
        col, landing_row = choose_placement(board, "T", rng)
        assert col in (0, 2)
        assert landing_row == 5
