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
    """
    Event handler called when the bot is ready.
    Sets the bot's status and prints a message indicating the bot is online.
    """
    print(f"{bot.user} est en ligne !")
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game("Démineur !")
    )

@bot.command(name="boom")
async def boom_command(ctx, *args):
    """
    Commande pour démarrer une nouvelle partie de démineur ou afficher les règles.
    !boom @joueur1 @joueur2 ... (2 à 4 joueurs) - Démarre une nouvelle partie avec les joueurs mentionnés.
    !boom rules - Affiche les règles du jeu.
    """
    if len(args) == 1 and args[0].lower() == "rules":
        rules_text = (
            "**Règles du démineur :**\n"
            "- `!r A1` pour révéler A1\n"
            "- `!f A1` pour poser un drapeau\n"
            "- Cliquer sur un drapeau adverse:\n"
            "   - s'il y a une bombe, vous perdez\n"
            "   - sinon, l'autre joueur perd.\n"
            "- Dernier survivant gagne ou puzzle terminé => on compare les scores.\n"
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

    # Création de la partie
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
        "Utilisez `!r <Case>` pour révéler, `!f <Case>` pour poser un drapeau.\n"
    )

    # Affichage initial
    board_text = new_game.print_board_text()
    bombs_left = new_game.bomb_count - new_game.count_all_flags()
    await send_map_in_chunks(ctx, board_text, bombs_left)


@bot.command(name="r")
async def reveal_command(ctx, case: str):
    channel_id = ctx.channel.id
    if channel_id not in games_in_progress:
        await ctx.send("Aucune partie en cours ici.")
        return

    data = games_in_progress[channel_id]
    game: MinesweeperGame = data["game"]
    turn_order = data["turn_order"]
    i_current = data["current_player_index"]
    current_player = turn_order[i_current]

    if ctx.author != current_player:
        await ctx.send("Ce n'est pas ton tour.")
        return

    row, col = convert_case_to_coords(case)
    if not game.is_valid_coords(row, col):
        await ctx.send("Coup interdit (hors de la grille). Réessayez.")
        return

    cell = game.board[(row, col)]
    action_msg = f"{ctx.author.mention} a révélé la case {case}."

    # 1) Case drapeau adverse ?
    if cell["status"] == "flagged":
        if cell["flag_owner"] == ctx.author.id:
            await ctx.send("Coup interdit (c'est TON propre drapeau). Réessayez.")
            return
        else:
            # On révèle un drapeau adverse
            cell["status"] = "revealed"
            bomb_clicked = (cell["value"] == 'b')
            if bomb_clicked:
                await ctx.send(f"{action_msg}\n💥 Bombe sous le drapeau ! {ctx.author.mention} est éliminé.")
                remove_player_from_game(data, ctx.author)
            else:
                owner_id = cell["flag_owner"]
                loser_member = find_member_by_id(turn_order, owner_id)
                if loser_member:
                    await ctx.send(f"{action_msg}\nDrapeau sans bombe ! {loser_member.mention} est éliminé.")
                    remove_player_from_game(data, loser_member)
                else:
                    await ctx.send(f"{action_msg}\nDrapeau orphelin ? Personne n'est éliminé.")

            ended = await check_end_game(ctx, data, last_click=(row, col), bomb_clicked=bomb_clicked, safe_flag_clicked=(not bomb_clicked))
            if ended:
                scenario_is_one_left = await which_end_game(ctx, data, last_click=(row,col), bomb_clicked=False, safe_flag_clicked=False)
                if scenario_is_one_left:
                    final_msg = await finalize_and_rank(ctx, data, scenario='one_left',
                        last_click=(row,col), bomb_clicked=False, safe_flag_clicked=False)
                    await ctx.send(final_msg[0])
                    await send_map_in_chunks(ctx, final_msg[1], game.bomb_count)
                    await ctx.send(final_msg[2])
                    games_in_progress.pop(ctx.channel.id, None)
                    return
                else:
                    final_msg = await finalize_and_rank(ctx, data, scenario='all_solved')
                    await ctx.send(final_msg[0])
                    await send_map_in_chunks(ctx, final_msg[1], game.bomb_count)
                    await ctx.send(final_msg[2])
                    games_in_progress.pop(ctx.channel.id, None)
                    return

            await display_map_in_chunks(ctx, game, data)
            data["current_player_index"] %= len(data["turn_order"])
            next_player = data["turn_order"][data["current_player_index"]]
            await ctx.send(f"Tour de {next_player.mention}.")
            return

    # 2) Révélation classique
    result_msg = game.reveal_case(row, col)
    if ("Impossible" in result_msg) or ("déjà révélée" in result_msg):
        await ctx.send(result_msg + " Réessayez.")
        await display_map_in_chunks(ctx, game, data)
        return

    bomb_clicked = ("BOOM" in result_msg)
    await ctx.send(f"{action_msg}\n{result_msg}")

    if bomb_clicked:
        await ctx.send(f"{ctx.author.mention} est éliminé !")
        remove_player_from_game(data, ctx.author)

    ended = await check_end_game(ctx, data, last_click=(row, col), bomb_clicked=bomb_clicked, safe_flag_clicked=False)
    if ended:
        scenario_is_one_left = await which_end_game(ctx, data, last_click=(row,col), bomb_clicked=False, safe_flag_clicked=False)
        if scenario_is_one_left:
            final_msg = await finalize_and_rank(ctx, data, scenario='one_left',
                last_click=(row,col), bomb_clicked=False, safe_flag_clicked=False)
            await ctx.send(final_msg[0])
            await send_map_in_chunks(ctx, final_msg[1], game.bomb_count)
            await ctx.send(final_msg[2])
            games_in_progress.pop(ctx.channel.id, None)
            return
        else:
            final_msg = await finalize_and_rank(ctx, data, scenario='all_solved')
            await ctx.send(final_msg[0])
            await send_map_in_chunks(ctx, final_msg[1], game.bomb_count)
            await ctx.send(final_msg[2])
            games_in_progress.pop(ctx.channel.id, None)
            return
        
    await display_map_in_chunks(ctx, game, data)
    
    data["current_player_index"] = (data["current_player_index"] + 1) % len(data["turn_order"])
    next_player = data["turn_order"][data["current_player_index"]]
    await ctx.send(f"Tour de {next_player.mention}.")


