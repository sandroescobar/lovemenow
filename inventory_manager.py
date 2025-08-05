#!/usr/bin/env python3
"""
Inventory Management Utility for LoveMeNow
Simple command-line tool to manage product inventory
"""

import sys
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Configure logging for inventory operations
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Product, db
from app import create_app

load_dotenv()

def with_app_context(func):
    """Decorator to run function within Flask app context"""
    def wrapper(*args, **kwargs):
        app = create_app()
        with app.app_context():
            return func(*args, **kwargs)
    return wrapper

@with_app_context
def list_products():
    """List all products with their current stock levels"""
    products = db.session.query(Product).order_by(Product.id).all()
    
    print("\n" + "="*80)
    print("PRODUCT INVENTORY REPORT")
    print("="*80)
    print(f"{'ID':<5} {'Name':<30} {'Stock':<8} {'In Stock':<10} {'Price':<10}")
    print("-"*80)
    
    for product in products:
        status = "Yes" if product.is_available else "No"
        print(f"{product.id:<5} {product.name[:29]:<30} {product.quantity_on_hand:<8} {status:<10} ${product.price:<9.2f}")
    
    print("-"*80)
    total_products = len(products)
    in_stock_count = sum(1 for p in products if p.is_available)
    out_of_stock_count = total_products - in_stock_count
    
    print(f"Total Products: {total_products}")
    print(f"In Stock: {in_stock_count}")
    print(f"Out of Stock: {out_of_stock_count}")
    print("="*80)

@with_app_context
def update_stock(product_id, new_quantity):
    """Update stock for a specific product"""
    try:
        product = db.session.query(Product).get(product_id)
        if not product:
            print(f"❌ Product with ID {product_id} not found!")
            return False
        
        old_quantity = product.quantity_on_hand
        old_status = product.is_available
        
        # Update quantity
        product.quantity_on_hand = new_quantity
        
        # Update in_stock status based on quantity
        if new_quantity > 0:
            product.in_stock = True
        else:
            product.in_stock = False
        
        db.session.commit()
        
        print(f"✅ Updated {product.name}:")
        print(f"   Stock: {old_quantity} → {new_quantity}")
        print(f"   Available: {old_status} → {product.is_available}")
        
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating product: {str(e)}")
        return False

@with_app_context
def restock_all(quantity=10):
    """Restock all products to a specific quantity"""
    try:
        products = db.session.query(Product).all()
        updated_count = 0
        
        for product in products:
            product.quantity_on_hand = quantity
            product.in_stock = True
            updated_count += 1
        
        db.session.commit()
        print(f"✅ Restocked {updated_count} products to {quantity} units each")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error restocking products: {str(e)}")
        return False

@with_app_context
def find_out_of_stock():
    """Find all out of stock products"""
    products = db.session.query(Product).filter(
        (Product.quantity_on_hand <= 0) | (Product.in_stock == False)
    ).all()
    
    if not products:
        print("✅ All products are in stock!")
        return
    
    print(f"\n❌ Found {len(products)} out of stock products:")
    print("-"*60)
    for product in products:
        print(f"ID {product.id}: {product.name} (Stock: {product.quantity_on_hand})")
    print("-"*60)

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("LoveMeNow Inventory Manager")
        print("Usage:")
        print("  python inventory_manager.py list                    - List all products")
        print("  python inventory_manager.py update <id> <quantity>  - Update specific product")
        print("  python inventory_manager.py restock [quantity]      - Restock all products (default: 10)")
        print("  python inventory_manager.py out-of-stock           - Find out of stock products")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_products()
    
    elif command == "update":
        if len(sys.argv) != 4:
            print("Usage: python inventory_manager.py update <product_id> <new_quantity>")
            return
        
        try:
            product_id = int(sys.argv[2])
            quantity = int(sys.argv[3])
            update_stock(product_id, quantity)
        except ValueError:
            print("❌ Product ID and quantity must be numbers!")
    
    elif command == "restock":
        quantity = 10  # default
        if len(sys.argv) > 2:
            try:
                quantity = int(sys.argv[2])
            except ValueError:
                print("❌ Quantity must be a number!")
                return
        
        restock_all(quantity)
    
    elif command == "out-of-stock":
        find_out_of_stock()
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Available commands: list, update, restock, out-of-stock")

if __name__ == "__main__":
    main()