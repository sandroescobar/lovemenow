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
    geocode_address, get_driving_distance, get_hybrid_delivery_quote
)

uber_bp = Blueprint('uber', __name__)
logger = logging.getLogger(__name__)

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
    """Get delivery quote with hybrid logic (Uber < 10mi, Google Maps > 10mi)"""
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
        if 'delivery_address' not in data:
            return jsonify({'error': 'Missing delivery_address'}), 400
        
        # Cache check
        address_key = f"{data['delivery_address'].get('address', '').strip().lower()}-{data['delivery_address'].get('city', '').strip().lower()}-{data['delivery_address'].get('zip', '').strip()}"
        cache_key = f"quote_cache_{hash(address_key)}"
        
        if cache_key in session:
            cached_quote = session[cache_key]
            cache_time = datetime.fromisoformat(cached_quote['timestamp'])
            if (datetime.now() - cache_time).total_seconds() < 300:
                logger.info(f"Returning cached quote for address: {address_key}")
                return jsonify({'success': True, 'quote': cached_quote['quote']})
        
        # Initial area check
        is_valid, error_msg = is_in_delivery_area(data['delivery_address'])
        if not is_valid:
            return jsonify({'success': False, 'error': error_msg}), 400
        
        # Get coordinates
        pickup_address = get_miami_store_address()
        store_coords = get_miami_store_coordinates()
        delivery_coords = geocode_address(data['delivery_address'])
        
        if not delivery_coords:
            return jsonify({'success': False, 'error': 'Could not verify delivery address. Please check and try again.'}), 400
            
        # Calculate straight-line distance
        straight_line_distance = calculate_distance(
            store_coords['latitude'], store_coords['longitude'],
            delivery_coords[0], delivery_coords[1]
        )
        logger.info(f"Straight-line distance: {straight_line_distance:.2f} miles")
        
        # Final area check with distance
        is_valid_dist, dist_error = is_in_delivery_area(data['delivery_address'], straight_line_distance)
        if not is_valid_dist:
            return jsonify({'success': False, 'error': dist_error}), 400
            
        # Get hybrid quote
        quote_data = get_hybrid_delivery_quote(
            pickup_address, 
            format_address_for_uber(data['delivery_address']),
            store_coords, 
            delivery_coords,
            straight_line_distance
        )
        
        # Cache and return
        session[cache_key] = {
            'quote': quote_data,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({'success': True, 'quote': quote_data})
        
    except Exception as e:
        logger.error(f"Error getting delivery quote: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': 'Failed to get delivery quote'}), 500

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
        
        # Check if this is a manual dispatch quote
        if quote_id.startswith('manual_'):
            logger.info(f"Manual dispatch requested for order {order_id} (Quote: {quote_id})")
            
            # Send Slack alert for manual dispatch
            from services.slack_notifications import send_manual_delivery_alert
            send_manual_delivery_alert(order, reason="Long distance delivery (>10 miles) or Uber API unavailable", quote_id=quote_id)
            
            # Create a "manual" delivery record in database
            uber_delivery = UberDelivery(
                order_id=order.id,
                quote_id=quote_id,
                delivery_id=f"manual_{order.order_number}_{int(datetime.now().timestamp())}",
                status='manual_dispatch',
                fee=int(order.shipping_amount * 100), # Use shipping_amount from order
                currency='usd'
            )
            
            # Let's see if we can get the fee from the session cache or if we need to pass it
            # For now, we'll just mark it as processing and let the staff handle it.
            
            db.session.add(uber_delivery)
            order.status = 'processing'
            db.session.commit()
            
            return jsonify({
                'success': True,
                'delivery': {
                    'id': uber_delivery.delivery_id,
                    'status': 'manual_dispatch',
                    'message': 'Manual dispatch initiated. A staff member will contact you soon.'
                }
            })

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