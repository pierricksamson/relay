import base64
import requests

with open("requirements.txt", "rb") as f:
    encoded = base64.b64encode(f.read()).decode()

response = requests.post(
    "http://localhost:10001/api/send",
    json={
        "api_key": "pk_ndBZvbrlxs6TSAoT6wKK8CcanBprQ_FkEJjGA8ell6A",
        "message": "Envoi du fichier requirements.txt",
        "type": "file",
        "files": [
            {"filename": "requirements.txt", "content_base64": encoded},
        ],
    },
)

if response.status_code == 200:
    response = requests.post(
        "http://localhost:10001/api/send",
        json={
            "api_key": "pk_ndBZvbrlxs6TSAoT6wKK8CcanBprQ_FkEJjGA8ell6A",
            "message": "2 eme message",
            "title": "Test",
            "color": "#58ed5e",
        },
    )




print(response.status_code, response.json())