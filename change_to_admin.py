"""
to_admin.py — Promeut un utilisateur Relay en administrateur.

Utilisation :
    python to_admin.py -id <discord_id>
    python to_admin.py --id <discord_id>

Exemple :
    python to_admin.py -id 7876454563212
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from src.config import Config
from src.database import get_db, _column_exists


def set_admin(discord_id: str) -> int:
    """Passe admin=1 pour l'utilisateur correspondant. Retourne le nombre de lignes touchées."""
    with get_db() as db:
        if not _column_exists(db, "users", "admin"):
            db.execute("ALTER TABLE users ADD COLUMN admin INTEGER NOT NULL DEFAULT 0")

        cur = db.execute(
            "UPDATE users SET admin = 1 WHERE discord_id = ?",
            (discord_id,),
        )
        return cur.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description="Promeut un utilisateur Relay en admin.")
    parser.add_argument(
        "-id", "--id",
        dest="discord_id",
        required=True,
        help="Discord ID de l'utilisateur à promouvoir en admin.",
    )
    args = parser.parse_args()

    try:
        rows = set_admin(args.discord_id)
    except sqlite3.Error as e:
        print(f"Erreur base de données : {e}", file=sys.stderr)
        sys.exit(1)

    if rows == 0:
        print(
            f"Aucun utilisateur trouvé avec discord_id={args.discord_id!r} "
            f"(base : {Config.DATABASE_PATH}). L'utilisateur doit s'être connecté "
            "au moins une fois via OAuth Discord avant de pouvoir être promu."
        )
        sys.exit(1)

    print(f"✅ Utilisateur discord_id={args.discord_id} promu administrateur.")


if __name__ == "__main__":
    main()