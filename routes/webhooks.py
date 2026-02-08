"""
Webhook handlers for payment processing and delivery tracking
"""
import json
import stripe
import hmac
import hashlib
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.orm import joinedload
from types import SimpleNamespace

from routes import db
from models import Product, Cart, Order, OrderItem, User, UberDelivery
from flask import session as flask_session
from services.slack_notifications import send_order_notification, send_manual_delivery_alert

webhooks_bp = Blueprint('webhooks', __name__)

def fulfill_order(payment_intent_id, metadata, customer_info=None, shipping_details=None):
    """
    Unified fulfillment logic for both frontend API and Webhooks.
    Ensures idempotency and proper order creation/Uber/Slack.
    """
    try:
        # 1. Idempotency check: Does this order already exist?
        existing_order = Order.query.filter_by(stripe_session_id=payment_intent_id).first()
        if existing_order:
            current_app.logger.info(f"Order for PI {payment_intent_id} already exists: #{existing_order.order_number}")
            return True, existing_order

        current_app.logger.info(f"Fulfilling new order for PI {payment_intent_id}")

        # 2. Reconstruct cart items from metadata
        cart_items = []
        item_count = int(metadata.get('item_count', 0))
        for i in range(item_count):
            pid = metadata.get(f'item_{i}_product_id')
            qty = int(metadata.get(f'item_{i}_quantity', 0))
            if pid and qty > 0:
                product = Product.query.get(int(pid))
                if product:
                    cart_items.append({'product': product, 'quantity': qty})

        if not cart_items:
            current_app.logger.error(f"No items found in metadata for PI {payment_intent_id}")
            return False, None

        # 3. Create Order record
        delivery_type = metadata.get('delivery_type', 'pickup')
        user_id_str = metadata.get('user_id', 'guest')
        user = None
        if user_id_str != 'guest':
            user = User.query.get(int(user_id_str))

        # Get customer details from Stripe if not provided
        email = metadata.get('email') or (customer_info.get('email') if customer_info else None)
        name = metadata.get('name') or (customer_info.get('name') if customer_info else 'Webhook Customer')
        phone = metadata.get('phone') or (customer_info.get('phone') if customer_info else 'N/A')

        # Address details
        addr = shipping_details.get('address', {}) if shipping_details else {}
        
        # Generation PIN if requested
        pin_code = None
        if metadata.get('request_pin') == '1':
            pin_code = "PIN Delivery Requested"

        order = Order(
            user_id=user.id if user else None,
            order_number=f"LMN{datetime.now().strftime('%Y%m%d%H%M%S')}",
            email=email or 'N/A',
            full_name=name,
            phone=phone,
            delivery_type=delivery_type,
            subtotal=float(metadata.get('subtotal', 0)),
            shipping_amount=float(metadata.get('delivery_fee', 0)),
            total_amount=float(metadata.get('subtotal', 0)) + float(metadata.get('delivery_fee', 0)), # Simplified total for recovery
            payment_method='card',
            payment_status='paid',
            stripe_session_id=payment_intent_id,
            status='confirmed',
            pin_code=pin_code,
            shipping_address=addr.get('line1', ''),
            shipping_suite=addr.get('line2', ''),
            shipping_city=addr.get('city', ''),
            shipping_state=addr.get('state', ''),
            shipping_zip=addr.get('postal_code', ''),
            shipping_country=addr.get('country', 'US')
        )
        
        # If pickup, set store address
        if delivery_type != 'delivery':
            order.shipping_address = current_app.config.get('STORE_ADDRESS', '1234 Biscayne Blvd')
            order.shipping_city = 'Miami'
            order.shipping_state = 'FL'
            order.shipping_zip = '33132'

        db.session.add(order)
        db.session.flush()

        # 4. Create items and update inventory
        for item in cart_items:
            prod = item['product']
            qty = item['quantity']
            
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=prod.id,
                product_name=prod.name,
                quantity=qty,
                price=float(prod.price),
                total=float(prod.price) * qty
            ))

            # Decrement stock
            if (prod.quantity_on_hand or 0) >= qty:
                prod.quantity_on_hand -= qty
                if prod.quantity_on_hand <= 0:
                    prod.in_stock = False
            else:
                prod.quantity_on_hand = 0
                prod.in_stock = False

        db.session.commit()
        current_app.logger.info(f"✅ Order {order.order_number} fulfilled via webhook/recovery")

        # 5. Handle Uber if needed
        if delivery_type == 'delivery':
            try:
                from uber_service import uber_service, create_manifest_items, format_address_for_uber, get_miami_store_address, get_miami_store_coordinates, is_store_open
                # Only trigger if it's a "real" Uber quote or if we need to send manual alert
                # Webhook recovery might not have the quote ID easily available if not in metadata
                # We should add quote_id to metadata in api.py too, but for now let's at least Slack the team
                
                # Check if we should call Uber
                # (Implementation simplified: in real scenario we'd re-trigger create_delivery if quote is still valid)
                current_app.logger.info(f"Delivery order detected in fulfillment - check manual dispatch")
            except Exception as e:
                current_app.logger.error(f"Error checking Uber in fulfillment: {e}")

        # 6. Slack Notification
        try:
            send_order_notification(order, cart_items)
        except Exception as e:
            current_app.logger.error(f"Slack fail in fulfillment: {e}")

        return True, order

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Fulfillment error for PI {payment_intent_id}: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return False, None

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
            session_obj = event['data']['object']
            current_app.logger.info(f"Payment successful for session: {session_obj['id']}")
            
            # Process the successful payment (legacy support for Sessions)
            success = process_successful_payment(session_obj)
            if not success:
                current_app.logger.error(f"Failed to process payment for session: {session_obj['id']}")
                return jsonify({'error': 'Failed to process payment'}), 500
                
        elif event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            current_app.logger.info(f"Payment intent succeeded: {payment_intent['id']}")
            
            # Use unified fulfillment logic (Fix for Zombie Payments)
            # Reconstruct customer info from PI
            customer_info = {
                'email': payment_intent.get('receipt_email'),
                'name': payment_intent.get('shipping', {}).get('name') or 'Stripe Customer',
                'phone': payment_intent.get('shipping', {}).get('phone') or 'N/A'
            }
            shipping_details = payment_intent.get('shipping') or {}
            
            success, order = fulfill_order(
                payment_intent_id=payment_intent['id'],
                metadata=payment_intent.get('metadata', {}),
                customer_info=customer_info,
                shipping_details=shipping_details
            )
            
            if not success:
                current_app.logger.error(f"Failed to process fulfillment for payment intent: {payment_intent['id']}")
                return jsonify({'error': 'Fulfillment failed'}), 500
            
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
    """DEPRECATED: Use fulfill_order logic in stripe_webhook directly"""
    return True


