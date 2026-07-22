"""
Discord bot wrapper.

The bot runs on its own event loop in a background thread so the Flask
process (WSGI, sync) can stay simple. Flask hands off "send this DM" work to
the bot's loop with `asyncio.run_coroutine_threadsafe` and blocks on the
result, which is fine at MVP volume (a handful of notifications/minute).

Requirements for the bot to be able to DM someone:
- The Discord user must share at least one server with the bot, OR have
  interacted with it before (Discord's DM rules), otherwise `send DM` raises
  discord.Forbidden.
- The user must not have DMs disabled for the server / the bot blocked.
"""

import asyncio
import logging
import threading

import discord

from config import Config

log = logging.getLogger("discord-notify-bot")

intents = discord.Intents.default()
intents.members = True  # needed to resolve users the bot hasn't cached yet

_client = discord.Client(intents=intents)
_loop: asyncio.AbstractEventLoop | None = None
_ready_event = threading.Event()


@_client.event
async def on_ready():
    log.info("Bot connected as %s (id=%s)", _client.user, _client.user.id)
    _ready_event.set()


def start_bot_in_background() -> None:
    """Boot the bot on its own thread + event loop. Safe to call once at app startup."""
    global _loop

    if not Config.DISCORD_BOT_TOKEN:
        log.warning("DISCORD_BOT_TOKEN is empty — bot will not start. /api/send will fail.")
        return

    def _run():
        global _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        try:
            _loop.run_until_complete(_client.start(Config.DISCORD_BOT_TOKEN))
        except Exception:
            log.exception("Discord bot crashed")

    thread = threading.Thread(target=_run, name="discord-bot", daemon=True)
    thread.start()


class SendResult:
    def __init__(self, ok: bool, error: str | None = None):
        self.ok = ok
        self.error = error


def send_dm(
    discord_id: str,
    message: str,
    key_prefix: str | None = None,
    timeout: float = 15.0,
) -> SendResult:
    """
    Synchronous wrapper: send a DM to a Discord user id from Flask's thread.
    Blocks until the bot's loop finishes the coroutine (or times out).

    The message is wrapped in an embed so we can attach a small footer
    reminding the recipient which API key sent it (its prefix, e.g.
    "pk_AbC123XyZ…") — enough for them to go revoke it from the dashboard
    if the notification is unexpected.
    """
    if _loop is None:
        return SendResult(False, "Le bot Discord n'est pas démarré (token manquant ?).")

    async def _send():
        user = _client.get_user(int(discord_id))
        if user is None:
            try:
                user = await _client.fetch_user(int(discord_id))
            except discord.NotFound:
                raise RuntimeError("Utilisateur Discord introuvable.")

        embed = discord.Embed(description=message, color=discord.Color.blurple())
        if key_prefix:
            embed.set_footer(
                text=f"Envoyé via la clé {key_prefix}… — désactivable depuis votre dashboard Relay"
            )
        await user.send(embed=embed)

    future = asyncio.run_coroutine_threadsafe(_send(), _loop)
    try:
        future.result(timeout=timeout)
        return SendResult(True)
    except discord.Forbidden:
        return SendResult(
            False,
            "Impossible d'envoyer un DM : l'utilisateur doit partager un serveur "
            "avec le bot et autoriser les messages privés.",
        )
    except discord.HTTPException as e:
        return SendResult(False, f"Erreur Discord: {e}")
    except asyncio.TimeoutError:
        return SendResult(False, "Le bot n'a pas répondu à temps.")
    except Exception as e:  # noqa: BLE001 - surfaced to the API caller
        return SendResult(False, str(e))


def bot_is_ready(timeout: float = 0.0) -> bool:
    return _ready_event.wait(timeout)