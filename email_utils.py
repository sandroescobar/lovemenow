# email_utils.py
import os, json, requests

SENDLAYER_API_KEY = os.getenv("SENDLAYER_API_KEY")
SENDLAYER_API_URL = "https://console.sendlayer.com/api/v1/email"

def send_email_sendlayer(to_name: str, to_email: str,
                         subject: str, html_body: str,
                         plain_body: str = "") -> dict:
    """
    Fire a single transactional email via SendLayer JSON API.
    Returns the parsed JSON response (or raises for HTTP errors).
    """

    if not SENDLAYER_API_KEY:
        raise RuntimeError("SENDLAYER_API_KEY is not set in your environment")

    # Get environment-specific settings
    from_email = os.getenv("FROM_EMAIL", "hello@lovemenowmiami.com")
    from_name = os.getenv("FROM_NAME", "LoveMeNow")
    email_tags = os.getenv("EMAIL_TAGS", "production").split(",")
    
    payload = {
        "From": {"name": from_name, "email": from_email},
        "To":   [{"name": to_name, "email": to_email}],
        "Subject": subject,
        "ContentType": "HTML",
        "HTMLContent": html_body,
        "PlainContent": plain_body or "See HTML version.",
        "Tags": email_tags
    }

    headers = {
        "Authorization": f"Bearer {SENDLAYER_API_KEY}",
        "Content-Type": "application/json"
    }

    resp = requests.post(SENDLAYER_API_URL,
                         headers=headers,
                         data=json.dumps(payload),
                         timeout=15)

    resp.raise_for_status()            # raises if SendLayer returns ≥400
    return resp.json()                 # success → JSON with “message_id”
