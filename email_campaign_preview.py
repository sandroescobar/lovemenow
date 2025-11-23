"""
Email Campaign Preview Tool
Shows all emails that would be sent before actually sending them
Separates: Abandoned/Incomplete Orders vs Repeat Customers
"""

import os
import sys
import stripe
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Setup Flask app context
sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

# Import from app.py (NOT app_factory.py) - app.py properly initializes db with db.init_app(app)
from app import create_app

app = create_app()

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Import models and db after app is created
from routes import db
from models import User, Order


class EmailCampaignPreview:
    """Preview email campaigns without sending anything"""
    
    def __init__(self):
        self.abandoned_checkout_emails = []
        self.repeat_customer_emails = []
    
    # ═════════════════════════════════════════════════════════════
    # ABANDONED/INCOMPLETE ORDERS (from Stripe)
    # ═════════════════════════════════════════════════════════════
    
    def fetch_abandoned_orders_from_stripe(self, days_back=90):
        """
        Query Stripe for failed/incomplete payment intents from last N days
        Returns list of dicts with customer info and payment details
        """
        print(f"🔍 Fetching abandoned/failed orders from Stripe (last {days_back} days)...\n")
        
        abandoned_orders = []
        cutoff_time = int((datetime.now() - timedelta(days=days_back)).timestamp())
        
        try:
            # Fetch all payment intents from the time period and filter locally
            all_intents = stripe.PaymentIntent.list(
                limit=100,
                created={'gte': cutoff_time},
                expand=['data.customer']
            )
            
            for pi in all_intents.data:
                # Only include non-succeeded intents (abandoned/incomplete)
                if pi.status in ['requires_action', 'requires_capture', 'requires_confirmation', 'requires_payment_method']:
                    customer_email = pi.get('receipt_email')
                    
                    # Try to get from customer object
                    if not customer_email and pi.customer:
                        try:
                            if isinstance(pi.customer, dict):
                                customer_email = pi.customer.get('email')
                            else:
                                customer_obj = stripe.Customer.retrieve(pi.customer)
                                customer_email = customer_obj.email
                        except:
                            pass
                    
                    customer_email = customer_email or 'unknown@example.com'
                    
                    # Get customer name
                    customer_name = 'Guest Customer'
                    if pi.customer:
                        try:
                            if isinstance(pi.customer, dict):
                                customer_name = pi.customer.get('name') or customer_email or 'Guest Customer'
                            else:
                                customer_obj = stripe.Customer.retrieve(pi.customer)
                                customer_name = customer_obj.name or customer_obj.email or 'Guest Customer'
                        except:
                            pass
                    
                    abandoned_orders.append({
                        'email': customer_email,
                        'name': customer_name,
                        'pi_id': pi.id,
                        'amount': pi.amount / 100,  # Convert from cents
                        'currency': (pi.currency or 'usd').upper(),
                        'status': pi.status,
                        'created': datetime.fromtimestamp(pi.created),
                        'reason': f"Status: {pi.status.replace('_', ' ').title()}"
                    })
            
            # Also check for failed charges
            try:
                failed_charges = stripe.Charge.list(
                    limit=100,
                    created={'gte': cutoff_time}
                )
                
                for charge in failed_charges.data:
                    # Only include failed charges
                    if charge.status == 'failed':
                        customer_email = charge.receipt_email or 'unknown@example.com'
                        
                        # Skip duplicates
                        if not any(a['pi_id'] == charge.payment_intent for a in abandoned_orders):
                            abandoned_orders.append({
                                'email': customer_email,
                                'name': charge.description or 'Guest Customer',
                                'pi_id': charge.payment_intent,
                                'amount': charge.amount / 100,
                                'currency': (charge.currency or 'usd').upper(),
                                'status': 'failed',
                                'created': datetime.fromtimestamp(charge.created),
                                'reason': charge.failure_message or 'Payment failed'
                            })
            except:
                pass  # Failed charges might not be accessible depending on Stripe account
            
            print(f"✅ Found {len(abandoned_orders)} abandoned/incomplete orders\n")
            return abandoned_orders
            
        except Exception as e:
            print(f"❌ Error fetching from Stripe: {e}\n")
            return []
    
    # ═════════════════════════════════════════════════════════════
    # REPEAT CUSTOMERS (from Database)
    # ═════════════════════════════════════════════════════════════
    
    def fetch_repeat_customers(self):
        """
        Query database for users who have completed orders (payment_status='paid')
        Returns list of dicts with customer info and order history
        """
        print(f"🔍 Fetching repeat customers from database...\n")
        
        repeat_customers = []
        
        try:
            # Get all users who have at least one completed order
            users_with_orders = db.session.query(User).join(
                Order, User.id == Order.user_id
            ).filter(
                Order.payment_status == 'paid'
            ).distinct().all()
            
            for user in users_with_orders:
                # Get user's order history
                orders = Order.query.filter_by(
                    user_id=user.id,
                    payment_status='paid'
                ).order_by(Order.created_at.desc()).all()
                
                if orders:
                    # Calculate total spent
                    total_spent = sum(float(order.total_amount or 0) for order in orders)
                    last_order = orders[0]
                    
                    repeat_customers.append({
                        'email': user.email,
                        'name': user.full_name,
                        'user_id': user.id,
                        'total_orders': len(orders),
                        'total_spent': total_spent,
                        'last_order_date': last_order.created_at,
                        'last_order_amount': float(last_order.total_amount or 0),
                        'marketing_opt_in': user.marketing_opt_in
                    })
            
            print(f"✅ Found {len(repeat_customers)} repeat customers\n")
            return repeat_customers
            
        except Exception as e:
            print(f"❌ Error fetching repeat customers: {e}\n")
            return []
    
    # ═════════════════════════════════════════════════════════════
    # DEDUPLICATION & FILTERING
    # ═════════════════════════════════════════════════════════════
    
    def deduplicate_and_filter(self, abandoned_orders, repeat_customers):
        """
        Remove duplicates (people in both lists)
        Filter respects marketing_opt_in for registered users
        """
        abandoned_emails = set()
        
        # Build abandoned checkout list (guests don't have marketing_opt_in)
        for order in abandoned_orders:
            email = order['email'].lower().strip()
            abandoned_emails.add(email)
            self.abandoned_checkout_emails.append(order)
        
        # Build repeat customer list (only those opted in)
        for customer in repeat_customers:
            email = customer['email'].lower().strip()
            
            # Skip if they're in the abandoned list (don't spam them)
            if email not in abandoned_emails:
                # Only add if they opted in, or if they don't have that field (guest)
                if customer.get('marketing_opt_in', True):
                    self.repeat_customer_emails.append(customer)
    
    # ═════════════════════════════════════════════════════════════
    # DISPLAY PREVIEW
    # ═════════════════════════════════════════════════════════════
    
    def print_preview(self):
        """Pretty-print the email campaign preview"""
        
        print("\n")
        print("=" * 80)
        print("EMAIL CAMPAIGN PREVIEW - NO EMAILS SENT YET".center(80))
        print("=" * 80)
        print()
        
        # ─ ABANDONED CHECKOUT RECOVERY ─
        print("📧 CAMPAIGN 1: ABANDONED/INCOMPLETE CHECKOUT RECOVERY")
        print("─" * 80)
        
        if self.abandoned_checkout_emails:
            for idx, order in enumerate(self.abandoned_checkout_emails, 1):
                print(f"\n[{idx}] {order['email']}")
                print(f"    Name: {order['name']}")
                print(f"    Failed Payment: {order['created'].strftime('%Y-%m-%d %H:%M')}")
                print(f"    Amount: ${order['amount']:.2f} {order['currency']}")
                print(f"    Status: {order['reason']}")
            
            print(f"\n✅ Total: {len(self.abandoned_checkout_emails)} emails in this campaign")
        else:
            print("\n(No abandoned orders found)")
        
        print()
        print()
        
        # ─ REPEAT CUSTOMER RE-ENGAGEMENT ─
        print("📧 CAMPAIGN 2: REPEAT CUSTOMER RE-ENGAGEMENT")
        print("─" * 80)
        
        if self.repeat_customer_emails:
            for idx, customer in enumerate(self.repeat_customer_emails, 1):
                print(f"\n[{idx}] {customer['email']}")
                print(f"    Name: {customer['name']}")
                print(f"    Last Purchase: {customer['last_order_date'].strftime('%Y-%m-%d')}")
                print(f"    Total Spent: ${customer['total_spent']:.2f}")
                print(f"    Orders: {customer['total_orders']}")
                print(f"    Last Order: ${customer['last_order_amount']:.2f}")
            
            print(f"\n✅ Total: {len(self.repeat_customer_emails)} emails in this campaign")
        else:
            print("\n(No repeat customers found)")
        
        print()
        print()
        
        # ─ SUMMARY ─
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        total = len(self.abandoned_checkout_emails) + len(self.repeat_customer_emails)
        print(f"Total emails to be sent: {total}")
        print(f"  • Abandoned Checkout Recovery: {len(self.abandoned_checkout_emails)}")
        print(f"  • Repeat Customer Re-engagement: {len(self.repeat_customer_emails)}")
        print("=" * 80)
        print()
        
        return total
    
    def export_to_csv(self, filename='email_campaign_preview.csv'):
        """Export email lists to CSV for review"""
        import csv
        
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write abandoned checkout section
            writer.writerow(['ABANDONED CHECKOUT RECOVERY'])
            writer.writerow(['Email', 'Name', 'Failed Date', 'Amount', 'Status'])
            for order in self.abandoned_checkout_emails:
                writer.writerow([
                    order['email'],
                    order['name'],
                    order['created'].strftime('%Y-%m-%d'),
                    f"${order['amount']:.2f}",
                    order['reason']
                ])
            
            writer.writerow([])  # Blank line
            
            # Write repeat customers section
            writer.writerow(['REPEAT CUSTOMER RE-ENGAGEMENT'])
            writer.writerow(['Email', 'Name', 'Last Purchase', 'Total Spent', 'Orders'])
            for customer in self.repeat_customer_emails:
                writer.writerow([
                    customer['email'],
                    customer['name'],
                    customer['last_order_date'].strftime('%Y-%m-%d'),
                    f"${customer['total_spent']:.2f}",
                    customer['total_orders']
                ])
        
        print(f"✅ Preview exported to: {filepath}\n")


def main():
    """Run the email campaign preview"""
    
    with app.app_context():
        preview = EmailCampaignPreview()
        
        # Fetch data
        abandoned = preview.fetch_abandoned_orders_from_stripe(days_back=90)
        repeat = preview.fetch_repeat_customers()
        
        # Process and deduplicate
        preview.deduplicate_and_filter(abandoned, repeat)
        
        # Display preview
        total = preview.print_preview()
        
        # Export to CSV
        preview.export_to_csv()
        
        if total == 0:
            print("⚠️  No emails to send. Check your data in Stripe and database.\n")
        else:
            print("📋 Review the lists above. When ready to send, we can run the actual campaign.")
            print("   (No emails have been sent yet!)\n")


if __name__ == '__main__':
    main()