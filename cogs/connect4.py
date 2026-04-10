import discord
from discord import app_commands
from discord.ext import commands
from game.connect4_engine import Connect4Engine

class Connect4Controls(discord.ui.View):
    def __init__(self, game: Connect4Engine, p1: discord.Member, p2: discord.Member, is_pve: bool = False):
        super().__init__(timeout=300) # 5 minutes max per turn
        self.game = game
        self.p1 = p1
        self.p2 = p2
        self.is_pve = is_pve
        
        for i in range(7):
            btn = discord.ui.Button(
                label=str(i + 1),
                style=discord.ButtonStyle.primary if i % 2 == 0 else discord.ButtonStyle.secondary,
                custom_id=f"c4_col_{i}",
                row=0 if i < 4 else 1
            )
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    def make_callback(self, col: int):
        async def button_callback(interaction: discord.Interaction):
            current_player_id = self.game.players[self.game.current_turn]
            if interaction.user.id != current_player_id:
                await interaction.response.send_message("It's not your turn!", ephemeral=True)
                return
                
            # Defer the interaction immediately to give the bot up to 15 minutes to calculate
            await interaction.response.defer()
                
            success = self.game.drop_piece(col)
            if not success:
                await interaction.followup.send("That column is full!", ephemeral=True)
                return

            # If PvE mode, bot takes its turn calculating
            if self.is_pve and not self.game.winner and not self.game.is_draw:
                self.game.bot_play()

            # Process Game Endings or Next Turn
            if self.game.winner:
                winner_user = self.p1 if self.game.winner == self.game.P1 else self.p2
                content = f"🏆 **Game Over!** {winner_user.mention} wins!\n\n{self.game.render_emoji_board()}"
                for child in self.children:
                    child.disabled = True
                await interaction.edit_original_response(content=content, view=self)
                self.stop()
            elif self.game.is_draw:
                content = f"🤝 **It's a Draw!**\n\n{self.game.render_emoji_board()}"
                for child in self.children:
                    child.disabled = True
                await interaction.edit_original_response(content=content, view=self)
                self.stop()
            else:
                next_player = self.p1 if self.game.current_turn == self.game.P1 else self.p2
                emoji = "🔴" if self.game.current_turn == self.game.P1 else "🟡"
                content = f"🎮 **Connect 4**\n{next_player.mention}'s Turn ({emoji})\n\n{self.game.render_emoji_board()}"
                await interaction.edit_original_response(content=content, view=self)
                
        return button_callback

class ChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("You cannot accept this challenge.", ephemeral=True)
            return
            
        game = Connect4Engine(player1_id=self.challenger.id, player2_id=self.opponent.id)
        view = Connect4Controls(game, self.challenger, self.opponent)
        
        content = f"🎮 **Connect 4**\n{self.challenger.mention}'s Turn (🔴)\n\n{game.render_emoji_board()}"
        await interaction.response.edit_message(content=content, view=view)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("You cannot decline this challenge.", ephemeral=True)
            return

        await interaction.response.edit_message(content=f"❌ {self.opponent.mention} declined the challenge.", view=None)
        self.stop()

class Connect4Cog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="connect4", description="Challenge someone (or the bot!) to a game of Connect 4")
    async def challenge(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
            return
            
        if opponent.bot and opponent.id != self.bot.user.id:
            await interaction.response.send_message("You cannot play against other bots!", ephemeral=True)
            return

        # Handle PvE
        if opponent.id == self.bot.user.id:
            game = Connect4Engine(player1_id=interaction.user.id, player2_id=self.bot.user.id)
            view = Connect4Controls(game, interaction.user, self.bot.user, is_pve=True)
            content = f"🤖 **PvE Connect 4 (You vs Bot)**\n{interaction.user.mention}'s Turn (🔴)\n\n{game.render_emoji_board()}"
            await interaction.response.send_message(content=content, view=view)
            return

        # Handle PvP
        view = ChallengeView(challenger=interaction.user, opponent=opponent)
        await interaction.response.send_message(
            f"⚔️ {opponent.mention}, you have been challenged to a game of Connect 4 by {interaction.user.mention}!", 
            view=view
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Connect4Cog(bot))
