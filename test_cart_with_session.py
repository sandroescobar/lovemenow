#!/usr/bin/env python3
"""
Test cart validation with proper session handling
"""
import requests
import json

def test_cart_with_session():
    """Test cart validation using session cookies"""
    base_url = 'http://127.0.0.1:2100'
    
    print('🧪 TESTING CART WITH SESSION COOKIES')
    print('=' * 60)
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    # First, visit the homepage to establish a session
    print('🌐 Establishing session by visiting homepage...')
    try:
        response = session.get(f'{base_url}/')
        print(f'   Homepage status: {response.status_code}')
        
        # Extract CSRF token from the page if needed
        if 'csrf_token' in response.text:
            print('   ✅ Session established with CSRF token')
        else:
            print('   ⚠️  No CSRF token found, but session should be established')
            
    except Exception as e:
        print(f'   ❌ Failed to establish session: {e}')
        return False
    
    # Clear cart first
    print('\n🧹 Clearing cart...')
    try:
        response = session.post(f'{base_url}/api/cart/clear', 
                               headers={'Content-Type': 'application/json'})
        print(f'   Clear cart status: {response.status_code}')
        if response.status_code == 200:
            print('   ✅ Cart cleared successfully')
        else:
            print(f'   ⚠️  Clear cart response: {response.text[:100]}...')
    except Exception as e:
        print(f'   ❌ Failed to clear cart: {e}')
    
    # Test 1: Add 1 item to product with limited stock
    print('\n🧪 TEST 1: Adding 1 item to product 71 (should succeed)')
    try:
        response = session.post(f'{base_url}/api/cart/add', 
                               json={'product_id': 71, 'quantity': 1},
                               headers={'Content-Type': 'application/json'})
        
        print(f'   Status: {response.status_code}')
        if response.status_code == 200:
            data = response.json()
            print(f'   ✅ SUCCESS: {data.get("message")}')
            print(f'   Cart count: {data.get("count")}')
            print(f'   Current in cart: {data.get("current_in_cart")}')
            print(f'   Stock available: {data.get("stock_available")}')
        else:
            print(f'   ❌ FAILED: {response.text[:200]}...')
            return False
    except Exception as e:
        print(f'   ❌ ERROR: {e}')
        return False
    
    # Test 2: Try to add another item (should fail)
    print('\n🧪 TEST 2: Adding another item to same product (should fail)')
    try:
        response = session.post(f'{base_url}/api/cart/add', 
                               json={'product_id': 71, 'quantity': 1},
                               headers={'Content-Type': 'application/json'})
        
        print(f'   Status: {response.status_code}')
        if response.status_code == 400:
            data = response.json()
            print(f'   ✅ SUCCESS: Properly rejected!')
            print(f'   Error: {data.get("error")}')
            print(f'   Max additional: {data.get("max_additional")}')
            print(f'   Current in cart: {data.get("current_in_cart")}')
            print(f'   Stock available: {data.get("stock_available")}')
            return True
        elif response.status_code == 200:
            data = response.json()
            print(f'   ❌ STILL BROKEN: Should have failed but succeeded')
            print(f'   Message: {data.get("message")}')
            return False
        else:
            print(f'   ❌ UNEXPECTED: {response.text[:200]}...')
            return False
    except Exception as e:
        print(f'   ❌ ERROR: {e}')
        return False

if __name__ == "__main__":
    success = test_cart_with_session()
    
    print('\n' + '=' * 60)
    if success:
        print('🎉 CART VALIDATION IS WORKING!')
        print('✅ The backend now properly validates stock limits')
        print('✅ Frontend should now show proper error messages')
    else:
        print('❌ CART VALIDATION STILL BROKEN')
        print('🔧 Check Flask app logs for errors')
        print('🔧 Make sure Flask app is running on port 2100')