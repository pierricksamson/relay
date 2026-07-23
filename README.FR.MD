# Relay — notifications Discord pour vos scripts

*[Read this in English](README.MD)*

MVP Flask + discord.py + SQLite permettant d'envoyer un DM Discord depuis
n'importe quel script via une simple requête `POST /api/send`.

## Arborescence du projet

Flask cherche les templates dans `templates/` et les fichiers statiques dans
`static/` à la racine du projet.

```
.
├── app.py                  # routes Flask (public, dashboard, API, admin)
├── bot.py                  # wrapper discord.py (thread + event loop séparés)
├── config.py                # chargement de la config depuis .env
├── database.py              # couche SQLite (users, api_keys, notifications, settings)
├── discord_oauth.py         # flux OAuth2 "Authorization Code" (scope identify)
├── demo.py                  # script de démo du client API (context manager, décorateur, etc.)
├── requirements.txt
├── .env                     # à créer, voir "Configuration" ci-dessous
├── templates/
│   ├── base.html            # layout commun (nav, footer, sélecteur de langue, modale confirm)
│   ├── index.html           # page d'accueil / présentation
│   ├── dashboard.html       # clés API, historique, zone dangereuse (suppression de compte)
│   ├── docs.html            # référence API (endpoint, exemples Python/cURL/JS)
│   ├── admin.html           # dashboard admin (stats, réglages globaux, liste des utilisateurs)
│   └── cgu.html             # conditions générales d'utilisation
├── static/
│   ├── css/style.css
│   ├── js/main.js           # onglets docs, copie de clé, sélecteur de langue, modale confirm
│   └── lang/
│       ├── fr.json
│       └── en.json
└── instance/                # créé automatiquement (contient app.db, SQLite)
```

## Configuration (`.env`)

Créez un fichier `.env` à la racine avec les clés suivantes (voir `config.py`) :

```env
SECRET_KEY=une-chaine-aleatoire-longue-et-imprevisible
BASE_URL=http://localhost:5000

DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=http://localhost:5000/callback
DISCORD_BOT_TOKEN=...

DATABASE_PATH=instance/app.db
RATE_LIMIT_PER_MINUTE=30
MAX_API_KEYS_PER_USER=5
```

`RATE_LIMIT_PER_MINUTE` et `MAX_API_KEYS_PER_USER` ne sont que des valeurs de
démarrage : un compte admin peut ensuite les modifier dynamiquement depuis
`/admin`, sans redémarrer l'application.

Pour `SECRET_KEY`, générez une vraie valeur aléatoire plutôt que d'utiliser
une chaîne devinable :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Où récupérer les identifiants Discord

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

Pour promouvoir un utilisateur en administrateur (accès à `/admin`), il n'y a
pas d'interface dédiée : positionnez la colonne `admin` à `1` directement en
base pour la ligne correspondante de la table `users`.

```bash
sqlite3 instance/app.db "UPDATE users SET admin = 1 WHERE discord_id = 'VOTRE_ID_DISCORD';"
```

## Test rapide de l'API

Une fois connecté et une clé générée depuis `/dashboard` :

```bash
curl -X POST http://localhost:5000/api/send \
  -H "Content-Type: application/json" \
  -d '{"api_key": "pk_votre_cle", "message": "Test depuis curl"}'
```

Un exemple plus complet (context manager pour notifier le résultat d'un
bloc de code, décorateur pour notifier le résultat d'une fonction, gestion
des erreurs 400/401/429/502) est disponible dans `demo.py` :

```bash
export RELAY_API_KEY=pk_votre_cle
python demo.py
```

## Pages et routes principales

| Route | Description |
|---|---|
| `GET /` | Page d'accueil publique |
| `GET /docs` | Référence API (endpoint, codes de réponse, exemples) |
| `GET /cgu` | Conditions générales d'utilisation |
| `GET /login`, `GET /callback`, `GET /logout` | Flux OAuth2 Discord |
| `GET /dashboard` | Clés API, historique de notifications, suppression de compte |
| `POST /api/send` | Endpoint public : envoie un DM Discord via une clé API |
| `GET /admin`, `POST /admin/settings` | Réservé aux comptes admin : stats globales, réglages, liste des utilisateurs |
| `GET /robots.txt`, `GET /sitemap.xml` | SEO : les routes privées et l'API sont exclues de l'indexation |

## Internationalisation

L'interface est disponible en français et en anglais via un sélecteur de
langue en haut de page (`static/lang/fr.json` / `static/lang/en.json`,
appliqués côté client par `static/js/main.js` via les attributs
`data-i18n` / `data-i18n-placeholder`). La langue choisie est mémorisée dans
le `localStorage` du navigateur.

## Notes / limites connues du MVP

- Le bot tourne dans un thread + event loop séparé (voir `bot.py`) ; c'est
  suffisant pour un faible volume mais ce n'est pas fait pour scaler à un
  gros débit de notifications simultanées.
- Pas de pagination sur l'historique des notifications, seulement les N
  dernières (`HISTORY_PAGE_SIZE` dans `config.py`, 20 par défaut).
- Le contenu des messages envoyés est conservé en clair dans l'historique :
  ne mettez pas de secrets/tokens dans vos messages.
- Voir [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md) pour la liste complète des
  points à corriger avant une mise en production (mode debug, CSRF, cookies
  de session, en-têtes de sécurité, etc.).