"""
Relay API demo — showcases every field accepted by POST /api/send.

Only 2 requests are made:

  1. Predefined `type` + a file attachment.
     - "type" picks a ready-made title/color (see bot.NOTIFICATION_TYPES).
     - "files" is decoded from base64 server-side, forwarded straight to
       Discord and never written to disk.

  2. Custom `title` + `color`, no `type`.
     - Shows the fields you'd use when no predefined type fits your case.
     - "title"/"color" are ignored whenever "type" is provided, so this
       request intentionally omits it.

Set RELAY_API_KEY in your environment before running:

    export RELAY_API_KEY=pk_your_key
    python demo.py
"""

import base64
import os

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:10001")
API_KEY = os.environ.get("API_KEY", "pk_[...]")


def send(payload: dict) -> requests.Response:
    response = requests.post(f"{BASE_URL}/api/send", json=payload, timeout=15)
    print(f"-> {response.status_code} {response.json()}")
    return response


def main() -> None:
    # 1. Predefined type ("file") + an attachment (all fields but title/color)
    with open("requirements.txt", "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    send(
        {
            "api_key": API_KEY,
            "message": "Sending requirements.txt as an attachment.",
            "type": "file",
            "files": [
                {"filename": "requirements.txt", "content_base64": encoded},
            ],
        }
    )

    # 2. Custom title + color (no "type" this time, so they actually apply)
    send(
        {
            "api_key": API_KEY,
            "message": "Custom embed with no predefined type.",
            "title": "🔧 Custom notification",
            "color": "#58ED5E",
        }
    )


if __name__ == "__main__":
    main()