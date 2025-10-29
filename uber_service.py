"""
Uber Direct API Integration Service
"""
import requests
import json
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from flask import current_app

logger = logging.getLogger(__name__)

class UberDirectService:
    """Service class for Uber Direct API integration"""
    
    def __init__(self):
        self.base_url = "https://api.uber.com/v1"  # Default to production
        self.auth_url = "https://auth.uber.com/oauth/v2/token"
        self.client_id = None
        self.client_secret = None
        self.customer_id = None
        self.access_token = None
        self.token_expires_at = None
        self.is_sandbox = False
        
    def configure(self, client_id: str, client_secret: str, customer_id: str, is_sandbox: bool = False):
        """Configure the service with Uber credentials"""
        self.client_id = client_id
        self.client_secret = client_secret
        self.customer_id = customer_id
        self.is_sandbox = is_sandbox
        
        # Set the correct API endpoint based on sandbox/production mode
        if is_sandbox:
            self.base_url = "https://sandbox-api.uber.com/v1"
            logger.info("🔧 Uber service configured for SANDBOX mode")
        else:
            self.base_url = "https://api.uber.com/v1"
            logger.info("🔧 Uber service configured for PRODUCTION mode")
        
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
            # Handle both dict and tuple formats
            if isinstance(pickup_coords, (tuple, list)):
                data["pickup_latitude"] = pickup_coords[0]
                data["pickup_longitude"] = pickup_coords[1]
            else:
                data["pickup_latitude"] = pickup_coords['latitude']
                data["pickup_longitude"] = pickup_coords['longitude']
        
        if dropoff_coords:
            # Handle both dict and tuple formats
            if isinstance(dropoff_coords, (tuple, list)):
                data["dropoff_latitude"] = dropoff_coords[0]
                data["dropoff_longitude"] = dropoff_coords[1]
            else:
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
    is_sandbox = app.config.get('UBER_SANDBOX', False)
    
    if client_id and client_secret and customer_id:
        uber_service.configure(client_id, client_secret, customer_id, is_sandbox=is_sandbox)
        logger.info(f"Uber Direct service configured successfully - Customer ID: {customer_id}")
        logger.info(f"Mode: {'SANDBOX' if is_sandbox else 'PRODUCTION'}")
        
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
    return {
        "street_address": ["351 NE 79th St", "Unit 101"],
        "city": "Miami",
        "state": "FL", 
        "zip_code": "33138",
        "country": "US"
    }

def get_miami_store_coordinates():
    """Get store coordinates for Miami location"""
    # Coordinates for 351 NE 79th St Unit 101, Miami, FL 33138
    return {
        "latitude": 25.8465,
        "longitude": -80.1917
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
        # Handle both ORM objects and dicts
        if hasattr(item, 'product'):
            # ORM object (Cart model)
            product = item.product
            quantity = item.quantity
        else:
            # Dictionary format
            product = item['product']
            quantity = item['quantity']
        
        # Get product ID (handle both ORM objects and dicts)
        if hasattr(product, 'id'):
            product_id = product.id
        else:
            product_id = product['id']
        
        # Create a discreet manifest item
        manifest_items.append({
            "name": f"Package #{product_id}",  # Discreet naming
            "quantity": quantity,
            "weight": 100,  # Default weight in grams
            "dimensions": {
                "length": 15,  # Default dimensions in cm
                "height": 10,
                "depth": 5
            }
        })
    
    return manifest_items

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) using Haversine formula
    Returns distance in miles
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in miles
    r = 3956
    
    return c * r

