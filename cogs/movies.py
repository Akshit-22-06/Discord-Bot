import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from database.db import add_movie, get_movies, clear_movies, remove_movie

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
            votes = m.get('votes', 1)
            vote_text = "vote" if votes == 1 else "votes"
            movie_list += f"**{i+1}.** {m['title']} *(Added by {m['added_by']}) - {votes} {vote_text}*\n"
        
        embed.description = movie_list
        await interaction.response.send_message(embed=embed)

    @movie_group.command(name="clear", description="Clear the movie pool")
    async def clear(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not guild_id:
            return
            
        clear_movies(guild_id)
        await interaction.response.send_message("🗑️ **Movie pool cleared!** Ready for a new movie night.")

    @movie_group.command(name="info", description="Get info about a movie currently in the pool")
    async def info(self, interaction: discord.Interaction, title: str):
        guild_id = interaction.guild_id
        if not guild_id:
            return
            
        movies = get_movies(guild_id)
        # Find the movie case-insensitively
        movie = next((m for m in movies if m['title'].lower() == title.lower()), None)
        
        if not movie:
            await interaction.response.send_message(f"❌ Could not find **{title}** in the current movie pool.", ephemeral=True)
            return
            
        votes = movie.get('votes', 1)
        vote_text = "vote" if votes == 1 else "votes"
        
        embed = discord.Embed(title=f"🍿 {movie['title']}", color=discord.Color.blue())
        embed.add_field(name="Added By", value=movie['added_by'], inline=True)
        embed.add_field(name="Current Votes", value=f"{votes} {vote_text}", inline=True)
        
        await interaction.response.send_message(embed=embed)

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

        # Weighted selection logic
        weights = [m.get('votes', 1) for m in movies]
        winner = random.choices(movies, weights=weights, k=1)[0]

        # The spinning animation loop
        spin_cycles = 10
        delay = 0.05
        friction = 1.25
        last_movie = None
        
        for i in range(spin_cycles - 1):
            random_movie = random.choice(movies)
            # Prevent duplicate visual frames if there are at least 2 movies
            while len(movies) > 1 and random_movie == last_movie:
                random_movie = random.choice(movies)
            last_movie = random_movie
            
            await msg.edit(content=f"🎰 **Spinning the Movie Roulette...**\n\n> 🔄 *{random_movie['title']}*")
            await asyncio.sleep(delay)
            delay *= friction # Slow down the spin gradually

        # Final Selected Movie
        votes = winner.get('votes', 1)
        vote_text = "vote" if votes == 1 else "votes"
        await msg.edit(content=f"🎯 **The wheel has stopped!**\n\n🍿 **Tonight's Movie:**\n# {winner['title']}\n*(Suggested by {winner['added_by']}) - Won with {votes} {vote_text}!*")
        
        # Remove the winner from the pool so it can't win again
        remove_movie(winner['id'])

async def setup(bot: commands.Bot):
    await bot.add_cog(MovieCog(bot))
