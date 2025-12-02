// static/js/checkout.js

(() => {
  // ----- Bootstrap -----
  const bootEl = document.getElementById('checkout-bootstrap');
  const BOOT = bootEl ? JSON.parse(bootEl.textContent || '{}') : {};
  const cartData = BOOT.cart || { items: [], subtotal: 0 };
  const STRIPE_KEY = BOOT.stripePublishableKey;
  let selectedDeliveryType = (BOOT.defaultDeliveryType || 'pickup').toLowerCase();

  // ----- Stripe -----
  const stripe = STRIPE_KEY ? Stripe(STRIPE_KEY) : null;
  let elements = null;
  let clientSecret = null;
  let stripeInitialized = false;

  // Payment Request (Apple/Google Pay)
  let paymentRequest = null;
  let prButton = null;

  // ----- State -----
  let deliveryQuote = null;  // { fee_dollars }
  let isGettingQuote = false;
  let latestTotals = null;   // keep last totals for PR amount
  let isQuoteLocked = false; // Prevent address changes from updating quote after selection
  let lastQuoteKey = null;

  // ----- DOM -----
  const deliveryOptions = document.querySelectorAll('.delivery-option');
  const deliveryAddressSection = document.getElementById('delivery-address-section');
  const deliveryFeeRow = document.getElementById('delivery-fee-row');
  const checkoutButton = document.getElementById('checkout-button');
  const errorMessage = document.getElementById('error-message');
  const successMessage = document.getElementById('success-message');

  const subtotalEl = document.getElementById('subtotal');
  const discountRow = document.getElementById('discount-row');
  const discountAmtEl = document.getElementById('discount-amount');
  const discountLblEl = document.getElementById('discount-code-label');
  const deliveryFeeEl = document.getElementById('delivery-fee');
  const taxEl = document.getElementById('tax-amount');
  const totalEl = document.getElementById('total');
  const statusEl = document.getElementById('checkout-status');

  // ----- Helpers -----
  function cents(x) { return Math.round(Number(x || 0) * 100); }

  function resetCheckoutButton() {
    if (!checkoutButton) return;
    checkoutButton.disabled = true;
    const spinner = document.querySelector('.loading-spinner');
    if (spinner) spinner.style.display = 'none';
  }

  function money(x) {
    const n = Number(x || 0);
    return n.toLocaleString(undefined, { style: 'currency', currency: 'USD' });
  }

  function refreshExpressTotal() {
    if (!paymentRequest || !latestTotals) return;
    try {
      paymentRequest.update({ total: { label: 'LoveMeNow', amount: cents(latestTotals.total) } });
    } catch (_) {}
  }

  function renderTotals(t) {
    latestTotals = t;
    if (subtotalEl) subtotalEl.textContent = money(t.subtotal || 0);

    const hasDiscount = Number(t.discount_amount || 0) > 0;
    if (discountRow) {
      discountRow.style.display = hasDiscount ? 'flex' : 'none';
      if (discountAmtEl) discountAmtEl.textContent = `-${money(t.discount_amount || 0)}`;
      if (discountLblEl) discountLblEl.textContent = t.discount_code ? `(${t.discount_code})` : '';
    }

    // Show the delivery row whenever "delivery" is selected (even if $0 before quote)
    if (selectedDeliveryType === 'delivery') {
      if (deliveryFeeRow) deliveryFeeRow.style.display = 'flex';
      if (deliveryFeeEl) deliveryFeeEl.textContent = money(t.delivery_fee || 0);
    } else {
      if (deliveryFeeRow) deliveryFeeRow.style.display = 'none';
      if (deliveryFeeEl) deliveryFeeEl.textContent = money(0);
    }

    if (taxEl)  taxEl.textContent  = money(t.tax || 0);
    if (totalEl) totalEl.textContent = money(t.total || 0);

    // keep PR total in sync
    refreshExpressTotal();
  }

  // Canonical source of truth: always ask /api/cart/totals
  async function updateOrderSummary() {
    const type = (selectedDeliveryType || 'pickup').toLowerCase();

    try {
      let res;
      if (type === 'delivery' && deliveryQuote && typeof deliveryQuote.fee_dollars !== 'undefined') {
        // We have a quote: POST it so backend includes delivery fee with discount/tax
        res = await fetch('/api/cart/totals', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            delivery_type: 'delivery',
            delivery_quote: { fee_dollars: Number(deliveryQuote.fee_dollars) }
          })
        });
      } else {
        // Pickup or delivery before quote (delivery fee = $0)
        res = await fetch(`/api/cart/totals?delivery_type=${encodeURIComponent(type)}`);
      }
      if (!res.ok) throw new Error(`Totals fetch failed (${res.status})`);
      const totals = await res.json();
      renderTotals(totals);
    } catch (e) {
      console.error(e);
    }
  }

  function showError(msg) {
    if (!errorMessage) return;
    errorMessage.textContent = msg;
    errorMessage.style.display = 'block';
    if (successMessage) successMessage.style.display = 'none';
    errorMessage.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => { errorMessage.style.display = 'none'; }, 5000);
  }

  function hideDeliveryError() {
    const errorDiv = document.getElementById('delivery-error-message');
    if (errorDiv) errorDiv.style.display = 'none';
  }

  function showDeliveryError(msg) {
    const errorDiv = document.getElementById('delivery-error-message');
    const errorText = document.getElementById('delivery-error-text');
    if (errorDiv && errorText) {
      errorText.textContent = msg;
      errorDiv.style.display = 'block';
      errorDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function displayCartItems(items) {
    const cartItemsEl = document.getElementById('cart-items');
    if (!cartItemsEl) return;
    cartItemsEl.innerHTML = '';
    (items || []).forEach(item => {
      const el = document.createElement('div');
      el.className = 'order-item';
      el.innerHTML = `
        <div class="item-details">
          <div class="item-name">${item.name}</div>
          <div class="item-quantity">Qty: ${item.quantity}</div>
        </div>
        <div class="item-price">${money(Number(item.price) * Number(item.quantity))}</div>
      `;
      cartItemsEl.appendChild(el);
    });
  }

  // ----- Delivery option wiring -----
  function setupDeliveryOptions() {
    deliveryOptions.forEach(opt => {
      opt.addEventListener('click', () => {
        deliveryOptions.forEach(o => o.classList.remove('active'));
        opt.classList.add('active');
        selectedDeliveryType = (opt.dataset.type || 'pickup').toLowerCase();

        // Whenever delivery mode changes, force a fresh PI with the right total
        stripeInitialized = false;
        clientSecret = null;
        elements = null;
        const sc = document.getElementById('stripe-checkout');
        if (sc) sc.innerHTML = '';
        const ec = document.getElementById('express-checkout');
        if (ec) ec.innerHTML = '';
        const ecr = document.getElementById('express-checkout-right');
        if (ecr) { ecr.innerHTML = ''; ecr.style.display = 'none'; }

        if (selectedDeliveryType === 'delivery') {
          if (deliveryAddressSection) deliveryAddressSection.style.display = 'block';
          if (deliveryFeeRow) deliveryFeeRow.style.display = 'flex';
          document.getElementById('address').required = true;
          document.getElementById('city').required = true;
          document.getElementById('zip').required = true;
          if (statusEl) statusEl.textContent = 'Please enter your delivery address';
        } else {
          if (deliveryAddressSection) deliveryAddressSection.style.display = 'none';
          if (deliveryFeeRow) deliveryFeeRow.style.display = 'none';
          document.getElementById('address').required = false;
          document.getElementById('city').required = false;
          document.getElementById('zip').required = false;
          hideDeliveryError();
          resetQuoteLock(); // Reset quote lock when switching away from delivery
          if (statusEl) statusEl.textContent = 'Initializing payment system...';
          initializeStripe(); // pickup can init immediately
        }

        updateOrderSummary();
      });
    });

    // Default selection — simulate click to run the same code path
    const defaultBtn =
      document.querySelector(`.delivery-option[data-type="${selectedDeliveryType}"]`) ||
      document.querySelector('.delivery-option[data-type="pickup"]') ||
      document.querySelector('.delivery-option');
    if (defaultBtn) defaultBtn.click();
    else updateOrderSummary(); // fallback
  }

  // ----- Address helpers -----
  function handleSavedAddressChange() {
    const savedAddressSelect = document.getElementById('saved-address');
    const manualAddressFields = document.getElementById('manual-address-fields');
    const addressField = document.getElementById('address');
    const suiteField = document.getElementById('suite');
    const cityField = document.getElementById('city');
    const stateField = document.getElementById('state');
    const zipField = document.getElementById('zip');

    if (!savedAddressSelect) return;

    if (savedAddressSelect.value === 'manual' || savedAddressSelect.value === '') {
      manualAddressFields.style.display = 'block';
      if (savedAddressSelect.value === 'manual') {
        addressField.value = '';
        suiteField.value = '';
        cityField.value = 'Miami';
        stateField.value = 'FL';
        zipField.value = '';
      }
    } else {
      const opt = savedAddressSelect.options[savedAddressSelect.selectedIndex];
      addressField.value = opt.dataset.address || '';
      suiteField.value   = opt.dataset.suite || '';
      cityField.value    = opt.dataset.city || 'Miami';
      stateField.value   = opt.dataset.state || 'FL';
      zipField.value     = opt.dataset.zip || '';
      manualAddressFields.style.display = 'block';
    }
  }

  function debounce(fn, wait) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  }
  const debouncedGetQuote = debounce(getDeliveryQuote, 500);

  async function getDeliveryQuote() {
    if (selectedDeliveryType !== 'delivery' || isGettingQuote || isQuoteLocked) return;

    const address = document.getElementById('address').value;
    const city    = document.getElementById('city').value;
    const zip     = document.getElementById('zip').value;
    const state   = document.getElementById('state').value;

    if (!address || !city || !zip) {
      deliveryQuote = null;
      lastQuoteKey = null;
      isQuoteLocked = false;
      updateOrderSummary();
      return;
    }

    const quoteKey = `${address.trim().toLowerCase()}|${city.trim().toLowerCase()}|${(state || '').trim().toLowerCase()}|${zip.trim()}`;
    if (isQuoteLocked && quoteKey === lastQuoteKey) {
      return;
    }
    if (isQuoteLocked && quoteKey !== lastQuoteKey) {
      isQuoteLocked = false;
      deliveryQuote = null;
      lastQuoteKey = null;
      showQuoteUnlockMessage();
      updateOrderSummary();
    }

    isGettingQuote = true;
    try {
      const r = await fetch('/api/uber/quote', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          delivery_address:{ address, city, state, zip, country:'US' }
        })
      });
      const data = await r.json();
      if (data.success) {
        deliveryQuote = data.quote;
        lastQuoteKey = quoteKey;
        hideDeliveryError();
        updateOrderSummary();

        // Now that we have the delivery quote, re-init Stripe with correct total on server
        stripeInitialized = false;
        clientSecret = null;
        elements = null;
        initializeStripe();
        
        // LOCK THE QUOTE - prevent address changes from fetching new quotes
        // Customer must switch to pickup or restart checkout to change address
        isQuoteLocked = true;
        console.log('✅ Delivery quote locked. Address changes will not trigger new quotes until payment is complete or checkout is restarted.');
        showQuoteLockMessage();
      } else {
        deliveryQuote = null;
        lastQuoteKey = null;
        isQuoteLocked = false;
        updateOrderSummary();
        showDeliveryError(data.error || 'Unable to get delivery quote.');
      }
    } catch (e) {
      deliveryQuote = null;
      lastQuoteKey = null;
      isQuoteLocked = false;
      updateOrderSummary();
      showDeliveryError('Unable to get delivery quote. Please try again.');
    } finally {
      isGettingQuote = false;
    }
  }

  function showQuoteLockMessage() {
    // Show message to customer that quote is locked
    const messageEl = document.getElementById('quote-lock-message');
    if (messageEl) {
      messageEl.style.display = 'block';
      setTimeout(() => {
        messageEl.style.display = 'none';
      }, 4000);
    }
  }

  function resetQuoteLock() {
    // Reset quote lock when switching delivery types or when explicitly needed
    isQuoteLocked = false;
    deliveryQuote = null;
  }

  // ----- Stripe (backend owns totals incl. discount) -----
  async function initializeStripe() {
    if (stripeInitialized) return;
    if (!stripe) { showError('Stripe not loaded'); return; }

    stripeInitialized = true;
    if (statusEl) statusEl.textContent = 'Setting up payment...';

    try {
      const body = {
        delivery_type: selectedDeliveryType,
        // send quote so backend can include delivery fee in server-side calculation
        delivery_quote: deliveryQuote || null
        // NOTE: discount is NOT sent; backend reads session and re-validates
      };
      const r = await fetch('/create-checkout-session', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(body)
      });
      const data = await r.json();
      if (!r.ok || data.error) throw new Error(data.error || 'Failed to create checkout session');

      clientSecret = data.clientSecret;
      if (!clientSecret || !clientSecret.startsWith('pi_') || !clientSecret.includes('_secret_')) {
        throw new Error('Invalid Payment Intent client secret');
      }

      // 🔍 Debug: Extract and log PaymentIntent ID
      const piId = clientSecret.split('_secret_')[0];
      console.log('✅ Fresh PaymentIntent created:', piId);
      console.log('📋 Delivery type:', selectedDeliveryType, 'Quote:', deliveryQuote);

      elements = stripe.elements({
        clientSecret,
        appearance: { theme: 'stripe', variables: { colorPrimary: 'hsl(var(--primary-color))' } }
      });

      // Payment Element (tabs are controlled by server-side PI config)
      const paymentElement = elements.create('payment');
      paymentElement.mount('#stripe-checkout');

      // Express checkout (Apple/Google Pay) via Payment Request Button
      try {
        // Prefer the authoritative server PI amount; fall back to latestTotals in UI
        let startAmount = cents(latestTotals?.total || 0);
        try {
          const { paymentIntent: pi } = await stripe.retrievePaymentIntent(clientSecret);
          if (pi && typeof pi.amount === 'number') startAmount = pi.amount; // amount in cents from server
        } catch (_) {}

        paymentRequest = stripe.paymentRequest({
          country: 'US',
          currency: 'usd',
          total: { label: 'LoveMeNow', amount: startAmount },
          requestPayerName: true,
          requestPayerEmail: true,
          requestPayerPhone: true
        });

        const result = await paymentRequest.canMakePayment();
        console.log('canMakePayment →', result);

        // Choose where to mount: right column preferred, else legacy container
        const containerId =
          document.getElementById('express-checkout-right') ? '#express-checkout-right' :
          (document.getElementById('express-checkout') ? '#express-checkout' : null);

        if (result && containerId) {
          const btn = elements.create('paymentRequestButton', {
            paymentRequest,
            // optional styling; Stripe auto-chooses Apple/Google theme as needed
            style: { paymentRequestButton: { type: 'buy', theme: 'dark', height: '44px' } }
          });
          btn.mount(containerId);
          const mountEl = document.querySelector(containerId);
          if (mountEl) mountEl.style.display = '';
          prButton = btn;
        }

        paymentRequest?.on('paymentmethod', async (ev) => {
          // Confirm the payment using the payment method from Apple/Google Pay
          try {
            console.log('💳 Processing Apple/Google Pay payment...', ev.paymentMethod.id);
            
            const { error, paymentIntent } = await stripe.confirmCardPayment(
              clientSecret,
              {
                payment_method: ev.paymentMethod.id,
                // Re-apply billing details from payer info (in case they were modified)
                billing_details: {
                  name: ev.payerName || '',
                  email: ev.payerEmail || '',
                  phone: ev.payerPhone || ''
                }
              }
            );

            if (error) {
              console.error('❌ Payment confirmation error:', error);
              ev.complete('fail');
              showError(error.message || 'Apple/Google Pay payment failed');
              checkoutButton.disabled = false;
              return;
            }

            if (!paymentIntent) {
              console.error('❌ No payment intent returned');
              ev.complete('fail');
              showError('Payment processing error. Please try again.');
              checkoutButton.disabled = false;
              return;
            }

            console.log('📊 Payment Intent status:', paymentIntent.status);
            ev.complete('success');

            // Handle based on payment status
            if (paymentIntent.status === 'succeeded') {
              console.log('✅ Payment succeeded via Apple/Google Pay:', paymentIntent.id);
              await createOrder(paymentIntent.id);
              return;
            } else if (paymentIntent.status === 'requires_action') {
              console.log('🔐 3D Secure authentication required');
              showError('Your bank requires additional authentication. Please complete the verification.');
              checkoutButton.disabled = false;
              return;
            } else {
              console.warn('⚠️ Unexpected payment status:', paymentIntent.status);
              showError('Payment status: ' + paymentIntent.status);
              checkoutButton.disabled = false;
              return;
            }
          } catch (error) {
            console.error('❌ Payment request error:', error);
            ev.complete('fail');
            showError('Payment failed: ' + (error.message || 'Unknown error'));
            checkoutButton.disabled = false;
          }
        });
      } catch (_) {
        // Non-fatal: Payment Request Button just won't render
      }

      checkoutButton.disabled = false;
      if (statusEl) statusEl.textContent = 'Ready to complete your order';
    } catch (e) {
      showError('Failed to initialize payment system: ' + e.message);
      const box = document.getElementById('stripe-checkout');
      if (box) {
        box.innerHTML = `<div style="color:red;text-align:center;padding:20px;">
          Failed to initialize payment system<br><small>${e.message}</small></div>`;
      }
    }
  }

  // ----- Checkout click -----
  checkoutButton?.addEventListener('click', async () => {
    if (!elements || !clientSecret) { showError('Payment system not ready'); return; }
    if (!validateForm()) return;

    checkoutButton.disabled = true;
    const spinner = document.querySelector('.loading-spinner');
    if (spinner) spinner.style.display = 'inline-block';

    try {
      const fullNameEl = document.getElementById('fullName');
      const name = fullNameEl
        ? fullNameEl.value
        : `${document.getElementById('firstName').value} ${document.getElementById('lastName').value}`;

      const { error, paymentIntent } = await stripe.confirmPayment({
        elements,
        confirmParams: {
          return_url: window.location.origin + '/checkout-success',
          payment_method_data: {
            billing_details: {
              name,
              email: document.getElementById('email').value,
              phone: document.getElementById('phone').value
            }
          }
        },
        redirect: 'if_required'
      });

      if (error) {
        showError(error.message);
        checkoutButton.disabled = false;
        if (spinner) spinner.style.display = 'none';
        return;
      }

      if (paymentIntent.status === 'succeeded') {
        await createOrder(paymentIntent.id);
        return;
      }

      showError('Payment was not completed successfully');
      checkoutButton.disabled = false;
      if (spinner) spinner.style.display = 'none';
    } catch (_) {
      showError('Payment processing failed');
      checkoutButton.disabled = false;
      const spinner = document.querySelector('.loading-spinner');
      if (spinner) spinner.style.display = 'none';
    }
  });

  async function createOrder(paymentIntentId) {
    try {
      const orderData = {
        payment_intent_id: paymentIntentId,
        delivery_type: selectedDeliveryType,
        customer_info: {
          email: document.getElementById('email').value,
          first_name: document.getElementById('fullName')
            ? document.getElementById('fullName').value.split(' ')[0]
            : document.getElementById('firstName').value,
          last_name: document.getElementById('fullName')
            ? document.getElementById('fullName').value.split(' ').slice(1).join(' ')
            : document.getElementById('lastName').value,
          phone: document.getElementById('phone').value
        }
      };

      if (selectedDeliveryType === 'delivery') {
        orderData.delivery_address = {
          address: document.getElementById('address').value,
          suite: document.getElementById('suite').value,
          city: document.getElementById('city').value,
          state: document.getElementById('state').value,
          zip: document.getElementById('zip').value,
          country: 'US'
        };
        if (deliveryQuote) {
          orderData.delivery_quote = deliveryQuote;
          orderData.quote_id = deliveryQuote.id;  // ← PASS QUOTE ID FOR UBER DELIVERY
          orderData.delivery_fee_cents = Math.round((deliveryQuote.fee_dollars || 0) * 100);  // ← PASS FEE IN CENTS
        }
      }

      const r = await fetch('/api/create-order', {
        method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(orderData)
      });
      const result = await r.json();

      if (result.success) {
        try {
          await fetch('/api/cart/clear', { method:'POST', headers:{'Content-Type':'application/json'} });
          localStorage.removeItem('cartCount'); localStorage.removeItem('cart');
          const cartCountEl = document.getElementById('cartCount');
          if (cartCountEl) { cartCountEl.textContent = '0'; cartCountEl.style.display = 'none'; cartCountEl.classList.remove('has-items'); }
        } catch (_) {}

        if (result.tracking_url) {
          window.location.href = result.tracking_url; // delivery
        } else {
          window.location.href = `/checkout-success?order_id=${result.order_id}`; // pickup
        }
      } else {
        showError('Failed to create order: ' + (result.error || 'Unknown error'));
        checkoutButton.disabled = false;
        const spinner = document.querySelector('.loading-spinner');
        if (spinner) spinner.style.display = 'none';
      }
    } catch (_) {
      showError('Failed to create order');
      checkoutButton.disabled = false;
      const spinner = document.querySelector('.loading-spinner');
      if (spinner) spinner.style.display = 'none';
    }
  }

  function validateForm() {
    const isLoggedIn = document.getElementById('fullName') !== null;
    let required = isLoggedIn ? ['phone'] : ['email','firstName','lastName','phone'];
    if (selectedDeliveryType === 'delivery') required = required.concat(['address','city','zip']);

    for (const id of required) {
      const f = document.getElementById(id);
      if (!f || !f.value.trim()) {
        const name = f?.labels?.[0]?.textContent || id;
        showError(`Please fill in ${name}`);
        f?.focus();
        return false;
      }
    }

    if (!isLoggedIn) {
      const email = document.getElementById('email').value;
      const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRe.test(email)) {
        showError('Please enter a valid email address');
        document.getElementById('email').focus();
        return false;
      }
    }
    return true;
  }

  function updateCartCount() {
    fetch('/api/cart/count')
      .then(r => r.json())
      .then(d => {
        const el = document.getElementById('cartCount');
        if (!el) return;
        el.textContent = d.count;
        el.style.display = d.count > 0 ? 'inline-block' : 'none';
      }).catch(()=>{});
  }

  function updateWishlistCount() {
    fetch('/api/wishlist/count')
      .then(r => r.json())
      .then(d => {
        const el = document.getElementById('wishlistCount');
        if (!el) return;
        el.textContent = d.count;
        el.style.display = d.count > 0 ? 'inline-block' : 'none';
      }).catch(()=>{});
  }

  // Wire up address field listeners
  function setupAddressListeners() {
    ['address','city','zip','state'].forEach(id => {
      const f = document.getElementById(id);
      if (!f) return;
      f.addEventListener('input', () => {
        if (selectedDeliveryType === 'delivery') debouncedGetQuote();
      });
      f.addEventListener('blur', () => {
        if (selectedDeliveryType === 'delivery') debouncedGetQuote();
      });
      f.addEventListener('focus', () => {
        if (selectedDeliveryType === 'delivery' && isQuoteLocked) {
          isQuoteLocked = false;
          lastQuoteKey = null;
          deliveryQuote = null;
          showQuoteUnlockMessage();
          updateOrderSummary();
        }
      });
    });

    const saved = document.getElementById('saved-address');
    if (saved) {
      saved.addEventListener('change', () => {
        handleSavedAddressChange();
        if (selectedDeliveryType === 'delivery') {
          isQuoteLocked = false;
          lastQuoteKey = null;
          deliveryQuote = null;
          showQuoteUnlockMessage();
          setTimeout(() => debouncedGetQuote(), 100);
        }
      });
    }
  }

  // ----- Init -----
  document.addEventListener('DOMContentLoaded', () => {
    resetCheckoutButton();
    displayCartItems(cartData.items || []);
    setupDeliveryOptions();
    setupAddressListeners();
    updateCartCount();
    updateWishlistCount();
  });
})();
