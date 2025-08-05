# emails.py
import os, json, requests
from flask import render_template

SENDLAYER_KEY = os.getenv("SENDLAYER_API_KEY")          # in .env / Railway vars
SENDLAYER_URL = "https://api.sendlayer.com/v1/email"

FROM_NAME  = "LoveMeNow"
FROM_EMAIL = "hello@lovemenow.co"

def send_email(to_email: str,
               subject: str,
               html_template: str,
               txt_template: str | None = None,
               **template_ctx):
    """Render a Jinja template and POST it to SendLayer."""
    html_body = render_template(html_template, **template_ctx)
    plain_body = render_template(txt_template,  **template_ctx) if txt_template else None

    payload = {
        "From": {"name": FROM_NAME, "email": FROM_EMAIL},
        "To":   [{"email": to_email}],
        "Subject": subject,
        "ContentType": "HTML",
        "HTMLContent": html_body,
        "PlainContent": plain_body or "",
        "Tags": ["marketing"]
    }

    r = requests.post(
        SENDLAYER_URL,
        headers={
            "Authorization": f"Bearer {SENDLAYER_KEY}",
            "Content-Type": "application/json"
        },
        data=json.dumps(payload),
        timeout=10
    )
    r.raise_for_status()                 # raises on 4 xx / 5 xx
    return r.json()                      # message_id, status, etc.
