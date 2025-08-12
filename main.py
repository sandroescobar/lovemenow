import os
from urllib.parse import urlencode
from datetime import timedelta
from flask import Flask, render_template, redirect, request, url_for, flash
from dotenv import load_dotenv
from flask_login import login_user, logout_user
from sqlalchemy import text
from routes import db, bcrypt, login_mgr
from models     import User
from flask_talisman import Talisman
# ← import AFTER extensions declared

# ── env vars ─────────────────────────────────────────────────
load_dotenv()                        # reads .env in local dev

# ── Flask app ────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"]              = os.getenv("SECRET_KEY", "dev_key")
app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=1)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DB_URL",
    "mysql+pymysql://root:Ae9542790079@127.0.0.1:3306/love_me_now_db",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ── DISABLE CSP TEMPORARILY TO TEST STRIPE ─────────────────────────────
print("🚫 DISABLING CSP TEMPORARILY TO TEST STRIPE")
print("🚫 This will allow Stripe frames to load without CSP blocking")
# CSP disabled - no Talisman configuration applied

# ── plug extensions into this single app ─────────────────────
db.init_app(app)
bcrypt.init_app(app)
login_mgr.init_app(app)
login_mgr.login_view    = "login_modal"
login_mgr.login_message = "Please log in first."

# ── loader callback required by Flask‑Login ──────────────────
@login_mgr.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))

# ── routes (very trimmed) ─────────────────────────────────────
@app.route("/")
def index():
    try:
        # Import models here to avoid circular imports
        from models import Product, Category
        
        # Get featured products (limit to 3)
        featured_products = (
            Product.query
            .filter(Product.in_stock == True, Product.quantity_on_hand > 0)
            .limit(3)
            .all()
        )
        
        return render_template("index.html", featured_products=featured_products)
    except Exception as e:
        # If there's any error, return template with empty products
        return render_template("index.html", featured_products=[])

@app.route("/products", methods = ['GET', 'POST'])
def products():
    return render_template("products.html")

@app.route("/register_modal", methods = ['GET', 'POST'])
def register_modal():

    if request.method == 'POST' and 'full_name' in request.form and 'email' in request.form and 'password' in request.form and 'passwordCon' in request.form:
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        password_confirmation = request.form['passwordCon']

        if password != password_confirmation:
            flash("Passwords do not match")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered", "warning")
            return redirect(url_for("register_modal"))

        user = User(email=email, full_name=full_name)
        user.password = password  # triggers the bcrypt‑hash setter
        db.session.add(user)
        db.session.commit()

    return redirect(url_for("index"))


@app.route("/login_modal", methods = ['GET', 'POST'])
def login_modal():
    msg = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            remember_flag = "remember" in request.form  # True if box checked
            login_user(user, remember=remember_flag)
            flash("you've logged in successfully", "success")
            return redirect(url_for("index"))

        flash("Incorrect email or password!", "danger")

    qs = urlencode({"modal": "login"})
    return redirect(f"{url_for('index')}?{qs}")



@app.route("/logged_in_modal", methods = ['GET', 'POST'])
def logged_in_modal():
    return render_template("logged_in_modal.html",logged_in=User.is_authenticated)


@app.route("/user_profile", methods = ['GET', 'POST'])
def user_profile():
    return render_template("user_profile.html")

@app.route("/logout")
def logout():
    logout_user()              # clears the session
    flash("You’ve been logged out.", "success")
    return redirect(url_for("index"))

@app.route("/user_profile_button")
def user_profile_button():

    return redirect(url_for('user_profile'))

