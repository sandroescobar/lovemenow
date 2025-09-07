#!/usr/bin/env python3
"""
Raw SQL approach to merge Du Douche products
"""

from app import create_app
from routes import db
from sqlalchemy import text

def merge_du_douche_raw():
    """Merge Du Douche products using raw SQL"""
    
    app = create_app()
    with app.app_context():
        print("Merging Du Douche products using raw SQL...")
        
        try:
            # Step 1: Update the stone product name
            db.session.execute(text(
                "UPDATE products SET name = 'Du Douche', base_upc = '860008092000' WHERE id = 63"
            ))
            
            # Step 2: Get color IDs
            stone_color_result = db.session.execute(text(
                "SELECT id FROM colors WHERE name = 'Greige (Warm Gray)'"
            )).fetchone()
            
            midnight_color_result = db.session.execute(text(
                "SELECT id FROM colors WHERE name = 'Black'"
            )).fetchone()
            
            if not stone_color_result or not midnight_color_result:
                print("❌ Could not find required colors")
                return
            
            stone_color_id = stone_color_result[0]
            midnight_color_id = midnight_color_result[0]
            
            print(f"Stone color ID: {stone_color_id}, Midnight color ID: {midnight_color_id}")
            
            # Step 3: Update the stone variant to have the stone color
            db.session.execute(text(
                "UPDATE product_variants SET color_id = :color_id, variant_name = 'Stone' WHERE product_id = 63"
            ), {'color_id': stone_color_id})
            
            # Step 4: Create new variant for midnight (move the midnight variant to stone product)
            db.session.execute(text(
                "UPDATE product_variants SET product_id = 63, color_id = :color_id, variant_name = 'Midnight' WHERE product_id = 64"
            ), {'color_id': midnight_color_id})
            
            # Step 5: Update product_colors relationship for the main product
            # Remove existing relationships
            db.session.execute(text("DELETE FROM product_colors WHERE product_id = 63"))
            
            # Add both colors
            db.session.execute(text(
                "INSERT INTO product_colors (product_id, color_id) VALUES (63, :stone_color_id), (63, :midnight_color_id)"
            ), {
                'stone_color_id': stone_color_id,
                'midnight_color_id': midnight_color_id
            })
            
            # Step 6: Update any cart items that reference the midnight product
            db.session.execute(text(
                "UPDATE cart SET product_id = 63 WHERE product_id = 64"
            ))
            
            # Step 7: Update any wishlist items that reference the midnight product
            db.session.execute(text(
                "UPDATE wishlist SET product_id = 63 WHERE product_id = 64"
            ))
            
            # Step 8: Delete the midnight product (variants were already moved)
            db.session.execute(text("DELETE FROM products WHERE id = 64"))
            
            # Commit all changes
            db.session.commit()
            print("✅ Successfully merged Du Douche products!")
            
            # Verify the result
            result = db.session.execute(text(
                """
                SELECT p.name, pv.variant_name, c.name as color_name, pv.id as variant_id
                FROM products p
                JOIN product_variants pv ON p.id = pv.product_id
                LEFT JOIN colors c ON pv.color_id = c.id
                WHERE p.id = 63
                ORDER BY pv.id
                """
            )).fetchall()
            
            print("Merged product details:")
            for row in result:
                print(f"  Product: {row[0]}, Variant: {row[1]}, Color: {row[2]}, Variant ID: {row[3]}")
            
            # Check colors relationship
            colors_result = db.session.execute(text(
                """
                SELECT c.name
                FROM colors c
                JOIN product_colors pc ON c.id = pc.color_id
                WHERE pc.product_id = 63
                """
            )).fetchall()
            
            print(f"Product colors: {[row[0] for row in colors_result]}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error merging products: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    merge_du_douche_raw()