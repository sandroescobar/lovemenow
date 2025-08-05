# 🛍️ LoveMeNow - Secure E-commerce Platform

A modern, enterprise-grade Flask-based e-commerce platform with comprehensive security measures, user management, shopping cart functionality, and payment processing.

## 🚀 New Secure Architecture

This application has been completely restructured with enterprise-level security and modern Flask best practices:

- ✅ **Modular Blueprint Architecture**
- ✅ **Application Factory Pattern**
- ✅ **Comprehensive Security Headers**
- ✅ **Input Validation & Sanitization**
- ✅ **Rate Limiting & DDoS Protection**
- ✅ **Secure Session Management**
- ✅ **Production-Ready Deployment**

## 🛡️ Security Features

### Application Security
- **Flask-Talisman**: Security headers and CSP
- **Rate Limiting**: Protection against abuse
- **Input Validation**: XSS and injection prevention
- **Error Handling**: No sensitive data exposure
- **Secure Cookies**: HTTPOnly, Secure, SameSite

### Authentication Security
- **bcrypt**: Secure password hashing
- **Session Security**: Secure session management
- **Login Protection**: Brute force prevention
- **Password Requirements**: Strong password enforcement

### Infrastructure Security
- **HTTPS Enforcement**: SSL/TLS in production
- **Environment Variables**: No hardcoded secrets
- **Database Security**: Parameterized queries
- **Logging**: Comprehensive security logging

## 🏗️ Architecture

```
LoveMeNow/
├── app.py                 # Main application factory
├── wsgi.py               # Production WSGI entry point
├── main.py               # Legacy compatibility (deprecated)
├── config.py             # Configuration management
├── security.py           # Security middleware
├── models.py             # Database models
├── routes/               # Modular route blueprints
│   ├── __init__.py
│   ├── main.py          # Main routes
│   ├── auth.py          # Authentication routes
│   ├── api.py           # API endpoints
│   ├── cart.py          # Shopping cart routes
│   └── wishlist.py      # Wishlist routes
├── templates/            # HTML templates
│   ├── errors/          # Error pages
│   └── ...
├── static/              # Static assets
└── requirements.txt     # Dependencies
```

## 🚀 Quick Start

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd LoveMeNow
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the application**
   ```bash
   # New secure way (recommended)
   python app.py
   
   # Legacy compatibility (deprecated)
   python main.py
   ```

### Production Deployment

```bash
# Production server
gunicorn wsgi:app --workers 2 --timeout 120
```

## 🔧 Environment Variables

Create a `.env` file with:

```env
# Flask Configuration (REQUIRED)
SECRET_KEY=your_super_secret_key_minimum_32_characters
FLASK_ENV=production

# Database (REQUIRED)
DB_URL=mysql+pymysql://username:password@host:port/database_name

# Stripe (REQUIRED)
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_publishable_key

# Domain (REQUIRED)
DOMAIN=https://yourdomain.com

# Email Service (OPTIONAL)
SENDLAYER_API_KEY=your_sendlayer_api_key

# Security (OPTIONAL)
REDIS_URL=redis://localhost:6379/0
SENTRY_DSN=your_sentry_dsn_for_error_tracking
```

## 📦 Features

### Core Features
- **User Authentication**: Secure registration, login, profile management
- **Product Catalog**: Browse with categories, filtering, and search
- **Shopping Cart**: Real-time cart with inventory management
- **Wishlist**: Save favorite products
- **Payment Processing**: Secure Stripe integration
- **Responsive Design**: Mobile-first responsive interface

### Security Features
- **HTTPS Enforcement**: SSL/TLS encryption
- **Security Headers**: HSTS, CSP, XSS protection
- **Rate Limiting**: DDoS and abuse protection
- **Input Validation**: XSS and injection prevention
- **Secure Sessions**: HTTPOnly, Secure cookies
- **Error Handling**: No information disclosure

### Admin Features
- **Product Management**: CRUD operations
- **User Management**: Account administration
- **Order Management**: Order processing
- **Analytics**: Sales and user metrics

## 🌐 Deployment

### Render.com (Recommended)
```bash
# Automatic deployment with render.yaml
git push origin main
```

### Manual Server
```bash
# Install dependencies
pip install -r requirements.txt

# Run with Gunicorn
gunicorn wsgi:app --workers 2 --bind 0.0.0.0:8000
```

### Docker (Optional)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:8000"]
```

## 📚 Documentation

- **[Deployment Guide](DEPLOYMENT_GUIDE_SECURE.md)**: Comprehensive deployment instructions
- **[Security Checklist](SECURITY_CHECKLIST.md)**: Security verification steps

## 🔍 Testing

```bash
# Check security headers
curl -I https://yourdomain.com

# Test rate limiting
for i in {1..100}; do curl https://yourdomain.com/api/health; done
```

## 🚨 Migration from Legacy

If upgrading from the old structure:

1. **Backup your data**
2. **Update environment variables**
3. **Test with new structure**: `python app.py`
4. **Deploy with new WSGI**: `gunicorn wsgi:app`

The old `main.py` is maintained for compatibility but deprecated.

## 🛠️ Technology Stack

### Backend
- **Flask 3.0**: Modern Python web framework
- **SQLAlchemy 2.0**: Advanced ORM
- **Flask-Login**: Authentication management
- **Flask-Bcrypt**: Password hashing
- **Flask-Talisman**: Security headers
- **Flask-Limiter**: Rate limiting

### Database
- **MySQL**: Primary database (development)
- **PostgreSQL**: Production database (Render)
- **Redis**: Session storage and caching (optional)

### Security
- **bcrypt**: Password hashing
- **Talisman**: Security headers
- **CSP**: Content Security Policy
- **HTTPS**: SSL/TLS encryption
- **Rate Limiting**: Abuse prevention

### Frontend
- **HTML5**: Modern markup
- **CSS3**: Responsive styling
- **JavaScript**: Interactive functionality
- **Font Awesome**: Icon library

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is proprietary software. All rights reserved.

## 🆘 Support

For deployment issues:
1. Check [DEPLOYMENT_GUIDE_SECURE.md](DEPLOYMENT_GUIDE_SECURE.md)
2. Verify environment variables
3. Check application logs
4. Test security headers
5. Monitor error tracking

## 🎯 Production Checklist

Before going live:
- [ ] All environment variables set
- [ ] HTTPS enabled
- [ ] Security headers verified
- [ ] Rate limiting tested
- [ ] Database secured
- [ ] Backups configured
- [ ] Monitoring enabled
- [ ] Error tracking setup

---

**⚠️ Important**: Always use `python app.py` for development and `gunicorn wsgi:app` for production. The old `main.py` is deprecated.