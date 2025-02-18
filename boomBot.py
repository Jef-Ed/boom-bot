import discord
from discord.ext import commands
from typing import Optional
import random

from config.config import Config
from games import MinesweeperGame

config = Config()
DISCORD_TOKEN: Optional[str] = config.get("discord.token")

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionnaire de parties par channel
games_in_progress = {}

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    await bot.change_presence(status=discord.Status.online,
                             activity=discord.Game("Démineur !"))

@bot.command(name="boom")
async def boom_command(ctx, *args):
    """
    Commande !boom
    - !boom @player1 @player2 ... -> démarre une partie multi-joueurs (2 à 4 joueurs).
    - !boom rules -> affiche les règles du démineur.
    """
    if len(args) == 1 and args[0].lower() == "rules":
        rules_text = (
            "**Règles du démineur :**\n"
            "- Commandes de base :\n"
            "  `!r A1` pour révéler A1\n"
            "  `!f A1` pour poser/enlever un drapeau sur A1\n"
            "- On ne peut pas commencer par un drapeau.\n"
            "- Cliquer sur un drapeau adverse provoque l'élimination de celui qui clique si c'est une bombe, "
            " ou de l'adversaire si la case est sûre.\n"
            "- Dernier survivant gagne ou fin de map → on compare les scores.\n"
        )
        await ctx.send(rules_text)
        return

    mentioned_players = ctx.message.mentions
    nb_players = len(mentioned_players)

    # Min 2, max 4
    if nb_players < 2:
        await ctx.send("Il faut au moins 2 joueurs pour démarrer une partie.")
        return
    if nb_players > 4:
        await ctx.send("Maximum 4 joueurs autorisés pour une partie.")
        return

    # Créer la partie
    new_game = MinesweeperGame(size=16, bomb_count=40)
    channel_id = ctx.channel.id

    turn_order = list(mentioned_players)
    random.shuffle(turn_order)

    games_in_progress[channel_id] = {
        "game": new_game,
        "turn_order": turn_order,  # liste de discord.Member
        "current_player_index": 0,
        "elimination_order": []
    }

    first_player = turn_order[0]
    await ctx.send(
        f"Nouvelle partie démarrée avec {', '.join(p.mention for p in turn_order)}!\n"
        f"Tour de {first_player.mention}.\n"
        f"Utilisez `!r <Case>` pour révéler (obligatoire au premier coup), `!f <Case>` pour drapeau.\n"
    )

    # Affichage initial
    board_text = new_game.print_board_text()
    bombes_restantes = new_game.bomb_count - new_game.count_all_flags()
    await ctx.send(f"```\n{board_text}\n```\nBombes restantes: **{bombes_restantes}**")

