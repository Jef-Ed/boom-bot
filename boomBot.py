import discord
from discord.ext import commands
from typing import Optional
import random

from config.config import Config
from games import MinesweeperGame
from utils import *

config = Config()
DISCORD_TOKEN: Optional[str] = config.get("discord.token")

if not isinstance(DISCORD_TOKEN, str) or not DISCORD_TOKEN.strip():
    raise ValueError("Error: Discord bot token is invalid or missing from config.yml")

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionnary of game per channel
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

    if nb_players < 2:
        await ctx.send("Il faut au moins 2 joueurs pour démarrer une partie.")
        return
    if nb_players > 4:
        await ctx.send("Maximum 4 joueurs autorisés pour une partie.")
        return

    # Create the actual game
    new_game = MinesweeperGame(size=16, bomb_count=40)
    channel_id = ctx.channel.id

    turn_order = list(mentioned_players)
    random.shuffle(turn_order)

    games_in_progress[channel_id] = {
        "game": new_game,
        "turn_order": turn_order,
        "current_player_index": 0,
        "elimination_order": []
    }

    first_player = turn_order[0]
    await ctx.send(
        f"Nouvelle partie démarrée avec {', '.join(p.mention for p in turn_order)}!\n"
        f"Tour de {first_player.mention}.\n"
        f"Utilisez `!r <Case>` pour révéler (obligatoire au premier coup), `!f <Case>` pour drapeau.\n"
    )

    # Visual display
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

    # Is your turn?
    if ctx.author != current_player:
        await ctx.send(f"Ce n'est pas votre tour, {ctx.author.mention}!")
        return

    # Convert ex: "A1" to (0, 0)
    row, col = convert_case_to_coords(case)
    if not game.is_valid_coords(row, col):
        await ctx.send(f"La case {case} est hors de la grille. (Coup interdit, rejouez)")
        return

    cell = game.board[(row, col)]

    # Log action
    action_msg = f"{ctx.author.mention} a révélé la case {case}."

    # Case: Is case a flag?
    if cell["status"] == "flagged":
        # DOes flag belong to player?
        if cell["flag_owner"] == ctx.author.id:
            await ctx.send("Vous ne pouvez pas révéler VOTRE propre drapeau. (Coup interdit, rejouez)")
            return
        else:
            # Ennemy flag => reveal
            cell["status"] = "revealed"
            is_bomb = (cell["value"] == 'b')
            if is_bomb:
                # Attacking player loses
                await ctx.send(
                    f"{action_msg}\n"
                    f"💥 Bombe trouvée sous le drapeau. {ctx.author.mention} est éliminé !"
                )
                remove_player_from_game(data, ctx.author)
            else:
                # Flag owner loses
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

            # Display map
            board_text = game.print_board_text()
            bombes_restantes = game.bomb_count - game.count_all_flags()
            await ctx.send(f"```\n{board_text}\n```\nBombes restantes: **{bombes_restantes}**")

            # Does game end?
            if end_game_if_needed(ctx, data):
                return

            # Valid move => next player
            data["current_player_index"] %= len(data["turn_order"])
            next_player = data["turn_order"][data["current_player_index"]]
            await ctx.send(f"C'est maintenant au tour de {next_player.mention} !")
            return

    # Standard case : normal reveal
    result_msg = game.reveal_case(row, col)
    if "Impossible" in result_msg:
        await ctx.send(result_msg + " (coup interdit, rejouez).")
        return

    await ctx.send(f"{action_msg}\n{result_msg}")

    # Bomb?
    if "BOOM" in result_msg:
        # Current player loses
        await ctx.send(f"{ctx.author.mention} est éliminé !")
        remove_player_from_game(data, ctx.author)

        # Display map
        board_text = game.print_board_text()
        bombes_restantes = game.bomb_count - game.count_all_flags()
        await ctx.send(f"```\n{board_text}\n```\nBombes restantes: **{bombes_restantes}**")

        if end_game_if_needed(ctx, data):
            return

        # Next turn
        data["current_player_index"] %= len(data["turn_order"])
        next_player = data["turn_order"][data["current_player_index"]]
        await ctx.send(f"C'est maintenant au tour de {next_player.mention} !")
    else:
        # Valid reveal
        board_text = game.print_board_text()
        bombes_restantes = game.bomb_count - game.count_all_flags()
        await ctx.send(f"```\n{board_text}\n```\nBombes restantes: **{bombes_restantes}**")

        # Is map complete?
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

    # Avoid starting with a flag
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

    # Display map
    board_text = game.print_board_text()
    bombes_restantes = game.bomb_count - game.count_all_flags()
    await ctx.send(f"```\n{board_text}\n```\nBombes restantes: **{bombes_restantes}**")

    # Valid move => next player
    data["current_player_index"] = (i_current + 1) % len(turn_order)
    next_player = turn_order[data["current_player_index"]]
    await ctx.send(f"C'est maintenant au tour de {next_player.mention} !")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)