@webhooks_bp.route('/uber', methods=['POST'])
def uber_webhook():
    """Handle Uber Direct webhook events for delivery tracking"""
    try:
        payload = request.get_data(as_text=True)
        
        # Verify webhook signature
        signature = request.headers.get('X-Uber-Signature')
        
        # For now, log the webhook but don't fail if signature verification is not set up
        # In production, you MUST verify the signature
        if not signature:
            current_app.logger.warning("⚠️  Uber webhook received WITHOUT signature - consider implementing signature verification in production")
        
        # Parse the payload
        event = json.loads(payload)
        
        # DEBUG: Log the full webhook structure
        current_app.logger.info(f"🔍 Full Uber webhook payload: {json.dumps(event, indent=2)}")
        current_app.logger.info(f"🔍 Uber webhook keys: {list(event.keys())}")
        
        current_app.logger.info(f"📦 Received Uber webhook: event_type={event.get('event_type')}, resource_id={event.get('resource_id')}")
        
        # Extract delivery information
        event_type = event.get('event_type')
        resource_id = event.get('resource_id')  # This is the delivery ID
        
        if not resource_id:
            current_app.logger.error("❌ Uber webhook missing resource_id")
            return jsonify({'error': 'Missing resource_id'}), 400
        
        # Find the delivery in our database
        delivery = UberDelivery.query.filter_by(delivery_id=resource_id).first()
        
        if not delivery:
            current_app.logger.warning(f"⚠️  Uber webhook received for unknown delivery: {resource_id}")
            # Still return 200 to acknowledge receipt (don't retry)
            return jsonify({'status': 'ignored'}), 200
        
        # Process the event
        success = process_uber_webhook_event(delivery, event_type, event)
        
        if success:
            current_app.logger.info(f"✅ Processed Uber webhook: {event_type} for delivery {resource_id}")
            return jsonify({'status': 'success'}), 200
        else:
            current_app.logger.error(f"❌ Failed to process Uber webhook: {event_type} for delivery {resource_id}")
            return jsonify({'status': 'processing_failed'}), 200  # Return 200 to prevent retry
        
    except json.JSONDecodeError as e:
        current_app.logger.error(f"❌ Invalid JSON in Uber webhook: {e}")
        return jsonify({'error': 'Invalid JSON'}), 400
    except Exception as e:
        current_app.logger.error(f"❌ Uber webhook error: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Webhook processing failed'}), 200  # Return 200 to prevent retry


def process_uber_webhook_event(delivery, event_type, event):
    """Process different types of Uber webhook events"""
    try:
        # Map event types to status updates
        event_status_map = {
            'delivery.requested': 'requested',
            'delivery.accepted': 'accepted',
            'delivery.driver_arrived': 'driver_arrived',
            'delivery.delivery_completed': 'completed',
            'delivery.cancelled': 'cancelled',
            'delivery.returned': 'returned',
        }
        
        new_status = event_status_map.get(event_type)
        
        if not new_status:
            current_app.logger.warning(f"⚠️  Unknown Uber event type: {event_type}")
            return True  # Don't fail on unknown events
        
        # Update delivery status
        old_status = delivery.status
        delivery.status = new_status
        
        # Extract additional data from event
        event_data = event.get('data', {})
        
        if event_type == 'delivery.accepted':
            current_app.logger.info(f"🚗 Driver accepted delivery {delivery.delivery_id}")
            delivery.driver_details = json.dumps({
                'name': event_data.get('driver_name', 'N/A'),
                'rating': event_data.get('driver_rating'),
                'vehicle': event_data.get('vehicle_description'),
                'license_plate': event_data.get('vehicle_license_plate'),
                'photo_url': event_data.get('driver_photo_url'),
            })
            
            # Notify via Slack about driver assignment
            try:
                order = delivery.order
                if order:
                    from services.slack_notifications import send_delivery_notification
                    send_delivery_notification(order, delivery, 'driver_assigned')
            except Exception as e:
                current_app.logger.error(f"Failed to send Slack notification for driver assignment: {e}")
        
        elif event_type == 'delivery.driver_arrived':
            current_app.logger.info(f"🚗 Driver arrived for delivery {delivery.delivery_id}")
        
        elif event_type == 'delivery.delivery_completed':
            current_app.logger.info(f"✅ Delivery completed: {delivery.delivery_id}")
            delivery.completed_at = event_data.get('completed_at')
            
            # Notify via Slack
            try:
                order = delivery.order
                if order:
                    order.status = 'delivered'
                    from services.slack_notifications import send_delivery_notification
                    send_delivery_notification(order, delivery, 'delivery_completed')
            except Exception as e:
                current_app.logger.error(f"Failed to send Slack notification for delivery completion: {e}")
        
        elif event_type == 'delivery.cancelled':
            current_app.logger.error(f"🚫 DELIVERY CANCELLED: {delivery.delivery_id}")
            current_app.logger.error(f"   Reason: {event_data.get('cancellation_reason', 'Unknown')}")
            
            delivery.cancelled_at = event_data.get('cancelled_at')
            delivery.cancellation_reason = event_data.get('cancellation_reason', 'Unknown')
            
            # ALERT: Delivery was cancelled - notify immediately
            try:
                order = delivery.order
                if order:
                    order.status = 'delivery_cancelled'
                    from services.slack_notifications import send_delivery_notification
                    send_delivery_notification(order, delivery, 'delivery_cancelled')
                    current_app.logger.error(f"🚨 SLACK ALERT SENT: Order {order.order_number} delivery cancelled!")
            except Exception as e:
                current_app.logger.error(f"Failed to send Slack notification for delivery cancellation: {e}")
        
        # Save changes
        db.session.commit()
        current_app.logger.info(f"📝 Updated delivery {delivery.delivery_id}: {old_status} → {new_status}")
        
        return True
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error processing Uber webhook event: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return False