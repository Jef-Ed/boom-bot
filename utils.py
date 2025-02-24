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

def convert_case_to_coords(case: str) -> tuple[int, int]:
    case = case.strip().upper()
    col_part, row_part = "", ""
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
    return (row, col)

async def check_end_game(ctx, data, last_click=None, bomb_clicked=False, safe_flag_clicked=False):
    turn_order = data["turn_order"]
    game = data["game"]

    if len(turn_order) == 1:
        return True, "one_left"
    elif game.is_all_safe_revealed():
        return True, "all_solved"
    
    return False, None

async def finalize_and_rank(ctx, data, scenario, last_click=None, bomb_clicked=False, safe_flag_clicked=False):
    """
    Modifie la map finale (header, bomb_e, flag_e, etc.) selon scenario,
    puis construit un classement.
    Retourne la liste de lignes (strings) à envoyer.
    """
    game = data["game"]
    turn_order = data["turn_order"]
    elimination_order = data["elimination_order"]

    final_map = game.finalize_endgame(
        scenario,
        last_click=last_click,
        bomb_clicked=bomb_clicked,
        safe_flag_clicked=safe_flag_clicked
    )

    # Construire le classement
    # Survivants => tri desc par nb bombes drapeau-tisées
    survivors = list(turn_order)
    survivors.sort(key=lambda p: game.count_flags_by_user(p.id), reverse=True)
    
    # On réunit ensuite les éliminés dans l'ordre
    ranking_list = []
    for p in survivors:
        sc = game.count_flags_by_user(p.id)
        ranking_list.append((p, sc, False))
    for e in elimination_order:
        sc = game.count_flags_by_user(e.id)
        ranking_list.append((e, sc, True))

    lines = []
    if scenario == 'all_solved':
        lines.append("**Fin de partie : puzzle complété !**")
    elif len(survivors) == 1:
        winner = survivors[0]
        lines.append(f"{winner.mention} est le dernier survivant ! Fin de partie.")
    else:
        lines.append(f"C'est quoi ce scenario de Fin de partie ?")

    lines.append(final_map)

    pos = 1
    for (pl, sc, elim) in ranking_list:
        st = "(Éliminé)" if elim else "(Survivant)"
        lines.append(f"{pos}. {pl.display_name} {st} - Bombes drapeau-tisées: {sc}")
        pos += 1

    data["game"] = None
    return lines