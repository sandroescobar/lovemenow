#!/usr/bin/env python3
"""
Start ngrok to expose local server for Stripe webhooks
"""
import subprocess
import time
import requests
import json

def start_ngrok():
    """Start ngrok and get the public URL"""
    print("🚀 STARTING NGROK TO EXPOSE YOUR LOCAL SERVER")
    print("=" * 60)
    print("This will create a public URL that Stripe can use to send webhooks")
    print("=" * 60)
    print()
    
    print("📡 Starting ngrok tunnel...")
    
    # Start ngrok in the background
    try:
        # Kill any existing ngrok processes
        subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
        time.sleep(2)
        
        # Start ngrok
        process = subprocess.Popen(
            ['ngrok', 'http', '2100', '--log=stdout'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print("⏳ Waiting for ngrok to start...")
        time.sleep(5)
        
        # Get the public URL from ngrok API
        try:
            response = requests.get('http://127.0.0.1:4040/api/tunnels')
            tunnels = response.json()
            
            if tunnels.get('tunnels'):
                public_url = tunnels['tunnels'][0]['public_url']
                webhook_url = f"{public_url}/webhooks/stripe"
                
                print("✅ NGROK TUNNEL CREATED SUCCESSFULLY!")
                print()
                print("🌐 Public URL:", public_url)
                print("🔗 Webhook URL:", webhook_url)
                print()
                print("📋 NEXT STEPS:")
                print("1. Go to your Stripe Dashboard: https://dashboard.stripe.com/webhooks")
                print("2. Create a new webhook endpoint with this URL:")
                print(f"   {webhook_url}")
                print("3. Select 'payment_intent.succeeded' event")
                print("4. Save the webhook")
                print("5. Make a real purchase - you'll get Slack notifications!")
                print()
                print("⚠️  IMPORTANT: Keep this script running while testing!")
                print("   If you stop this script, the tunnel will close.")
                print()
                
                # Test the webhook URL
                print("🧪 Testing webhook URL...")
                test_payload = {
                    "id": "evt_ngrok_test",
                    "type": "payment_intent.succeeded",
                    "data": {
                        "object": {
                            "id": "pi_ngrok_test",
                            "amount": 2999,
                            "currency": "usd",
                            "status": "succeeded",
                            "metadata": {
                                "item_count": "1",
                                "item_0_product_id": "69",
                                "item_0_quantity": "1"
                            },
                            "receipt_email": "test@ngrok.com"
                        }
                    }
                }
                
                try:
                    test_response = requests.post(
                        webhook_url,
                        json=test_payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    
                    if test_response.status_code == 200:
                        print("✅ Webhook URL is working!")
                        print("🔔 Check Slack for test notification")
                    else:
                        print(f"⚠️  Webhook test returned {test_response.status_code}")
                        
                except Exception as e:
                    print(f"⚠️  Could not test webhook: {e}")
                
                print()
                print("🎯 NOW MAKE A REAL PURCHASE AND YOU'LL GET SLACK NOTIFICATIONS!")
                
                # Keep the process running
                print("\n" + "="*60)
                print("🔄 NGROK TUNNEL IS RUNNING...")
                print("Press Ctrl+C to stop")
                print("="*60)
                
                try:
                    process.wait()
                except KeyboardInterrupt:
                    print("\n🛑 Stopping ngrok...")
                    process.terminate()
                    
            else:
                print("❌ Could not get ngrok tunnel information")
                
        except Exception as e:
            print(f"❌ Error getting ngrok tunnel info: {e}")
            print("💡 Try opening http://127.0.0.1:4040 in your browser to see ngrok status")
            
    except Exception as e:
        print(f"❌ Error starting ngrok: {e}")
        print("🔧 Make sure ngrok is installed: brew install ngrok")

if __name__ == "__main__":
    start_ngrok()