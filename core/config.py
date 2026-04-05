import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GUILD_ID = os.getenv("GUILD_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DISCORD_TOKEN:
    print("Warning: DISCORD_TOKEN is not set in the environment.")

if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY is not set in the environment.")
