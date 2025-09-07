#!/bin/bash

echo "🔧 SETTING UP STRIPE CLI WEBHOOKS FOR LOCAL DEVELOPMENT"
echo "======================================================="

# Check if Stripe CLI is installed
if ! command -v stripe &> /dev/null; then
    echo "❌ Stripe CLI is not installed"
    echo "📦 Installing Stripe CLI..."
    
    # Install Stripe CLI using homebrew
    if command -v brew &> /dev/null; then
        brew install stripe/stripe-cli/stripe
        echo "✅ Stripe CLI installed"
    else
        echo "❌ Homebrew not found. Please install Stripe CLI manually:"
        echo "   https://stripe.com/docs/stripe-cli#install"
        exit 1
    fi
else
    echo "✅ Stripe CLI is already installed"
fi

echo ""
echo "🔑 LOGGING INTO STRIPE..."
echo "This will open your browser to authenticate with Stripe"
stripe login

echo ""
echo "🚀 STARTING WEBHOOK FORWARDING..."
echo "This will forward Stripe webhooks to your local Flask app"
echo ""
echo "🎯 Your Flask app should be running on http://localhost:2100"
echo "🔗 Webhooks will be forwarded to: http://localhost:2100/webhooks/stripe"
echo ""
echo "⏹️  Press Ctrl+C to stop webhook forwarding when done testing"
echo ""

# Start webhook forwarding
stripe listen --forward-to localhost:2100/webhooks/stripe

echo ""
echo "🛑 Webhook forwarding stopped"