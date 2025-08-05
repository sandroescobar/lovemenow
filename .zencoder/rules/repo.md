---
description: Repository Information Overview
globs: []
alwaysApply: true
---

# LoveMeNow Information

## Summary
LoveMeNow is a Flask-based e-commerce web application for selling adult products. It features user authentication, product browsing, shopping cart functionality, and user profile management. The application uses a MySQL database for data storage and follows a standard MVC-like architecture.

## Structure
- **static/**: Contains frontend assets (CSS, JavaScript, images)
- **templates/**: HTML templates for the web pages
- **main.py**: Application entry point and route definitions
- **models.py**: Database models using SQLAlchemy ORM
- **routes.py**: Flask extensions initialization
- **uploadData.py**: Utility script for importing product data from Excel

## Language & Runtime
**Language**: Python
**Version**: Python 3.x
**Framework**: Flask
**Database**: MySQL with SQLAlchemy ORM
**Package Manager**: pip (implied)

## Dependencies
**Main Dependencies**:
- Flask: Web framework
- Flask-Login: User authentication
- Flask-SQLAlchemy: ORM for database operations
- Flask-Bcrypt: Password hashing
- SQLAlchemy: Database ORM
- python-dotenv: Environment variable management
- PyMySQL: MySQL database connector

**Frontend Dependencies**:
- Font Awesome 6.0.0: Icon library
- Custom CSS/JS: For styling and interactivity

## Database Models
**User Model**:
- Authentication fields (email, password_hash)
- Profile information (full_name)
- Stripe integration (stripe_customer_id)

**Product Model**:
- Product details (name, description, price, etc.)
- Category relationship
- Images relationship

**Category Model**:
- Hierarchical structure with self-referential relationship
- Product categorization

**UserAddress Model**:
- User shipping information
- Default address flag

## Build & Installation
```bash
# Clone the repository
git clone <repository-url>

# Install dependencies
pip install flask flask-login flask-sqlalchemy flask-bcrypt sqlalchemy python-dotenv pymysql pandas openpyxl

# Set up environment variables
# Create a .env file with:
# SECRET_KEY=your_secret_key
# DB_URL=mysql+pymysql://username:password@host:port/database_name

# Run the application
python main.py
```

## Main Features
**Authentication**:
- User registration and login
- Password management
- Account deletion

**Product Management**:
- Product browsing and filtering
- Quick view functionality
- Product details

**User Profile**:
- Address management
- Account settings

**Shopping Experience**:
- Cart functionality (frontend only)
- Wishlist functionality (frontend only)

## Frontend Structure
**Templates**:
- Base layout with modular components
- Modal-based UI for authentication and quick views
- Responsive design

**JavaScript**:
- Product slideshow functionality
- Cart and wishlist management
- Quick view modal implementation
- Quantity selection

**CSS**:
- Custom styling with responsive design
- Animation effects for UI elements

## API Endpoints
- `/api/product/<id>`: JSON endpoint for product details
- Various routes for user authentication and profile management
- Product listing and detail pages

## Development
The application runs in debug mode during development:
```bash
python main.py
```

Database tables are automatically created if they don't exist when the application starts.