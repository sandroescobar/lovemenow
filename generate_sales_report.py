

import csv
import os
import sys
from decimal import Decimal

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Order, OrderItem, Product, Category

def generate_report():
    app = create_app()
    with app.app_context():
        # IDs provided by user (excluding 168)
        order_ids = [148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167]
        
        # Fetch orders, excluding those with total_amount == 0.51
        orders = Order.query.filter(Order.id.in_(order_ids)).filter(Order.total_amount != Decimal('0.51')).all()
        
        # Map to store: Category Name -> { Product Name -> Quantity }
        report_data = {}
        
        for order in orders:
            for item in order.items:
                product = Product.query.get(item.product_id)
                category_name = "Unknown"
                if product and product.category:
                    category_name = product.category.name
                
                if category_name not in report_data:
                    report_data[category_name] = {}
                
                prod_name = item.product_name or (product.name if product else "Unknown Product")
                report_data[category_name][prod_name] = report_data[category_name].get(prod_name, 0) + item.quantity
        
        # Write to CSV
        output_file = 'sales_by_category.csv'
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Category', 'Products', 'Total Quantity Sold'])
            
            # Sort by category
            for cat in sorted(report_data.keys()):
                # Format products as: "Product A (qty), Product B (qty)"
                product_details = []
                total_cat_qty = 0
                for prod in sorted(report_data[cat].keys()):
                    qty = report_data[cat][prod]
                    product_details.append(f"{prod} ({qty})")
                    total_cat_qty += qty
                
                writer.writerow([cat, ", ".join(product_details), total_cat_qty])
        
        print(f"✅ Report generated successfully: {output_file}")
        print(f"Included {len(orders)} orders.")

if __name__ == "__main__":
    generate_report()
