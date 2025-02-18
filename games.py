import random
from collections import deque

class MinesweeperGame:
    """
    Classe pour gérer la logique du démineur.
    - board[(r,c)] = {
        "value": 0..8 ou 'b',
        "status": 'hidden'|'revealed'|'flagged',
        "flag_owner": None|user_id
      }
    """

    def __init__(self, size: int = 16, bomb_count: int = 40):
        self.size = size
        self.bomb_count = bomb_count
        self.board = {}
        self.first_click_done = False
        self.initialize_board()

    def initialize_board(self):
        """
        Initialise chaque case avec :
        - value = 0
        - status = 'hidden'
        - flag_owner = None
        """
        self.board = {
            (r, c): {
                "value": 0,
                "status": "hidden",
                "flag_owner": None
            }
            for r in range(self.size)
            for c in range(self.size)
        }

    def generate_bombs(self, first_click_coords: tuple[int, int]):
        """
        Place les bombes de façon aléatoire en évitant la case du 'first click'.
        """
        placed_bombs = 0
        while placed_bombs < self.bomb_count:
            r = random.randint(0, self.size - 1)
            c = random.randint(0, self.size - 1)
            if (r, c) != first_click_coords and self.board[(r, c)]["value"] != 'b':
                self.board[(r, c)]["value"] = 'b'
                placed_bombs += 1

        # Mise à jour des nombres
        for (r, c), cell in self.board.items():
            if cell["value"] != 'b':
                cell["value"] = self.count_adjacent_bombs(r, c)

    def count_adjacent_bombs(self, row: int, col: int) -> int:
        """
        Compte le nombre de bombes autour de (row, col).
        """
        directions = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)
        ]
        count = 0
        for dr, dc in directions:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.size and 0 <= nc < self.size:
                if self.board[(nr, nc)]["value"] == 'b':
                    count += 1
        return count

    def is_valid_coords(self, row: int, col: int) -> bool:
        """Vérifie que (row, col) est dans la grille."""
        return 0 <= row < self.size and 0 <= col < self.size

    def reveal_case(self, row: int, col: int) -> str:
        """
        Révèle la case (row, col) (hors cas de "cliquer un drapeau adverse").
        Retourne un message sur la révélation ou un message d'erreur ("Impossible...").
        """
        cell = self.board[(row, col)]

        if cell["status"] == "revealed":
            return "Cette case est déjà révélée."
        if cell["status"] == "flagged":
            return "Impossible de révéler une case déjà flaggée."

        # Premier clic => on place les bombes
        if not self.first_click_done:
            self.first_click_done = True
            self.generate_bombs((row, col))

        cell["status"] = "revealed"

        if cell["value"] == 'b':
            return "💥 BOOM! Bombe touchée."

        if cell["value"] == 0:
            self.flood_reveal(row, col)
            return "Case vide. Révélation des voisines."
        else:
            return f"La case contient le chiffre {cell['value']}."

    def flood_reveal(self, start_row: int, start_col: int):
        """
        Révélation en cascade (flood fill) des 0 adjacents.
        """
        queue = deque()
        queue.append((start_row, start_col))

        while queue:
            r, c = queue.popleft()
            for dr, dc in [
                (-1, -1), (-1, 0), (-1, 1),
                (0, -1),           (0, 1),
                (1, -1),  (1, 0),  (1, 1)
            ]:
                nr, nc = r + dr, c + dc
                if self.is_valid_coords(nr, nc):
                    neighbor = self.board[(nr, nc)]
                    if neighbor["status"] == "hidden" and neighbor["value"] != 'b':
                        neighbor["status"] = "revealed"
                        if neighbor["value"] == 0:
                            queue.append((nr, nc))

    def flag_case(self, row: int, col: int, user_id: int) -> str:
        """
        Pose / enlève un drapeau sur (row, col) pour user_id.
        """
        if not self.is_valid_coords(row, col):
            return "La case est hors de la grille."

        cell = self.board[(row, col)]
        if cell["status"] == "revealed":
            return "Cette case est déjà révélée, impossible de flag."

        if cell["status"] == "flagged":
            # On enlève le drapeau
            cell["status"] = "hidden"
            cell["flag_owner"] = None
            return "Drapeau retiré."
        else:
            # On pose un drapeau
            cell["status"] = "flagged"
            cell["flag_owner"] = user_id
            return "Drapeau placé."

    def count_all_flags(self) -> int:
        """Retourne le nombre total de drapeaux placés."""
        return sum(1 for cell in self.board.values() if cell["status"] == "flagged")

    def count_flags_by_user(self, user_id: int) -> int:
        """
        Retourne le nombre de bombes que user_id a effectivement drapeau-tisées.
        (i.e. drapeau posé sur une case "value" = 'b').
        """
        count = 0
        for cell in self.board.values():
            if cell["status"] == "flagged" and cell["flag_owner"] == user_id and cell["value"] == 'b':
                count += 1
        return count

    def is_all_safe_revealed(self) -> bool:
        """
        True si toutes les cases non-bombes sont révélées.
        """
        for cell in self.board.values():
            if cell["value"] != 'b' and cell["status"] != 'revealed':
                return False
        return True

    def force_reveal_all(self):
        """
        Révèle toutes les cases (pour l'affichage final).
        """
        for cell in self.board.values():
            cell["status"] = "revealed"

    def print_board_text(self) -> str:
        """
        Représentation texte de la grille.
        """
        header = "   " + " ".join(chr(ord('A') + c) for c in range(self.size))
        lines = [header]

        for r in range(self.size):
            row_cells = []
            for c in range(self.size):
                cell = self.board[(r, c)]
                if cell["status"] == "hidden":
                    row_cells.append("■")
                elif cell["status"] == "flagged":
                    row_cells.append("🚩")
                else:
                    if cell["value"] == 'b':
                        row_cells.append("💣")
                    elif cell["value"] == 0:
                        row_cells.append(" ")
                    else:
                        row_cells.append(str(cell["value"]))
            lines.append(f"{str(r+1).rjust(2)} " + " ".join(row_cells))
        return "\n".join(lines)