@bot.command(name="r")
async def reveal_command(ctx, case: str):
    """
    Commande !r <Case> pour révéler la case (ex: !r A1).
    """
    channel_id = ctx.channel.id
    if channel_id not in games_in_progress:
        await ctx.send("Aucune partie en cours ici. Lancez-en une avec !boom.")
        return

    data = games_in_progress[channel_id]
    game = data["game"]
    turn_order = data["turn_order"]
    i_current = data["current_player_index"]
    current_player = turn_order[i_current]

    # Vérif du tour
    if ctx.author != current_player:
        await ctx.send(f"Ce n'est pas votre tour, {ctx.author.mention}!")
        return

    # Convertit ex: "A1" en (0, 0)
    row, col = convert_case_to_coords(case)
    if not game.is_valid_coords(row, col):
        await ctx.send(f"La case {case} est hors de la grille. (Coup interdit, rejouez)")
        return

    cell = game.board[(row, col)]

    # Log de l'action
    action_msg = f"{ctx.author.mention} a révélé la case {case}."

    # Cas: la case est drapeau ?
    if cell["status"] == "flagged":
        # Est-ce le drapeau du joueur lui-même ?
        if cell["flag_owner"] == ctx.author.id:
            await ctx.send("Vous ne pouvez pas révéler VOTRE propre drapeau. (Coup interdit, rejouez)")
            return
        else:
            # Drapeau adverse => on révèle
            cell["status"] = "revealed"
            is_bomb = (cell["value"] == 'b')
            if is_bomb:
                # L'attaquant perd
                await ctx.send(
                    f"{action_msg}\n"
                    f"💥 Bombe trouvée sous le drapeau. {ctx.author.mention} est éliminé !"
                )
                remove_player_from_game(data, ctx.author)
            else:
                # Le propriétaire du drapeau perd
                owner_id = cell["flag_owner"]
                loser_member = find_member_by_id(turn_order, owner_id)
                if loser_member:
                    await ctx.send(
                        f"{action_msg}\n"
                        f"Ce drapeau était faux ! {loser_member.mention} est éliminé !"
                    )
                    remove_player_from_game(data, loser_member)
                else:
                    await ctx.send(
                        f"{action_msg}\n"
                        "Le propriétaire de ce drapeau n'existe plus, rien ne se passe."
                    )

            # Affichage de la map
            board_text = game.print_board_text()
            bombes_restantes = game.bomb_count - game.count_all_flags()
            await ctx.send(f"```\n{board_text}\n```\nBombes restantes: **{bombes_restantes}**")

            # Fin de partie ?
            if end_game_if_needed(ctx, data):
                return

            # Coup validé => next player
            data["current_player_index"] %= len(data["turn_order"])
            next_player = data["turn_order"][data["current_player_index"]]
            await ctx.send(f"C'est maintenant au tour de {next_player.mention} !")
            return

    # Cas standard : reveal normal
    result_msg = game.reveal_case(row, col)
    if "Impossible" in result_msg:
        await ctx.send(result_msg + " (coup interdit, rejouez).")
        return

    await ctx.send(f"{action_msg}\n{result_msg}")

    # Bombe ?
    if "BOOM" in result_msg:
        # Le joueur courant perd
        await ctx.send(f"{ctx.author.mention} est éliminé !")
        remove_player_from_game(data, ctx.author)

        # Afficher la map
        board_text = game.print_board_text()
        bombes_restantes = game.bomb_count - game.count_all_flags()
        await ctx.send(f"```\n{board_text}\n```\nBombes restantes: **{bombes_restantes}**")

        if end_game_if_needed(ctx, data):
            return

        # Tour suivant
        data["current_player_index"] %= len(data["turn_order"])
        next_player = data["turn_order"][data["current_player_index"]]
        await ctx.send(f"C'est maintenant au tour de {next_player.mention} !")
    else:
        # Reveal valide
        board_text = game.print_board_text()
        bombes_restantes = game.bomb_count - game.count_all_flags()
        await ctx.send(f"```\n{board_text}\n```\nBombes restantes: **{bombes_restantes}**")

        # Check si la map est complétée ?
        if game.is_all_safe_revealed():
            # Tous les joueurs survivants partagent la victoire => on fait un classement
            await ctx.send("Toutes les cases sûres ont été révélées. Partie terminée !")
            end_game_with_ranking(ctx, data, completed_map=True)
            return

        # Next player
        data["current_player_index"] = (i_current + 1) % len(turn_order)
        next_player = turn_order[data["current_player_index"]]
        await ctx.send(f"C'est maintenant au tour de {next_player.mention} !")

@bot.command(name="f")
async def flag_command(ctx, case: str):
    """
    Commande !f <Case> pour poser ou retirer un drapeau sur la case.
    Interdit si la partie n'a pas encore eu son premier reveal.
    """
    channel_id = ctx.channel.id
    if channel_id not in games_in_progress:
        await ctx.send("Aucune partie en cours ici. Lancez-en une avec !boom.")
        return

    data = games_in_progress[channel_id]
    game = data["game"]
    turn_order = data["turn_order"]
    i_current = data["current_player_index"]
    current_player = turn_order[i_current]

    if ctx.author != current_player:
        await ctx.send(f"Ce n'est pas votre tour, {ctx.author.mention}!")
        return

    # Empêcher de commencer par un drapeau
    if not game.first_click_done:
        await ctx.send("Vous ne pouvez pas poser de drapeau avant le premier reveal ! (Coup interdit, rejouez)")
        return

    row, col = convert_case_to_coords(case)
    if not game.is_valid_coords(row, col):
        await ctx.send(f"La case {case} est hors de la grille. (Coup interdit, rejouez)")
        return

    msg = game.flag_case(row, col, ctx.author.id)
    if "révélée" in msg.lower():
        await ctx.send(msg + " (coup interdit, rejouez).")
        return

    # Action
    if "Drapeau placé" in msg:
        action_msg = f"{ctx.author.mention} a placé un drapeau sur la case {case}."
    elif "retiré" in msg.lower():
        action_msg = f"{ctx.author.mention} a retiré le drapeau de la case {case}."
    else:
        action_msg = f"{ctx.author.mention} a modifié le drapeau de la case {case}."

    await ctx.send(f"{action_msg}\n{msg}")

    # Affichage map
    board_text = game.print_board_text()
    bombes_restantes = game.bomb_count - game.count_all_flags()
    await ctx.send(f"```\n{board_text}\n```\nBombes restantes: **{bombes_restantes}**")

    # Coup validé => next player
    data["current_player_index"] = (i_current + 1) % len(turn_order)
    next_player = turn_order[data["current_player_index"]]
    await ctx.send(f"C'est maintenant au tour de {next_player.mention} !")

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


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)