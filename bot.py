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

from src.config import Config

log = logging.getLogger("discord-notify-bot")

intents = discord.Intents.default()
intents.members = True  # needed to resolve users the bot hasn't cached yet

_client = discord.Client(intents=intents)
_loop: asyncio.AbstractEventLoop | None = None
_ready_event = threading.Event()

# ---------------------------------------------------------------------
# Types de notification : titre affiché + couleur d'embed.
# Champ "type" optionnel côté API ; si absent/vide -> comportement actuel
# (pas de titre, couleur blurple par défaut).
# ---------------------------------------------------------------------

NOTIFICATION_TYPES = {

    # Général
    "info": {
        "title": "ℹ️ Info",
        "color": discord.Color.blurple()
    },
    "success": {
        "title": "✅ Success",
        "color": discord.Color.green()
    },
    "warning": {
        "title": "⚠️ Warning",
        "color": discord.Color.orange()
    },
    "alert": {
        "title": "🚨 Alert",
        "color": discord.Color.red()
    },
    "error": {
        "title": "❌ Error",
        "color": discord.Color.red()
    },
    "critical": {
        "title": "🔥 Critical",
        "color": discord.Color.dark_red()
    },


    # Développement
    "debug": {
        "title": "🐛 Debug",
        "color": discord.Color.dark_grey()
    },
    "test": {
        "title": "🧪 Test",
        "color": discord.Color.teal()
    },
    "build": {
        "title": "🏗️ Build",
        "color": discord.Color.blue()
    },
    "compile": {
        "title": "⚙️ Compile",
        "color": discord.Color.blue()
    },
    "deploy": {
        "title": "🚀 Deployment",
        "color": discord.Color.purple()
    },
    "release": {
        "title": "📦 Release",
        "color": discord.Color.purple()
    },
    "rollback": {
        "title": "↩️ Rollback",
        "color": discord.Color.orange()
    },


    # Serveur / Infrastructure
    "server": {
        "title": "🖥️ Server",
        "color": discord.Color.dark_blue()
    },
    "startup": {
        "title": "🟢 Startup",
        "color": discord.Color.green()
    },
    "shutdown": {
        "title": "🔴 Shutdown",
        "color": discord.Color.red()
    },
    "restart": {
        "title": "🔄 Restart",
        "color": discord.Color.orange()
    },
    "maintenance": {
        "title": "🛠️ Maintenance",
        "color": discord.Color.orange()
    },
    "uptime": {
        "title": "⏱️ Uptime",
        "color": discord.Color.green()
    },


    # Monitoring
    "cpu": {
        "title": "🧠 CPU",
        "color": discord.Color.orange()
    },
    "ram": {
        "title": "💾 RAM",
        "color": discord.Color.orange()
    },
    "disk": {
        "title": "💿 Disk",
        "color": discord.Color.orange()
    },
    "temperature": {
        "title": "🌡️ Temperature",
        "color": discord.Color.red()
    },
    "performance": {
        "title": "📊 Performance",
        "color": discord.Color.blue()
    },
    "health": {
        "title": "❤️ Health Check",
        "color": discord.Color.green()
    },


    # Réseau
    "network": {
        "title": "🌐 Network",
        "color": discord.Color.blue()
    },
    "connection": {
        "title": "🔗 Connection",
        "color": discord.Color.blue()
    },
    "timeout": {
        "title": "⌛ Timeout",
        "color": discord.Color.orange()
    },
    "offline": {
        "title": "📴 Offline",
        "color": discord.Color.red()
    },
    "online": {
        "title": "📡 Online",
        "color": discord.Color.green()
    },


    # Sécurité
    "security": {
        "title": "🔒 Security",
        "color": discord.Color.gold()
    },
    "login": {
        "title": "🔑 Login",
        "color": discord.Color.green()
    },
    "logout": {
        "title": "🚪 Logout",
        "color": discord.Color.greyple()
    },
    "authentication": {
        "title": "🪪 Authentication",
        "color": discord.Color.gold()
    },
    "permission": {
        "title": "⛔ Permission",
        "color": discord.Color.red()
    },
    "attack": {
        "title": "⚔️ Attack Detected",
        "color": discord.Color.dark_red()
    },
    "firewall": {
        "title": "🧱 Firewall",
        "color": discord.Color.dark_gold()
    },


    # Base de données
    "database": {
        "title": "🗄️ Database",
        "color": discord.Color.teal()
    },
    "backup": {
        "title": "💽 Backup",
        "color": discord.Color.green()
    },
    "restore": {
        "title": "♻️ Restore",
        "color": discord.Color.blue()
    },
    "migration": {
        "title": "🔀 Migration",
        "color": discord.Color.purple()
    },


    # API
    "api": {
        "title": "🔌 API",
        "color": discord.Color.blue()
    },
    "request": {
        "title": "📨 Request",
        "color": discord.Color.blurple()
    },
    "rate_limit": {
        "title": "🚦 Rate Limit",
        "color": discord.Color.orange()
    },
    "webhook": {
        "title": "🪝 Webhook",
        "color": discord.Color.purple()
    },


    # Utilisateurs
    "user": {
        "title": "👤 User",
        "color": discord.Color.light_grey()
    },
    "signup": {
        "title": "📝 New User",
        "color": discord.Color.green()
    },
    "delete_user": {
        "title": "🗑️ User Deleted",
        "color": discord.Color.red()
    },


    # Paiements / Business
    "payment": {
        "title": "💳 Payment",
        "color": discord.Color.gold()
    },
    "purchase": {
        "title": "🛒 Purchase",
        "color": discord.Color.green()
    },
    "invoice": {
        "title": "🧾 Invoice",
        "color": discord.Color.blue()
    },
    "refund": {
        "title": "↩️ Refund",
        "color": discord.Color.orange()
    },


    # IA / Machine Learning
    "ai": {
        "title": "🤖 AI",
        "color": discord.Color.purple()
    },
    "model": {
        "title": "🧠 Model",
        "color": discord.Color.purple()
    },
    "training": {
        "title": "📚 Training",
        "color": discord.Color.blue()
    },
    "prediction": {
        "title": "🔮 Prediction",
        "color": discord.Color.teal()
    },


    # Trading / Finance
    "trade": {
        "title": "📈 Trade",
        "color": discord.Color.green()
    },
    "buy": {
        "title": "🟢 Buy",
        "color": discord.Color.green()
    },
    "sell": {
        "title": "🔴 Sell",
        "color": discord.Color.red()
    },
    "profit": {
        "title": "💰 Profit",
        "color": discord.Color.green()
    },
    "loss": {
        "title": "📉 Loss",
        "color": discord.Color.red()
    },
    "market": {
        "title": "📊 Market",
        "color": discord.Color.blue()
    },


    # Bots
    "bot": {
        "title": "🤖 Bot",
        "color": discord.Color.purple()
    },
    "bot_online": {
        "title": "🟢 Bot Online",
        "color": discord.Color.green()
    },
    "bot_offline": {
        "title": "🔴 Bot Offline",
        "color": discord.Color.red()
    },
    "command": {
        "title": "⌨️ Command",
        "color": discord.Color.blurple()
    },


    # Fichiers
    "file": {
        "title": "📄 File",
        "color": discord.Color.blue()
    },
    "upload": {
        "title": "⬆️ Upload",
        "color": discord.Color.green()
    },
    "download": {
        "title": "⬇️ Download",
        "color": discord.Color.blue()
    },
    "storage": {
        "title": "📁 Storage",
        "color": discord.Color.orange()
    }
}


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
    notif_type: str | None = None,
    timeout: float = 15.0,
) -> SendResult:
    """
    Synchronous wrapper: send a DM to a Discord user id from Flask's thread.
    Blocks until the bot's loop finishes the coroutine (or times out).

    The message is wrapped in an embed so we can attach a small footer
    reminding the recipient which API key sent it (its prefix, e.g.
    "pk_AbC123XyZ…") — enough for them to go revoke it from the dashboard
    if the notification is unexpected.

    notif_type: optional, one of NOTIFICATION_TYPES keys (case-insensitive):
    "info" | "warning" | "alert" | "success". If None/empty/unknown, falls
    back to the historical plain blurple embed with no title (unchanged
    behavior).
    """
    if _loop is None:
        return SendResult(
            False,
            "🇫🇷 Le bot Discord n'est pas démarré (token manquant ?). / "
            "🇺🇸 Discord bot is not running (missing token?).",
        )

    style = NOTIFICATION_TYPES.get((notif_type or "").strip().lower())

    async def _send():
        user = _client.get_user(int(discord_id))
        if user is None:
            try:
                user = await _client.fetch_user(int(discord_id))
            except discord.NotFound:
                raise RuntimeError(
                    "🇫🇷 Utilisateur Discord introuvable. / 🇺🇸 Discord user not found."
                )

        embed = discord.Embed(
            description=message,
            color=style["color"] if style else discord.Color.blurple(),
        )
        if style:
            embed.title = style["title"]
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
            "🇫🇷 Impossible d'envoyer un DM : l'utilisateur doit partager un serveur "
            "avec le bot et autoriser les messages privés. / "
            "🇺🇸 Could not send DM: the user must share a server with the bot "
            "and allow direct messages.",
        )
    except discord.HTTPException as e:
        return SendResult(False, f"🇫🇷 Erreur Discord: {e} / 🇺🇸 Discord error: {e}")
    except asyncio.TimeoutError:
        return SendResult(
            False,
            "🇫🇷 Le bot n'a pas répondu à temps. / 🇺🇸 The bot did not respond in time.",
        )
    except Exception as e:  # noqa: BLE001 - surfaced to the API caller
        return SendResult(False, str(e))


def bot_is_ready(timeout: float = 0.0) -> bool:
    return _ready_event.wait(timeout)