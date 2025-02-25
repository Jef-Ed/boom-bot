from discord.user import User
from discord.member import Member
from typing import Optional
from games import MinesweeperGame, GameData
from discord.ext.commands import Context

def find_member_by_id(members: list[User | Member], member_id) -> Optional[User | Member]:
    for member in members:
        if member.id == member_id:
            return member
    return None

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

def validate_move(ctx: Context, data: GameData, case: str, is_flag: bool = False) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Vérifie si un mouvement est valide.
    Retourne un tuple (message d'erreur, ligne, colonne).
    """
    game = data["game"]

    if ctx.author != data["turn_order"][data["current_player_index"]]:
        return "Ce n'est pas ton tour.", None, None

    if is_flag and not game.first_click_done:
        return "Pas de drapeau avant la première révélation. Réessayez.", None, None

    row, col = convert_case_to_coords(case)
    if not game.is_valid_coords(row, col):
        return "Coup interdit (hors de la grille). Réessayez.", None, None

    return None, row, col

def remove_player_from_game(data: GameData, member: User | Member):
    turn_order = data["turn_order"]
    if member in turn_order:
        idx = turn_order.index(member)
        turn_order.remove(member)
        data["elimination_order"].append(member)
        if idx < data["current_player_index"]:
            data["current_player_index"] -= 1
        if turn_order:
            data["current_player_index"] %= len(turn_order)

async def pass_to_next_player(ctx: Context, data: GameData):
    data["current_player_index"] = (data["current_player_index"] + 1) % len(data["turn_order"])
    next_player = data["turn_order"][data["current_player_index"]]
    await ctx.send(f"Tour de {next_player.mention}.")

async def display_map_in_chunks(ctx: Context, game: MinesweeperGame):
    board_text = game.print_board_text()
    bombs_left = game.bomb_count - game.count_all_flags()
    await send_map_in_chunks(ctx, board_text, bombs_left)

async def send_map_in_chunks(ctx: Context, board_text: str, bombs_left: int):
    lines = board_text.split("\n")
    chunk1 = lines[0:5]
    chunk2 = lines[5:9]
    chunk3 = lines[9:13]

    await ctx.send("\n".join(chunk1))
    await ctx.send("\n".join(chunk2))
    await ctx.send(f"{"\n".join(chunk3)}\n\nBombes restantes: {bombs_left}")

async def check_end_game(data) -> tuple[bool, Optional[str]]:
    turn_order = data["turn_order"]
    game: MinesweeperGame = data["game"]

    if len(turn_order) == 1:
        return True, "one_left"
    elif game.is_all_safe_revealed():
        return True, "all_solved"
    
    return False, None

async def finalize_and_rank(data: GameData, scenario: Optional[str], last_click=None, bomb_clicked=False, safe_flag_clicked=False) -> list[str]:
    """
    Modifie la map finale (header, bomb_e, flag_e, etc.) selon scenario,
    puis construit un classement.
    Retourne la liste de lignes (strings) à envoyer.
    """
    game: MinesweeperGame = data["game"]
    turn_order = data["turn_order"]
    elimination_order = data["elimination_order"]

    final_map = game.finalize_endgame(
        scenario,
        last_click=last_click,
        bomb_clicked=bomb_clicked,
        safe_flag_clicked=safe_flag_clicked
    )

    # Construire le classement
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
        winner: User | Member = survivors[0]
        lines.append(f"{winner.mention} est le dernier survivant ! Fin de partie.")
    else:
        lines.append(f"C'est quoi ce scenario de Fin de partie ?")

    lines.append(final_map)

    pos = 1
    for (player, sc, elim) in ranking_list:
        st = "(Éliminé)" if elim else "(Survivant)"
        lines.append(f"{pos}. {player.display_name} {st} - Drapeau trouvés: {sc}")
        pos += 1

    return lines