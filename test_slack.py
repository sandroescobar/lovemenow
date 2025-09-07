#!/usr/bin/env python3
"""
Quick test script to verify Slack webhook is working
"""
import requests
import json
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')

def test_slack_webhook():
    """Test if Slack webhook is working"""
    print(f"Testing Slack webhook: {SLACK_WEBHOOK_URL}")
    
    if not SLACK_WEBHOOK_URL:
        print("❌ SLACK_WEBHOOK_URL not found in environment")
        return False
    
    # Simple test message
    test_message = {
        "text": "🧪 Test message from LoveMeNow - Slack integration working!"
    }
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            json=test_message,
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Slack webhook test successful!")
            return True
        else:
            print(f"❌ Slack webhook test failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Slack webhook: {str(e)}")
        return False

if __name__ == "__main__":
    test_slack_webhook()