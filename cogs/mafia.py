"""
cogs/mafia.py
Discord Mafia game cog — supports human players AND AI bots.

Slash commands:
  /join        — Join the game lobby
  /addbot      — Add 1–4 AI bots to fill the lobby
  /start       — Start the game (requires ≥ 3 total players)
  /action      — Night action (Mafia kill / Doctor heal / Cop investigate)
  /vote        — Vote to lynch someone during the day
  /next        — Advance the game phase; bots act automatically
  /status      — Show current game state
  /end         — Force-end the game
"""

import discord
from discord import app_commands
from discord.ext import commands
import random
from collections import Counter

from game.manager import game_manager
from game.models import GamePhase, Role, BotPersonality
from game.bot_ai import (
    BOT_NAMES, PERSONALITY_EMOJI, VOTE_MESSAGES,
    decide_night_action, decide_vote,
    get_discussion_message, get_bot_night_message,
)

# Track used bot names per game session to avoid duplicates
_used_bot_names: set[str] = set()


def _pick_bot_name(personality: BotPersonality) -> str:
    pool = BOT_NAMES.get(personality, ["Bot"])
    available = [n for n in pool if n not in _used_bot_names]
    if not available:
        available = pool  # reset if all names exhausted
    name = random.choice(available)
    _used_bot_names.add(name)
    return name


class MafiaGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─────────────────────────────────────────────────────────────────────────
    # /join
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(name="join", description="Join the Mafia game in this channel")
    async def join_game(self, interaction: discord.Interaction):
        game = game_manager.get_or_create_game(interaction.channel_id)

        if game.phase != GamePhase.LOBBY:
            await interaction.response.send_message(
                "A game is already in progress! Wait for it to finish.", ephemeral=True
            )
            return

        success = game.add_player(interaction.user.id, interaction.user.display_name)
        if success:
            humans = sum(1 for p in game.players.values() if not p.is_bot)
            bots   = len(game.players) - humans
            bot_str = f" + {bots} 🤖" if bots > 0 else ""
            await interaction.response.send_message(
                f"🎭 **{interaction.user.display_name}** has joined the game! "
                f"({humans} human{bot_str} — {len(game.players)} total)\n"
                f"*Use `/addbot` to fill empty slots with AI players.*"
            )
        else:
            await interaction.response.send_message(
                "You have already joined the game!", ephemeral=True
            )

    # ─────────────────────────────────────────────────────────────────────────
    # /addbot
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(name="addbot", description="Add AI bot players to fill the lobby")
    @app_commands.describe(
        count="How many bots to add (1–4)",
        personality="Bot personality type (leave blank for random)"
    )
    @app_commands.choices(personality=[
        app_commands.Choice(name="🔥 Aggressive – votes quickly and boldly",   value="AGGRESSIVE"),
        app_commands.Choice(name="👁️ Paranoid – trusts no one",                value="PARANOID"),
        app_commands.Choice(name="🌿 Passive – quiet and laid-back",            value="PASSIVE"),
        app_commands.Choice(name="🔍 Detective – calculates every move",        value="DETECTIVE"),
        app_commands.Choice(name="🎲 Random – surprise me!",                    value="RANDOM"),
    ])
    async def add_bot(
        self,
        interaction: discord.Interaction,
        count: int = 1,
        personality: str = "RANDOM",
    ):
        game = game_manager.get_or_create_game(interaction.channel_id)

        if game.phase != GamePhase.LOBBY:
            await interaction.response.send_message(
                "You can only add bots during the lobby phase!", ephemeral=True
            )
            return

        count = max(1, min(count, 4))
        personalities = list(BotPersonality)

        embed = discord.Embed(
            title="🤖 Bot Players Added to Lobby",
            color=discord.Color.from_rgb(88, 101, 242),
        )

        for _ in range(count):
            p = random.choice(personalities) if personality == "RANDOM" else BotPersonality[personality]
            name = _pick_bot_name(p)
            game.add_bot(name, p)
            embed.add_field(
                name=f"{PERSONALITY_EMOJI[p]} {name}",
                value=f"*{p.value} personality*",
                inline=True,
            )

        humans = sum(1 for p in game.players.values() if not p.is_bot)
        bots   = len(game.players) - humans
        embed.set_footer(
            text=f"Lobby: {humans} human(s) + {bots} bot(s) = {len(game.players)} total | Min 3 to start"
        )
        await interaction.response.send_message(embed=embed)

    # ─────────────────────────────────────────────────────────────────────────
    # /start
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(name="start", description="Start the Mafia game")
    async def start_game(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)

        if not game or game.phase != GamePhase.LOBBY:
            await interaction.response.send_message(
                "No active lobby. Use `/join` to create one, then `/addbot` to fill seats.",
                ephemeral=True,
            )
            return

        if len(game.players) < 3:
            await interaction.response.send_message(
                f"Need at least **3 players** to start. "
                f"Currently have **{len(game.players)}**. "
                f"Use `/addbot` to fill empty slots!",
                ephemeral=True,
            )
            return

        game.assign_roles()
        game.phase = GamePhase.NIGHT
        game.day_number = 1

        await interaction.response.send_message(
            "🌙 **The game has started!** Roles are being assigned..."
        )

        # DM every human player their role + list of bots in the game
        bot_info_lines = [
            f"  {PERSONALITY_EMOJI[p.personality]} **{p.name}** ({p.personality.value})"
            for p in game.players.values() if p.is_bot
        ]
        bot_section = (
            "\n\n**🤖 AI Bots in this game:**\n" + "\n".join(bot_info_lines)
            if bot_info_lines else ""
        )

        for user_id, player in game.players.items():
            if player.is_bot:
                continue
            user = self.bot.get_user(user_id)
            if user:
                try:
                    role_hints = {
                        Role.MAFIA:    "🔪 Eliminate a town member each night with `/action`.",
                        Role.COP:      "🔍 Investigate a player each night with `/action`.",
                        Role.DOCTOR:   "💊 Protect a player each night with `/action`.",
                        Role.VILLAGER: "🗳️ Find the Mafia by discussion and `/vote`.",
                    }
                    await user.send(
                        f"🎭 **Your role in #{interaction.channel.name}:** **{player.role.value}**\n"
                        f"{role_hints.get(player.role, '')}"
                        f"{bot_section}"
                    )
                except discord.errors.Forbidden:
                    await interaction.channel.send(
                        f"⚠️ Could not DM <@{user_id}>. Please enable DMs from server members."
                    )

        await interaction.channel.send(
            "🌃 **Night 1** has begun. Everyone close your eyes.\n"
            "• Mafia, Cop, Doctor: use `/action <member>` to act.\n"
            "• 🤖 AI bots will act automatically when you call `/next`.\n"
            "• Call `/next` when you're ready to resolve the night."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # /action  (human night actions)
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(name="action", description="Use your role's night action")
    async def night_action(self, interaction: discord.Interaction, target: discord.Member):
        game = game_manager.get_game(interaction.channel_id)

        if not game or game.phase != GamePhase.NIGHT:
            await interaction.response.send_message(
                "You can only use actions during the Night.", ephemeral=True
            )
            return

        player = game.players.get(interaction.user.id)
        if not player or not player.is_alive:
            await interaction.response.send_message(
                "You are not in this game or are already dead.", ephemeral=True
            )
            return

        # Look for target among all game players (including bots by name)
        target_player = game.players.get(target.id)
        if not target_player or not target_player.is_alive:
            await interaction.response.send_message(
                "Invalid target — they're not in the game or already dead.", ephemeral=True
            )
            return

        if player.role == Role.MAFIA:
            game.mafia_target = target.id
            await interaction.response.send_message(
                f"🔪 You've chosen to kill **{target.display_name}** tonight.", ephemeral=True
            )
        elif player.role == Role.DOCTOR:
            game.doctor_target = target.id
            await interaction.response.send_message(
                f"💊 You've chosen to protect **{target.display_name}** tonight.", ephemeral=True
            )
        elif player.role == Role.COP:
            result = "Mafia" if target_player.role == Role.MAFIA else "Town"
            game.cop_results[target.id] = result
            await interaction.response.send_message(
                f"🔍 You investigated **{target.display_name}**. "
                f"Their allegiance is: **{result}**.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Villagers sleep during the night — you have no special action.", ephemeral=True
            )

    # ─────────────────────────────────────────────────────────────────────────
    # /vote  (human day votes)
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(name="vote", description="Vote to lynch someone during the day")
    async def vote(self, interaction: discord.Interaction, target: discord.Member):
        game = game_manager.get_game(interaction.channel_id)

        if not game or game.phase != GamePhase.DAY:
            await interaction.response.send_message(
                "You can only vote during the Day.", ephemeral=True
            )
            return

        player = game.players.get(interaction.user.id)
        if not player or not player.is_alive:
            await interaction.response.send_message("You cannot vote.", ephemeral=True)
            return

        target_player = game.players.get(target.id)
        if not target_player or not target_player.is_alive:
            await interaction.response.send_message("Invalid target.", ephemeral=True)
            return

        game.votes[interaction.user.id] = target.id
        await interaction.response.send_message(
            f"🗳️ **{interaction.user.display_name}** has voted for **{target.display_name}**."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # /next  (advance phase — bots act automatically here)
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(name="next", description="Advance to the next game phase (bots act automatically)")
    async def next_phase(self, interaction: discord.Interaction):
        from game.ai_gm import generate_night_story

        game = game_manager.get_game(interaction.channel_id)
        if not game:
            await interaction.response.send_message("No active game.", ephemeral=True)
            return

        if game.phase not in (GamePhase.NIGHT, GamePhase.DAY):
            await interaction.response.send_message(
                "The game is not in an active phase.", ephemeral=True
            )
            return

        await interaction.response.defer()

        # ══════════════════════════════════════════════════════════════════════
        # NIGHT → DAY transition
        # ══════════════════════════════════════════════════════════════════════
        if game.phase == GamePhase.NIGHT:

            # ── Step 1: Bot night actions ──────────────────────────────────
            bot_night_msgs = []
            for bot in game.get_alive_bots():
                target_id = decide_night_action(bot, game)
                if target_id is None:
                    continue

                if bot.role == Role.MAFIA and game.mafia_target is None:
                    game.mafia_target = target_id
                    msg = get_bot_night_message(bot)
                    if msg:
                        bot_night_msgs.append(msg)

                elif bot.role == Role.DOCTOR and game.doctor_target is None:
                    game.doctor_target = target_id
                    msg = get_bot_night_message(bot)
                    if msg:
                        bot_night_msgs.append(msg)

                elif bot.role == Role.COP:
                    target_player = game.players.get(target_id)
                    if target_player:
                        result = "Mafia" if target_player.role == Role.MAFIA else "Town"
                        game.cop_results[target_id] = result
                        msg = get_bot_night_message(bot)
                        if msg:
                            bot_night_msgs.append(msg)

            if bot_night_msgs:
                await interaction.channel.send("\n".join(bot_night_msgs))

            # ── Step 2: Resolve night outcomes ────────────────────────────
            killed = []
            healed = []

            if game.mafia_target:
                if game.doctor_target == game.mafia_target:
                    healed.append(game.players[game.mafia_target].name)
                else:
                    victim = game.players.get(game.mafia_target)
                    if victim:
                        victim.is_alive = False
                        killed.append(victim.name)

            game.mafia_target  = None
            game.doctor_target = None
            game.cop_target    = None
            game.phase         = GamePhase.DAY

            # ── Step 3: AI-generated night narrative ──────────────────────
            story = generate_night_story(killed, healed, game.day_number)
            await interaction.followup.send(
                f"☀️ **Day {game.day_number} has begun!**\n\n{story}\n\n"
                f"*Discuss among yourselves, use `/vote` to vote, "
                f"then call `/next` to tally the votes.*"
            )

            # ── Step 4: Bot day discussion messages ───────────────────────
            alive_bots = game.get_alive_bots()
            if alive_bots:
                chatty = [b for b in alive_bots if random.random() < 0.75]
                for bot in chatty:
                    msg  = get_discussion_message(bot, game)
                    icon = PERSONALITY_EMOJI[bot.personality]
                    await interaction.channel.send(f"{icon} **{bot.name}:** {msg}")

            # ── Check win condition ────────────────────────────────────────
            win = game.check_win_condition()
            if win:
                await interaction.channel.send(f"🏆 **Game Over!** {win}")
                game_manager.remove_game(interaction.channel_id)
                _used_bot_names.clear()
                return

        # ══════════════════════════════════════════════════════════════════════
        # DAY → NIGHT transition
        # ══════════════════════════════════════════════════════════════════════
        elif game.phase == GamePhase.DAY:

            # ── Step 1: Auto-cast bot votes ────────────────────────────────
            for bot in game.get_alive_bots():
                if bot.user_id not in game.votes:
                    target_id = decide_vote(bot, game)
                    if target_id:
                        game.votes[bot.user_id] = target_id
                        target_name = game.players[target_id].name
                        icon = PERSONALITY_EMOJI[bot.personality]
                        vote_template = VOTE_MESSAGES[bot.personality]
                        await interaction.channel.send(
                            f"{icon} " + vote_template.format(bot=bot.name, target=target_name)
                        )

            # ── Step 2: Tally votes ────────────────────────────────────────
            if game.votes:
                vote_counts = Counter(game.votes.values())

                # Build a readable vote summary
                summary_lines = []
                for voter_id, target_id in game.votes.items():
                    voter  = game.players.get(voter_id)
                    target = game.players.get(target_id)
                    if voter and target:
                        icon = "🤖" if voter.is_bot else "👤"
                        summary_lines.append(f"  {icon} **{voter.name}** → {target.name}")
                summary_str = "\n".join(summary_lines) or "No votes recorded."

                top_target_id = vote_counts.most_common(1)[0][0]
                lynched       = game.players[top_target_id]
                lynched.is_alive = False

                await interaction.followup.send(
                    f"**📊 Vote Tally:**\n{summary_str}\n\n"
                    f"⚖️ The town has spoken! **{lynched.name}** has been lynched.\n"
                    f"They were the **{lynched.role.value}**."
                )
            else:
                await interaction.followup.send(
                    "⚖️ No votes were cast. The town was too divided — no one was lynched."
                )

            game.votes = {}
            game.day_number += 1
            game.phase = GamePhase.NIGHT

            # ── Check win condition ────────────────────────────────────────
            win = game.check_win_condition()
            if win:
                await interaction.channel.send(f"🏆 **Game Over!** {win}")
                game_manager.remove_game(interaction.channel_id)
                _used_bot_names.clear()
                return

            await interaction.channel.send(
                f"🌙 **Night {game.day_number}** has fallen. The town sleeps...\n"
                f"• Night roles: use `/action <member>`.\n"
                f"• 🤖 AI bots will act automatically.\n"
                f"• Call `/next` to resolve the night."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # /status
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(name="status", description="Show the current game status")
    async def status(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)
        if not game:
            await interaction.response.send_message(
                "No active game in this channel.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎭 Mafia — Game Status",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.add_field(name="📅 Phase", value=game.phase.value, inline=True)
        if game.phase not in (GamePhase.LOBBY, GamePhase.ENDED):
            embed.add_field(name="☀️ Day", value=str(game.day_number), inline=True)

        alive = game.get_alive_players()
        dead  = [p for p in game.players.values() if not p.is_alive]

        alive_lines = [
            f"{'🤖' if p.is_bot else '👤'} **{p.name}**"
            + (f" ({PERSONALITY_EMOJI[p.personality]})" if p.is_bot else "")
            for p in alive
        ]
        dead_lines = [
            f"~~{'🤖' if p.is_bot else '👤'} {p.name}~~ *(was {p.role.value})*"
            for p in dead
        ]

        embed.add_field(
            name=f"✅ Alive ({len(alive)})",
            value="\n".join(alive_lines) or "Nobody",
            inline=False,
        )
        if dead_lines:
            embed.add_field(
                name=f"💀 Dead ({len(dead)})",
                value="\n".join(dead_lines),
                inline=False,
            )

        if game.phase == GamePhase.DAY and game.votes:
            vote_counts = Counter(game.votes.values())
            vote_lines  = [
                f"**{game.players[tid].name}**: {cnt} vote(s)"
                for tid, cnt in vote_counts.most_common()
                if game.players.get(tid)
            ]
            embed.add_field(
                name="🗳️ Current Votes",
                value="\n".join(vote_lines) or "None yet",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    # ─────────────────────────────────────────────────────────────────────────
    # /end
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(name="end", description="Force-end the current game and clear the lobby")
    async def end_game(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)
        if not game:
            await interaction.response.send_message(
                "No active game to end.", ephemeral=True
            )
            return

        game_manager.remove_game(interaction.channel_id)
        _used_bot_names.clear()
        await interaction.response.send_message("🛑 **Game stopped and lobby cleared.**")


async def setup(bot: commands.Bot):
    await bot.add_cog(MafiaGame(bot))
