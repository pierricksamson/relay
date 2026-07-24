import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
import json

from dotenv import set_key
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf

import bot
import src.database as db
import src.discord_oauth as discord_oauth
from src.config import Config


def bilingual(fr: str, en: str) -> str:
    return f"🇺🇸 {en} / 🇫🇷 {fr}"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config.update(
        SESSION_COOKIE_SECURE=True,      # jamais transmis en clair (HTTP)
        SESSION_COOKIE_HTTPONLY=True,    # déjà le défaut Flask, à expliciter
        SESSION_COOKIE_SAMESITE="Lax",   # limite les envois cross-site
        PERMANENT_SESSION_LIFETIME=timedelta(days=12),
    )
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # 64 Ko, large marge pour un message de 2000 caractères
    app.secret_key = Config.SECRET_KEY
    csrf = CSRFProtect(app)
    app.jinja_env.globals["csrf_token"] = generate_csrf

    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri=Config.STOCKAGE_URI,
        strategy="moving-window",
    )

    db.init_db()
    bot.start_bot_in_background()

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def load_i18n() -> dict:
        data = {}
        lang_dir = os.path.join(app.static_folder, "lang")
        for lang in ("fr", "en", "es"):
            with open(os.path.join(lang_dir, f"{lang}.json"), encoding="utf-8") as f:
                data[lang] = json.load(f)
        return data

    app.jinja_env.globals["i18n_data"] = load_i18n()

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

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login"))
            if not user["admin"]:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    app.jinja_env.globals["current_user"] = current_user
    app.jinja_env.globals["avatar_url"] = discord_oauth.avatar_url

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
            "https://cdn.jsdelivr.net https://unpkg.com; "
            "font-src 'self' https://fonts.gstatic.com https://unpkg.com data:; "
            "img-src 'self' data: blob: https://cdn.discordapp.com https://cdn.jsdelivr.net https://unpkg.com; "
            "connect-src 'self' https: http: https://unpkg.com https://cdn.jsdelivr.net data: blob:;"
        )
        return response

    # -----------------------------------------------------------------
    # Public pages
    # -----------------------------------------------------------------

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/cgu")
    def cgu():
        return render_template("cgu.html")

    @app.get("/docs")
    def docs():
        return render_template(
            "docs.html", base_url=Config.BASE_URL, limit=db.get_rate_limit_per_minute()
        )

    # -----------------------------------------------------------------
    # SEO : Robots.txt & Sitemap
    # -----------------------------------------------------------------

    @app.get("/robots.txt")
    def robots():
        """Sert le fichier robots.txt qui dit aux moteurs de recherche quoi regarder."""
        # On bloque l'accès aux pages privées et à l'API pour éviter qu'elles soient indexées sur Google
        lines = [
            "User-agent: *",
            "Disallow: /admin/",
            "Disallow: /dashboard/",
            "Disallow: /api/",
            "Disallow: /login",
            "Disallow: /callback",
            "Disallow: /logout",
            "",
            # Indique dynamiquement l'URL de ton sitemap
            f"Sitemap: {url_for('sitemap', _external=True)}"
        ]
        return Response("\n".join(lines), mimetype="text/plain")

    @app.get("/sitemap.xml")
    def sitemap():
        """Génère le sitemap automatiquement à chaque requête."""
        # Liste des pages publiques à indexer : (nom_de_la_fonction, priorité, fréquence_actualisation)
        pages = [
            ("index", 1.0, "weekly"),
            ("docs", 0.8, "weekly"),
            ("cgu", 0.5, "monthly")
        ]

        # Actualisation : on utilise la date d'aujourd'hui (format YYYY-MM-DD)
        # Comme la route est dynamique, la date lastmod sera toujours récente !
        lastmod = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        xml_sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_sitemap += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

        for endpoint, priority, changefreq in pages:
            # _external=True permet d'avoir le lien complet (ex: https://tonsite.com/docs au lieu de juste /docs)
            url = url_for(endpoint, _external=True)
            xml_sitemap += '  <url>\n'
            xml_sitemap += f'    <loc>{url}</loc>\n'
            xml_sitemap += f'    <lastmod>{lastmod}</lastmod>\n'
            xml_sitemap += f'    <changefreq>{changefreq}</changefreq>\n'
            xml_sitemap += f'    <priority>{priority}</priority>\n'
            xml_sitemap += '  </url>\n'

        xml_sitemap += '</urlset>'

        # On renvoie bien du XML pour que les navigateurs et les bots le comprennent
        return Response(xml_sitemap, mimetype='application/xml')

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

        user, is_new = db.upsert_user(
            discord_id=discord_user["id"],
            username=discord_user.get("username", "inconnu"),
            avatar=discord_user.get("avatar"),
        )

        if is_new:

            message = """
                        🇺🇸 - Your Relay account has been created
                        🇫🇷 - Votre compte Relay à bien été créé
                    """

            result = bot.send_dm(user["discord_id"], message, key_prefix='server')
            
            db.log_notification(
                user_id=user["id"],
                api_key_id=None,
                message=message,
                status="sent" if result.ok else "failed",
                error=None if result.ok else result.error,
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
        new_key_error = session.pop("new_key_error", None)
        delete_error = session.pop("delete_error", None)

        return render_template(
            "dashboard.html",
            user=user,
            keys=keys,
            notifications=notifications,
            new_key=new_key,
            new_key_error=new_key_error,
            delete_error=delete_error,
            max_keys=db.get_max_api_keys_per_user(),
            active_keys_count=db.count_active_api_keys(user["id"]),
        )

    @app.post("/dashboard/keys")
    @login_required
    def create_key():
        user = current_user()
        max_keys = db.get_max_api_keys_per_user()
        active = db.count_active_api_keys(user["id"])
        if active >= max_keys:
            session["new_key_error"] = bilingual(
                f"Limite atteinte : {max_keys} clé(s) active(s) maximum. "
                "Révoquez une clé existante avant d'en générer une nouvelle.",
                f"Limit reached: {max_keys} active key(s) maximum. "
                "Revoke an existing key before generating a new one.",
            )
            return redirect(url_for("dashboard"))

        name = (request.form.get("name") or "Default key").strip()[:60] or "Default key"
        plaintext_key = db.generate_api_key(user["id"], name=name)
        # shown once via flash-in-session, never stored in plaintext
        session["new_key"] = plaintext_key
        return redirect(url_for("dashboard"))

    @app.post("/dashboard/delete-account")
    @login_required
    def delete_account():
        user = current_user()
        confirm_text = (request.form.get("confirm_text") or "").strip().upper()

        if confirm_text not in ["SUPPRIMER", "DELETE"]:
            session["delete_error"] = bilingual(
                "Vous devez taper SUPPRIMER pour confirmer.",
                "You must type DELETE to confirm.",
            )
            return redirect(url_for("dashboard"))

        db.log_audit(
            user["id"],
            "delete_account",
            f"discord_id={user['discord_id']} username={user['username']}",
        )
        db.delete_user_data(user["id"])
        session.clear()
        return redirect(url_for("index"))

    @app.post("/dashboard/keys/<int:key_id>/revoke")
    @login_required
    def revoke_key(key_id):
        user = current_user()
        db.revoke_api_key(user["id"], key_id)
        return redirect(url_for("dashboard"))

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def get_dynamic_rate_limit():
        return f"{db.get_rate_limit_per_minute()} per minute"

    @app.post("/api/send")
    @csrf.exempt
    @limiter.limit(get_dynamic_rate_limit) # Se réévalue à chaque requête !
    def api_send():
        payload = request.get_json(silent=True) or {}
        api_key = payload.get("api_key")
        message = payload.get("message")

        if not api_key or not isinstance(api_key, str):
            return jsonify(error=bilingual(
                "Champ 'api_key' manquant ou invalide.",
                "Missing or invalid 'api_key' field.",
            )), 400
        if not message or not isinstance(message, str):
            return jsonify(error=bilingual(
                "Champ 'message' manquant ou invalide.",
                "Missing or invalid 'message' field.",
            )), 400
        if len(message) > 2000:
            return jsonify(error=bilingual(
                "Le message dépasse la limite Discord de 2000 caractères.",
                "Message exceeds Discord's 2000 character limit.",
            )), 413

        auth = db.verify_api_key(api_key)
        if auth is None:
            return jsonify(error=bilingual(
                "Clé API invalide ou révoquée.",
                "Invalid or revoked API key.",
            )), 401

        user = auth["user"]
        api_key_id = auth["api_key_id"]
        key_prefix = auth["key_prefix"]

        rate_limit = db.get_rate_limit_per_minute()
        if rate_limit > 0:
            since = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            recent = db.count_recent_notifications(user["id"], since)
            if recent >= rate_limit:
                return jsonify(error=bilingual(
                    "Limite de débit atteinte, réessayez dans une minute.",
                    "Rate limit reached, try again in a minute.",
                )), 429

        result = bot.send_dm(user["discord_id"], message, key_prefix=key_prefix)

        db.log_notification(
            user_id=user["id"],
            api_key_id=api_key_id,
            message=message,
            status="sent" if result.ok else "failed",
            error=None if result.ok else result.error,
        )

        if not result.ok:
            return jsonify(error=result.error or bilingual(
                "Échec de l'envoi.",
                "Send failed.",
            )), 502

        return jsonify(status="sent"), 200

    # -----------------------------------------------------------------
    # Admin
    # -----------------------------------------------------------------

    @app.get("/admin")
    @admin_required
    def admin_dashboard():
        return render_template(
            "admin.html",
            stats=db.get_overview_stats(),
            users_overview=db.list_users_overview(),
            rate_limit=db.get_rate_limit_per_minute(),
            max_keys=db.get_max_api_keys_per_user(),
        )

    @app.post("/admin/settings")
    @admin_required
    def admin_update_settings():
        user = current_user()
        old_rate = db.get_rate_limit_per_minute()
        old_max_keys = db.get_max_api_keys_per_user()

        rate_limit = (request.form.get("rate_limit_per_minute") or "").strip()
        max_keys = (request.form.get("max_api_keys_per_user") or "").strip()

        if rate_limit.isdigit():
            value = int(rate_limit)
            if value != old_rate:
                db.set_setting("rate_limit_per_minute", value)
                set_key(Config.ENV_PATH, "RATE_LIMIT_PER_MINUTE", str(value))
                os.environ["RATE_LIMIT_PER_MINUTE"] = str(value)
                db.log_audit(user["id"], "update_rate_limit", f"{old_rate} -> {value}")

        if max_keys.isdigit() and int(max_keys) >= 1:
            value = int(max_keys)
            if value != old_max_keys:
                db.set_setting("max_api_keys_per_user", value)
                set_key(Config.ENV_PATH, "MAX_API_KEYS_PER_USER", str(value))
                os.environ["MAX_API_KEYS_PER_USER"] = str(value)
                db.log_audit(user["id"], "update_max_keys", f"{old_max_keys} -> {value}")

        return redirect(url_for("admin_dashboard"))

    # -----------------------------------------------------------------
    # Errors
    # -----------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("index.html"), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10001, debug=True, use_reloader=True)