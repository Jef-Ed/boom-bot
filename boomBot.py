import discord
from discord.ext import commands
from discord.ext.commands import Context
from typing import Optional
import random
from config.config import Config
from games import MinesweeperGame, GameData
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

games_in_progress: dict[int, GameData] = {}

@bot.event
async def on_ready():
    print(f"{bot.user} est en ligne !")
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game("Démineur !")
    )

@bot.command(name="boom")
async def boom_command(ctx: Context, *args):
    """
    Commande pour démarrer une nouvelle partie de démineur ou afficher les règles.
    !boom @joueur1 @joueur2 ... (2 à 4 joueurs) - Démarre une nouvelle partie avec les joueurs mentionnés.
    !boom rules - Affiche les règles du jeu.
    """
    if len(args) == 1 and args[0].lower() == "rules":
        rules_text = (
            "**Règles du démineur :**\n"
            "- `!r A1` pour révéler A1\n"
            "- `!f A1` pour poser un drapeau en A1\n"
            "- Cliquer sur un drapeau adverse:\n"
            "   - s'il y a une bombe, vous perdez\n"
            "   - sinon, l'autre joueur perd.\n"
            "- Dernier survivant gagne ou si le puzzle est terminé on compte les drapeaux.\n"
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
        "Utilisez `!r A1` pour révéler, `!f A1` pour poser un drapeau.\n"
    )

    board_text = new_game.print_board_text()
    bombs_left = new_game.bomb_count - new_game.count_all_flags()
    await send_map_in_chunks(ctx, board_text, bombs_left)


@bot.command(name="r")
async def reveal_command(ctx: Context, case: str):
    channel_id = ctx.channel.id
    if channel_id not in games_in_progress:
        await ctx.send("Aucune partie en cours ici.")
        return

    data = games_in_progress[channel_id]
    game = data["game"]
    
    error_msg, row, col = validate_move(ctx, data, case)
    if error_msg or row is None or col is None:
        if error_msg:
            await ctx.send(error_msg)
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
                loser_member = find_member_by_id(data["turn_order"], owner_id)
                if loser_member:
                    await ctx.send(f"{action_msg}\nDrapeau sans bombe ! {loser_member.mention} est éliminé.")
                    remove_player_from_game(data, loser_member)
                else:
                    await ctx.send(f"{action_msg}\nDrapeau orphelin ? Personne n'est éliminé.")

            ended, scenario = await check_end_game(data)
            if ended:
                await handle_end_of_game(ctx, data, row, col, bomb_clicked=bomb_clicked, safe_flag_clicked=(not bomb_clicked), scenario=scenario)
                return

            await display_map_in_chunks(ctx, game)
            data["current_player_index"] %= len(data["turn_order"])
            next_player = data["turn_order"][data["current_player_index"]]
            await ctx.send(f"Tour de {next_player.mention}.")
            return

    # 2) Révélation classique
    result_msg = game.reveal_case(row, col)
    if ("Impossible" in result_msg) or ("déjà révélée" in result_msg):
        await ctx.send(result_msg + " Réessayez.")
        await display_map_in_chunks(ctx, game)
        return

    bomb_clicked = ("BOOM" in result_msg)
    await ctx.send(f"{action_msg}\n{result_msg}")

    if bomb_clicked:
        await ctx.send(f"{ctx.author.mention} est éliminé !")
        remove_player_from_game(data, ctx.author)

    ended, scenario = await check_end_game(data)
    if ended:
        await handle_end_of_game(ctx, data, row, col,
                                 bomb_clicked=bomb_clicked,
                                 safe_flag_clicked=(not bomb_clicked),
                                 scenario=scenario)
        return
        
    await display_map_in_chunks(ctx, game)
    await pass_to_next_player(ctx, data)


@bot.command(name="f")
async def flag_command(ctx: Context, case: str):
    channel_id = ctx.channel.id
    if channel_id not in games_in_progress:
        await ctx.send("Pas de partie en cours.")
        return

    data = games_in_progress[channel_id]
    game = data["game"]
    
    error_msg, row, col = validate_move(ctx, data, case, is_flag=True)
    if error_msg:
        await ctx.send(error_msg)
        return

    msg = game.flag_case(row, col, ctx.author.id)
    if "Impossible" in msg or "déjà révélée" in msg or "hors de la grille" in msg:
        await ctx.send(msg + " (coup interdit, rejouez).")
        await display_map_in_chunks(ctx, game)
        return
    
    ended, scenario = await check_end_game(data)
    if ended:
        await handle_end_of_game(ctx, data, row, col,
                                 bomb_clicked=False,
                                 safe_flag_clicked=False,
                                 scenario=scenario)
        return

    await ctx.send(f"{ctx.author.mention} : {msg}")
    await display_map_in_chunks(ctx, game)
    await pass_to_next_player(ctx, data)

async def handle_end_of_game(ctx: Context, data: GameData, row, col, bomb_clicked, safe_flag_clicked, scenario):
    """
    Gère la fin de partie en affichant la map et le classement.
    """
    game = data["game"]
    bomb_count = game.bomb_count

    final_msg = await finalize_and_rank(data, scenario=scenario,
                                        last_click=(row, col),
                                        bomb_clicked=bomb_clicked,
                                        safe_flag_clicked=safe_flag_clicked)
    
    await ctx.send(final_msg[0])
    await send_map_in_chunks(ctx, final_msg[1], bomb_count)
    await ctx.send(final_msg[2])

    games_in_progress.pop(ctx.channel.id, None)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)