#!/usr/bin/env python3
"""
Correct merge: Combine Du Douche Stone and Midnight into ONE product with two variants
"""

from app import create_app
from routes import db
from sqlalchemy import text

def merge_du_douche_correctly():
    """Merge Du Douche products into one product with Stone and Midnight variants"""
    
    app = create_app()
    with app.app_context():
        print("Merging Du Douche products into ONE product with two variants...")
        
        try:
            # Step 1: Update the stone product to be the main "Du Douche" product
            db.session.execute(text(
                "UPDATE products SET name = 'Du Douche', base_upc = '860008092000' WHERE id = 63"
            ))
            print("✅ Updated main product name to 'Du Douche'")
            
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
            
            print(f"✅ Found colors - Stone: {stone_color_id}, Midnight: {midnight_color_id}")
            
            # Step 3: Update the stone variant (product_id=63) to have proper stone color
            db.session.execute(text(
                "UPDATE product_variants SET color_id = :color_id, variant_name = 'Stone' WHERE product_id = 63"
            ), {'color_id': stone_color_id})
            print("✅ Updated Stone variant")
            
            # Step 4: Move the midnight variant from product_id=64 to product_id=63 and set midnight color
            db.session.execute(text(
                "UPDATE product_variants SET product_id = 63, color_id = :color_id, variant_name = 'Midnight' WHERE product_id = 64"
            ), {'color_id': midnight_color_id})
            print("✅ Moved Midnight variant to main product")
            
            # Step 5: Update the main product's colors relationship
            # Remove existing relationships for product 63
            db.session.execute(text("DELETE FROM product_colors WHERE product_id = 63"))
            
            # Add both colors to the main product
            db.session.execute(text(
                "INSERT INTO product_colors (product_id, color_id) VALUES (63, :stone_color_id), (63, :midnight_color_id)"
            ), {
                'stone_color_id': stone_color_id,
                'midnight_color_id': midnight_color_id
            })
            print("✅ Updated product colors relationship")
            
            # Step 6: Update any cart items that reference the midnight product (product_id=64)
            cart_updates = db.session.execute(text(
                "UPDATE cart SET product_id = 63 WHERE product_id = 64"
            ))
            print(f"✅ Updated cart items (affected: {cart_updates.rowcount})")
            
            # Step 7: Update any wishlist items that reference the midnight product (product_id=64)
            wishlist_updates = db.session.execute(text(
                "UPDATE wishlist SET product_id = 63 WHERE product_id = 64"
            ))
            print(f"✅ Updated wishlist items (affected: {wishlist_updates.rowcount})")
            
            # Step 8: Clean up the old midnight product
            # First remove its color relationships
            db.session.execute(text("DELETE FROM product_colors WHERE product_id = 64"))
            print("✅ Removed old product color relationships")
            
            # Then delete the midnight product (its variant was already moved)
            db.session.execute(text("DELETE FROM products WHERE id = 64"))
            print("✅ Deleted old midnight product")
            
            # Commit all changes
            db.session.commit()
            print("\n🎉 Successfully merged Du Douche products!")
            
            # Verify the result
            print("\n📋 Verification:")
            result = db.session.execute(text(
                """
                SELECT p.id, p.name, pv.id as variant_id, pv.variant_name, c.name as color_name, pv.quantity_on_hand
                FROM products p
                JOIN product_variants pv ON p.id = pv.product_id
                LEFT JOIN colors c ON pv.color_id = c.id
                WHERE p.id = 63
                ORDER BY pv.id
                """
            )).fetchall()
            
            print("Merged product details:")
            for row in result:
                print(f"  Product {row[0]}: {row[1]}")
                print(f"    Variant {row[2]}: {row[3]} - {row[4]} (Stock: {row[5]})")
            
            # Check colors relationship
            colors_result = db.session.execute(text(
                """
                SELECT c.name
                FROM colors c
                JOIN product_colors pc ON c.id = pc.color_id
                WHERE pc.product_id = 63
                """
            )).fetchall()
            
            print(f"\nAvailable colors: {[row[0] for row in colors_result]}")
            
            # Check images
            images_result = db.session.execute(text(
                """
                SELECT pv.variant_name, pi.url, pi.is_primary
                FROM product_variants pv
                LEFT JOIN product_images pi ON pv.id = pi.product_variant_id
                WHERE pv.product_id = 63
                ORDER BY pv.variant_name, pi.is_primary DESC
                """
            )).fetchall()
            
            print(f"\nImages per variant:")
            current_variant = None
            for row in images_result:
                if row[0] != current_variant:
                    current_variant = row[0]
                    print(f"  {current_variant}:")
                if row[1]:
                    primary = " (PRIMARY)" if row[2] else ""
                    print(f"    - {row[1]}{primary}")
                else:
                    print(f"    - No images")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error merging products: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    merge_du_douche_correctly()