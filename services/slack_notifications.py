"""
Slack notification service for order alerts
"""
import requests
import json
from flask import current_app
from typing import Dict, List, Optional
from datetime import datetime
import pytz


class SlackNotificationService:
    """Service for sending Slack notifications about orders"""
    
    def __init__(self):
        self.webhook_url = current_app.config.get('SLACK_WEBHOOK_URL')
        current_app.logger.info(f"🔍 SLACK DEBUG - Webhook URL configured: {'YES' if self.webhook_url else 'NO'}")
        if self.webhook_url:
            current_app.logger.info(f"🔍 SLACK DEBUG - Webhook URL: {self.webhook_url[:50]}...{self.webhook_url[-10:]}")
    
    def send_order_notification(self, order, order_items: List[Dict]) -> bool:
        """
        Send a Slack notification for a new paid order
        
        Args:
            order: Order model instance
            order_items: List of order items with product details
            
        Returns:
            bool: True if notification sent successfully, False otherwise
        """
        if not self.webhook_url:
            current_app.logger.warning("Slack webhook URL not configured, skipping notification")
            return False
        
        try:
            # Build the Slack message
            message = self._build_order_message(order, order_items)
            
            # Send to Slack
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )
            
            if response.status_code == 200:
                current_app.logger.info(f"Slack notification sent successfully for order {order.order_number}")
                return True
            else:
                current_app.logger.error(f"Failed to send Slack notification: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            current_app.logger.error(f"Error sending Slack notification: {str(e)}")
            return False
    
    def _build_order_message(self, order, order_items: List[Dict]) -> Dict:
        """Build the Slack message payload"""
        
        # Determine order type and build appropriate message
        is_delivery = order.delivery_type == 'delivery'
        
        # Build product list
        products_text = ""
        for item in order_items:
            product = item['product']
            quantity = item['quantity']
            
            # Get product UPC and wholesale_id if available
            upc = getattr(product, 'upc', 'N/A') or 'N/A'
            wholesale_id = getattr(product, 'wholesale_id', 'N/A') or 'N/A'
            
            products_text += f"• {product.name}\n"
            products_text += f"  - Wholesale ID: {wholesale_id}\n"
            products_text += f"  - UPC: {upc}\n"
            products_text += f"  - Quantity: {quantity}\n\n"
        
        # Build customer info based on delivery type
        if is_delivery:
            # For delivery orders
            customer_info = f"""
👤 *Customer:* {order.full_name}
📧 *Email:* {order.email}
📱 *Phone:* {getattr(order, 'phone', 'Not provided')}
📍 *Delivery Address:* {order.shipping_address}
{f"   {order.shipping_suite}" if order.shipping_suite else ""}
   {order.shipping_city}, {order.shipping_state} {order.shipping_zip}
"""
            
            # Add Uber tracking link if available
            uber_link = ""
            if hasattr(order, 'delivery') and order.delivery and hasattr(order.delivery, 'tracking_url') and order.delivery.tracking_url:
                uber_link = f"\n🚚 *Track Driver:* {order.delivery.tracking_url}"
            
        else:
            # For pickup orders
            customer_info = f"""
👤 *Customer:* {order.full_name}
📧 *Email:* {order.email}
📱 *Phone:* {getattr(order, 'phone', 'Not provided')}
"""
            uber_link = ""
        
        # Convert UTC time to Eastern Time
        utc_time = order.created_at
        if utc_time.tzinfo is None:
            # If no timezone info, assume UTC
            utc_time = pytz.UTC.localize(utc_time)
        
        # Convert to Eastern Time
        eastern = pytz.timezone('US/Eastern')
        local_time = utc_time.astimezone(eastern)
        
        # Build the main message
        pin_text = ""
        if getattr(order, 'pin_code', None):
            if order.pin_code == "PIN Delivery Requested":
                pin_text = f"🚨 *PIN DELIVERY REQUESTED:* `Customer must provide PIN to driver`"
            else:
                pin_text = f"🔐 *PIN:* `{order.pin_code}`"

        message_text = f"""🛍️ *NEW ORDER - {order.order_number}*

{customer_info}
📦 *Items:*
{products_text}
🚚 *Fulfillment:* {"🚗 Delivery" if is_delivery else "🏪 Store Pickup"}
💰 *Total:* ${float(order.total_amount):.2f}
{pin_text}
{uber_link}

⏰ *Order Time:* {local_time.strftime('%I:%M %p on %m/%d/%Y')} EST
"""
        
        # Create Slack message payload
        return {
            "text": f"New Order: {order.order_number}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message_text
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"🏪 {current_app.config.get('STORE_NAME', 'LoveMeNow')} | Order #{order.order_number}"
                        }
                    ]
                }
            ]
        }
    
    def send_manual_delivery_alert(self, order, reason: str, quote_id: Optional[str] = None) -> bool:
        if not self.webhook_url:
            current_app.logger.warning("Slack webhook URL not configured, skipping manual delivery alert")
            return False
        address_lines = f"{order.shipping_address}\n"
        if order.shipping_suite:
            address_lines += f"   {order.shipping_suite}\n"
        address_lines += f"   {order.shipping_city}, {order.shipping_state} {order.shipping_zip}"
        details = []
        if quote_id:
            details.append(f"*Quote ID:* {quote_id}")
        if reason:
            details.append(f"*Reason:* {reason}")
        details_text = "\n".join(details) if details else "*Reason:* Manual courier dispatch required"
        
        pin_text = ""
        if getattr(order, 'pin_code', None):
            if order.pin_code == "PIN Delivery Requested":
                pin_text = f"🚨 *PIN DELIVERY REQUESTED:* `Customer must provide PIN to driver`"
            else:
                pin_text = f"🔐 *Verification PIN:* `{order.pin_code}`"

        manual_text = f"""⚠️ *MANUAL DELIVERY REQUIRED*

*Order:* {order.order_number}
*Customer:* {order.full_name}
*Phone:* {getattr(order, 'phone', 'Not provided')}
*Address:*
{address_lines}
{pin_text}
{details_text}
*Total:* ${float(order.total_amount):.2f}
"""
        message = {
            "text": f"Manual Delivery Required: {order.order_number}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": manual_text
                    }
                },
                {
                    "type": "divider"
                }
            ]
        }
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )
            if response.status_code == 200:
                current_app.logger.info(f"Manual delivery alert sent for order {order.order_number}")
                return True
            current_app.logger.error(f"Failed to send manual delivery alert: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            current_app.logger.error(f"Error sending manual delivery alert: {str(e)}")
            return False
    
    def send_test_notification(self) -> bool:
        """Send a test notification to verify Slack integration"""
        if not self.webhook_url:
            current_app.logger.warning("Slack webhook URL not configured")
            return False
        
        test_message = {
            "text": "🧪 Slack Integration Test",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🧪 *Slack Integration Test*\n\nThis is a test message to verify that Slack notifications are working correctly for LoveMeNow order alerts.\n\n✅ If you can see this message, the integration is working!"
                    }
                }
            ]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=test_message,
                timeout=10
            )
            
            if response.status_code == 200:
                current_app.logger.info("Slack test notification sent successfully")
                return True
            else:
                current_app.logger.error(f"Failed to send Slack test notification: {response.status_code}")
                return False
                
        except Exception as e:
            current_app.logger.error(f"Error sending Slack test notification: {str(e)}")
            return False


