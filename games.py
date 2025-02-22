import random
from collections import deque
from emojis import EMOJI_CASES, EMOJI_HEADER, EMOJI_LINES

class MinesweeperGame:
    def __init__(self, size=16, bomb_count=40):
        self.size = size
        self.bomb_count = bomb_count
        self.board = {}
        self.first_click_done = False
        self.initialize_board()

    def initialize_board(self):
        self.board = {
            (r, c): {
                "value": 0,
                "status": "hidden",
                "flag_owner": None
            }
            for r in range(self.size)
            for c in range(self.size)
        }

    def generate_bombs(self, first_click_coords):
        placed = 0
        while placed < self.bomb_count:
            r = random.randint(0, self.size - 1)
            c = random.randint(0, self.size - 1)
            if (r, c) != first_click_coords and self.board[(r, c)]["value"] != 'b':
                self.board[(r, c)]["value"] = 'b'
                placed += 1

        for (r, c), cell in self.board.items():
            if cell["value"] != 'b':
                cell["value"] = self.count_adjacent_bombs(r, c)

    def count_adjacent_bombs(self, row, col):
        directions = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)
        ]
        cnt = 0
        for dr, dc in directions:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.size and 0 <= nc < self.size:
                if self.board[(nr, nc)]["value"] == 'b':
                    cnt += 1
        return cnt

    def is_valid_coords(self, r, c):
        return 0 <= r < self.size and 0 <= c < self.size

    def reveal_case(self, r, c):
        cell = self.board[(r, c)]
        if cell["status"] == "revealed":
            return "Cette case est déjà révélée."
        if cell["status"] == "flagged":
            return "Impossible de révéler une case déjà flaggée."

        if not self.first_click_done:
            self.first_click_done = True
            self.generate_bombs((r, c))

        cell["status"] = "revealed"
        if cell["value"] == 'b':
            return "💥 BOOM! Bombe touchée."

        if cell["value"] == 0:
            self.flood_reveal(r, c)
            return "Case vide. Révélation autour."
        return f"La case contient {cell['value']}."

    def flood_reveal(self, sr, sc):
        queue = deque()
        queue.append((sr, sc))
        while queue:
            rr, cc = queue.popleft()
            for dr, dc in [
                (-1, -1), (-1, 0), (-1, 1),
                (0, -1),           (0, 1),
                (1, -1),  (1, 0),  (1, 1)
            ]:
                nr, nc = rr + dr, cc + dc
                if self.is_valid_coords(nr, nc):
                    neigh = self.board[(nr, nc)]
                    if neigh["status"] == "hidden" and neigh["value"] != 'b':
                        neigh["status"] = "revealed"
                        if neigh["value"] == 0:
                            queue.append((nr, nc))

    def flag_case(self, row: int, col: int, user_id: int) -> str:
        """
        Pose un drapeau sur (row, col) pour user_id.
        Il est interdit de retirer un drapeau (les drapeaux sont définitifs).
        """
        if not self.is_valid_coords(row, col):
            return "La case est hors de la grille."

        cell = self.board[(row, col)]
        
        if cell["status"] == "revealed":
            return "Cette case est déjà révélée, impossible de flag."

        if cell["status"] == "flagged":
            return "Impossible de retirer un drapeau (déjà flaggé)."

        cell["status"] = "flagged"
        cell["flag_owner"] = user_id
        return "Drapeau placé."


    def is_all_safe_revealed(self):
        for v in self.board.values():
            if v["value"] != 'b' and v["status"] != 'revealed':
                return False
        return True

    def force_reveal_all(self):
        for v in self.board.values():
            v["status"] = "revealed"

    def count_all_flags(self):
        return sum(1 for v in self.board.values() if v["status"] == "flagged")

    def count_flags_by_user(self, user_id):
        cnt = 0
        for v in self.board.values():
            if v["status"] == "flagged" and v["flag_owner"] == user_id and v["value"] == 'b':
                cnt += 1
        return cnt

    def print_board_text(self) -> str:
        """
        Affiche la carte en émojis uniquement, sans espace.
        1) Première ligne = entête de colonnes
        2) Lignes suivantes = n° de ligne + cases
        Produira 1 + self.size = 17 lignes (pour size=16).
        """
        lines = []
        header_emojis = [EMOJI_HEADER[c] for c in range(0, self.size+1)]
        lines.append("".join(header_emojis))

        for r in range(self.size):
            row_parts = [EMOJI_LINES[r+1]]

            for c in range(self.size):
                cell = self.board[(r, c)]
                if cell["status"] == "hidden":
                    row_parts.append(EMOJI_CASES["hidden"])
                elif cell["status"] == "flagged":
                    row_parts.append(EMOJI_CASES["flag"])
                else:
                    val = cell["value"]
                    if val == 'b':
                        row_parts.append(EMOJI_CASES["bomb"])
                    else:
                        row_parts.append(EMOJI_CASES[str(val)])
            
            lines.append("".join(row_parts))

        return "\n".join(lines)