@bot.command(name="f")
async def flag_command(ctx, case: str):
    channel_id = ctx.channel.id
    if channel_id not in games_in_progress:
        await ctx.send("Pas de partie en cours.")
        return

    data = games_in_progress[channel_id]
    game: MinesweeperGame = data["game"]
    turn_order = data["turn_order"]
    i_current = data["current_player_index"]
    current_player = turn_order[i_current]

    if ctx.author != current_player:
        await ctx.send("Ce n'est pas ton tour.")
        return

    if not game.first_click_done:
        await ctx.send("Pas de drapeau avant la première révélation. Réessayez.")
        return

    row, col = convert_case_to_coords(case)
    if not game.is_valid_coords(row, col):
        await ctx.send("Coup interdit (hors grille). Réessayez.")
        return

    msg = game.flag_case(row, col, ctx.author.id)
    if "Impossible" in msg or "déjà révélée" in msg or "hors de la grille" in msg:
        await ctx.send(msg + " (coup interdit, rejouez).")
        await display_map_in_chunks(ctx, game, data)
        return

    await ctx.send(f"{ctx.author.mention} : {msg}")

    ended = await check_end_game(ctx, data, last_click=(row,col), bomb_clicked=False, safe_flag_clicked=False)
    if ended:
        scenario_is_one_left = await which_end_game(ctx, data, last_click=(row,col), bomb_clicked=False, safe_flag_clicked=False)
        if scenario_is_one_left:
            final_msg = await finalize_and_rank(ctx, data, scenario='one_left',
                last_click=(row,col), bomb_clicked=False, safe_flag_clicked=False)
            await ctx.send(final_msg[0])
            await send_map_in_chunks(ctx, final_msg[1], game.bomb_count)
            await ctx.send(final_msg[2])
            games_in_progress.pop(ctx.channel.id, None)
            return
        else:
            final_msg = await finalize_and_rank(ctx, data, scenario='all_solved')
            await ctx.send(final_msg[0])
            await send_map_in_chunks(ctx, final_msg[1], game.bomb_count)
            await ctx.send(final_msg[2])
            games_in_progress.pop(ctx.channel.id, None)
            return
    
    await display_map_in_chunks(ctx, game, data)

    data["current_player_index"] = (i_current + 1) % len(data["turn_order"])
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