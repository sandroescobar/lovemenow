# email_marketing.py
from datetime import datetime
from flask import render_template, current_app
from models import User, Product, db
from email_utils import send_email_sendlayer


class EmailMarketing:
    """Email marketing service for LoveMeNow"""
    
    @staticmethod
    def get_opted_in_users():
        """Get all users who have opted into marketing emails"""
        return User.query.filter_by(marketing_opt_in=True, active=True).all()
    
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email when user opts into marketing"""
        try:
            html_body = render_template("emails/welcome.html", user=user)
            
            result = send_email_sendlayer(
                to_name=user.full_name,
                to_email=user.email,
                subject="🎉 Welcome to LoveMeNow VIP Club!",
                html_body=html_body
            )
            
            current_app.logger.info(f"Welcome email sent to {user.email}")
            return result
            
        except Exception as e:
            current_app.logger.error(f"Failed to send welcome email to {user.email}: {e}")
            return None
    
    @staticmethod
    def send_new_product_announcement(product_id):
        """Send new product announcement to all opted-in users"""
        product = Product.query.get(product_id)
        if not product:
            current_app.logger.error(f"Product {product_id} not found")
            return
        
        users = EmailMarketing.get_opted_in_users()
        sent_count = 0
        
        for user in users:
            try:
                html_body = render_template("emails/new_product.html", 
                                          user=user, 
                                          product=product)
                
                send_email_sendlayer(
                    to_name=user.full_name,
                    to_email=user.email,
                    subject=f"🆕 New Arrival: {product.name}",
                    html_body=html_body
                )
                sent_count += 1
                
            except Exception as e:
                current_app.logger.error(f"Failed to send new product email to {user.email}: {e}")
        
        current_app.logger.info(f"New product announcement sent to {sent_count} users")
        return sent_count
    
    @staticmethod
    def send_sale_announcement(sale_title, sale_description, discount_percent=None, products=None):
        """Send sale announcement to all opted-in users"""
        users = EmailMarketing.get_opted_in_users()
        sent_count = 0
        
        # If specific products aren't provided, get featured products
        if not products:
            products = Product.query.limit(6).all()
        
        for user in users:
            try:
                html_body = render_template("emails/sale.html", 
                                          user=user,
                                          sale_title=sale_title,
                                          sale_description=sale_description,
                                          discount_percent=discount_percent,
                                          products=products)
                
                subject = f"🔥 {sale_title}"
                if discount_percent:
                    subject += f" - {discount_percent}% OFF!"
                
                send_email_sendlayer(
                    to_name=user.full_name,
                    to_email=user.email,
                    subject=subject,
                    html_body=html_body
                )
                sent_count += 1
                
            except Exception as e:
                current_app.logger.error(f"Failed to send sale email to {user.email}: {e}")
        
        current_app.logger.info(f"Sale announcement sent to {sent_count} users")
        return sent_count
    
    @staticmethod
    def send_newsletter(subject, content, featured_products=None):
        """Send custom newsletter to all opted-in users"""
        users = EmailMarketing.get_opted_in_users()
        sent_count = 0
        
        if not featured_products:
            featured_products = Product.query.limit(4).all()
        
        for user in users:
            try:
                html_body = render_template("emails/newsletter.html", 
                                          user=user,
                                          content=content,
                                          featured_products=featured_products)
                
                send_email_sendlayer(
                    to_name=user.full_name,
                    to_email=user.email,
                    subject=subject,
                    html_body=html_body
                )
                sent_count += 1
                
            except Exception as e:
                current_app.logger.error(f"Failed to send newsletter to {user.email}: {e}")
        
        current_app.logger.info(f"Newsletter sent to {sent_count} users")
        return sent_count
    
    @staticmethod
    def send_abandoned_cart_reminder(user, cart_items):
        """Send abandoned cart reminder (for future implementation)"""
        try:
            html_body = render_template("emails/abandoned_cart.html", 
                                      user=user,
                                      cart_items=cart_items)
            
            send_email_sendlayer(
                to_name=user.full_name,
                to_email=user.email,
                subject="💕 You left something special behind...",
                html_body=html_body
            )
            
            current_app.logger.info(f"Abandoned cart email sent to {user.email}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send abandoned cart email to {user.email}: {e}")
            return False