@app.route("/miami-map")
def miami_map():
    """Generate and serve Miami coverage map"""
    try:
        import folium
        
        # Create map centered on Miami
        m = folium.Map(
            location=[25.756, -80.26],      # roughly Doral / middle of the metro
            zoom_start=9,                   # shows Homestead ↔ Fort Lauderdale in one view
            control_scale=True,             # little km / mi ruler bottom-left
            tiles="cartodbpositron"         # clean, grey OSM basemap
        )
        
        # Add coverage area markers
        cities = {
            # Miami-Dade
            "Downtown Miami":   (25.7743, -80.1937),
            "Brickell":        (25.7601, -80.1951),
            "Wynwood":         (25.8005, -80.1990),
            "Little Haiti":    (25.8259, -80.2003),
            "Coral Gables":    (25.7215, -80.2684),
            "West Miami":      (25.7587, -80.2978),
            "Sweetwater":      (25.7631, -80.3720),
            "Doral":           (25.8195, -80.3553),
            "Miami Beach":     (25.7906, -80.1300),
            "North Miami":     (25.8901, -80.1867),
            "Miami Gardens":   (25.9420, -80.2456),
            "Hialeah":         (25.8576, -80.2781),
            "Kendall":         (25.6793, -80.3173),
            "South Miami":     (25.7079, -80.2939),
            "Homestead":       (25.4687, -80.4776),
            
            # Broward
            "Pembroke Pines":  (26.0086, -80.3570),
            "Miramar":         (25.9826, -80.3431),
            "Davie":           (26.0814, -80.2806),
            "Hollywood":       (26.0112, -80.1495),
            "Aventura":        (25.9565, -80.1429),
            "Fort Lauderdale": (26.1224, -80.1373)
        }
        
        for name, (lat, lng) in cities.items():
            folium.Marker(
                location=(lat, lng),
                tooltip=name,
                popup=f"We deliver to {name}!"
            ).add_to(m)
        
        # Add store location - Miami Vape Smoke Shop (pickup location)
        store_lat, store_lng = 25.70816, -80.407   # 351 NE 79th St, Miami FL 33138
        folium.Marker(
            location=(store_lat, store_lng),
            tooltip="🏬 Miami Vape Smoke Shop - LoveMeNow Pickup",
            popup="<b>Miami Vape Smoke Shop</b><br>351 NE 79th St<br>Miami, FL 33138<br><em>LoveMeNow Pickup Location</em>",
            icon=folium.Icon(color="red", icon="shopping-cart", prefix="fa")
        ).add_to(m)
        
        # Return the map as HTML
        from flask import Response
        response = Response(m._repr_html_(), mimetype='text/html')
        # Allow this route to be embedded in iframes from same origin
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response
        
    except ImportError:
        # If folium is not installed, return a simple message
        return """
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; font-family: Arial, sans-serif;">
            <div style="text-align: center;">
                <h3>Miami Coverage Map</h3>
                <p>We deliver throughout Miami-Dade and Broward counties!</p>
                <div style="margin-top: 2rem; padding: 1.5rem; background: #667eea; color: white; border-radius: 8px;">
                    <h4>🏬 Pickup Location</h4>
                    <p><strong>Miami Vape Smoke Shop</strong></p>
                    <p>351 NE 79th St<br>Miami, FL 33138</p>
                    <p><em>LoveMeNow Pickup Location</em></p>
                </div>
                <p><em>Install folium to see the interactive map</em></p>
            </div>
        </div>
        """
    except Exception as e:
        return f"""
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; font-family: Arial, sans-serif;">
            <div style="text-align: center;">
                <h3>Miami Coverage Map</h3>
                <p>We deliver throughout Miami-Dade and Broward counties!</p>
                <div style="margin-top: 2rem; padding: 1.5rem; background: #667eea; color: white; border-radius: 8px;">
                    <h4>🏬 Pickup Location</h4>
                    <p><strong>Miami Vape Smoke Shop</strong></p>
                    <p>351 NE 79th St<br>Miami, FL 33138</p>
                    <p><em>LoveMeNow Pickup Location</em></p>
                </div>
                <p><em>Error: {str(e)}</em></p>
            </div>
        </div>
        """




# ── run & create tables once ─────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()                # <- now User is known, table created
        # quick sanity check
        db.session.execute(text("SELECT 1"))
        print("✅  DB connected and tables ensured.")

    app.run(debug=True)
