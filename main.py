import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import logging
from aiohttp import web
from core.config import DISCORD_TOKEN

# Setup Logging for Production
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('discord')

# --- Dummy Web Server for Render Free Tier ---
async def handle_ping(request):
    return web.Response(text="Bot is actively running!")

async def start_dummy_server():
    app = web.Application()
    app.add_routes([web.get('/', handle_ping)])  # HEAD is auto-handled by aiohttp from GET
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Dummy Web Server running on port {port} to satisfy Render!")

class HybridBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=commands.DefaultHelpCommand())

    async def setup_hook(self):
        # NOTE: self.user is None here — do NOT log it. Use on_ready for that.

        # Start dummy web server for Render health checks
        await start_dummy_server()

        # Load cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f"Loaded cog: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load cog {filename}: {e}")

        # Setup Global Error Handler
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            logger.error(f"Command Error triggered by {interaction.user}: {error}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("⚠️ An error occurred while processing this command.", ephemeral=True)
                else:
                    await interaction.response.send_message("⚠️ An error occurred while processing this command.", ephemeral=True)
            except discord.errors.HTTPException as e:
                # Catch 429 HTML block errors from Cloudflare
                logger.error(f"Failed to send error response to user due to Discord rate limits: {e}")

        # Note: We removed automatic command syncing here!
        # Discord heavily rate limits bots that sync global commands on every boot.
        # Use the `!sync` command below inside Discord to manually update your commands.

    async def on_ready(self):
        logger.info(f"------")
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"------")

bot = HybridBot()

# --- Manual Sync Command ---
# Type `!sync` in your Discord server to manually update slash commands.
# This avoids Discord's strict automated rate limits.
@bot.command()
@commands.is_owner()
async def sync(ctx):
    await ctx.send("Syncing slash commands globally... (This may take a moment)")
    synced = await bot.tree.sync()
    await ctx.send(f"✅ Successfully synced {len(synced)} commands.")
    logger.info(f"Manual Sync: Synced {len(synced)} slash commands.")

if __name__ == "__main__":
    from database.db import init_db
    init_db() # Ensure tables exist before boot
    
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN, log_handler=None) # We use our own customized logging format above
    else:
        logger.critical("Failed to start: DISCORD_TOKEN is missing. Please setup your .env file.")
