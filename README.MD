# Relay — notifications Discord pour vos scripts

MVP Flask + discord.py + SQLite permettant d'envoyer un DM Discord depuis
n'importe quel script via une simple requête `POST /api/send`.

## Arborescence attendue

Flask cherche les templates dans `templates/` et les fichiers statiques dans
`static/` à la racine du projet. Voici comment ranger tous les fichiers :

```
.
├── app.py
├── bot.py
├── config.py
├── database.py
├── discord_oauth.py
├── requirements.txt
├── .env
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── dashboard.html
│   └── docs.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
└── instance/          # créé automatiquement (contient app.db, SQLite)
```

Les fichiers `dashboard.html` et `static/js/main.js` fournis ici étaient
manquants : `dashboard.html` était une copie de la page d'accueil (elle
n'affichait ni l'avatar Discord, ni les clés API, ni l'historique), et
`main.js` n'existait pas alors que `base.html` le charge et que la page
`/docs` a besoin de JS pour faire fonctionner les onglets Python/cURL/JS.

## Configuration (.env)

Puisque vous avez déjà un `.env`, vérifiez juste qu'il contient bien toutes
ces clés (voir `config.py`) :

```env
SECRET_KEY=une-chaine-aleatoire-longue
BASE_URL=http://localhost:5000

DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=http://localhost:5000/callback
DISCORD_BOT_TOKEN=...

DATABASE_PATH=instance/app.db
RATE_LIMIT_PER_MINUTE=30
```

### Où récupérer ces valeurs

1. Allez sur le [Discord Developer Portal](https://discord.com/developers/applications)
   et créez une application.
2. Onglet **OAuth2** : récupérez `DISCORD_CLIENT_ID` et `DISCORD_CLIENT_SECRET`,
   puis ajoutez `http://localhost:5000/callback` (ou votre domaine en prod)
   dans la liste des **Redirects**.
3. Onglet **Bot** : créez un bot, récupérez `DISCORD_BOT_TOKEN`. Activez
   l'intent **Server Members Intent** (nécessaire pour `fetch_user` dans
   `bot.py`).
4. Le bot doit partager au moins un serveur avec chaque utilisateur (ou avoir
   déjà reçu un message de lui) pour pouvoir lui envoyer un DM — c'est une
   règle Discord, pas une limite de Relay. Invitez donc votre bot sur un
   serveur commun avec vos utilisateurs de test via une URL d'invitation
   générée dans l'onglet **OAuth2 > URL Generator** (scope `bot`, aucune
   permission particulière requise pour de simples DM).

## Installation et lancement

```bash
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate

pip install -r requirements.txt

python app.py
```

Le site est alors sur `http://localhost:5000`. `db.init_db()` crée
automatiquement `instance/app.db` et ses tables au premier lancement — rien
à migrer à la main.

## Test rapide de l'API

Une fois connecté et une clé générée depuis `/dashboard` :

```bash
curl -X POST http://localhost:5000/api/send \
  -H "Content-Type: application/json" \
  -d '{"api_key": "pk_votre_cle", "message": "Test depuis curl"}'
```

## Notes / limites connues du MVP

- Le bot tourne dans un thread + event loop séparé (voir `bot.py`) ; c'est
  suffisant pour un faible volume mais ce n'est pas fait pour scaler à un
  gros débit de notifications simultanées.
- Pas de pagination sur l'historique des notifications, seulement les N
  dernières (`HISTORY_PAGE_SIZE` dans `config.py`, 20 par défaut).
- `debug=True` dans `app.py` (`app.run(..., debug=True)`) : à désactiver en
  production, et à servir derrière un vrai serveur WSGI (gunicorn, etc.)
  plutôt que le serveur de développement Flask.
- Le secret Flask (`SECRET_KEY`) doit être une vraie valeur aléatoire en
  production — la valeur par défaut dans `config.py` n'est là que pour le
  dev local.