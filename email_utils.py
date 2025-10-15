# email_utils.py
from flask import current_app
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

    api_key = os.getenv("SENDLAYER_API_KEY")
    if not api_key:
        current_app.logger.error("SENDLAYER_API_KEY is not set in your environment; skipping email send")
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
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Log the outbound request (without sensitive headers)
    try:
        current_app.logger.info(f"SendLayer: POST {SENDLAYER_API_URL} -> to={to_email} subject={subject} tags={email_tags}")
    except Exception:
        pass

    resp = requests.post(
        SENDLAYER_API_URL,
        headers=headers,
        data=json.dumps(payload),
        timeout=15
    )

    try:
        resp.raise_for_status()            # raises if SendLayer returns ≥400
    except requests.HTTPError as http_err:
        # Log response body for diagnostics
        try:
            current_app.logger.error(f"SendLayer HTTPError: status={resp.status_code} body={resp.text}")
        except Exception:
            pass
        raise

    try:
        result = resp.json()
    except ValueError:
        # Not JSON? Log and raise
        current_app.logger.error(f"SendLayer non-JSON response: status={resp.status_code} body={resp.text[:500]}")
        raise

    # Log success minimally
    try:
        mid = result.get('message_id') or result.get('id')
        current_app.logger.info(f"SendLayer: sent ok -> message_id={mid}")
    except Exception:
        pass

    return result                 # success → JSON with “message_id”
