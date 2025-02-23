import random
from collections import deque
from emojis import EMOJI_CASES, EMOJI_LINES, EMOJI_HEADER, EMOJIS_ENDGAME

class MinesweeperGame:
    def __init__(self, size=12, bomb_count=22):
        self.size = size
        self.bomb_count = bomb_count
        self.board = {}
        self.first_click_done = False
        self.initialize_board()
        self.header = [EMOJI_HEADER[i] for i in range(self.size + 1)]

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
        excluded_coords = set()
        directions = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)
        ]
        excluded_coords.add(first_click_coords)
        fr, fc = first_click_coords
        for dr, dc in directions:
            nr, nc = fr + dr, fc + dc
            if 0 <= nr < self.size and 0 <= nc < self.size:
                excluded_coords.add((nr, nc))

        placed = 0
        while placed < self.bomb_count:
            r = random.randint(0, self.size - 1)
            c = random.randint(0, self.size - 1)
            if (r, c) not in excluded_coords and self.board[(r, c)]["value"] != 'b':
                self.board[(r, c)]["value"] = 'b'
                placed += 1

        for (r, c), cell in self.board.items():
            if cell["value"] != 'b':
                cell["value"] = self.count_adjacent_bombs(r, c)

    def count_adjacent_bombs(self, r, c):
        directions = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)
        ]
        cnt = 0
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
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

    def flag_case(self, r, c, user_id):
        if not self.is_valid_coords(r, c):
            return "La case est hors de la grille."
        cell = self.board[(r, c)]
        if cell["status"] == "revealed":
            return "Cette case est déjà révélée, impossible de flag."
        if cell["status"] == "flagged":
            return "Impossible de retirer un drapeau (déjà flaggé)."

        cell["status"] = "flagged"
        cell["flag_owner"] = user_id
        return "Drapeau placé."

    def is_all_safe_revealed(self):
        """
        True si toutes les cases non-bombes sont révélées ou flaggées
        ET le total de drapeaux n'excède pas le bomb_count.
        """
        safe_ok = True
        for cell in self.board.values():
            if cell["value"] != 'b':
                if cell["status"] not in ("revealed", "flagged"):
                    safe_ok = False
                    break

        if self.count_all_flags() > self.bomb_count:
            safe_ok = False
        return safe_ok

    def reveal_all_bombs(self):
        for v in self.board.values():
            if v["value"] == 'b':
                v["status"] = "revealed"

    def count_all_flags(self):
        return sum(1 for v in self.board.values() if v["status"] == "flagged")

    def count_flags_by_user(self, user_id):
        cnt = 0
        for v in self.board.values():
            if v["status"] == "flagged" and v["flag_owner"] == user_id and v["value"] == 'b':
                cnt += 1
        return cnt

    def finalize_endgame(self, scenario, last_click=None, bomb_clicked=False, safe_flag_clicked=False):
        """
        Gère la fin de partie :
        - On remplace le header[0] selon scenario :
            * 'all_solved' => <:swag_boom:...>
            * 'one_left' => <:sad_boom:...>
        - On révèle toutes les bombes
        - Si la partie s'achève sur un clic bombe => on remplace cette bombe par 'bomb_e'
        - Si la partie s'achève sur un clic drapeau sûr => 'flag_e'
        """
        if scenario == "one_left":
            self.header[0] = EMOJIS_ENDGAME[0]
        elif scenario == "all_solved":
            self.header[0] = EMOJIS_ENDGAME[1]
        else:
            print("Bug scenario ending")

        self.reveal_all_bombs()

        if last_click is not None:
            (r, c) = last_click
            cell = self.board.get((r,c))
            if cell:
                if bomb_clicked and cell["value"] == 'b':
                    cell["value"] = 'bomb_e'
                if safe_flag_clicked and cell["status"] == "revealed" and cell["value"] != 'b':
                    cell["value"] = 'flag_e'

        return self.print_board_text()

    def print_board_text(self):
        lines = []

        lines.append("".join(self.header))

        for r in range(self.size):
            row_parts = [EMOJI_LINES[r+1]]
            for c in range(self.size):
                cell = self.board[(r,c)]
                if cell["status"] == "hidden":
                    row_parts.append(EMOJI_CASES["hidden"])
                elif cell["status"] == "flagged":
                    if cell["value"] == 'flag_e':
                        row_parts.append(EMOJIS_ENDGAME[2])
                    else:
                        row_parts.append(EMOJI_CASES["flag"])
                else:
                    val = cell["value"]
                    if val == 'bomb_e':
                        row_parts.append(EMOJIS_ENDGAME[3])
                    elif val == 'b':
                        row_parts.append(EMOJI_CASES["bomb"])
                    elif val == 'flag_e':
                        row_parts.append(EMOJIS_ENDGAME[2])
                    else:
                        row_parts.append(EMOJI_CASES.get(str(val), "?"))

            lines.append("".join(row_parts))

        return "\n".join(lines)