"""
Webhook handlers for payment processing
"""
import json
import stripe
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.orm import joinedload

from routes import db
from models import Product, Cart, Order, OrderItem, User
from flask import session as flask_session
from services.slack_notifications import send_order_notification

webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        # Verify webhook signature
        endpoint_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
        if endpoint_secret and endpoint_secret != 'whsec_test_webhook_secret_for_development':
            # Production: verify signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        else:
            # Development/testing: skip signature verification
            current_app.logger.info("Development mode: Skipping webhook signature verification")
            event = json.loads(payload)
        
        current_app.logger.info(f"Received Stripe webhook: {event['type']}")
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            current_app.logger.info(f"Payment successful for session: {session['id']}")
            
            # Process the successful payment
            success = process_successful_payment(session)
            if not success:
                current_app.logger.error(f"Failed to process payment for session: {session['id']}")
                return jsonify({'error': 'Failed to process payment'}), 500
                
        elif event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            current_app.logger.info(f"Payment intent succeeded: {payment_intent['id']}")
            
            # Process the successful payment intent
            success = process_successful_payment_intent(payment_intent)
            if not success:
                current_app.logger.error(f"Failed to process payment intent: {payment_intent['id']}")
                return jsonify({'error': 'Failed to process payment intent'}), 500
            
        else:
            current_app.logger.info(f"Unhandled event type: {event['type']}")
        
        return jsonify({'status': 'success'})
        
    except ValueError as e:
        current_app.logger.error(f"Invalid payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        current_app.logger.error(f"Invalid signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400
    except Exception as e:
        current_app.logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

def process_successful_payment(stripe_session):
    """Process a successful payment and update inventory"""
    try:
        session_id = stripe_session['id']
        customer_email = stripe_session.get('customer_details', {}).get('email', '')
        
        # Get shipping address from Stripe session
        shipping_details = stripe_session.get('shipping_details', {})
        shipping_address = shipping_details.get('address', {}) if shipping_details else {}
        
        # Get cart items from Stripe session metadata
        metadata = stripe_session.get('metadata', {})
        cart_items = []
        
        # Try to find user by email or metadata
        user = None
        if customer_email:
            user = User.query.filter_by(email=customer_email).first()
        elif metadata.get('user_id'):
            user = User.query.get(int(metadata['user_id']))
        
        # Reconstruct cart items from metadata
        item_count = int(metadata.get('item_count', 0))
        for i in range(item_count):
            product_id = metadata.get(f'item_{i}_product_id')
            quantity = metadata.get(f'item_{i}_quantity')
            
            if product_id and quantity:
                product = Product.query.get(int(product_id))
                if product:
                    cart_items.append({
                        'product': product,
                        'quantity': int(quantity)
                    })
                else:
                    current_app.logger.warning(f"Product {product_id} not found during webhook processing")
        
        if not cart_items:
            current_app.logger.warning(f"No cart items found for session {session_id}")
            return True
        
        # Create order record
        order = create_order_from_stripe_session(stripe_session, user, cart_items)
        if not order:
            return False
        
        # Process each cart item and update inventory
        for item in cart_items:
            product = item['product']
            quantity = item['quantity']
            
            # Check if we have enough stock
            if product.quantity_on_hand < quantity:
                current_app.logger.error(
                    f"Insufficient stock for product {product.id}: "
                    f"requested {quantity}, available {product.quantity_on_hand}"
                )
                # In a real system, you might want to handle this more gracefully
                # For now, we'll decrement what we can
                quantity = max(0, product.quantity_on_hand)
            
            # Decrement inventory using the Product method
            if quantity > 0:
                success = product.decrement_inventory(quantity)
                if success:
                    current_app.logger.info(
                        f"Decremented inventory for product {product.id}: "
                        f"new quantity = {product.quantity_on_hand}, in_stock = {product.in_stock}"
                    )
                else:
                    current_app.logger.error(
                        f"Failed to decrement inventory for product {product.id}"
                    )
            
            # Create order item
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                price=product.price,
                quantity=item['quantity'],  # Use original quantity for order record
                total=product.price * item['quantity']
            )
            db.session.add(order_item)
        
        # Clear user's cart after successful payment
        if user:
            Cart.query.filter_by(user_id=user.id).delete()
        else:
            # For guest users, clear session cart
            # Note: This will only work if the webhook is called in the same session
            # For better handling, we'll also clear it in the frontend after successful payment
            if 'cart' in flask_session:
                flask_session.pop('cart', None)
                flask_session.modified = True
        
        # Commit all changes
        db.session.commit()
        
        # Send Slack notification after successful order processing
        try:
            current_app.logger.info(f"Attempting to send Slack notification for order {order.order_number}")
            success = send_order_notification(order, cart_items)
            if success:
                current_app.logger.info(f"Slack notification sent successfully for order {order.order_number}")
            else:
                current_app.logger.warning(f"Slack notification failed for order {order.order_number}")
        except Exception as e:
            # Don't fail the webhook if Slack notification fails
            current_app.logger.error(f"Failed to send Slack notification for order {order.order_number}: {str(e)}")
            import traceback
            current_app.logger.error(f"Slack notification traceback: {traceback.format_exc()}")
        
        current_app.logger.info(f"Successfully processed payment for session {session_id}")
        return True
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing payment: {str(e)}")
        return False

