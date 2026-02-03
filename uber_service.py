"""
Uber Direct API Integration Service
"""
import requests
import json
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from flask import current_app, has_app_context

logger = logging.getLogger(__name__)

_DEFAULT_STORE_SETTINGS = {
    'address': '351 NE 79th St',
    'suite': 'Unit 101',
    'city': 'Miami',
    'state': 'FL',
    'zip': '33138',
    'latitude': 25.8466,
    'longitude': -80.1891,
}


def _store_config_value(key: str, default_key: str = None):
    if has_app_context():
        config = current_app.config
        if key in config:
            return config.get(key)
    if default_key and default_key in _DEFAULT_STORE_SETTINGS:
        return _DEFAULT_STORE_SETTINGS[default_key]
    return _DEFAULT_STORE_SETTINGS.get(key, None)


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
                       manifest_items: list, use_robocourier: bool = False, dropoff_notes: str = None) -> Dict:
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
        
        # Add special delivery notes for driver instructions
        if dropoff_notes:
            data["dropoff_notes"] = dropoff_notes
        
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
    street = _store_config_value('STORE_ADDRESS', 'address') or _DEFAULT_STORE_SETTINGS['address']
    suite = _store_config_value('STORE_SUITE', 'suite') or _DEFAULT_STORE_SETTINGS['suite']
    city = _store_config_value('STORE_CITY', 'city') or _DEFAULT_STORE_SETTINGS['city']
    state = _store_config_value('STORE_STATE', 'state') or _DEFAULT_STORE_SETTINGS['state']
    zipcode = _store_config_value('STORE_ZIP', 'zip') or _DEFAULT_STORE_SETTINGS['zip']
    return {
        "street_address": [street, suite],
        "city": city,
        "state": state,
        "zip_code": zipcode,
        "country": "US"
    }

def get_miami_store_coordinates():
    """Get store coordinates for Miami location"""
    return {
        "latitude": float(_store_config_value('STORE_LATITUDE', 'latitude') or _DEFAULT_STORE_SETTINGS['latitude']),
        "longitude": float(_store_config_value('STORE_LONGITUDE', 'longitude') or _DEFAULT_STORE_SETTINGS['longitude'])
    }

