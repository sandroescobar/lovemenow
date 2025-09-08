#!/usr/bin/env python3
"""
Debug script to check Stripe environment variables
Run this to see what Stripe keys are being loaded
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=== STRIPE ENVIRONMENT DEBUG ===")
print(f"Current working directory: {os.getcwd()}")
print(f"FLASK_ENV: {os.getenv('FLASK_ENV', 'NOT SET')}")
print()

# Check environment variables
stripe_secret = os.getenv('STRIPE_SECRET_KEY')
stripe_publishable = os.getenv('STRIPE_PUBLISHABLE_KEY')

print("Environment Variables:")
if stripe_secret:
    print(f"STRIPE_SECRET_KEY: {stripe_secret[:20]}...{stripe_secret[-4:]} (length: {len(stripe_secret)})")
else:
    print("STRIPE_SECRET_KEY: NOT SET")

if stripe_publishable:
    print(f"STRIPE_PUBLISHABLE_KEY: {stripe_publishable[:20]}...{stripe_publishable[-4:]} (length: {len(stripe_publishable)})")
else:
    print("STRIPE_PUBLISHABLE_KEY: NOT SET")

print()

# Check fallback from stripe_config.py
try:
    from stripe_config import STRIPE_LIVE_SECRET_KEY, STRIPE_LIVE_PUBLISHABLE_KEY
    print("Fallback from stripe_config.py:")
    print(f"STRIPE_LIVE_SECRET_KEY: {STRIPE_LIVE_SECRET_KEY[:20]}...{STRIPE_LIVE_SECRET_KEY[-4:]} (length: {len(STRIPE_LIVE_SECRET_KEY)})")
    print(f"STRIPE_LIVE_PUBLISHABLE_KEY: {STRIPE_LIVE_PUBLISHABLE_KEY[:20]}...{STRIPE_LIVE_PUBLISHABLE_KEY[-4:]} (length: {len(STRIPE_LIVE_PUBLISHABLE_KEY)})")
except ImportError as e:
    print(f"Could not import from stripe_config.py: {e}")

print()

# Check what the config would use
from config import Config
config = Config()

print("Final Configuration Values:")
print(f"STRIPE_SECRET_KEY: {config.STRIPE_SECRET_KEY[:20]}...{config.STRIPE_SECRET_KEY[-4:]} (length: {len(config.STRIPE_SECRET_KEY)})")
print(f"STRIPE_PUBLISHABLE_KEY: {config.STRIPE_PUBLISHABLE_KEY[:20]}...{config.STRIPE_PUBLISHABLE_KEY[-4:]} (length: {len(config.STRIPE_PUBLISHABLE_KEY)})")

print()
print("=== END DEBUG ===")