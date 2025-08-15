#!/usr/bin/env python3
"""
Deployment verification script for LoveMeNow on Render
Run this after deployment to verify everything is working correctly
"""

import os
import sys
import requests
import json
from urllib.parse import urljoin

def verify_deployment(base_url):
    """Verify the deployment is working correctly"""
    
    print(f"🚀 Verifying deployment at: {base_url}")
    print("=" * 50)
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Health Check
    tests_total += 1
    print("1. Testing health check endpoint...")
    try:
        response = requests.get(urljoin(base_url, '/api/health'), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'healthy':
                print("   ✅ Health check passed")
                tests_passed += 1
            else:
                print(f"   ❌ Health check failed: {data}")
        else:
            print(f"   ❌ Health check returned {response.status_code}")
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
    
    # Test 2: Main page loads
    tests_total += 1
    print("2. Testing main page...")
    try:
        response = requests.get(base_url, timeout=10)
        if response.status_code == 200:
            print("   ✅ Main page loads successfully")
            tests_passed += 1
        else:
            print(f"   ❌ Main page returned {response.status_code}")
    except Exception as e:
        print(f"   ❌ Main page error: {e}")
    
    # Test 3: HTTPS redirect (if not already HTTPS)
    tests_total += 1
    print("3. Testing HTTPS redirect...")
    if base_url.startswith('http://'):
        try:
            http_url = base_url
            response = requests.get(http_url, allow_redirects=False, timeout=10)
            if response.status_code in [301, 302, 308]:
                location = response.headers.get('Location', '')
                if location.startswith('https://'):
                    print("   ✅ HTTPS redirect working")
                    tests_passed += 1
                else:
                    print(f"   ❌ Redirect to non-HTTPS: {location}")
            else:
                print(f"   ❌ No HTTPS redirect (status: {response.status_code})")
        except Exception as e:
            print(f"   ❌ HTTPS redirect test error: {e}")
    else:
        print("   ✅ Already using HTTPS")
        tests_passed += 1
    
    # Test 4: Security headers
    tests_total += 1
    print("4. Testing security headers...")
    try:
        response = requests.get(base_url, timeout=10)
        headers = response.headers
        
        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'Content-Security-Policy'
        ]
        
        missing_headers = []
        for header in security_headers:
            if header not in headers:
                missing_headers.append(header)
        
        if not missing_headers:
            print("   ✅ Security headers present")
            tests_passed += 1
        else:
            print(f"   ⚠️  Missing security headers: {missing_headers}")
            tests_passed += 0.5  # Partial credit
            
    except Exception as e:
        print(f"   ❌ Security headers test error: {e}")
    
    # Test 5: Checkout page accessibility
    tests_total += 1
    print("5. Testing checkout page...")
    try:
        response = requests.get(urljoin(base_url, '/checkout'), timeout=10)
        if response.status_code == 200:
            print("   ✅ Checkout page accessible")
            tests_passed += 1
        else:
            print(f"   ❌ Checkout page returned {response.status_code}")
    except Exception as e:
        print(f"   ❌ Checkout page error: {e}")
    
    # Results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{tests_total} passed")
    
    if tests_passed == tests_total:
        print("🎉 All tests passed! Deployment looks good.")
        return True
    elif tests_passed >= tests_total * 0.8:
        print("⚠️  Most tests passed. Check warnings above.")
        return True
    else:
        print("❌ Multiple tests failed. Check deployment.")
        return False

def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python verify_deployment.py <base_url>")
        print("Example: python verify_deployment.py https://lovemenow.onrender.com")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    success = verify_deployment(base_url)
    
    if success:
        print("\n🚀 Deployment verification completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Deployment verification failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()