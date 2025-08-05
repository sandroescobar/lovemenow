#!/usr/bin/env python3
"""
Debug script to test Stripe integration
"""
import os
import stripe
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_stripe_integration():
    """Test Stripe integration"""
    
    # Get API key
    stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
    
    if not stripe_secret_key:
        return False
    
    # Set API key
    stripe.api_key = stripe_secret_key
    
    try:
        # Test creating a simple checkout session
        
        session = stripe.checkout.Session.create(
            ui_mode='embedded',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Test Product',
                        'description': 'Test product for debugging',
                    },
                    'unit_amount': 2999,  # $29.99 in cents
                },
                'quantity': 1,
            }],
            mode='payment',
            return_url='http://127.0.0.1:2400/checkout-success?session_id={CHECKOUT_SESSION_ID}',
        )
        
        # Test accessing client_secret
        
        # Method 1: Direct access
        try:
            client_secret = session.client_secret
        except AttributeError as e:
            pass
        
        # Method 2: Dictionary access
        try:
            client_secret = session['client_secret']
        except (KeyError, TypeError) as e:
            pass
        
        # Method 3: getattr
        try:
            client_secret = getattr(session, 'client_secret', None)
        except Exception as e:
            pass
        
        # Method 4: Check session data
        try:
            session_dict = dict(session)
            client_secret = session_dict.get('client_secret')
        except Exception as e:
            pass
        
        # Print session data for debugging
        try:
            session_data = dict(session)
            for key, value in session_data.items():
                if key == 'client_secret':
                    pass
                else:
                    pass
        except Exception as e:
            pass
        
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_stripe_integration()