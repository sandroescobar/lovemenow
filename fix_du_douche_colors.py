#!/usr/bin/env python3
"""
Fix Du-Douche color variants
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DB_URL = os.getenv('DB_URL')
if not DB_URL:
    print("Error: DB_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

def fix_du_douche_colors():
    """Fix Du-Douche color variants"""
    session = Session()
    
    try:
        # Find available colors
        result = session.execute(text("SELECT id, name, hex FROM colors ORDER BY name"))
        colors = result.fetchall()
        print("Available colors:")
        for color in colors:
            print(f"  {color.id}: {color.name} ({color.hex})")
        
        # Find Du-Douche variants
        result = session.execute(text("""
            SELECT pv.id, pi.url
            FROM product_variants pv
            JOIN products p ON pv.product_id = p.id
            LEFT JOIN product_images pi ON pi.product_variant_id = pv.id
            WHERE p.upc = '860008092007'
            ORDER BY pv.id, pi.id
        """))
        
        variants = result.fetchall()
        print(f"\nDu-Douche variants:")
        
        # Group by variant
        variant_data = {}
        for row in variants:
            if row.id not in variant_data:
                variant_data[row.id] = []
            if row.url:
                variant_data[row.id].append(row.url)
        
        for variant_id, images in variant_data.items():
            print(f"  Variant {variant_id}:")
            for img in images:
                print(f"    {img}")
        
        # Assign colors based on UPC folders
        # 860008092007 = Black (Midnight)
        # 860008092021 = Beige (Greige/Warm Gray)
        
        # Find Midnight and Greige colors
        result = session.execute(text("SELECT id, name FROM colors WHERE name IN ('Midnight', 'Greige (Warm Gray)')"))
        color_map = {row.name: row.id for row in result.fetchall()}
        
        print(f"\nColor mapping: {color_map}")
        
        # Update variants with colors
        for variant_id, images in variant_data.items():
            if any('860008092007' in img for img in images):
                # This is the black variant
                if 'Midnight' in color_map:
                    session.execute(text("""
                        UPDATE product_variants 
                        SET color_id = :color_id 
                        WHERE id = :variant_id
                    """), {'color_id': color_map['Midnight'], 'variant_id': variant_id})
                    print(f"  ✅ Assigned Midnight to variant {variant_id}")
                    
            elif any('860008092021' in img for img in images):
                # This is the beige variant
                if 'Greige (Warm Gray)' in color_map:
                    session.execute(text("""
                        UPDATE product_variants 
                        SET color_id = :color_id 
                        WHERE id = :variant_id
                    """), {'color_id': color_map['Greige (Warm Gray)'], 'variant_id': variant_id})
                    print(f"  ✅ Assigned Greige to variant {variant_id}")
        
        session.commit()
        print("\n🎉 Du-Douche color variants fixed!")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    fix_du_douche_colors()