def send_order_notification(order, order_items: List[Dict]) -> bool:
    """
    Convenience function to send order notification
    
    Args:
        order: Order model instance
        order_items: List of order items with product details
        
    Returns:
        bool: True if notification sent successfully
    """
    service = SlackNotificationService()
    return service.send_order_notification(order, order_items)


def send_manual_delivery_alert(order, reason: str, quote_id: Optional[str] = None) -> bool:
    service = SlackNotificationService()
    return service.send_manual_delivery_alert(order, reason, quote_id)


def send_test_notification() -> bool:
    """
    Convenience function to send test notification
    
    Returns:
        bool: True if test notification sent successfully
    """
    service = SlackNotificationService()
    return service.send_test_notification()


def send_delivery_notification(order, delivery, event_type: str) -> bool:
    """
    Send delivery status update notifications to Slack
    
    Args:
        order: Order model instance
        delivery: UberDelivery model instance
        event_type: Type of delivery event ('driver_assigned', 'delivery_completed', 'delivery_cancelled', etc.)
        
    Returns:
        bool: True if notification sent successfully
    """
    webhook_url = current_app.config.get('SLACK_WEBHOOK_URL')
    
    if not webhook_url:
        current_app.logger.warning("Slack webhook URL not configured, skipping delivery notification")
        return False
    
    try:
        # Build delivery status message
        if event_type == 'driver_assigned':
            color = "good"  # Green
            status_emoji = "🚗"
            message_title = f"*DRIVER ASSIGNED* - Order {order.order_number}"
            
            # Parse driver details if available
            driver_info = ""
            if delivery.driver_details:
                try:
                    import json
                    driver_data = json.loads(delivery.driver_details)
                    driver_info = f"""
👤 *Driver:* {driver_data.get('name', 'N/A')}
⭐ *Rating:* {driver_data.get('rating', 'N/A')}
🚙 *Vehicle:* {driver_data.get('vehicle', 'N/A')}
📋 *License Plate:* {driver_data.get('license_plate', 'N/A')}
"""
                except:
                    pass
            
            message_body = f"""Order {order.order_number} - Driver has accepted and is on the way!

🏪 *From:* LoveMeNow
📍 *To:* {order.shipping_address}
{f"   {order.shipping_suite}" if order.shipping_suite else ""}
   {order.shipping_city}, {order.shipping_state} {order.shipping_zip}

{driver_info}

🔗 *Track:* {delivery.tracking_url if delivery.tracking_url else 'N/A'}
"""
        
        elif event_type == 'delivery_completed':
            color = "good"  # Green
            status_emoji = "✅"
            message_title = f"*DELIVERY COMPLETED* - Order {order.order_number}"
            message_body = f"""Order {order.order_number} has been successfully delivered!

📍 *Delivery Address:* {order.shipping_address}
{f"   {order.shipping_suite}" if order.shipping_suite else ""}
   {order.shipping_city}, {order.shipping_state} {order.shipping_zip}

👤 *Customer:* {order.full_name}
💰 *Total:* ${float(order.total_amount):.2f}
"""
        
        elif event_type == 'delivery_cancelled':
            color = "danger"  # Red
            status_emoji = "🚫"
            message_title = f"*⚠️  DELIVERY CANCELLED* - Order {order.order_number}"
            cancellation_reason = getattr(delivery, 'cancellation_reason', 'Unknown reason')
            message_body = f"""⚠️  Order {order.order_number} delivery was CANCELLED!

❌ *Reason:* {cancellation_reason}

📍 *Delivery Address:* {order.shipping_address}
{f"   {order.shipping_suite}" if order.shipping_suite else ""}
   {order.shipping_city}, {order.shipping_state} {order.shipping_zip}

👤 *Customer:* {order.full_name}
📞 *Phone:* {getattr(order, 'phone', 'Not provided')}
💰 *Total:* ${float(order.total_amount):.2f}

⚠️  *ACTION REQUIRED:* Contact customer immediately to reschedule or arrange alternative delivery
"""
        
        else:
            # Generic delivery event
            color = "#0099FF"
            status_emoji = "📦"
            message_title = f"*DELIVERY UPDATE* - Order {order.order_number}"
            message_body = f"""Order {order.order_number}: {event_type.replace('_', ' ')}

📍 *Address:* {order.shipping_address}
👤 *Customer:* {order.full_name}
"""
        
        # Create Slack message
        message = {
            "text": message_title,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message_title
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message_body
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"{status_emoji} Delivery ID: `{delivery.delivery_id}` | Order: `{order.order_number}`"
                        }
                    ]
                }
            ]
        }
        
        # Send to Slack
        response = requests.post(webhook_url, json=message, timeout=10)
        
        if response.status_code == 200:
            current_app.logger.info(f"✅ Delivery notification sent: {event_type} for order {order.order_number}")
            return True
        else:
            current_app.logger.error(f"Failed to send delivery notification: {response.status_code}")
            return False
            
    except Exception as e:
        current_app.logger.error(f"Error sending delivery notification: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return False