# Relay — Discord notifications for your scripts

*[Lire ceci en français](README.fr.md)*

A Flask + discord.py + SQLite MVP that sends a Discord DM from any script
via a simple `POST /api/send` request.

## Project layout

Flask looks for templates in `templates/` and static assets in `static/` at
the project root.

```
.
├── app.py                  # Flask routes (public, dashboard, API, admin)
├── bot.py                  # discord.py wrapper (runs on its own thread + event loop)
├── config.py                # loads configuration from .env
├── database.py              # SQLite data layer (users, api_keys, notifications, settings)
├── discord_oauth.py         # OAuth2 "Authorization Code" flow (scope: identify)
├── demo.py                  # API client demo (context manager, decorator, error handling, etc.)
├── requirements.txt
├── .env                     # to create, see "Configuration" below
├── templates/
│   ├── base.html            # shared layout (nav, footer, language switcher, confirm modal)
│   ├── index.html           # landing / marketing page
│   ├── dashboard.html       # API keys, notification history, danger zone (account deletion)
│   ├── docs.html             # API reference (endpoint, Python/cURL/JS examples)
│   ├── admin.html            # admin dashboard (stats, global settings, user list)
│   └── cgu.html              # terms of service
├── static/
│   ├── css/style.css
│   ├── js/main.js            # docs tabs, key copy button, language switcher, confirm modal
│   └── lang/
│       ├── fr.json
│       └── en.json
└── instance/                 # created automatically (holds app.db, SQLite)
```

## Configuration (`.env`)

Create a `.env` file at the project root with the following keys (see
`config.py`):

```env
SECRET_KEY=a-long-unpredictable-random-string
BASE_URL=http://localhost:5000

DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=http://localhost:5000/callback
DISCORD_BOT_TOKEN=...

DATABASE_PATH=instance/app.db
RATE_LIMIT_PER_MINUTE=30
MAX_API_KEYS_PER_USER=5
```

`RATE_LIMIT_PER_MINUTE` and `MAX_API_KEYS_PER_USER` are only startup
defaults: an admin account can change them dynamically from `/admin`
without restarting the app.

For `SECRET_KEY`, generate a real random value instead of using a guessable
string:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Where to get the Discord credentials

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
   and create an application.
2. **OAuth2** tab: grab `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET`, then
   add `http://localhost:5000/callback` (or your production domain) to the
   **Redirects** list.
3. **Bot** tab: create a bot, grab `DISCORD_BOT_TOKEN`. Enable the
   **Server Members Intent** (required for `fetch_user` in `bot.py`).
4. The bot must share at least one server with each user (or have already
   received a message from them) to be able to DM them — that's a Discord
   rule, not a Relay limitation. Invite your bot to a server shared with
   your test users via an invite URL generated from the
   **OAuth2 > URL Generator** tab (`bot` scope, no special permission needed
   for plain DMs).

## Install and run

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

python app.py
```

The site is then available at `http://localhost:5000`. `db.init_db()`
automatically creates `instance/app.db` and its tables on first run —
nothing to migrate by hand.

There's no dedicated UI to promote a user to admin (to access `/admin`):
set the `admin` column to `1` directly in the database for the matching row
in the `users` table.

```bash
sqlite3 instance/app.db "UPDATE users SET admin = 1 WHERE discord_id = 'YOUR_DISCORD_ID';"
```

## Quick API test

Once logged in and a key has been generated from `/dashboard`:

```bash
curl -X POST http://localhost:5000/api/send \
  -H "Content-Type: application/json" \
  -d '{"api_key": "pk_your_key", "message": "Test from curl"}'
```

A more complete example (a context manager to notify the outcome of a code
block, a decorator to notify the outcome of a function call, handling of
400/401/429/502 errors) is available in `demo.py`:

```bash
export RELAY_API_KEY=pk_your_key
python demo.py
```

## Main pages and routes

| Route | Description |
|---|---|
| `GET /` | Public landing page |
| `GET /docs` | API reference (endpoint, response codes, examples) |
| `GET /cgu` | Terms of service |
| `GET /login`, `GET /callback`, `GET /logout` | Discord OAuth2 flow |
| `GET /dashboard` | API keys, notification history, account deletion |
| `POST /api/send` | Public endpoint: sends a Discord DM via an API key |
| `GET /admin`, `POST /admin/settings` | Admin-only: global stats, settings, user list |
| `GET /robots.txt`, `GET /sitemap.xml` | SEO: private routes and the API are excluded from indexing |

## Internationalization

The UI is available in French and English via a language switcher at the
top of the page (`static/lang/fr.json` / `static/lang/en.json`, applied
client-side by `static/js/main.js` through `data-i18n` /
`data-i18n-placeholder` attributes). The chosen language is remembered in
the browser's `localStorage`.

## Notes / known MVP limitations

- The bot runs on its own thread + event loop (see `bot.py`); that's enough
  for low volume but isn't designed to scale to a high rate of concurrent
  notifications.
- No pagination on notification history, only the last N entries
  (`HISTORY_PAGE_SIZE` in `config.py`, 20 by default).
- Sent message content is kept in plaintext in the history: don't put
  secrets/tokens in your messages.
- See [`SECURITY_AUDIT.en.md`](SECURITY_AUDIT.en.md) for the full list of
  items to fix before going to production (debug mode, CSRF, session
  cookies, security headers, etc.).