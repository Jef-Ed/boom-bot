
def find_member_by_id(members, member_id):
    """
    Trouve un membre dans une liste de membres Discord par son ID.
    """
    for member in members:
        if member.id == member_id:
            return member
    return None

def remove_player_from_game(data, member):
    """
    Élimine `member` du turn_order, l'ajoute à elimination_order.
    """
    turn_order = data["turn_order"]
    if member in turn_order:
        idx = turn_order.index(member)
        turn_order.remove(member)
        data["elimination_order"].append(member)  # ordre d'élimination
        if idx < data["current_player_index"]:
            data["current_player_index"] -= 1
        if turn_order:
            data["current_player_index"] %= len(turn_order)

def end_game_if_needed(ctx, data) -> bool:
    """
    Vérifie s'il reste 0 ou 1 joueur :
      - 0 joueur => plus personne, fin sans vainqueur ?
      - 1 joueur => last survivor = vainqueur
    Sinon, on continue.
    Retourne True si la partie est terminée.
    """
    turn_order = data["turn_order"]
    if len(turn_order) == 0:
        ctx.send("Plus aucun joueur en jeu, partie terminée !")
        end_game_with_ranking(ctx, data, completed_map=False)
        return True
    if len(turn_order) == 1:
        winner = turn_order[0]
        ctx.send(f"{winner.mention} est le dernier survivant ! Partie terminée.")
        end_game_with_ranking(ctx, data, completed_map=False)
        return True
    return False

def convert_case_to_coords(case: str) -> tuple[int, int]:
    """
    Convertit 'A1' en (0, 0), etc.
    Gère plusieurs lettres pour la colonne si nécessaire.
    """
    case = case.strip().upper()
    col_part = ""
    row_part = ""

    for char in case:
        if char.isalpha():
            col_part += char
        elif char.isdigit():
            row_part += char

    if not col_part or not row_part:
        return -1, -1  # Hors de la grille

    # Conversion type Excel (A=0, B=1, ... Z=25, AA=26, ...)
    col = 0
    for ch in col_part:
        col = col * 26 + (ord(ch) - ord('A') + 1)
    col -= 1

    row = int(row_part) - 1
    return row, col

def end_game_with_ranking(ctx, data, completed_map: bool):
    """
    Fin de partie : on révèle la map et on affiche un classement.
    completed_map = True si on a révélé toutes les cases sûres (égalité).
    """
    game = data["game"]
    turn_order = data["turn_order"]
    elimination_order = data["elimination_order"]  # ordre d'élimination

    # Révéler la map
    game.force_reveal_all()
    board_text = game.print_board_text()

    # Construire un classement
    # 1) Les joueurs survivants (dans l'ordre actuel) sont en haut du classement
    # 2) Ensuite, ceux éliminés en ordre inverse d'élimination (le dernier éliminé est plus haut)
    survivors = list(turn_order)  # non éliminés
    eliminated = list(elimination_order)  # ordre d'élimination
    # On va calculer un "score" => +1 par bombe effectivement drapeau-tisée
    ranking_list = []

    # Survivants => on leur calcule le score
    for player in survivors:
        score = game.count_flags_by_user(player.id)
        ranking_list.append((player, score, False))  # (joueur, score, is_eliminated=False)

    # Éliminés => dans l'ordre d'élimination, le premier éliminé se retrouve en bas
    # Si tu préfères l'inverse, on peut inverser la liste
    for player in reversed(eliminated):
        score = game.count_flags_by_user(player.id)
        ranking_list.append((player, score, True))

    # Affichage final
    msg_lines = ["**Fin de partie !**"]
    msg_lines.append("Carte révélée :\n```")
    msg_lines.append(board_text)
    msg_lines.append("```")

    # Construit l'affichage du classement
    # Note : si tu veux trier par score, c'est possible, 
    # mais ici on affiche "survivants" puis ordre d'élimination, 
    # en mentionnant le score