def is_store_open() -> Tuple[bool, str]:
    """
    Check if store is currently open based on Miami timezone hours.
    Store hours:
    - Monday-Thursday: 10 AM - 10 PM
    - Friday-Saturday: 10 AM - 12 AM (midnight)
    - Sunday: 11 AM - 8 PM
    
    Returns: (is_open: bool, message: str)
    """
    from datetime import datetime
    import pytz
    
    # Get current time in Miami timezone
    miami_tz = pytz.timezone('America/New_York')
    now = datetime.now(miami_tz)
    current_day = now.weekday()  # 0=Monday, 6=Sunday
    current_hour = now.hour
    current_minute = now.minute
    current_time_minutes = current_hour * 60 + current_minute
    
    # Define store hours (in minutes from midnight)
    store_hours = {
        0: (10 * 60, 22 * 60),      # Monday: 10 AM - 10 PM
        1: (10 * 60, 22 * 60),      # Tuesday: 10 AM - 10 PM
        2: (10 * 60, 22 * 60),      # Wednesday: 10 AM - 10 PM
        3: (10 * 60, 22 * 60),      # Thursday: 10 AM - 10 PM
        4: (10 * 60, 24 * 60),      # Friday: 10 AM - 12 AM (midnight)
        5: (10 * 60, 24 * 60),      # Saturday: 10 AM - 12 AM (midnight)
        6: (11 * 60, 20 * 60),      # Sunday: 11 AM - 8 PM
    }
    
    if current_day not in store_hours:
        return False, "Store is closed"
    
    open_time, close_time = store_hours[current_day]
    
    if current_time_minutes < open_time or current_time_minutes >= close_time:
        day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][current_day]
        open_hour = open_time // 60
        open_minute = open_time % 60
        close_hour = (close_time // 60) % 24
        close_minute = close_time % 60
        return False, f"Store is closed. {day_name} hours: {open_hour}:{open_minute:02d} AM - {close_hour}:{close_minute:02d} PM"
    
    return True, "Store is open"

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

def get_hybrid_delivery_quote(pickup_address: Dict, dropoff_address: Dict, 
                              pickup_coords: Dict, dropoff_coords: Dict,
                              straight_line_distance: float) -> Dict:
    """
    Get a delivery quote using either Uber Direct or Google Maps (Manual Dispatch)
    Based on distance and Uber API availability.
    """
    from flask import current_app
    
    # 1. Under 10 miles: Try Uber Direct first
    if straight_line_distance <= 10:
        try:
            logger.info(f"Straight-line distance {straight_line_distance:.2f} <= 10mi, trying Uber Direct...")
            uber_service = UberDirectService()
            uber_service.configure(
                client_id=current_app.config.get('UBER_CLIENT_ID'),
                client_secret=current_app.config.get('UBER_CLIENT_SECRET'),
                customer_id=current_app.config.get('UBER_CUSTOMER_ID'),
                is_sandbox=current_app.config.get('UBER_SANDBOX', True)
            )
            
            uber_quote = uber_service.create_quote_with_coordinates(
                pickup_address, dropoff_address,
                pickup_coords=pickup_coords,
                dropoff_coords=dropoff_coords
            )
            
            # If we got a valid Uber quote, return it
            return {
                'id': uber_quote['id'],
                'fee': uber_quote['fee'],
                'fee_dollars': uber_quote['fee'] / 100,
                'currency': uber_quote['currency'],
                'pickup_duration': uber_quote.get('pickup_duration', 0),
                'dropoff_eta': uber_quote.get('dropoff_eta'),
                'duration': uber_quote.get('duration', 0),
                'expires': uber_quote.get('expires'),
                'source': 'uber_direct'
            }
        except Exception as e:
            logger.warning(f"Uber Direct quote failed for <10mi distance: {str(e)}. Falling back to Google Maps.")
            # Fall through to Google Maps calculation if Uber fails even for < 10mi

    # 2. Over 10 miles or Uber failed: Use Google Maps Distance Matrix
    logger.info(f"Using Google Maps for distance/duration calculation (Distance: {straight_line_distance:.2f}mi)")
    
    # Format addresses for Google Maps
    origin_street = ' '.join(filter(None, pickup_address.get('street_address', [])))
    origin_str = f"{origin_street}, {pickup_address.get('city', '')}, {pickup_address.get('state', '')} {pickup_address.get('zip_code', '')}"
    
    dest_street = ' '.join(filter(None, dropoff_address.get('street_address', [])))
    dest_str = f"{dest_street}, {dropoff_address.get('city', '')}, {dropoff_address.get('state', '')} {dropoff_address.get('zip_code', '')}"
    
    matrix = get_driving_distance_matrix(origin_str, dest_str)
    
    if not matrix:
        logger.warning("Failed to get driving distance from Google Maps, falling back to straight-line distance")
        # Use straight-line distance with a 1.25x buffer for driving distance estimation
        driving_distance = straight_line_distance * 1.25
        # Estimate duration: ~2.5 minutes per mile (includes traffic/signals)
        duration_minutes = driving_distance * 2.5
    else:
        driving_distance = matrix['distance']
        duration_minutes = matrix['duration']
    
    # Calculate fee using custom formula
    fee_cents = calculate_manual_delivery_fee(driving_distance, duration_minutes)
    
    return {
        'id': f"manual_{int(datetime.now().timestamp())}",
        'fee': fee_cents,
        'fee_dollars': fee_cents / 100,
        'currency': 'USD',
        'pickup_duration': 15, # Default 15 min pickup for manual
        'duration': int(duration_minutes),
        'expires': (datetime.now() + timedelta(minutes=30)).isoformat(),
        'source': 'manual_dispatch',
        'driving_distance': driving_distance
    }

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

def calculate_manual_delivery_fee(distance_miles: float, duration_minutes: float) -> int:
    """
    Calculate delivery fee for manual dispatch (long distance)
    Returns fee in cents
    Formula: Base Fee + (Miles * Per-Mile Fee) + (Minutes * Per-Minute Fee)
    """
    # Pricing constants (could be moved to config)
    base_fee = 10.00      # $10.00 base (reduced from $15)
    mile_fee = 1.00       # $1.00 per mile (reduced from $1.50)
    minute_fee = 0.15     # $0.15 per minute (reduced from $0.25)
    
    total_fee_dollars = base_fee + (distance_miles * mile_fee) + (duration_minutes * minute_fee)
    
    # Round to 2 decimal places and convert to cents
    return int(round(total_fee_dollars, 2) * 100)

def get_driving_distance_matrix(origin_address: str, destination_address: str) -> Optional[Dict[str, float]]:
    """
    Get actual driving distance and duration using Google Maps Distance Matrix API
    Returns dict with 'distance' (miles) and 'duration' (minutes) or None if API call fails
    """
    try:
        from flask import current_app
        import requests
        
        api_key = current_app.config.get('GOOGLE_MAPS_API_KEY')
        if not api_key:
            logger.warning("Google Maps API key not configured")
            return None
        
        # Google Maps Distance Matrix API endpoint
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            'origins': origin_address,
            'destinations': destination_address,
            'units': 'imperial',
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
                    distance_miles = distance_meters * 0.000621371
                    
                    # Duration is returned in seconds, convert to minutes
                    duration_seconds = element['duration']['value']
                    duration_minutes = duration_seconds / 60
                    
                    logger.info(f"Google Maps matrix: {distance_miles:.2f} miles, {duration_minutes:.1f} mins from '{origin_address}' to '{destination_address}'")
                    return {
                        'distance': distance_miles,
                        'duration': duration_minutes
                    }
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
        logger.error(f"Error getting driving distance matrix: {str(e)}")
        return None

def get_driving_distance(origin_address: str, destination_address: str) -> Optional[float]:
    """
    Legacy wrapper for get_driving_distance_matrix that only returns distance
    """
    matrix = get_driving_distance_matrix(origin_address, destination_address)
    return matrix['distance'] if matrix else None

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