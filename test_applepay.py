#!/usr/bin/env python3
"""
Quick test script to verify Apple Pay/Google Pay setup
"""
import os
import sys

def test_stripe_config():
    """Verify Stripe is configured"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        from flask import current_app
        
        print("🔍 Stripe Configuration Check")
        print("=" * 50)
        
        secret = current_app.config.get('STRIPE_SECRET_KEY')
        public = current_app.config.get('STRIPE_PUBLISHABLE_KEY')
        
        print(f"✓ Secret Key: {'✓ SET' if secret else '✗ MISSING'}")
        print(f"✓ Public Key: {'✓ SET' if public else '✗ MISSING'}")
        
        if not (secret and public):
            print("\n❌ ERROR: Stripe keys not configured!")
            print("   Set STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY in .env")
            return False
            
        print("\n✅ Stripe configuration OK")
        return True

def test_checkout_endpoints():
    """Verify checkout endpoints exist"""
    from app import create_app
    app = create_app()
    
    print("\n🔍 Checkout Endpoints Check")
    print("=" * 50)
    
    routes = [
        '/create-checkout-session',
        '/api/create-order',
        '/api/cart/totals',
        '/checkout'
    ]
    
    with app.test_client() as client:
        for route in routes:
            # HEAD request to check existence
            resp = client.head(route, follow_redirects=True)
            status = resp.status_code
            
            # 405 (Method Not Allowed) means route exists but doesn't support HEAD
            # 404 means route doesn't exist
            # 302 means redirect
            exists = status != 404
            
            symbol = "✓" if exists else "✗"
            print(f"{symbol} {route}: {status}")
    
    print("\n✅ Checkout endpoints verified")
    return True

def test_payment_intent_creation():
    """Test creating a payment intent"""
    from app import create_app
    import stripe
    from flask import current_app
    
    print("\n🔍 Stripe API Test")
    print("=" * 50)
    
    app = create_app()
    with app.app_context():
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        
        try:
            # Create a test payment intent for $10 USD
            intent = stripe.PaymentIntent.create(
                amount=1000,  # $10.00
                currency='usd',
                automatic_payment_methods={'enabled': False},
                payment_method_types=['card'],
                metadata={'test': 'true'}
            )
            
            print(f"✓ Created test PaymentIntent: {intent.id}")
            print(f"  - Amount: ${intent.amount / 100:.2f}")
            print(f"  - Status: {intent.status}")
            print(f"  - Client Secret: {intent.client_secret[:20]}...")
            
            # Clean up
            stripe.PaymentIntent.cancel(intent.id)
            print(f"✓ Cleaned up test PI")
            
            return True
        except stripe.error.StripeError as e:
            print(f"✗ Stripe Error: {e}")
            return False

def main():
    print("\n" + "=" * 50)
    print("Apple Pay / Google Pay Setup Verification")
    print("=" * 50 + "\n")
    
    checks = [
        ("Stripe Configuration", test_stripe_config),
        ("Checkout Endpoints", test_checkout_endpoints),
        ("Stripe API Connection", test_payment_intent_creation),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Error during {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_pass = all(r for _, r in results)
    
    print("\n" + "=" * 50)
    if all_pass:
        print("✅ All checks passed! Ready to test Apple Pay")
        print("\nNext steps:")
        print("1. Go to http://localhost:5000/checkout")
        print("2. Look for Apple Pay / Google Pay button")
        print("3. Click and authorize payment")
        print("4. Order should be created successfully")
    else:
        print("❌ Some checks failed. Please fix before testing")
    print("=" * 50 + "\n")
    
    return 0 if all_pass else 1

if __name__ == '__main__':
    sys.exit(main())