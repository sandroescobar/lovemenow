"""
Slack notification service for order alerts
"""
import requests
import json
from flask import current_app
from typing import Dict, List, Optional


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
        
        # Build the main message
        message_text = f"""🛍️ *NEW ORDER - {order.order_number}*

{customer_info}
📦 *Items:*
{products_text}
🚚 *Fulfillment:* {"🚗 Delivery" if is_delivery else "🏪 Store Pickup"}
💰 *Total:* ${float(order.total_amount):.2f}
{uber_link}

⏰ *Order Time:* {order.created_at.strftime('%I:%M %p on %m/%d/%Y')}
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


def send_test_notification() -> bool:
    """
    Convenience function to send test notification
    
    Returns:
        bool: True if test notification sent successfully
    """
    service = SlackNotificationService()
    return service.send_test_notification()