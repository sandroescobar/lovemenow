#!/usr/bin/env python3
"""
Test Stripe API connection
"""
import os
import stripe
from dotenv import load_dotenv
from config import Config

# Load environment variables
load_dotenv()

print("=== STRIPE CONNECTION TEST ===")

# Get configuration
config = Config()
stripe_secret_key = config.STRIPE_SECRET_KEY

print(f"Using Stripe secret key: {stripe_secret_key[:10]}...{stripe_secret_key[-4:]}")

# Set the API key
stripe.api_key = stripe_secret_key

try:
    # Test the connection by retrieving account information
    print("Testing Stripe API connection...")
    account = stripe.Account.retrieve()
    print(f"✅ SUCCESS: Connected to Stripe account: {account.id}")
    print(f"Account email: {account.email}")
    print(f"Account country: {account.country}")
    print(f"Charges enabled: {account.charges_enabled}")
    print(f"Payouts enabled: {account.payouts_enabled}")
    
except stripe.error.AuthenticationError as e:
    print(f"❌ AUTHENTICATION ERROR: {e}")
    print("This means the API key is invalid or not properly configured")
    
except stripe.error.StripeError as e:
    print(f"❌ STRIPE ERROR: {e}")
    
except Exception as e:
    print(f"❌ UNEXPECTED ERROR: {e}")

print("=== END TEST ===")