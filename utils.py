def find_member_by_id(members, member_id):
    for member in members:
        if member.id == member_id:
            return member
    return None

def remove_player_from_game(data, member):
    turn_order = data["turn_order"]
    if member in turn_order:
        idx = turn_order.index(member)
        turn_order.remove(member)
        data["elimination_order"].append(member)
        if idx < data["current_player_index"]:
            data["current_player_index"] -= 1
        if turn_order:
            data["current_player_index"] %= len(turn_order)

def end_game_if_needed(ctx, data) -> bool:
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
    case = case.strip().upper()
    col_part = ""
    row_part = ""

    for char in case:
        if char.isalpha():
            col_part += char
        elif char.isdigit():
            row_part += char

    if not col_part or not row_part:
        return -1, -1

    col = 0
    for ch in col_part:
        col = col * 26 + (ord(ch) - ord('A') + 1)
    col -= 1

    row = int(row_part) - 1
    return row, col

def end_game_with_ranking(ctx, data, completed_map: bool):
    game = data["game"]
    turn_order = data["turn_order"]
    elimination_order = data["elimination_order"]

    game.force_reveal_all()
    board_text = game.print_board_text()

    survivors = list(turn_order)
    eliminated = list(elimination_order)
    ranking_list = []

    for player in survivors:
        score = game.count_flags_by_user(player.id)
        ranking_list.append((player, score, False))

    for player in reversed(eliminated):
        score = game.count_flags_by_user(player.id)
        ranking_list.append((player, score, True))

    msg_lines = ["**Fin de partie !**", "Carte révélée :"]
    msg_lines.append(board_text)

    msg_lines.append("**Classement final :**")
    pos = 1
    for (player, score, elim) in ranking_list:
        status = "(Éliminé)" if elim else "(Survivant)"
        msg_lines.append(f"{pos}. {player.display_name} {status} - Bombes drapeau-tisées: {score}")
        pos += 1

    ctx.send("\n".join(msg_lines))
    data["game"] = None
