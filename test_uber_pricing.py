#!/usr/bin/env python3
"""
Test script to verify Uber Direct dynamic pricing is working
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from uber_service import uber_service, get_miami_store_address, get_miami_store_coordinates, format_address_for_uber
from flask import Flask
from dotenv import load_dotenv

def test_uber_quotes():
    """Test Uber quotes for different distances"""
    
    # Load environment variables
    load_dotenv()
    
    # Create Flask app for context
    app = Flask(__name__)
    app.config['UBER_CLIENT_ID'] = os.getenv('UBER_CLIENT_ID')
    app.config['UBER_CLIENT_SECRET'] = os.getenv('UBER_CLIENT_SECRET')
    app.config['UBER_CUSTOMER_ID'] = os.getenv('UBER_CUSTOMER_ID')
    
    with app.app_context():
        # Configure Uber service
        uber_service.configure(
            app.config['UBER_CLIENT_ID'],
            app.config['UBER_CLIENT_SECRET'],
            app.config['UBER_CUSTOMER_ID']
        )
        
        # Test addresses at different distances
        test_addresses = [
            {
                'name': 'Close address (Downtown Miami)',
                'address': {
                    'address': '100 SE 2nd Street',
                    'city': 'Miami',
                    'state': 'FL',
                    'zip': '33131',
                    'country': 'US'
                }
            },
            {
                'name': 'Medium distance (Miami Beach)',
                'address': {
                    'address': '1500 Ocean Drive',
                    'city': 'Miami Beach',
                    'state': 'FL',
                    'zip': '33139',
                    'country': 'US'
                }
            },
            {
                'name': 'Far distance (Aventura)',
                'address': {
                    'address': '19999 Biscayne Blvd',
                    'city': 'Aventura',
                    'state': 'FL',
                    'zip': '33180',
                    'country': 'US'
                }
            }
        ]
        
        pickup_address = get_miami_store_address()
        store_coords = get_miami_store_coordinates()
        
        print("🚚 Testing Uber Direct Dynamic Pricing")
        print("=" * 50)
        print(f"Store Location: {pickup_address['street_address'][0]}, {pickup_address['city']}")
        print()
        
        for test in test_addresses:
            try:
                print(f"📍 Testing: {test['name']}")
                print(f"   Address: {test['address']['address']}, {test['address']['city']}")
                
                # Format address for Uber
                delivery_address = format_address_for_uber(test['address'])
                
                # Get quote
                quote = uber_service.create_quote_with_coordinates(
                    pickup_address,
                    delivery_address,
                    pickup_coords=store_coords,
                    dropoff_coords=None
                )
                
                fee_dollars = quote['fee'] / 100
                duration_minutes = quote.get('duration', 0)
                
                print(f"   💰 Fee: ${fee_dollars:.2f}")
                print(f"   ⏱️  Duration: {duration_minutes} minutes")
                print(f"   🆔 Quote ID: {quote['id']}")
                print()
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                print()
        
        print("✅ Test completed!")
        print("\nNow your checkout should use these dynamic prices instead of the fixed $7.99")

if __name__ == "__main__":
    test_uber_quotes()