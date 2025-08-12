import random

def predict_mines(server_seed: str, mine_count: int) -> list:
    all_tiles = [(i, j) for i in range(5) for j in range(5)]
    return random.sample(all_tiles, mine_count)

def render_board(mines: list) -> str:
    """
    Renders the 5x5 grid with emojis.
    💣 for mine, 🟦 for safe tile
    """
    board = ""
    for i in range(5):
        for j in range(5):
            if (i, j) in mines:
                board += "💣"
            else:
                board += "🟩"
        board += "\n"
    return board
