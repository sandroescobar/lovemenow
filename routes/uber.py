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
from uber_service import uber_service, get_miami_store_address, get_miami_store_coordinates, format_address_for_uber, create_manifest_items

uber_bp = Blueprint('uber', __name__)
logger = logging.getLogger(__name__)

@uber_bp.route('/quote', methods=['POST'])
def get_delivery_quote():
    """Get delivery quote from Uber Direct"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['delivery_address']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get store pickup address and coordinates
        pickup_address = get_miami_store_address()
        store_coords = get_miami_store_coordinates()
        
        # Format customer delivery address
        delivery_address = format_address_for_uber(data['delivery_address'])
        
        # Create quote with Uber including coordinates to match delivery request
        quote = uber_service.create_quote_with_coordinates(
            pickup_address, 
            delivery_address,
            pickup_coords=store_coords,
            dropoff_coords=None  # Let Uber geocode the dropoff
        )
        
        return jsonify({
            'success': True,
            'quote': {
                'id': quote['id'],
                'fee': quote['fee'],
                'fee_dollars': quote['fee'] / 100,
                'currency': quote['currency'],
                'pickup_duration': quote.get('pickup_duration', 0),
                'dropoff_eta': quote.get('dropoff_eta'),
                'duration': quote.get('duration', 0),
                'expires': quote.get('expires')
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting delivery quote: {str(e)}")
        return jsonify({'error': 'Failed to get delivery quote'}), 500

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
            'name': current_app.config.get('STORE_NAME', 'LoveMeNow Miami'),
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
        
        # Create delivery with Uber
        delivery_response = uber_service.create_delivery(
            quote_id, pickup_info, dropoff_info, manifest_items
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