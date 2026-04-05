import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from database.db import add_movie, get_movies, clear_movies

# Create a group for the movie commands
class MovieCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    movie_group = app_commands.Group(name="movie", description="Movie Roulette Commands")

    @movie_group.command(name="add", description="Add a movie to the selection pool")
    async def add(self, interaction: discord.Interaction, title: str):
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        add_movie(guild_id, title, interaction.user.display_name)
        await interaction.response.send_message(f"🎬 Added **{title}** to the movie pool! (Suggested by {interaction.user.mention})")

    @movie_group.command(name="list", description="List all queued movies")
    async def list_movies(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not guild_id:
            return

        movies = get_movies(guild_id)
        if not movies:
            await interaction.response.send_message("The movie pool is currently empty. Use `/movie add` to add some!", ephemeral=True)
            return

        embed = discord.Embed(title="🍿 Current Movie Pool", color=discord.Color.gold())
        movie_list = ""
        for i, m in enumerate(movies):
            movie_list += f"**{i+1}.** {m['title']} *(Added by {m['added_by']})*\n"
        
        embed.description = movie_list
        await interaction.response.send_message(embed=embed)

    @movie_group.command(name="clear", description="Clear the movie pool")
    async def clear(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not guild_id:
            return
            
        clear_movies(guild_id)
        await interaction.response.send_message("🗑️ **Movie pool cleared!** Ready for a new movie night.")

    @movie_group.command(name="spin", description="Spin the wheel to randomly select a movie!")
    async def spin(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not guild_id:
            return

        movies = get_movies(guild_id)
        if not movies:
            await interaction.response.send_message("You can't spin an empty wheel! Add movies first using `/movie add`.", ephemeral=True)
            return

        if len(movies) == 1:
            await interaction.response.send_message(f"Only one movie in the pool! Tonight we are watching: 🍿 **{movies[0]['title']}**")
            return

        await interaction.response.send_message("🎰 **Spinning the Movie Roulette...**")
        msg = await interaction.original_response()

        # The spinning animation loop
        spin_cycles = 10
        delay = 0.1
        
        for i in range(spin_cycles):
            random_movie = random.choice(movies)
            await msg.edit(content=f"🎰 **Spinning the Movie Roulette...**\n\n> 🔄 *{random_movie['title']}*")
            await asyncio.sleep(delay)
            delay += 0.05 # Slow down the spin gradually

        # Final Selected Movie
        winner = random.choice(movies)
        await msg.edit(content=f"🎯 **The wheel has stopped!**\n\n🍿 **Tonight's Movie:**\n# {winner['title']}\n*(Suggested by {winner['added_by']})*")

async def setup(bot: commands.Bot):
    await bot.add_cog(MovieCog(bot))
