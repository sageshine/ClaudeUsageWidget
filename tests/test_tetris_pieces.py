import random

from claude_usage_widget.tetris_pieces import (
    COLS,
    ROWS,
    SHAPES,
    TOTAL_CELLS,
    choose_placement,
    choose_shape,
    choose_shape_and_placement,
    clear_full_rows,
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


def test_choose_shape_and_placement_on_empty_board_returns_valid_tuple():
    rng = random.Random(1)
    result = choose_shape_and_placement(empty_board(), rng)
    assert result is not None
    shape_id, col, landing_row = result
    assert shape_id in SHAPES
    assert isinstance(col, int)
    assert isinstance(landing_row, int)


def test_choose_shape_and_placement_falls_back_to_narrower_shape_when_wider_ones_dont_fit():
    # Fill column 2 solidly from row 0 to the floor. find_landing_row rejects a
    # placement the instant one of its cells maps onto a column whose first_filled
    # row is 0 (offset_limit = 0 - 1 - dr, which is negative for every dr >= 0).
    #
    # I has width 4, so its only candidate start_col is 0, spanning columns 0-3 --
    # which includes column 2, so I can never land.
    # T, S, Z, J, L all have width 3, with candidate start_col in {0, 1, 2}, spanning
    # columns {0,1,2}, {1,2,3}, {2,3,4} respectively -- every one of those spans
    # includes column 2. Each of these five shapes also has at least one cell in
    # every column of its span (verified against the SHAPES table), so column 2
    # blocks all of their candidate columns too.
    # Only O (width 2) has candidate start_cols {0,1,2,3}; start_col 0 (cols 0-1) and
    # start_col 3 (cols 3-4) never touch column 2, so O alone can still be placed.
    #
    # A single "pick one random shape and give up" attempt would fail ~6 times out of
    # 7. The new function must keep trying until it finds O, for any shuffle order.
    grid = [[None] * COLS for _ in range(ROWS)]
    for row in range(ROWS):
        grid[row][2] = "I"
    board = tuple(tuple(row) for row in grid)

    for seed in range(30):
        rng = random.Random(seed)
        result = choose_shape_and_placement(board, rng)
        assert result is not None
        shape_id, col, landing_row = result
        assert shape_id == "O"
        assert col in (0, 3)
        assert landing_row == ROWS - 2


def test_choose_shape_and_placement_returns_none_when_board_fully_blocked():
    # Top row filled across every column tops the board out for every shape (every
    # shape has a cell with dr == 0), mirroring
    # test_choose_placement_returns_none_when_no_column_fits.
    grid = [[None] * COLS for _ in range(ROWS)]
    for col in range(COLS):
        grid[0][col] = "I"
    board = tuple(tuple(row) for row in grid)
    rng = random.Random(0)
    assert choose_shape_and_placement(board, rng) is None


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


def test_clear_full_rows_removes_completed_row_and_shifts_down():
    grid = [[None] * COLS for _ in range(ROWS)]
    grid[ROWS - 1] = ["I", "I", "O", "O", "T"]  # 맨 아래 줄이 5칸 모두 참
    grid[ROWS - 2][0] = "L"  # 그 위 줄엔 한 칸만 참
    board = tuple(tuple(row) for row in grid)

    new_board, cleared_count = clear_full_rows(board)

    assert cleared_count == 1
    # 지워진 줄 위에 있던 "L" 조각이 한 칸 아래(맨 아래 줄)로 내려와야 함
    assert new_board[ROWS - 1][0] == "L"
    assert all(cell is None for cell in new_board[ROWS - 1][1:])
    # 맨 위에는 새 빈 행이 생겨야 함
    assert all(cell is None for cell in new_board[0])


def test_clear_full_rows_returns_original_board_unchanged_when_nothing_to_clear():
    board = place_piece(empty_board(), "O", 0, ROWS - 2)
    new_board, cleared_count = clear_full_rows(board)
    assert cleared_count == 0
    assert new_board == board


def test_clear_full_rows_does_not_mutate_input_board():
    grid = [[None] * COLS for _ in range(ROWS)]
    grid[ROWS - 1] = ["I", "I", "O", "O", "T"]
    board = tuple(tuple(row) for row in grid)

    clear_full_rows(board)

    assert board[ROWS - 1] == ("I", "I", "O", "O", "T")  # 원본 그대로
