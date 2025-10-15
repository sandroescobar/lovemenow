# routes/utils_email.py
import os, requests
from flask import current_app

SENDLAYER_API = "https://api.sendlayer.com/v1/email"

def send_email_sendlayer(to_email: str, subject: str, html: str, text: str | None = None):
    api_key = os.getenv("SENDLAYER_API_KEY") or current_app.config.get("SENDLAYER_API_KEY")
    if not api_key:
        raise RuntimeError("SENDLAYER_API_KEY missing")

    payload = {
        "from": {"email": current_app.config.get("ORDERS_FROM_EMAIL", "orders@lovemenowmiami.com"),
                 "name": current_app.config.get("BRAND_NAME", "LoveMeNow Miami")},
        "to": [{"email": to_email}],
        "subject": subject,
        "html_body": html,
    }
    if text:
        payload["plain_body"] = text

    r = requests.post(SENDLAYER_API,
                      headers={"Authorization": f"Bearer {api_key}",
                               "Content-Type": "application/json"},
                      json=payload, timeout=20)
    r.raise_for_status()
    return r.json()
