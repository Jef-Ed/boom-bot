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

games_in_progress = {}

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    await bot.change_presence(status=discord.Status.online,
                              activity=discord.Game("Démineur !"))

@bot.command(name="boom")
async def boom_command(ctx, *args):
    if len(args) == 1 and args[0].lower() == "rules":
        rules_text = (
            "**Règles du démineur :**\n"
            "- `!r A1` pour révéler A1\n"
            "- `!f A1` pour poser un drapeau sur A1\n"
            "- Cliquer sur un drapeau adverse:\n"
            "   - s'il y a une bombe, vous perdez\n"
            "   - sinon, l'autre joueur perd.\n"
            "- Dernier survivant gagne ou on compte les drapeaux si on finit la map.\n"
        )
        await ctx.send(rules_text)
        return

    mentioned_players = ctx.message.mentions
    nb_players = len(mentioned_players)
    if nb_players < 2:
        await ctx.send("Il faut au moins 2 joueurs pour démarrer.")
        return
    if nb_players > 4:
        await ctx.send("Maximum 4 joueurs.")
        return

    new_game = MinesweeperGame(size=12, bomb_count=22)
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
        f"Nouvelle partie avec {', '.join(p.mention for p in turn_order)}!\n"
        f"Tour de {first_player.mention}.\n"
        "Utilisez `!r <Case>` pour révéler, `!f <Case>` pour drapeau."
    )

    board_text = new_game.print_board_text()
    bombes_restantes = new_game.bomb_count - new_game.count_all_flags()
    await send_map_in_chunks(ctx, board_text, bombes_restantes)

@bot.command(name="r")
async def reveal_command(ctx, case: str):
    channel_id = ctx.channel.id
    if channel_id not in games_in_progress:
        await ctx.send("Pas de partie en cours ici.")
        return

    data = games_in_progress[channel_id]
    game = data["game"]
    turn_order = data["turn_order"]
    i_current = data["current_player_index"]
    current_player = turn_order[i_current]

    if ctx.author != current_player:
        await ctx.send("Ce n'est pas ton tour.")
        return

    row, col = convert_case_to_coords(case)
    if not game.is_valid_coords(row, col):
        await ctx.send(f"La case {case} est hors de la grille.")
        return

    cell = game.board[(row, col)]
    action_msg = f"{ctx.author.mention} a révélé la case {case}."

    if cell["status"] == "flagged":
        if cell["flag_owner"] == ctx.author.id:
            await ctx.send("Tu ne peux pas révéler TON propre drapeau.")
            return
        else:
            cell["status"] = "revealed"
            if cell["value"] == 'b':
                await ctx.send(f"{action_msg}\n💥 Bombe sous le drapeau ! {ctx.author.mention} éliminé.")
                remove_player_from_game(data, ctx.author)
            else:
                owner_id = cell["flag_owner"]
                loser_member = find_member_by_id(turn_order, owner_id)
                if loser_member:
                    await ctx.send(f"{action_msg}\nLe drapeau était faux ! {loser_member.mention} éliminé.")
                    remove_player_from_game(data, loser_member)
                else:
                    await ctx.send(f"{action_msg}\nDrapeau orphelin ? Personne n'est éliminé.")

            await display_map_in_chunks(ctx, game, data)
            if end_game_if_needed(ctx, data):
                return

            data["current_player_index"] %= len(data["turn_order"])
            next_player = data["turn_order"][data["current_player_index"]]
            await ctx.send(f"Tour de {next_player.mention}.")
            return

    result_msg = game.reveal_case(row, col)
    if "Impossible" in result_msg:
        await ctx.send(result_msg)
        return

    await ctx.send(f"{action_msg}\n{result_msg}")
    if "BOOM" in result_msg:
        await ctx.send(f"{ctx.author.mention} éliminé !")
        remove_player_from_game(data, ctx.author)

        await display_map_in_chunks(ctx, game, data)
        if end_game_if_needed(ctx, data):
            return

        data["current_player_index"] %= len(data["turn_order"])
        next_player = data["turn_order"][data["current_player_index"]]
        await ctx.send(f"Tour de {next_player.mention}.")
    else:
        await display_map_in_chunks(ctx, game, data)
        if game.is_all_safe_revealed():
            await ctx.send("Toutes les cases sûres révélées ! Fin.")
            end_game_with_ranking(ctx, data, completed_map=True)
            return

        data["current_player_index"] = (i_current + 1) % len(turn_order)
        next_player = turn_order[data["current_player_index"]]
        await ctx.send(f"Tour de {next_player.mention}.")

@bot.command(name="f")
async def flag_command(ctx, case: str):
    channel_id = ctx.channel.id
    if channel_id not in games_in_progress:
        await ctx.send("Pas de partie en cours.")
        return

    data = games_in_progress[channel_id]
    game = data["game"]
    turn_order = data["turn_order"]
    i_current = data["current_player_index"]
    current_player = turn_order[i_current]

    if ctx.author != current_player:
        await ctx.send("Ce n'est pas ton tour.")
        return

    if not game.first_click_done:
        await ctx.send("Pas de drapeau avant le premier reveal.")
        return

    row, col = convert_case_to_coords(case)
    if not game.is_valid_coords(row, col):
        await ctx.send("Hors grille.")
        return

    msg = game.flag_case(row, col, ctx.author.id)
    if "révélée" in msg.lower():
        await ctx.send(msg)
        return

    if "Drapeau placé" in msg:
        action_msg = f"{ctx.author.mention} a placé un drapeau sur {case}."
    elif "retiré" in msg.lower():
        action_msg = f"{ctx.author.mention} a retiré le drapeau de {case}."
    else:
        action_msg = f"{ctx.author.mention} a modifié un drapeau sur {case}."

    await ctx.send(f"{action_msg}\n{msg}")
    await display_map_in_chunks(ctx, game, data)

    data["current_player_index"] = (i_current + 1) % len(turn_order)
    next_player = data["turn_order"][data["current_player_index"]]
    await ctx.send(f"Tour de {next_player.mention}.")

async def display_map_in_chunks(ctx, game, data):
    board_text = game.print_board_text()
    bombs_left = game.bomb_count - game.count_all_flags()
    await send_map_in_chunks(ctx, board_text, bombs_left)

async def send_map_in_chunks(ctx, board_text: str, bombs_left: int):
    lines = board_text.split("\n")

    chunk1 = lines[0:5]
    chunk2 = lines[5:9]
    chunk3 = lines[9:13]

    await ctx.send("\n".join(chunk1))
    await ctx.send("\n".join(chunk2))
    await ctx.send(f"{"\n".join(chunk3)}\n\nBombes restantes: {bombs_left}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)