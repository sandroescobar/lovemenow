"""
Uber Direct API Integration Service
"""
import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from flask import current_app

logger = logging.getLogger(__name__)

class UberDirectService:
    """Service class for Uber Direct API integration"""
    
    def __init__(self):
        self.base_url = "https://api.uber.com/v1"
        self.auth_url = "https://auth.uber.com/oauth/v2/token"
        self.client_id = None
        self.client_secret = None
        self.customer_id = None
        self.access_token = None
        self.token_expires_at = None
        
    def configure(self, client_id: str, client_secret: str, customer_id: str):
        """Configure the service with Uber credentials"""
        self.client_id = client_id
        self.client_secret = client_secret
        self.customer_id = customer_id
        
    def _get_access_token(self) -> str:
        """Get or refresh OAuth access token"""
        # Check if we have a valid token
        if (self.access_token and self.token_expires_at and 
            datetime.now() < self.token_expires_at - timedelta(minutes=5)):
            return self.access_token
            
        # Request new token
        try:
            response = requests.post(
                self.auth_url,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data={
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'grant_type': 'client_credentials',
                    'scope': 'eats.deliveries'
                }
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                expires_in = token_data.get('expires_in', 2592000)  # Default 30 days
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                logger.info("Successfully obtained Uber Direct access token")
                return self.access_token
            else:
                logger.error(f"Failed to get access token: {response.status_code} - {response.text}")
                raise Exception(f"Failed to authenticate with Uber: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            raise
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make authenticated request to Uber API"""
        token = self._get_access_token()
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"Uber API error: {response.status_code} - {response.text}")
                raise Exception(f"Uber API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error making request to {url}: {str(e)}")
            raise
    
    def create_quote(self, pickup_address: Dict, dropoff_address: Dict) -> Dict:
        """Create a delivery quote"""
        return self.create_quote_with_coordinates(pickup_address, dropoff_address)
    
    def create_quote_with_coordinates(self, pickup_address: Dict, dropoff_address: Dict, 
                                    pickup_coords: Dict = None, dropoff_coords: Dict = None) -> Dict:
        """Create a delivery quote with optional coordinates"""
        endpoint = f"/customers/{self.customer_id}/delivery_quotes"
        
        # Format addresses as JSON strings (Uber API requirement)
        pickup_json = json.dumps(pickup_address)
        dropoff_json = json.dumps(dropoff_address)
        
        data = {
            "pickup_address": pickup_json,
            "dropoff_address": dropoff_json
        }
        
        # Add coordinates if provided to ensure quote matches delivery request exactly
        if pickup_coords:
            data["pickup_latitude"] = pickup_coords['latitude']
            data["pickup_longitude"] = pickup_coords['longitude']
        
        if dropoff_coords:
            data["dropoff_latitude"] = dropoff_coords['latitude']
            data["dropoff_longitude"] = dropoff_coords['longitude']
        
        try:
            quote = self._make_request('POST', endpoint, data)
            logger.info(f"Created quote: {quote.get('id')} - Fee: ${quote.get('fee', 0)/100:.2f}")
            return quote
        except Exception as e:
            logger.error(f"Error creating quote: {str(e)}")
            raise
    
    def _validate_phone_number(self, phone: str) -> str:
        """Validate and format phone number for Uber API (E.164 format)"""
        import re
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # If it doesn't start with +, add +1 for US numbers
        if not cleaned.startswith('+'):
            if cleaned.startswith('1'):
                cleaned = '+' + cleaned
            else:
                cleaned = '+1' + cleaned
        
        # Ensure it's a valid US number format (+1XXXXXXXXXX)
        if not re.match(r'^\+1\d{10}$', cleaned):
            logger.warning(f"Invalid phone number format: {phone}, using default")
            return '+13055550123'  # Default Miami number
        
        return cleaned
    
    def create_delivery(self, quote_id: str, pickup_info: Dict, dropoff_info: Dict, 
                       manifest_items: list, use_robocourier: bool = False) -> Dict:
        """Create a delivery using the EXACT Uber Direct API format"""
        endpoint = f"/customers/{self.customer_id}/deliveries"
        
        # Format addresses as JSON strings exactly as Uber API expects
        pickup_address_json = json.dumps(pickup_info['address'])
        dropoff_address_json = json.dumps(dropoff_info['address'])
        
        # Validate phone numbers to E.164 format
        pickup_phone = self._validate_phone_number(pickup_info['phone'])
        dropoff_phone = self._validate_phone_number(dropoff_info['phone'])
        
        # Build the EXACT payload as per Uber Direct API documentation
        data = {
            "pickup_name": pickup_info['name'],
            "pickup_address": pickup_address_json,
            "pickup_phone_number": pickup_phone,
            "dropoff_name": dropoff_info['name'],
            "dropoff_address": dropoff_address_json,
            "dropoff_phone_number": dropoff_phone,
            "manifest_items": manifest_items
        }
        
        # Add optional fields if available
        if pickup_info.get('latitude'):
            data["pickup_latitude"] = pickup_info['latitude']
        if pickup_info.get('longitude'):
            data["pickup_longitude"] = pickup_info['longitude']
        if dropoff_info.get('latitude'):
            data["dropoff_latitude"] = dropoff_info['latitude']
        if dropoff_info.get('longitude'):
            data["dropoff_longitude"] = dropoff_info['longitude']
        
        # Add quote_id if provided
        if quote_id:
            data["quote_id"] = quote_id
        
        # Add Robocourier for testing - this enables REAL Uber tracking with test automation
        if use_robocourier:
            # This is the correct way to enable Robocourier according to Uber documentation
            data["test_specifications"] = {
                "robo_courier_specification": {
                    "mode": "auto"
                }
            }
            logger.info("Enabled Robocourier for automated testing with REAL Uber tracking")
        
        try:
            # Make the API call to create REAL Uber delivery
            delivery = self._make_request('POST', endpoint, data)
            
            logger.info(f"Created Uber delivery: {delivery.get('id')}")
            logger.info(f"Tracking URL: {delivery.get('tracking_url')}")
            logger.info(f"Status: {delivery.get('status')}")
            
            return delivery
            
        except Exception as e:
            logger.error(f"Error creating delivery: {str(e)}")
            raise
    
    def get_delivery_status(self, delivery_id: str) -> Dict:
        """Get delivery status"""
        endpoint = f"/customers/{self.customer_id}/deliveries/{delivery_id}"
        
        try:
            delivery = self._make_request('GET', endpoint)
            return delivery
        except Exception as e:
            logger.error(f"Error getting delivery status: {str(e)}")
            raise
    
    def cancel_delivery(self, delivery_id: str) -> Dict:
        """Cancel a delivery"""
        endpoint = f"/customers/{self.customer_id}/deliveries/{delivery_id}/cancel"
        
        try:
            result = self._make_request('POST', endpoint)
            logger.info(f"Cancelled delivery: {delivery_id}")
            return result
        except Exception as e:
            logger.error(f"Error cancelling delivery: {str(e)}")
            raise

# Global service instance
uber_service = UberDirectService()

def init_uber_service(app):
    """Initialize Uber service with app configuration"""
    client_id = app.config.get('UBER_CLIENT_ID')
    client_secret = app.config.get('UBER_CLIENT_SECRET')
    customer_id = app.config.get('UBER_CUSTOMER_ID')
    
    if client_id and client_secret and customer_id:
        uber_service.configure(client_id, client_secret, customer_id)
        logger.info(f"Uber Direct service configured successfully - Customer ID: {customer_id}")
        
        # Test the connection by trying to get an access token
        try:
            token = uber_service._get_access_token()
            logger.info("Uber Direct API connection test successful")
        except Exception as e:
            logger.error(f"Uber Direct API connection test failed: {str(e)}")
    else:
        logger.warning("Uber Direct service not configured - missing credentials")
        logger.warning(f"UBER_CLIENT_ID: {'✓' if client_id else '✗'}")
        logger.warning(f"UBER_CLIENT_SECRET: {'✓' if client_secret else '✗'}")
        logger.warning(f"UBER_CUSTOMER_ID: {'✓' if customer_id else '✗'}")

def get_miami_store_address():
    """Get the store pickup address in Miami"""
    # You'll need to replace this with your actual store address
    return {
        "street_address": ["1234 Biscayne Blvd", "Suite 100"],
        "city": "Miami",
        "state": "FL", 
        "zip_code": "33132",
        "country": "US"
    }

def get_miami_store_coordinates():
    """Get store coordinates for Miami location"""
    # You'll need to replace with your actual store coordinates
    return {
        "latitude": 25.7617,
        "longitude": -80.1918
    }

def format_address_for_uber(address_dict: Dict) -> Dict:
    """Format address dictionary for Uber API"""
    return {
        "street_address": [address_dict.get('address', ''), address_dict.get('suite', '')],
        "city": address_dict.get('city', ''),
        "state": address_dict.get('state', ''),
        "zip_code": address_dict.get('zip', ''),
        "country": address_dict.get('country', 'US')
    }

def create_manifest_items(cart_items: list) -> list:
    """Create manifest items for Uber delivery from cart items"""
    manifest_items = []
    
    for item in cart_items:
        product = item['product']
        quantity = item['quantity']
        
        # Create a discreet manifest item
        manifest_items.append({
            "name": f"Package #{product['id']}",  # Discreet naming
            "quantity": quantity,
            "weight": 100,  # Default weight in grams
            "dimensions": {
                "length": 15,  # Default dimensions in cm
                "height": 10,
                "depth": 5
            }
        })
    
    return manifest_items