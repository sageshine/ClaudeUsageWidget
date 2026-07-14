import random

ROWS = 10
COLS = 5
TOTAL_CELLS = ROWS * COLS

SHAPES = {
    "I": ((0, 0), (0, 1), (0, 2), (0, 3)),
    "O": ((0, 0), (0, 1), (1, 0), (1, 1)),
    "T": ((0, 0), (0, 1), (0, 2), (1, 1)),
    "S": ((0, 1), (0, 2), (1, 0), (1, 1)),
    "Z": ((0, 0), (0, 1), (1, 1), (1, 2)),
    "J": ((0, 0), (1, 0), (1, 1), (1, 2)),
    "L": ((0, 2), (1, 0), (1, 1), (1, 2)),
}

SHAPE_COLORS = {
    "I": "#22D3EE",
    "O": "#FACC15",
    "T": "#A855F7",
    "S": "#22C55E",
    "Z": "#EF4444",
    "J": "#3B82F6",
    "L": "#F97316",
}


def empty_board():
    return tuple(tuple(None for _ in range(COLS)) for _ in range(ROWS))


def filled_cell_count(board) -> int:
    return sum(1 for row in board for cell in row if cell is not None)


def _piece_width(shape_id: str) -> int:
    return max(dc for _, dc in SHAPES[shape_id]) + 1


def find_landing_row(board, shape_id: str, start_col: int):
    cells = SHAPES[shape_id]
    width = _piece_width(shape_id)
    if start_col < 0 or start_col + width > COLS:
        return None

    best_offset = ROWS
    for dr, dc in cells:
        col = start_col + dc
        first_filled = next((r for r in range(ROWS) if board[r][col] is not None), ROWS)
        offset_limit = first_filled - 1 - dr
        best_offset = min(best_offset, offset_limit)

    if best_offset < 0:
        return None
    return best_offset


def place_piece(board, shape_id: str, start_col: int, row_offset: int):
    grid = [list(row) for row in board]
    for dr, dc in SHAPES[shape_id]:
        grid[row_offset + dr][start_col + dc] = shape_id
    return tuple(tuple(row) for row in grid)


def choose_placement(board, shape_id: str, rng: random.Random):
    width = _piece_width(shape_id)
    candidates = []
    for start_col in range(COLS - width + 1):
        landing = find_landing_row(board, shape_id, start_col)
        if landing is not None:
            candidates.append((start_col, landing))

    if not candidates:
        return None

    deepest = max(landing for _, landing in candidates)
    best = [c for c in candidates if c[1] == deepest]
    return rng.choice(best)


def choose_shape(rng: random.Random) -> str:
    return rng.choice(list(SHAPES.keys()))


def choose_shape_and_placement(board, rng: random.Random):
    shape_ids = list(SHAPES.keys())
    rng.shuffle(shape_ids)
    for shape_id in shape_ids:
        placement = choose_placement(board, shape_id, rng)
        if placement is not None:
            col, landing_row = placement
            return shape_id, col, landing_row
    return None


def clear_full_rows(board):
    remaining_rows = [row for row in board if any(cell is None for cell in row)]
    cleared_count = ROWS - len(remaining_rows)
    if cleared_count == 0:
        return board, 0
    empty_rows = [tuple(None for _ in range(COLS)) for _ in range(cleared_count)]
    return tuple(empty_rows + remaining_rows), cleared_count
