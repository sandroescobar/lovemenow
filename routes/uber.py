"""
Uber Direct integration routes
"""
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, session
from flask_login import current_user

from routes import db
from models import Order, OrderItem, UberDelivery, Product, Cart
from uber_service import (
    uber_service, get_miami_store_address, get_miami_store_coordinates, 
    format_address_for_uber, create_manifest_items, calculate_distance, 
    get_custom_delivery_price, is_peak_hours, geocode_address, get_driving_distance
)

uber_bp = Blueprint('uber', __name__)
logger = logging.getLogger(__name__)

AUTO_UBER_DISTANCE_THRESHOLD = 20  # miles automatically handed to Uber Direct before custom pricing

# TEMPORARILY DISABLED TO FIX INFINITE LOOP ISSUE
# @uber_bp.route('/quote', methods=['POST'])
# def get_delivery_quote():
#     """Get delivery quote from Uber Direct"""
#     try:
#         data = request.get_json()
#         
#         # Validate required fields
#         required_fields = ['delivery_address']
#         for field in required_fields:
#             if field not in data:
#                 return jsonify({'error': f'Missing required field: {field}'}), 400
#         
#         # Get store pickup address and coordinates
#         pickup_address = get_miami_store_address()
#         store_coords = get_miami_store_coordinates()
#         
#         # Format customer delivery address
#         delivery_address = format_address_for_uber(data['delivery_address'])
#         
#         # Create quote with Uber including coordinates to match delivery request
#         quote = uber_service.create_quote_with_coordinates(
#             pickup_address, 
#             delivery_address,
#             pickup_coords=store_coords,
#             dropoff_coords=None  # Let Uber geocode the dropoff
#         )
#         
#         return jsonify({
#             'success': True,
#             'quote': {
#                 'id': quote['id'],
#                 'fee': quote['fee'],
#                 'fee_dollars': quote['fee'] / 100,
#                 'currency': quote['currency'],

def is_in_delivery_area(address_data, distance_miles=None):
    """Check if address is in our delivery area (within 70 miles of Miami store)"""
    state = address_data.get('state', '').lower().strip()
    
    # Must be in Florida
    if state not in ['fl', 'florida']:
        return False, f"We only deliver within Florida. Address is in {state.upper()}"
    
    # If we have distance calculated, use that for validation
    if distance_miles is not None:
        if distance_miles > 70:
            return False, f"Address is {distance_miles:.1f} miles away. We deliver within 70 miles of our Miami store."
        return True, None
    
    # Fallback: Check if city is in known delivery areas (South Florida)
    delivery_areas = [
        'miami', 'hialeah', 'kendall', 'aventura', 'sunny isles', 'doral',
        'coral gables', 'hollywood', 'north miami beach', 'fort lauderdale',
        'pompano beach', 'wynwood', 'miami beach', 'homestead', 'pinecrest',
        'palmetto bay', 'cutler bay', 'south beach', 'brickell', 'downtown miami',
        'davie', 'plantation', 'sunrise', 'weston', 'miramar', 'pembroke pines',
        'cooper city', 'southwest ranches', 'lauderhill', 'tamarac', 'coral springs',
        'parkland', 'coconut creek', 'margate', 'north lauderdale', 'lauderdale lakes',
        'wilton manors', 'oakland park', 'lighthouse point', 'deerfield beach',
        'boca raton', 'delray beach', 'boynton beach', 'lake worth', 'west palm beach'
    ]
    
    city = address_data.get('city', '').lower().strip()
    
    # Check if city is in our delivery area
    for delivery_area in delivery_areas:
        if delivery_area in city or city in delivery_area:
            return True, None
    
    return False, f"We deliver within 70 miles of our Miami store. Please contact us if you're unsure about your delivery area."

