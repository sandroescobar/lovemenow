# 🚀 Deployment Guide - LoveMeNow

## 📋 Pre-Deployment Checklist

### 1. **Create Your .env File**
```bash
cp .env.example .env
```

Fill in these **REQUIRED** values:
```bash
SECRET_KEY=generate_a_32_character_random_string_here
DB_URL=your_database_connection_string
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key
FLASK_ENV=production
DOMAIN=https://yourdomain.com
```

### 2. **Security Verification**
- [ ] No hardcoded secrets in code ✅
- [ ] .env file created and filled ✅
- [ ] .gitignore includes .env ✅
- [ ] Strong SECRET_KEY generated ✅

## 🐙 GitHub Upload

### 1. **Initialize Git Repository**
```bash
git init
git add .
git commit -m "Initial commit - LoveMeNow e-commerce platform"
```

### 2. **Create GitHub Repository**
1. Go to GitHub.com
2. Create new repository named "LoveMeNow"
3. **DO NOT** initialize with README (you already have one)

### 3. **Push to GitHub**
```bash
git remote add origin https://github.com/yourusername/LoveMeNow.git
git branch -M main
git push -u origin main
```

## 🌐 Render.com Deployment

### 1. **Create Render Account**
- Sign up at render.com
- Connect your GitHub account

### 2. **Create Web Service**
1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Configure:
   - **Name**: lovemenow
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn main:app`

### 3. **Set Environment Variables**
In Render dashboard, add these environment variables:

```bash
FLASK_ENV=production
SECRET_KEY=your_32_character_secret_key
STRIPE_SECRET_KEY=sk_live_your_live_stripe_key  # Use live keys for production
STRIPE_PUBLISHABLE_KEY=pk_live_your_live_publishable_key
DOMAIN=https://lovemenow.onrender.com  # Update with your actual domain
SENDLAYER_API_KEY=your_email_api_key  # Optional
```

### 4. **Database Setup**
1. In Render, create a PostgreSQL database
2. Copy the connection string
3. Set `DB_URL` environment variable to the connection string

### 5. **Deploy**
- Click "Deploy"
- Wait for build to complete
- Your app will be live at `https://yourappname.onrender.com`

## 🌍 Custom Domain (GoDaddy)

### 1. **Configure Custom Domain in Render**
1. Go to your service settings
2. Add custom domain: `yourdomain.com`
3. Note the CNAME target provided by Render

### 2. **Configure DNS in GoDaddy**
1. Log into GoDaddy DNS management
2. Add CNAME record:
   - **Name**: `@` (or `www`)
   - **Value**: `yourapp.onrender.com` (from Render)
   - **TTL**: 600

### 3. **Update Environment Variables**
Update `DOMAIN` in Render:
```bash
DOMAIN=https://yourdomain.com
```

## 🔧 Post-Deployment

### 1. **Test Everything**
- [ ] Site loads correctly
- [ ] User registration works
- [ ] Login/logout works
- [ ] Products display correctly
- [ ] Stripe checkout works (test mode first!)
- [ ] All forms submit properly

### 2. **Enable Production Mode**
- [ ] Set `FLASK_ENV=production`
- [ ] Use live Stripe keys
- [ ] Test with real payment (small amount)

### 3. **Monitor**
- Check Render logs for errors
- Monitor database performance
- Set up uptime monitoring

## 🚨 Troubleshooting

### Common Issues:

**Build Fails**
- Check requirements.txt syntax
- Ensure all dependencies are listed

**Database Connection Error**
- Verify DB_URL format
- Check database is running
- Verify credentials

**Stripe Errors**
- Confirm API keys are correct
- Check test vs live mode
- Verify webhook endpoints

**Environment Variable Issues**
- Double-check spelling
- Ensure no extra spaces
- Verify all required vars are set

## 📞 Emergency Contacts

If something goes wrong:
1. Check Render logs first
2. Verify environment variables
3. Test locally with same config
4. Check database connectivity

## 🎉 Success!

Once deployed:
- Your site will be live at your custom domain
- SSL certificate will be automatically provided
- Automatic deployments from GitHub pushes
- Professional e-commerce platform ready!

---

**Remember**: Always test thoroughly before switching to live Stripe keys!