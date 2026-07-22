"""
demo.py — Démo de l'API Relay

Montre tout ce qu'on peut faire avec UNE seule clé API (pk_...) :
  - envoyer un message simple
  - envoyer plusieurs messages à la suite
  - gérer les erreurs (clé invalide, message trop long, rate limit, DM impossible)
  - notifier automatiquement le succès/échec d'un bloc de code (context manager)
  - notifier automatiquement le résultat d'une fonction (décorateur)
  - un petit exemple "cron / job de fond" concret

Utilisation :
    1. Récupère ta clé depuis le dashboard Relay (bouton "Générer une clé").
    2. Renseigne RELAY_API_KEY et RELAY_BASE_URL ci-dessous (ou via variables d'env).
    3. python demo.py
"""

from __future__ import annotations

import os
import time
import traceback
from contextlib import contextmanager
from functools import wraps

import requests

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

RELAY_BASE_URL = os.environ.get("RELAY_BASE_URL", "http://localhost:5000")
RELAY_API_KEY = os.environ.get("RELAY_API_KEY", "pk_[...]")


# --------------------------------------------------------------------------
# Client minimal
# --------------------------------------------------------------------------

class RelayError(Exception):
    """Levée quand l'API Relay répond avec une erreur."""


def send(message: str, *, base_url: str = RELAY_BASE_URL, api_key: str = RELAY_API_KEY) -> dict:
    """
    Envoie un message via Relay.

    Retourne le JSON de réponse en cas de succès (200).
    Lève RelayError en cas d'échec (400 / 401 / 429 / 502).
    """
    resp = requests.post(
        f"{base_url}/api/send",
        json={"api_key": api_key, "message": message},
        timeout=15,
    )

    try:
        data = resp.json()
    except ValueError:
        data = {}

    if resp.status_code == 200:
        return data

    reason = {
        400: "Requête invalide",
        401: "Clé API invalide ou révoquée",
        429: "Limite de débit atteinte",
        502: "Le bot n'a pas pu délivrer le DM",
    }.get(resp.status_code, "Erreur inconnue")

    raise RelayError(f"[{resp.status_code}] {reason} — {data.get('error', 'pas de détail')}")


# --------------------------------------------------------------------------
# Context manager : notifie le résultat d'un bloc de code
# --------------------------------------------------------------------------

@contextmanager
def notify_block(label: str):
    """
    Usage :
        with notify_block("Backup nocturne"):
            faire_le_backup()

    Envoie un DM de succès ou d'échec (avec la trace) à la fin du bloc.
    """
    start = time.monotonic()
    try:
        yield
    except Exception as exc:
        duration = time.monotonic() - start
        tb = traceback.format_exc(limit=3)
        try:
            send(f"❌ {label} a échoué après {duration:.1f}s : {exc}\n\n{tb[-1500:]}")
        except RelayError:
            pass  # on ne veut pas masquer l'erreur d'origine
        raise
    else:
        duration = time.monotonic() - start
        try:
            send(f"✅ {label} terminé avec succès en {duration:.1f}s.")
        except RelayError:
            pass


# --------------------------------------------------------------------------
# Décorateur : notifie le résultat d'une fonction
# --------------------------------------------------------------------------

def notify_on_call(label: str | None = None):
    """
    Usage :
        @notify_on_call("Job d'export CSV")
        def export_csv():
            ...

    Envoie un DM à chaque appel de la fonction (succès ou échec).
    """
    def decorator(func):
        name = label or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            with notify_block(name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# --------------------------------------------------------------------------
# Démo
# --------------------------------------------------------------------------

def demo_message_simple():
    print("\n--- 1) Message simple ---")
    try:
        result = send("👋 Test rapide depuis demo.py")
        print("OK :", result)
    except RelayError as e:
        print("Erreur :", e)


def demo_plusieurs_messages():
    print("\n--- 2) Plusieurs messages à la suite ---")
    etapes = [
        "🚀 Démarrage du pipeline",
        "📦 Récupération des données terminée",
        "🧮 Traitement terminé",
        "✅ Pipeline terminé avec succès",
    ]
    for etape in etapes:
        try:
            send(etape)
            print("Envoyé :", etape)
        except RelayError as e:
            print("Erreur d'envoi :", e)
        time.sleep(0.5)  # pour ne pas taper le rate limit trop vite


def demo_gestion_erreurs():
    print("\n--- 3) Gestion des erreurs ---")

    # Clé invalide
    try:
        send("Ce message ne devrait jamais arriver", api_key="pk_clef_invalide")
    except RelayError as e:
        print("Erreur attendue (clé invalide) :", e)

    # Message trop long (> 2000 caractères)
    try:
        send("x" * 2001)
    except RelayError as e:
        print("Erreur attendue (message trop long) :", e)


def demo_context_manager_succes():
    print("\n--- 4) Context manager (succès) ---")
    with notify_block("Tâche de démonstration"):
        time.sleep(1)  # simule du travail


def demo_context_manager_echec():
    print("\n--- 5) Context manager (échec) ---")
    try:
        with notify_block("Tâche qui échoue exprès"):
            raise ValueError("Boom, une erreur simulée")
    except ValueError:
        print("Exception relayée normalement après notification d'échec.")


@notify_on_call("Job d'export (décorateur)")
def job_export_exemple():
    """Exemple de fonction 'métier' notifiée automatiquement à chaque appel."""
    time.sleep(1)
    return {"lignes_exportees": 1234}


def demo_decorateur():
    print("\n--- 6) Décorateur @notify_on_call ---")
    result = job_export_exemple()
    print("Résultat :", result)


def demo_cron_job():
    """
    Exemple concret : un 'job' que tu lancerais via cron / systemd timer,
    qui prévient sur Discord uniquement si quelque chose se passe mal.
    """
    print("\n--- 7) Exemple job cron réaliste ---")

    def verifier_disque():
        # ... logique réelle ici (shutil.disk_usage, etc.)
        return 82  # % d'utilisation simulé

    usage = verifier_disque()
    if usage >= 90:
        try:
            send(f"⚠️ Alerte disque : {usage}% utilisé sur le serveur.")
        except RelayError as e:
            print("Impossible d'envoyer l'alerte :", e)
    else:
        print(f"Disque à {usage}%, tout va bien (pas de notification envoyée).")


if __name__ == "__main__":
    print(f"Relay demo — base_url={RELAY_BASE_URL}")
    if RELAY_API_KEY == "pk_votre_cle_ici":
        print(
            "\n⚠️  Renseigne ta vraie clé API (variable d'env RELAY_API_KEY "
            "ou modifie RELAY_API_KEY en haut du fichier) avant de lancer la démo.\n"
        )

    demo_message_simple()
    demo_plusieurs_messages()
    demo_gestion_erreurs()
    demo_context_manager_succes()
    demo_context_manager_echec()
    demo_decorateur()
    demo_cron_job()

    print("\nTerminé. Regarde ton historique dans le dashboard Relay 👀")