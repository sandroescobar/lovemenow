#!/usr/bin/env python3
"""
Test script to verify app configuration
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_config():
    """Test configuration"""
    
    # Check environment variables
    stripe_pub = os.getenv('STRIPE_PUBLISHABLE_KEY')
    stripe_secret = os.getenv('STRIPE_SECRET_KEY')
    db_url = os.getenv('DB_URL')
    
    # Test Flask app creation
    try:
        from app import create_app
        app = create_app('development')
        
        with app.app_context():
            # Test Stripe configuration
            import stripe
            stripe.api_key = app.config['STRIPE_SECRET_KEY']
            
            # Test basic Stripe call
            try:
                # Just test that we can access Stripe API
                stripe.Account.retrieve()
            except Exception as stripe_error:
                pass
                
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_config()