def create_order_from_stripe_session(stripe_session, user, cart_items):
    """Create an order record from Stripe session data"""
    try:
        import uuid
        
        # Generate order number
        order_number = f"LMN-{str(uuid.uuid4())[:8].upper()}"
        
        # Get customer details
        customer_details = stripe_session.get('customer_details', {})
        customer_email = customer_details.get('email', '')
        customer_name = customer_details.get('name', '')
        customer_phone = customer_details.get('phone', '')
        
        # Get shipping address
        shipping_details = stripe_session.get('shipping_details', {})
        shipping_address = shipping_details.get('address', {}) if shipping_details else {}
        
        # Calculate totals
        from decimal import Decimal
        subtotal = sum(Decimal(str(item['product'].price)) * item['quantity'] for item in cart_items)
        shipping_amount = Decimal('0')  # Shipping calculated separately based on delivery method
        total_amount = subtotal + shipping_amount
        
        # Create order
        order = Order(
            user_id=user.id if user else None,
            order_number=order_number,
            email=customer_email,
            full_name=customer_name,
            phone=customer_phone,
            shipping_address=shipping_address.get('line1', ''),
            shipping_suite=shipping_address.get('line2', ''),
            shipping_city=shipping_address.get('city', ''),
            shipping_state=shipping_address.get('state', ''),
            shipping_zip=shipping_address.get('postal_code', ''),
            shipping_country=shipping_address.get('country', 'US'),
            delivery_type='pickup',  # Webhook orders default to pickup
            subtotal=subtotal,
            shipping_amount=shipping_amount,
            total_amount=total_amount,
            payment_method='card',
            payment_status='paid',
            stripe_session_id=stripe_session['id'],
            status='processing'
        )
        
        db.session.add(order)
        db.session.flush()  # Get the order ID
        
        return order
        
    except Exception as e:
        current_app.logger.error(f"Error creating order: {str(e)}")
        return None

def process_successful_payment_intent(payment_intent):
    """Process a successful payment intent and send Slack notification"""
    try:
        payment_intent_id = payment_intent['id']
        current_app.logger.info(f"Processing payment intent: {payment_intent_id}")
        
        # Get metadata from payment intent
        metadata = payment_intent.get('metadata', {})
        current_app.logger.info(f"Payment intent metadata: {metadata}")
        
        # Build cart items from metadata
        cart_items = []
        item_count = int(metadata.get('item_count', 0))
        
        for i in range(item_count):
            product_id = metadata.get(f'item_{i}_product_id')
            quantity = int(metadata.get(f'item_{i}_quantity', 1))
            
            if product_id:
                product = Product.query.get(int(product_id))
                if product:
                    cart_items.append({
                        'product': product,
                        'quantity': quantity
                    })
        
        current_app.logger.info(f"Found {len(cart_items)} items from payment intent metadata")
        
        if not cart_items:
            current_app.logger.warning(f"No cart items found in payment intent {payment_intent_id}")
            return True  # Don't fail the webhook, but log the issue
        
        # Create a mock order object for Slack notification
        # Since the order is created in the frontend, we just need basic info for Slack
        from datetime import datetime
        mock_order = type('Order', (), {
            'order_number': f"PI-{payment_intent_id[-8:].upper()}",
            'total_amount': payment_intent['amount'] / 100,  # Convert from cents
            'delivery_type': 'pickup',  # Default for payment intents
            'email': payment_intent.get('receipt_email', 'N/A'),
            'payment_status': 'paid',
            'full_name': 'Webhook Customer',  # Required by Slack service
            'phone': 'N/A',  # Required by Slack service
            'created_at': datetime.now()  # Only needed for Slack timestamp formatting
        })()
        
        # Send Slack notification
        try:
            current_app.logger.info(f"Attempting to send Slack notification for payment intent {payment_intent_id}")
            success = send_order_notification(mock_order, cart_items)
            if success:
                current_app.logger.info(f"Slack notification sent successfully for payment intent {payment_intent_id}")
            else:
                current_app.logger.warning(f"Slack notification failed for payment intent {payment_intent_id}")
        except Exception as e:
            current_app.logger.error(f"Failed to send Slack notification for payment intent {payment_intent_id}: {str(e)}")
            import traceback
            current_app.logger.error(f"Slack notification traceback: {traceback.format_exc()}")
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error processing payment intent: {str(e)}")
        import traceback
        current_app.logger.error(f"Payment intent processing traceback: {traceback.format_exc()}")
        return False