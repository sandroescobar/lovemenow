import sys
sys.path.insert(0, '/Users/sandrosMac/Desktop/pycharmProjects/LoveMeNow')

from app import create_app
from models import ProductVariant

app = create_app()
with app.app_context():
    # Update Vanilla variant (ID 115)
    vanilla = ProductVariant.query.filter_by(id=115).first()
    if vanilla:
        vanilla.in_stock = 1
        vanilla.quantity_on_hand = 1
        from routes import db
        db.session.commit()
        print(f"✅ Updated Vanilla variant (ID 115): in_stock=1, quantity_on_hand=1")
    else:
        print("❌ Vanilla variant not found")
