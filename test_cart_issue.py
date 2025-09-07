#!/usr/bin/env python3
"""
Test script to reproduce the cart quantity issue
"""
import requests
import json

def test_cart_issue():
    """Test the cart quantity validation issue"""
    base_url = 'http://localhost:5000'
    
    # Test with a product that has limited stock
    product_id = 1  # Assuming this product exists and has limited stock
    
    print("🧪 Testing Cart Quantity Issue")
    print("=" * 50)
    
    # Step 1: Add item from product card (simulate)
    print("\n1️⃣ Adding 2 items from product card...")
    response1 = requests.post(f'{base_url}/api/cart/add',
        json={'product_id': product_id, 'quantity': 2},
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"Response 1: {response1.status_code}")
    print(f"Response 1 data: {response1.json()}")
    
    # Step 2: Try to add more from product detail page
    print("\n2️⃣ Adding 3 more items from product detail page...")
    response2 = requests.post(f'{base_url}/api/cart/add',
        json={'product_id': product_id, 'quantity': 3},
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"Response 2: {response2.status_code}")
    print(f"Response 2 data: {response2.json()}")
    
    # Check if validation worked
    if response2.status_code == 400:
        print("✅ Backend validation is working correctly!")
        print("The issue might be in the frontend not showing the error properly.")
    else:
        print("❌ Backend validation failed - this is the issue!")

if __name__ == "__main__":
    test_cart_issue()