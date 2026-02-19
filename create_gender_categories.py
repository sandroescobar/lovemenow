from app import app, db
from models import Category
import os

def create_gender_categories():
    print("🚀 Starting gender category migration...")
    
    with app.app_context():
        # 1. Check/Create 'Men' category
        men = Category.query.filter_by(slug='men').first()
        if not men:
            men = Category(name='Men', slug='men')
            db.session.add(men)
            db.session.flush() # Get the ID
            print(f"✓ Created 'Men' category (ID: {men.id})")
        else:
            print(f"- 'Men' category already exists (ID: {men.id})")

        # 2. Check/Create 'Women' category
        women = Category.query.filter_by(slug='women').first()
        if not women:
            women = Category(name='Women', slug='women')
            db.session.add(women)
            db.session.flush() # Get the ID
            print(f"✓ Created 'Women' category (ID: {women.id})")
        else:
            print(f"- 'Women' category already exists (ID: {women.id})")

        try:
            db.session.commit()
            print("✅ Gender categories created successfully!")
            
            # Print mapping for reference
            print("\n📝 Category Mapping Reference:")
            all_cats = Category.query.all()
            for cat in all_cats:
                parent = f" (Parent: {cat.parent.name})" if cat.parent else ""
                print(f"  - {cat.name}: {cat.id}{parent}")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error committing changes: {str(e)}")

if __name__ == "__main__":
    create_gender_categories()
