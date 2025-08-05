#!/usr/bin/env python3
"""
Debug script to test the checkout session creation directly
"""
import os
import sys
import stripe
from dotenv import load_dotenv

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import Product, Cart
from flask import current_app

# Load environment variables
load_dotenv()

def test_checkout_session_creation():
    """Test creating a checkout session directly"""
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        try:
            # Get Stripe API key from config
            stripe_secret_key = current_app.config.get('STRIPE_SECRET_KEY')
            
            if not stripe_secret_key:
                return False
            
            # Set Stripe API key
            stripe.api_key = stripe_secret_key
            
            # Create test line items (similar to what the route does)
            line_items = [{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Test Product',
                        'description': 'Test product for checkout debugging',
                    },
                    'unit_amount': 2999,  # $29.99 in cents
                },
                'quantity': 1,
            }]
            
            # Create the session exactly like the route does
            stripe_checkout_session = stripe.checkout.Session.create(
                ui_mode='embedded',
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                return_url='http://127.0.0.1:2400/checkout-success?session_id={CHECKOUT_SESSION_ID}',
                shipping_address_collection={'allowed_countries': ['US']},
                billing_address_collection='required',
                metadata={'test': 'true'},
            )
            
            # Test accessing client_secret (this is where the error occurs)
            
            # Check if session is None
            if stripe_checkout_session is None:
                return False
            
            # Try to access session ID first
            try:
                session_id = stripe_checkout_session.id
            except AttributeError as e:
                return False
            
            # Now try to access client_secret
            try:
                client_secret = stripe_checkout_session.client_secret
                return True
            except AttributeError as e:
                return False
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = test_checkout_session_creation()