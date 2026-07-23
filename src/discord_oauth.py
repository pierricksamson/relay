"""
Minimal Discord OAuth2 "Authorization Code" flow helpers.

Docs: https://discord.com/developers/docs/topics/oauth2
Scopes used: `identify` only (we never need email or guild lists).
"""

from urllib.parse import urlencode

import requests

from src.config import Config

SCOPES = "identify"


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": Config.DISCORD_CLIENT_ID,
        "redirect_uri": Config.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "prompt": "consent",
    }
    return f"{Config.DISCORD_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    data = {
        "client_id": Config.DISCORD_CLIENT_ID,
        "client_secret": Config.DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": Config.DISCORD_REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(Config.DISCORD_TOKEN_URL, data=data, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_discord_user(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(f"{Config.DISCORD_API_BASE}/users/@me", headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def avatar_url(discord_id: str, avatar_hash: str | None) -> str:
    if not avatar_hash:
        # default Discord avatar (based on discriminator-less new username system)
        return "https://cdn.discordapp.com/embed/avatars/0.png"
    ext = "gif" if avatar_hash.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.{ext}"