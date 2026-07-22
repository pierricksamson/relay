import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")

    DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
    DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
    DISCORD_REDIRECT_URI = os.environ.get(
        "DISCORD_REDIRECT_URI", "http://localhost:5000/callback"
    )
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

    DISCORD_API_BASE = "https://discord.com/api"
    DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
    DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"

    DATABASE_PATH = os.environ.get("DATABASE_PATH", "instance/app.db")

    # Notifications kept per user in the dashboard / history
    HISTORY_PAGE_SIZE = 20

    # Simple per-key rate limit (max sends per minute). 0 disables it.
    RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))