@uber_bp.route('/quote', methods=['POST'])
def get_delivery_quote():
    """Get delivery quote with distance-based pricing logic"""
    try:
        data = request.get_json()
        logger.info(f"Quote request received: {data}")
        
        # Check if store is open before providing quote
        from uber_service import is_store_open
        store_is_open, store_status = is_store_open()
        if not store_is_open:
            logger.warning(f"Quote request rejected - store closed: {store_status}")
            return jsonify({
                'success': False,
                'error': f"We're currently closed. {store_status}. We offer delivery during business hours."
            }), 400
        
        # Validate required fields
        required_fields = ['delivery_address']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create a normalized cache key for this address to prevent price jumping
        address_key = f"{data['delivery_address'].get('address', '').strip().lower()}-{data['delivery_address'].get('city', '').strip().lower()}-{data['delivery_address'].get('zip', '').strip()}"
        cache_key = f"quote_cache_{hash(address_key)}"
        
        # Check if we have a recent quote for this exact address (within 5 minutes)
        if cache_key in session:
            cached_quote = session[cache_key]
            from datetime import datetime
            cache_time = datetime.fromisoformat(cached_quote['timestamp'])
            if (datetime.now() - cache_time).total_seconds() < 300:  # 5 minutes
                logger.info(f"Returning cached quote for address: {address_key}")
                return jsonify({
                    'success': True,
                    'quote': cached_quote['quote']
                })
        
        # Initial check if address is in delivery area (without distance)
        is_valid, error_msg = is_in_delivery_area(data['delivery_address'])
        if not is_valid:
            logger.warning(f"Address outside delivery area: {data['delivery_address']}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Get store pickup address and coordinates
        pickup_address = get_miami_store_address()
        store_coords = get_miami_store_coordinates()
        logger.info(f"Store address: {pickup_address}")
        logger.info(f"Store coordinates: {store_coords}")
        
        # Format customer delivery address
        delivery_address = format_address_for_uber(data['delivery_address'])
        logger.info(f"Formatted delivery address: {delivery_address}")
        
        # Try to geocode the delivery address to calculate distance
        delivery_coords = None
        try:
            # For now, we'll use a simple geocoding approach
            # In production, you should use Google Maps Geocoding API or similar
            delivery_coords = geocode_address(data['delivery_address'])
        except Exception as geocode_error:
            logger.warning(f"Geocoding failed: {geocode_error}")
        
        # Calculate distance if we have coordinates
        distance_miles = None
        use_custom_pricing = False
        
        if delivery_coords:
            # First calculate straight-line distance for initial validation
            straight_line_distance = calculate_distance(
                store_coords['latitude'], store_coords['longitude'],
                delivery_coords[0], delivery_coords[1]
            )
            logger.info(f"Calculated straight-line distance: {straight_line_distance:.2f} miles")
            
            distance_miles = straight_line_distance
            
            # If straight-line distance > 10 miles, get actual driving distance for accurate pricing
            if straight_line_distance > 10:
                # Format addresses for Google Maps API
                store_address = f"{current_app.config.get('STORE_ADDRESS', '351 NE 79th St')} {current_app.config.get('STORE_SUITE', 'Unit 101')}, {current_app.config.get('STORE_CITY', 'Miami')}, {current_app.config.get('STORE_STATE', 'FL')} {current_app.config.get('STORE_ZIP', '33138')}"
                
                delivery_address_parts = []
                if data['delivery_address'].get('address'):
                    delivery_address_parts.append(data['delivery_address']['address'])
                if data['delivery_address'].get('city'):
                    delivery_address_parts.append(data['delivery_address']['city'])
                if data['delivery_address'].get('state'):
                    delivery_address_parts.append(data['delivery_address']['state'])
                if data['delivery_address'].get('zip'):
                    delivery_address_parts.append(data['delivery_address']['zip'])
                
                customer_address = ', '.join(delivery_address_parts)
                
                # Get actual driving distance for addresses outside 10-mile radius
                driving_distance = get_driving_distance(store_address, customer_address)
                
                if driving_distance:
                    distance_miles = driving_distance
                    logger.info(f"Using Google Maps driving distance: {distance_miles:.2f} miles")
                else:
                    # Fallback to city-based estimate if Google Maps fails (more accurate than straight-line)
                    city = data['delivery_address'].get('city', '').lower()
                    
                    # Use city-based estimates as fallback (same logic as below)
                    if any(far_city in city for far_city in ['fort lauderdale', 'pompano beach', 'coral springs', 'parkland']):
                        distance_miles = 26.0
                    elif any(broward_city in city for broward_city in ['hollywood', 'davie', 'plantation', 'sunrise', 'weston', 'miramar']):
                        distance_miles = 18.0
                    elif any(palm_city in city for palm_city in ['boca raton', 'delray beach', 'boynton beach', 'west palm beach']):
                        distance_miles = 35.0
                    elif any(south_city in city for south_city in ['homestead', 'florida city']):
                        distance_miles = 20.0
                    else:
                        # If city not recognized, use straight-line distance as last resort
                        distance_miles = straight_line_distance
                    
                    logger.warning(f"Google Maps failed, using city-based estimate: {distance_miles:.2f} miles for '{city}'")
            
            if distance_miles > AUTO_UBER_DISTANCE_THRESHOLD:
                use_custom_pricing = True
                logger.info(f"Distance {distance_miles:.2f} miles > {AUTO_UBER_DISTANCE_THRESHOLD} miles, using custom pricing")
            else:
                logger.info(f"Distance {distance_miles:.2f} miles <= {AUTO_UBER_DISTANCE_THRESHOLD} miles, will try Uber Direct first")
            
            # Validate distance is within 70 miles
            is_valid_distance, distance_error = is_in_delivery_area(data['delivery_address'], distance_miles)
            if not is_valid_distance:
                logger.warning(f"Address too far: {distance_miles:.2f} miles")
                return jsonify({
                    'success': False,
                    'error': distance_error
                }), 400
        
        # Try to get Uber quote first (for addresses within the auto-dispatch radius or as fallback)
        uber_quote = None
        if not use_custom_pricing:
            try:
                logger.info("Attempting to get Uber Direct quote...")
                uber_quote = uber_service.create_quote_with_coordinates(
                    pickup_address, 
                    delivery_address,
                    pickup_coords=store_coords,
                    dropoff_coords=delivery_coords
                )
                logger.info(f"Uber quote response: {uber_quote}")
                
                # If we got a valid Uber quote, use it
                quote_data = {
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
                
                # Cache the quote to prevent price jumping
                from datetime import datetime
                session[cache_key] = {
                    'quote': quote_data,
                    'timestamp': datetime.now().isoformat()
                }
                
                return jsonify({
                    'success': True,
                    'quote': quote_data
                })
                
            except Exception as uber_error:
                logger.warning(f"Uber Direct quote failed: {uber_error}")
                # Fall back to custom pricing
                use_custom_pricing = True
        
        # Use custom pricing for addresses outside the auto-dispatch radius or when Uber fails
        if use_custom_pricing:
            logger.info("Using custom pricing logic")
            
            # If we don't have distance, estimate based on city/zip code
            if distance_miles is None:
                # Estimate distance based on delivery area (rough approximation)
                city = data['delivery_address'].get('city', '').lower()
                zip_code = data['delivery_address'].get('zip', '')
                
                # Fort Lauderdale area (25-30 miles) - Based on actual Google Maps driving distance
                if any(far_city in city for far_city in ['fort lauderdale', 'pompano beach', 'coral springs', 'parkland']):
                    distance_miles = 26.0
                # Broward County cities (15-25 miles)
                elif any(broward_city in city for broward_city in ['hollywood', 'davie', 'plantation', 'sunrise', 'weston', 'miramar']):
                    distance_miles = 18.0
                # Palm Beach County (30-45 miles)
                elif any(palm_city in city for palm_city in ['boca raton', 'delray beach', 'boynton beach', 'west palm beach']):
                    distance_miles = 35.0
                # South Miami-Dade (15-25 miles)
                elif any(south_city in city for south_city in ['homestead', 'florida city']):
                    distance_miles = 20.0
                # Close Miami areas (5-12 miles)
                else:
                    distance_miles = 8.0
                    
                logger.info(f"Estimated distance based on city '{city}': {distance_miles:.2f} miles")
            
            # Calculate custom price
            peak_hours = is_peak_hours()
            custom_price = get_custom_delivery_price(distance_miles, peak_hours)
            
            # Generate a custom quote ID
            import uuid
            custom_quote_id = f"custom_{uuid.uuid4().hex[:8]}"
            
            # Estimate delivery time based on distance
            estimated_duration = max(30, int(distance_miles * 3))  # 3 minutes per mile, minimum 30 minutes
            
            logger.info(f"Custom quote: ${custom_price:.2f} for {distance_miles:.2f} miles (peak hours: {peak_hours})")
            
            quote_data = {
                'id': custom_quote_id,
                'fee': int(custom_price * 100),  # Convert to cents
                'fee_dollars': custom_price,
                'currency': 'usd',
                'pickup_duration': 15,  # 15 minutes to pickup
                'dropoff_eta': None,
                'duration': estimated_duration,
                'expires': None,
                'source': 'custom_pricing',
                'distance_miles': distance_miles,
                'peak_hours': peak_hours
            }
            
            # Cache the quote to prevent price jumping
            from datetime import datetime
            session[cache_key] = {
                'quote': quote_data,
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify({
                'success': True,
                'quote': quote_data
            })
        
        # This shouldn't be reached, but just in case
        return jsonify({
            'success': False,
            'error': 'Unable to generate delivery quote'
        }), 500
        
    except Exception as e:
        logger.error(f"Error getting delivery quote: {str(e)}")
        logger.error(f"Request data: {data}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Failed to get delivery quote: {str(e)}'
        }), 500

@uber_bp.route('/create-delivery', methods=['POST'])
def create_delivery():
    """Create Uber delivery for an order"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['order_id', 'quote_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        order_id = data['order_id']
        quote_id = data['quote_id']
        
        # Get the order
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Check if delivery already exists
        if order.delivery:
            return jsonify({'error': 'Delivery already exists for this order'}), 400
        
        # Only create delivery for delivery orders
        if order.delivery_type != 'delivery':
            return jsonify({'error': 'Order is not set for delivery'}), 400
        
        # Prepare pickup information (store)
        store_coords = get_miami_store_coordinates()
        pickup_info = {
            'address': get_miami_store_address(),
            'name': current_app.config.get('STORE_DISPLAY_NAME', 'Miami Vape Smoke Shop'),  # Display name for drivers
            'phone': current_app.config.get('STORE_PHONE', '+1234567890'),
            'latitude': store_coords['latitude'],
            'longitude': store_coords['longitude']
        }
        
        # Prepare dropoff information (customer)
        dropoff_address = {
            'address': order.shipping_address,
            'suite': order.shipping_suite or '',
            'city': order.shipping_city,
            'state': order.shipping_state,
            'zip': order.shipping_zip,
            'country': order.shipping_country
        }
        
        dropoff_info = {
            'address': format_address_for_uber(dropoff_address),
            'name': order.full_name,
            'phone': order.phone or '+1234567890',  # Use order phone or default
            'latitude': order.delivery_latitude,
            'longitude': order.delivery_longitude
        }
        
        # Create manifest items from order
        cart_items = []
        for item in order.items:
            cart_items.append({
                'product': {
                    'id': item.product_id,
                    'name': item.product_name
                },
                'quantity': item.quantity
            })
        
        manifest_items = create_manifest_items(cart_items)
        
        # Build driver instructions with store name
        store_display_name = current_app.config.get('STORE_DISPLAY_NAME', 'Miami Vape Smoke Shop')
        dropoff_notes = f"Walk into the store called {store_display_name}. Ask the employee working inside the shop for your order."
        
        # Create delivery with Uber
        delivery_response = uber_service.create_delivery(
            quote_id, pickup_info, dropoff_info, manifest_items, dropoff_notes=dropoff_notes
        )
        
        # Save delivery information to database
        uber_delivery = UberDelivery(
            order_id=order.id,
            quote_id=quote_id,
            delivery_id=delivery_response['id'],
            tracking_url=delivery_response.get('tracking_url'),
            status=delivery_response.get('status', 'pending'),
            fee=delivery_response.get('fee'),
            currency=delivery_response.get('currency', 'usd'),
            pickup_eta=datetime.fromisoformat(delivery_response['pickup_eta'].replace('Z', '+00:00')) if delivery_response.get('pickup_eta') else None,
            dropoff_eta=datetime.fromisoformat(delivery_response['dropoff_eta'].replace('Z', '+00:00')) if delivery_response.get('dropoff_eta') else None
        )
        
        db.session.add(uber_delivery)
        
        # Update order status
        order.status = 'processing'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'delivery': {
                'id': uber_delivery.delivery_id,
                'status': uber_delivery.status,
                'tracking_url': uber_delivery.tracking_url,
                'pickup_eta': uber_delivery.pickup_eta.isoformat() if uber_delivery.pickup_eta else None,
                'dropoff_eta': uber_delivery.dropoff_eta.isoformat() if uber_delivery.dropoff_eta else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating delivery: {str(e)}")
        return jsonify({'error': 'Failed to create delivery'}), 500

@uber_bp.route('/delivery-status/<delivery_id>')
def get_delivery_status(delivery_id):
    """Get delivery status from Uber"""
    try:
        # Get delivery from database
        uber_delivery = UberDelivery.query.filter_by(delivery_id=delivery_id).first()
        if not uber_delivery:
            return jsonify({'error': 'Delivery not found'}), 404
        
        # Get updated status from Uber
        delivery_status = uber_service.get_delivery_status(delivery_id)
        
        # Update database with latest status
        uber_delivery.status = delivery_status.get('status', uber_delivery.status)
        
        # Update courier information if available
        courier = delivery_status.get('courier')
        if courier:
            uber_delivery.courier_name = courier.get('name')
            uber_delivery.courier_phone = courier.get('phone_number')
            
            location = courier.get('location')
            if location:
                uber_delivery.courier_location_lat = location.get('lat')
                uber_delivery.courier_location_lng = location.get('lng')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'delivery': {
                'id': delivery_id,
                'status': uber_delivery.status,
                'tracking_url': uber_delivery.tracking_url,
                'pickup_eta': uber_delivery.pickup_eta.isoformat() if uber_delivery.pickup_eta else None,
                'dropoff_eta': uber_delivery.dropoff_eta.isoformat() if uber_delivery.dropoff_eta else None,
                'courier': {
                    'name': uber_delivery.courier_name,
                    'phone': uber_delivery.courier_phone,
                    'location': {
                        'lat': uber_delivery.courier_location_lat,
                        'lng': uber_delivery.courier_location_lng
                    } if uber_delivery.courier_location_lat else None
                } if uber_delivery.courier_name else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting delivery status: {str(e)}")
        return jsonify({'error': 'Failed to get delivery status'}), 500

@uber_bp.route('/store-orders')
def get_store_orders():
    """Get orders for store notification system"""
    try:
        # Get recent orders (last 24 hours)
        from datetime import timedelta
        since = datetime.utcnow() - timedelta(hours=24)
        
        orders = (Order.query
                 .filter(Order.created_at >= since)
                 .filter(Order.status.in_(['pending', 'processing', 'ready']))
                 .order_by(Order.created_at.desc())
                 .all())
        
        order_data = []
        for order in orders:
            # Get product IDs for discreet labeling
            product_ids = [item.product_id for item in order.items]
            
            order_info = {
                'id': order.id,
                'order_number': order.order_number,
                'customer_name': order.full_name,
                'customer_phone': order.phone,
                'customer_email': order.email,
                'delivery_type': order.delivery_type,
                'status': order.status,
                'product_ids': product_ids,
                'total_amount': float(order.total_amount),
                'created_at': order.created_at.isoformat(),
                'delivery_info': None
            }
            
            # Add delivery information if available
            if order.delivery and order.delivery_type == 'delivery':
                order_info['delivery_info'] = {
                    'status': order.delivery.status,
                    'tracking_url': order.delivery.tracking_url,
                    'pickup_eta': order.delivery.pickup_eta.isoformat() if order.delivery.pickup_eta else None,
                    'dropoff_eta': order.delivery.dropoff_eta.isoformat() if order.delivery.dropoff_eta else None,
                    'courier_name': order.delivery.courier_name,
                    'courier_phone': order.delivery.courier_phone
                }
            
            order_data.append(order_info)
        
        return jsonify({
            'success': True,
            'orders': order_data,
            'count': len(order_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting store orders: {str(e)}")
        return jsonify({'error': 'Failed to get store orders'}), 500

@uber_bp.route('/test-connection')
def test_uber_connection():
    """Test Uber Direct API connection"""
    try:
        # Try to get an access token
        token = uber_service._get_access_token()
        
        return jsonify({
            'success': True,
            'message': 'Successfully connected to Uber Direct API',
            'token_preview': token[:20] + '...' if token else 'No token'
        })
        
    except Exception as e:
        logger.error(f"Error testing Uber connection: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500