#!/usr/bin/env python3
"""
Debug Slack integration
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=== SLACK INTEGRATION DEBUG ===")

# Check environment variable
slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
print(f"SLACK_WEBHOOK_URL from env: {slack_webhook_url[:50]}...{slack_webhook_url[-10:] if slack_webhook_url else 'NOT SET'}")

if not slack_webhook_url:
    print("❌ SLACK_WEBHOOK_URL is not set in environment variables")
    exit(1)

# Test the webhook URL directly
print("\n=== TESTING SLACK WEBHOOK DIRECTLY ===")

test_message = {
    "text": "🧪 Direct Slack Test from Debug Script",
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "🧪 *Direct Slack Test*\n\nThis is a direct test from the debug script to verify the webhook URL is working.\n\n✅ If you see this, the webhook URL is correct!"
            }
        }
    ]
}

try:
    print(f"Sending test message to: {slack_webhook_url[:50]}...")
    response = requests.post(
        slack_webhook_url,
        json=test_message,
        timeout=10
    )
    
    print(f"Response status code: {response.status_code}")
    print(f"Response text: {response.text}")
    
    if response.status_code == 200:
        print("✅ SUCCESS: Slack webhook is working!")
    else:
        print(f"❌ FAILED: Slack webhook returned {response.status_code}")
        
except requests.exceptions.Timeout:
    print("❌ TIMEOUT: Request to Slack timed out")
except requests.exceptions.ConnectionError:
    print("❌ CONNECTION ERROR: Could not connect to Slack")
except Exception as e:
    print(f"❌ ERROR: {str(e)}")

print("\n=== END DEBUG ===")