import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for

import bot
import database as db
import discord_oauth
from config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    db.init_db()
    bot.start_bot_in_background()

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        return db.get_user(user_id)

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user():
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped

    app.jinja_env.globals["current_user"] = current_user
    app.jinja_env.globals["avatar_url"] = discord_oauth.avatar_url

    # -----------------------------------------------------------------
    # Public pages
    # -----------------------------------------------------------------

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/docs")
    def docs():
        return render_template("docs.html", base_url=Config.BASE_URL, limit=Config.RATE_LIMIT_PER_MINUTE)

    # -----------------------------------------------------------------
    # Discord OAuth2
    # -----------------------------------------------------------------

    @app.get("/login")
    def login():
        state = secrets.token_urlsafe(24)
        session["oauth_state"] = state
        return redirect(discord_oauth.build_authorize_url(state))

    @app.get("/callback")
    def callback():
        error = request.args.get("error")
        if error:
            return render_template("index.html", oauth_error="Connexion Discord refusée."), 400

        state = request.args.get("state")
        code = request.args.get("code")
        if not code or not state or state != session.pop("oauth_state", None):
            return render_template("index.html", oauth_error="Requête invalide (state)."), 400

        try:
            token_data = discord_oauth.exchange_code_for_token(code)
            discord_user = discord_oauth.fetch_discord_user(token_data["access_token"])
        except Exception:
            return (
                render_template(
                    "index.html", oauth_error="Échec de la connexion Discord. Réessayez."
                ),
                400,
            )

        user = db.upsert_user(
            discord_id=discord_user["id"],
            username=discord_user.get("username", "inconnu"),
            avatar=discord_user.get("avatar"),
        )
        session["user_id"] = user["id"]
        return redirect(url_for("dashboard"))

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    # -----------------------------------------------------------------
    # Dashboard
    # -----------------------------------------------------------------

    @app.get("/dashboard")
    @login_required
    def dashboard():
        user = current_user()
        keys = db.list_api_keys(user["id"])
        notifications = db.list_notifications(user["id"], limit=Config.HISTORY_PAGE_SIZE)
        new_key = session.pop("new_key", None)
        return render_template(
            "dashboard.html",
            user=user,
            keys=keys,
            notifications=notifications,
            new_key=new_key,
        )

    @app.post("/dashboard/keys")
    @login_required
    def create_key():
        user = current_user()
        name = (request.form.get("name") or "Default key").strip()[:60] or "Default key"
        plaintext_key = db.generate_api_key(user["id"], name=name)
        # shown once via flash-in-session, never stored in plaintext
        session["new_key"] = plaintext_key
        return redirect(url_for("dashboard"))

    @app.post("/dashboard/keys/<int:key_id>/revoke")
    @login_required
    def revoke_key(key_id):
        user = current_user()
        db.revoke_api_key(user["id"], key_id)
        return redirect(url_for("dashboard"))

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    @app.post("/api/send")
    def api_send():
        payload = request.get_json(silent=True) or {}
        api_key = payload.get("api_key")
        message = payload.get("message")

        if not api_key or not isinstance(api_key, str):
            return jsonify(error="Champ 'api_key' manquant ou invalide."), 400
        if not message or not isinstance(message, str):
            return jsonify(error="Champ 'message' manquant ou invalide."), 400
        if len(message) > 2000:
            return jsonify(error="Le message dépasse la limite Discord de 2000 caractères."), 400

        auth = db.verify_api_key(api_key)
        if auth is None:
            return jsonify(error="Clé API invalide ou révoquée."), 401

        user = auth["user"]
        api_key_id = auth["api_key_id"]
        key_prefix = auth["key_prefix"]

        if Config.RATE_LIMIT_PER_MINUTE > 0:
            since = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            recent = db.count_recent_notifications(user["id"], since)
            if recent >= Config.RATE_LIMIT_PER_MINUTE:
                return jsonify(error="Limite de débit atteinte, réessayez dans une minute."), 429

        result = bot.send_dm(user["discord_id"], message, key_prefix=key_prefix)

        db.log_notification(
            user_id=user["id"],
            api_key_id=api_key_id,
            message=message,
            status="sent" if result.ok else "failed",
            error=None if result.ok else result.error,
        )

        if not result.ok:
            return jsonify(error=result.error or "Échec de l'envoi."), 502

        return jsonify(status="sent"), 200

    # -----------------------------------------------------------------
    # Errors
    # -----------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("index.html"), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)