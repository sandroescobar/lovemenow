#!/usr/bin/env python3
"""
Test Slack integration with Flask app context
"""
import os
from dotenv import load_dotenv
from main import app

# Load environment variables
load_dotenv()

print("=== SLACK INTEGRATION TEST WITH FLASK CONTEXT ===")

with app.app_context():
    # Test the Slack service
    from services.slack_notifications import SlackNotificationService, send_test_notification
    
    print(f"Flask config SLACK_WEBHOOK_URL: {'SET' if app.config.get('SLACK_WEBHOOK_URL') else 'NOT SET'}")
    
    if app.config.get('SLACK_WEBHOOK_URL'):
        webhook_url = app.config.get('SLACK_WEBHOOK_URL')
        print(f"Webhook URL: {webhook_url[:50]}...{webhook_url[-10:]}")
        
        # Test the service
        print("\n=== TESTING SLACK SERVICE ===")
        try:
            success = send_test_notification()
            if success:
                print("✅ SUCCESS: Slack test notification sent!")
            else:
                print("❌ FAILED: Slack test notification failed")
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
    else:
        print("❌ SLACK_WEBHOOK_URL not configured in Flask app")

print("\n=== END TEST ===")