def get_driving_distance(origin_address: str, destination_address: str) -> Optional[float]:
    """
    Get actual driving distance using Google Maps Distance Matrix API
    Returns distance in miles or None if API call fails
    """
    try:
        from flask import current_app
        import requests
        import urllib.parse
        
        api_key = current_app.config.get('GOOGLE_MAPS_API_KEY')
        if not api_key:
            logger.warning("Google Maps API key not configured, falling back to straight-line distance")
            return None
        
        # Format addresses for Google Maps API
        origin = urllib.parse.quote(origin_address)
        destination = urllib.parse.quote(destination_address)
        
        # Google Maps Distance Matrix API endpoint
        url = f"https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            'origins': origin_address,
            'destinations': destination_address,
            'units': 'imperial',  # Get distance in miles
            'mode': 'driving',
            'key': api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data['status'] == 'OK' and data['rows']:
                element = data['rows'][0]['elements'][0]
                
                if element['status'] == 'OK':
                    # Distance is returned in meters, convert to miles
                    distance_meters = element['distance']['value']
                    distance_miles = distance_meters * 0.000621371  # Convert meters to miles
                    
                    logger.info(f"Google Maps driving distance: {distance_miles:.2f} miles from '{origin_address}' to '{destination_address}'")
                    return distance_miles
                else:
                    logger.warning(f"Google Maps API element error: {element['status']}")
                    return None
            else:
                logger.warning(f"Google Maps API error: {data.get('status', 'Unknown error')}")
                return None
        else:
            logger.error(f"Google Maps API HTTP error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting driving distance: {str(e)}")
        return None

def get_custom_delivery_price(distance_miles: float, is_peak_hours: bool = False) -> float:
    """
    Calculate custom delivery price for addresses outside 10-mile radius
    Returns price in dollars
    """
    base_price = 12.99  # Base price for deliveries outside 10 miles
    
    # Distance-based pricing (additional cost per mile beyond 10 miles)
    if distance_miles > 10:
        extra_miles = distance_miles - 10
        
        # Tiered pricing for longer distances
        if extra_miles <= 20:  # 10-30 miles
            distance_fee = extra_miles * 1.50  # $1.50 per extra mile
        else:  # 30-50 miles
            distance_fee = (20 * 1.50) + ((extra_miles - 20) * 2.00)  # $2.00 per mile for 30+ miles
        
        base_price += distance_fee
    
    # Peak hours surcharge (3:30 PM - 6:00 PM)
    if is_peak_hours:
        peak_surcharge = base_price * 0.25  # 25% surcharge during peak hours
        base_price += peak_surcharge
    
    # Cap the maximum delivery fee at $55 for extended range
    return min(base_price, 55.00)

def is_peak_hours() -> bool:
    """Check if current time is during peak hours (3:30 PM - 6:00 PM Miami time)"""
    try:
        import pytz
        miami_tz = pytz.timezone('America/New_York')  # Miami is in Eastern Time
        current_time = datetime.now(miami_tz)
        
        # Peak hours: 3:30 PM (15:30) to 6:00 PM (18:00)
        peak_start = current_time.replace(hour=15, minute=30, second=0, microsecond=0)
        peak_end = current_time.replace(hour=18, minute=0, second=0, microsecond=0)
        
        return peak_start <= current_time <= peak_end
    except ImportError:
        # Fallback if pytz is not available - assume not peak hours
        logger.warning("pytz not available, cannot determine peak hours")
        return False

def geocode_address(address_dict: Dict) -> Optional[Tuple[float, float]]:
    """
    Geocode an address to get latitude and longitude using a free geocoding service
    Returns (latitude, longitude) tuple or None if geocoding fails
    """
    try:
        # Format address for geocoding
        address_parts = []
        if address_dict.get('address'):
            address_parts.append(address_dict['address'])
        if address_dict.get('suite'):
            address_parts.append(address_dict['suite'])
        if address_dict.get('city'):
            address_parts.append(address_dict['city'])
        if address_dict.get('state'):
            address_parts.append(address_dict['state'])
        if address_dict.get('zip'):
            address_parts.append(address_dict['zip'])
        
        full_address = ', '.join(address_parts)
        logger.info(f"Geocoding address: {full_address}")
        
        # Use Nominatim (OpenStreetMap) free geocoding service
        import requests
        import urllib.parse
        
        encoded_address = urllib.parse.quote(full_address)
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded_address}&limit=1"
        
        headers = {
            'User-Agent': 'LoveMeNow-Delivery-Service/1.0'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                logger.info(f"Geocoded {full_address} to ({lat}, {lon})")
                return (lat, lon)
            else:
                logger.warning(f"No geocoding results for: {full_address}")
                return None
        else:
            logger.error(f"Geocoding API error: {response.status_code}")
            return None
        
    except Exception as e:
        logger.error(f"Error geocoding address: {str(e)}")
        return None