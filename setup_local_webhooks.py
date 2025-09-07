#!/usr/bin/env python3
"""
Setup script to enable Stripe webhooks for local development
"""
import subprocess
import sys
import time
import requests
import json

def check_ngrok_installed():
    """Check if ngrok is installed"""
    try:
        result = subprocess.run(['ngrok', 'version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ ngrok is installed")
            return True
        else:
            print("❌ ngrok is not installed")
            return False
    except FileNotFoundError:
        print("❌ ngrok is not installed")
        return False

def install_ngrok():
    """Install ngrok using homebrew"""
    print("📦 Installing ngrok...")
    try:
        subprocess.run(['brew', 'install', 'ngrok'], check=True)
        print("✅ ngrok installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install ngrok with brew")
        print("Please install ngrok manually from https://ngrok.com/download")
        return False
    except FileNotFoundError:
        print("❌ Homebrew not found. Please install ngrok manually from https://ngrok.com/download")
        return False

def start_ngrok_tunnel():
    """Start ngrok tunnel for port 2100"""
    print("🚀 Starting ngrok tunnel for port 2100...")
    
    # Start ngrok in background
    process = subprocess.Popen(['ngrok', 'http', '2100'], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE)
    
    # Wait a moment for ngrok to start
    time.sleep(3)
    
    # Get the public URL
    try:
        response = requests.get('http://127.0.0.1:4040/api/tunnels')
        data = response.json()
        
        if 'tunnels' in data and len(data['tunnels']) > 0:
            public_url = data['tunnels'][0]['public_url']
            webhook_url = f"{public_url}/webhooks/stripe"
            
            print(f"✅ ngrok tunnel started!")
            print(f"🌐 Public URL: {public_url}")
            print(f"🔗 Webhook URL: {webhook_url}")
            
            return webhook_url, process
        else:
            print("❌ Failed to get ngrok tunnel URL")
            return None, process
            
    except Exception as e:
        print(f"❌ Error getting ngrok URL: {e}")
        return None, process

def main():
    print("🔧 SETTING UP LOCAL STRIPE WEBHOOKS")
    print("=" * 50)
    
    # Check if ngrok is installed
    if not check_ngrok_installed():
        print("\n📦 Installing ngrok...")
        if not install_ngrok():
            print("\n❌ SETUP FAILED: Could not install ngrok")
            print("Please install ngrok manually and run this script again")
            return
    
    # Start ngrok tunnel
    webhook_url, ngrok_process = start_ngrok_tunnel()
    
    if webhook_url:
        print("\n🎉 SETUP COMPLETE!")
        print("=" * 50)
        print(f"✅ Your webhook URL: {webhook_url}")
        print("\n📋 NEXT STEPS:")
        print("1. Go to your Stripe Dashboard: https://dashboard.stripe.com/webhooks")
        print("2. Click 'Add endpoint'")
        print(f"3. Enter this URL: {webhook_url}")
        print("4. Select these events:")
        print("   - payment_intent.succeeded")
        print("   - checkout.session.completed")
        print("5. Save the endpoint")
        print("6. Copy the webhook signing secret and add it to your .env file:")
        print("   STRIPE_WEBHOOK_SECRET=whsec_your_secret_here")
        print("\n🚨 IMPORTANT:")
        print("- Keep this terminal window open while testing")
        print("- Your Flask app should be running on port 2100")
        print("- Make a test purchase to verify Slack notifications work")
        print("\n⏹️  Press Ctrl+C to stop ngrok when done testing")
        
        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping ngrok...")
            ngrok_process.terminate()
            print("✅ ngrok stopped")
    else:
        print("\n❌ SETUP FAILED: Could not start ngrok tunnel")
        if ngrok_process:
            ngrok_process.terminate()

if __name__ == "__main__":
    main()