#!/usr/bin/env python3
"""
Test script to verify Stripe integration
"""
import os
import stripe
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_stripe_setup():
    """Test basic Stripe setup"""
    
    # Set API key
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    
    try:
        # Test basic Stripe functionality
        
        # Create a simple checkout session
        session = stripe.checkout.Session.create(
            ui_mode='embedded',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Test Product',
                    },
                    'unit_amount': 2000,  # $20.00
                },
                'quantity': 1,
            }],
            mode='payment',
            return_url='http://127.0.0.1:2400/checkout-success?session_id={CHECKOUT_SESSION_ID}',
        )
        
        # Check for client_secret
        if hasattr(session, 'client_secret'):
            pass
        
        # Try to access as dict
        try:
            session_dict = dict(session)
            if 'client_secret' in session_dict:
                pass
        except Exception as e:
            pass
            
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_stripe_setup()