import discord
from discord import app_commands
from discord.ext import commands
from game.manager import game_manager
from game.models import GamePhase, Role

class MafiaGame(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="join", description="Join the Mafia game in this channel")
    async def join_game(self, interaction: discord.Interaction):
        game = game_manager.get_or_create_game(interaction.channel_id)
        
        if game.phase != GamePhase.LOBBY:
            await interaction.response.send_message("A game is already in progress in this channel!", ephemeral=True)
            return

        success = game.add_player(interaction.user.id, interaction.user.display_name)
        if success:
            await interaction.response.send_message(f"🎭 **{interaction.user.display_name}** has joined the game! ({len(game.players)} players)")
        else:
            await interaction.response.send_message("You have already joined the game!", ephemeral=True)

    @app_commands.command(name="start", description="Start the Mafia game")
    async def start_game(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)
        
        if not game or game.phase != GamePhase.LOBBY:
            await interaction.response.send_message("No game lobby is currently active. Use `/join` to start a lobby.", ephemeral=True)
            return
            
        if len(game.players) < 3: # Need at least 3 players for a basic game
            await interaction.response.send_message(f"Need at least 3 players to start. Currently have {len(game.players)}.", ephemeral=True)
            return

        game.assign_roles()
        game.phase = GamePhase.NIGHT
        game.day_number = 1
        
        await interaction.response.send_message("🌃 **The game has started! Setting up the town...**")
        
        # DM roles to players
        for user_id, player in game.players.items():
            user = self.bot.get_user(user_id)
            if user:
                try:
                    await user.send(f"Your role in the game (Channel {interaction.channel.name}) is **{player.role.value}**.")
                except discord.errors.Forbidden:
                    await interaction.channel.send(f"⚠️ Could not DM <@{user_id}>! Please enable DMs from server members.")

        await interaction.channel.send("It is now **Night 1**. Everyone close your eyes.\n*Roles with night actions (Mafia, Cop, Doctor) should use `/action <member>` in this channel (Responses will be hidden).*")

    @app_commands.command(name="action", description="Use your role's night action")
    async def night_action(self, interaction: discord.Interaction, target: discord.Member):
        game = game_manager.get_game(interaction.channel_id)
        if not game or game.phase != GamePhase.NIGHT:
            await interaction.response.send_message("You can only use actions during the Night.", ephemeral=True)
            return
            
        player = game.players.get(interaction.user.id)
        if not player or not player.is_alive:
            await interaction.response.send_message("You are not part of this game or you are dead.", ephemeral=True)
            return

        target_player = game.players.get(target.id)
        if not target_player or not target_player.is_alive:
            await interaction.response.send_message("Invalid target. They are not in the game or already dead.", ephemeral=True)
            return

        # Handle Action based on role
        if player.role == Role.MAFIA:
            game.mafia_target = target.id
            await interaction.response.send_message(f"🔪 You have chosen to kill {target.display_name}.", ephemeral=True)
        elif player.role == Role.DOCTOR:
            game.doctor_target = target.id
            await interaction.response.send_message(f"💊 You have chosen to protect {target.display_name}.", ephemeral=True)
        elif player.role == Role.COP:
            role_reveal = "Mafia" if target_player.role == Role.MAFIA else "Town"
            await interaction.response.send_message(f"🔍 You investigated {target.display_name}. Their allegiance is: **{role_reveal}**.", ephemeral=True)
        else:
            await interaction.response.send_message("Villagers sleep during the night. You have no action.", ephemeral=True)

    @app_commands.command(name="vote", description="Vote to lynch someone during the day")
    async def vote(self, interaction: discord.Interaction, target: discord.Member):
        game = game_manager.get_game(interaction.channel_id)
        if not game or game.phase != GamePhase.DAY:
            await interaction.response.send_message("You can only vote during the Day.", ephemeral=True)
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
        await interaction.response.send_message(f"🗳️ {interaction.user.display_name} has voted for **{target.display_name}**.")

    @app_commands.command(name="next", description="Progress to the next game phase (Day/Night)")
    async def next_phase(self, interaction: discord.Interaction):
        from game.ai_gm import generate_night_story
        
        game = game_manager.get_game(interaction.channel_id)
        if not game:
            await interaction.response.send_message("No game active.", ephemeral=True)
            return
        
        # NOTE: Ideally this is restricted to Game creator or Admin
        await interaction.response.defer()

        if game.phase == GamePhase.NIGHT:
            # Resolve Night Actions
            killed = []
            healed = []
            
            if game.mafia_target:
                if game.doctor_target == game.mafia_target:
                    healed.append(game.players[game.mafia_target].name)
                else:
                    target_player = game.players[game.mafia_target]
                    target_player.is_alive = False
                    killed.append(target_player.name)
            
            # Reset night state
            game.mafia_target = None
            game.doctor_target = None
            game.cop_target = None
            game.phase = GamePhase.DAY
            
            # AI Narrative
            story = generate_night_story(killed, healed, game.day_number)
            
            await interaction.followup.send(f"☀️ **Day {game.day_number} has begun!**\n\n{story}\n\n*Discuss and use `/vote` to eliminate a suspect.*")
            
            # Check Win Condition
            win = game.check_win_condition()
            if win:
                await interaction.channel.send(f"🏆 **Game Over!** {win}")
                game_manager.remove_game(interaction.channel_id)
                
        elif game.phase == GamePhase.DAY:
            # Resolve Day Votes
            if game.votes:
                # Count votes
                from collections import Counter
                vote_counts = Counter(game.votes.values())
                highest_votes = vote_counts.most_common(1)[0]
                
                target_id = highest_votes[0]
                lynched_player = game.players[target_id]
                lynched_player.is_alive = False
                
                await interaction.followup.send(f"⚖️ The town has spoken. **{lynched_player.name}** was lynched! They were the **{lynched_player.role.value}**.")
            else:
                await interaction.followup.send("⚖️ The town could not decide on a target. No one was lynched.")
            
            game.votes = {}
            game.day_number += 1
            game.phase = GamePhase.NIGHT
            
            win = game.check_win_condition()
            if win:
                await interaction.channel.send(f"🏆 **Game Over!** {win}")
                game_manager.remove_game(interaction.channel_id)
            else:
                await interaction.channel.send(f"🌃 It is now **Night {game.day_number}**. The town sleeps...\n*Roles with night actions should use `/action <member>`.*")

    @app_commands.command(name="status", description="Check the current game status")
    async def status(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)
        if not game:
            await interaction.response.send_message("No active game in this channel.", ephemeral=True)
            return

        embed = discord.Embed(title="Mafia Game Status", color=discord.Color.blue())
        embed.add_field(name="Phase", value=game.phase.value)
        if game.phase != GamePhase.LOBBY:
            embed.add_field(name="Day", value=str(game.day_number))
        
        alive_players = "\n".join([p.name for p in game.get_alive_players()])
        embed.add_field(name=f"Alive Players ({len(game.get_alive_players())})", value=alive_players or "None", inline=False)
        
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="end", description="End the current game")
    async def end_game(self, interaction: discord.Interaction):
        game = game_manager.get_game(interaction.channel_id)
        if not game:
            await interaction.response.send_message("No active game to end.", ephemeral=True)
            return
        
        game_manager.remove_game(interaction.channel_id)
        await interaction.response.send_message("🛑 **Game stopped and lobby cleared.**")

async def setup(bot: commands.Bot):
    await bot.add_cog(MafiaGame(bot))
