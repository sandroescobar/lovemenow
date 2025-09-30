// static/js/cart.js
// Renders cart items, applies/locks discounts, and syncs totals with server.

(() => {
  console.log('cart.js loading…');

  const LS_DISCOUNT_KEY = 'lmn_discount_applied';
  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const fmt = (n) => `$${Number(n || 0).toFixed(2)}`;

  const getCSRF = () =>
    (typeof window.getCSRFToken === 'function'
      ? window.getCSRFToken()
      : document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')) || '';

  document.addEventListener('DOMContentLoaded', () => {
    loadCart();
    if (window.updateCartCount) updateCartCount();
    if (window.updateWishlistCount) updateWishlistCount();
  });

  async function loadCart() {
    const mount = $('#cartContent');
    if (!mount) return;

    mount.innerHTML = `
      <div class="loading-cart" style="text-align:center;padding:2rem;">
        <i class="fas fa-spinner fa-spin" style="font-size:2rem;color:hsl(var(--primary-color));margin-bottom:1rem;"></i>
        <p>Loading your cart...</p>
      </div>
    `;

    try {
      // Non-blocking debug call
      fetch('/api/cart/debug').catch(() => {});

      const res = await fetch('/api/cart/');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      renderCart(mount, data);
      attachHandlers();
      await refreshCartSummary();  // server-truth numbers incl. discount/tax
      enforceAlreadyAppliedState();
    } catch (err) {
      mount.innerHTML = `
        <div class="empty-cart">
          <i class="fas fa-exclamation-triangle"></i>
          <h2>Error loading cart</h2>
          <p>Please refresh the page or try again later.</p>
          <button class="continue-shopping" onclick="location.reload()">
            <i class="fas fa-refresh"></i> Retry
          </button>
        </div>
      `;
    }
  }

  function renderCart(mount, cartData) {
    const products = cartData?.products || [];

    if (!products.length) {
      mount.innerHTML = `
        <div class="empty-cart">
          <i class="fas fa-shopping-cart"></i>
          <h2>Your cart is empty</h2>
          <p>Add some products to get started!</p>
          <a href="${window.location.origin}/products" class="continue-shopping">
            <i class="fas fa-arrow-left"></i> Continue Shopping
          </a>
        </div>
      `;
      return;
    }

    const itemsHTML = products.map((item) => {
      const sizeHTML = item.dimensions && String(item.dimensions).trim()
        ? `<div class="cart-item-size"><strong>Size:</strong> ${item.dimensions}</div>`
        : `<div class="cart-item-size"><strong>Sizing:</strong> One size fits all / Adjustable</div>`;

      const vId = item.variant_id ?? null;

      return `
        <div class="cart-item" data-product-id="${item.id}">
          <div class="cart-item-image">
            <img src="${item.image_url || '/static/img/placeholder.svg'}"
                 alt="${item.name}"
                 onerror="this.src='/static/img/placeholder.svg'">
          </div>

          <div class="cart-item-details">
            <h3>${item.name}</h3>
            ${sizeHTML}
            <div class="cart-item-price">${fmt(item.price)}</div>
          </div>

          <div class="quantity-controls">
            <input type="number"
                   class="quantity-input"
                   value="${item.quantity}"
                   min="1"
                   max="${item.max_quantity}"
                   data-action="qty-input"
                   data-id="${item.id}"
                   data-variant="${vId}">
            <div class="quantity-buttons">
              <button class="quantity-btn"
                      data-action="qty-dec"
                      data-id="${item.id}"
                      data-variant="${vId}">
                <i class="fas fa-minus"></i>
              </button>
              <button class="quantity-btn"
                      data-action="qty-inc"
                      data-id="${item.id}"
                      data-variant="${vId}"
                      ${item.quantity >= item.max_quantity ? 'disabled' : ''}>
                <i class="fas fa-plus"></i>
              </button>
            </div>
            ${item.max_quantity <= 5
              ? `<small style="color:#ff6b6b;font-size:0.8rem;margin-top:0.25rem;">Only ${item.max_quantity} left in stock</small>`
              : ''
            }
          </div>

          <div class="cart-item-total">${fmt(item.item_total)}</div>

          <button class="remove-btn"
                  data-action="remove"
                  data-id="${item.id}"
                  data-variant="${vId}">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      `;
    }).join('');

    mount.innerHTML = `
      <div class="cart-content">
        <div class="cart-items">${itemsHTML}</div>

        <div class="cart-summary">
          <h3>Order Summary</h3>

          <div class="summary-row">
            <span>Subtotal:</span>
            <span id="subtotal">$0.00</span>
          </div>

          <div class="summary-row" id="discount-row" style="display:none;">
            <span>Discount <span id="discount-code-label"></span>:</span>
            <span id="discount-amount">-$0.00</span>
          </div>

          <div class="summary-row">
            <span>Tax (8.75%):</span>
            <span id="tax-amount">$0.00</span>
          </div>

          <div class="summary-row">
            <span>Shipping:</span>
            <span id="shipping-amount">Calculated at checkout</span>
          </div>

          <div class="summary-row total">
            <span>Total:</span>
            <span id="total">$0.00</span>
          </div>

          <div class="discount-code-section">
            <div class="discount-label">Have a discount code?</div>
            <form id="cartDiscountForm" class="discount-form">
              <div class="discount-input-group">
                <input type="text"
                       class="discount-input"
                       id="cartDiscountCodeInput"
                       placeholder="Enter discount code">
                <button type="submit" class="discount-submit-btn" id="cartDiscountApplyBtn">
                  <i class="fas fa-check"></i> Apply
                </button>
              </div>
            </form>
            <small id="cart-discount-message" style="display:none;"></small>
          </div>

          <button class="checkout-btn" id="checkoutBtn">
            <i class="fas fa-lock"></i> Secure Checkout
          </button>

          <a href="${window.location.origin}/products"
             class="continue-shopping"
             style="width:100%;justify-content:center;margin-top:1rem;">
            <i class="fas fa-arrow-left"></i> Continue Shopping
          </a>
        </div>
      </div>
    `;
  }

  async function refreshCartSummary() {
    // Prefer server totals: keeps discount/tax logic identical to checkout
    try {
      const res = await fetch('/api/cart/totals', { cache: 'no-store' });
      if (!res.ok) throw new Error('no totals endpoint');
      const t = await res.json();

      const subtotal = t.subtotal ?? 0;
      const tax      = t.tax ?? t.tax_amount ?? 0;
      const discount = t.discount_amount ?? 0;
      const code     = t.discount_code ?? '';
      const ship     = t.delivery_fee ?? t.shipping_fee ?? null;
      const total    = t.total ?? 0;

      if ($('#subtotal'))         $('#subtotal').textContent = fmt(subtotal);
      if ($('#tax-amount'))       $('#tax-amount').textContent = fmt(tax);
      if ($('#total'))            $('#total').textContent = fmt(total);
      if ($('#shipping-amount') && ship != null) $('#shipping-amount').textContent = fmt(ship);

      if (discount && discount > 0) {
        $('#discount-row').style.display = '';
        $('#discount-amount').textContent = `-${fmt(discount).replace('$', '$')}`;
        if ($('#discount-code-label')) $('#discount-code-label').textContent = code ? `(${code})` : '';
      } else {
        $('#discount-row').style.display = 'none';
      }
    } catch {
      // Fallback if /api/cart/totals isn’t available: basic client calc
      const subText = $('#subtotal')?.textContent || '$0.00';
      const sub = Number(subText.replace(/[^0-9.]/g, '') || 0);
      const tax = sub * 0.0875; // Miami-Dade
      if ($('#tax-amount')) $('#tax-amount').textContent = fmt(tax);
      if ($('#total')) $('#total').textContent = fmt(sub + tax);
    }
  }

  function attachHandlers() {
    const root = $('.cart-content');
    if (!root) return;

    // Quantity + remove (event delegation)
    root.addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-action]');
      if (!btn) return;

      const action  = btn.dataset.action;
      const id      = Number(btn.dataset.id);
      const variant = btn.dataset.variant === 'null' ? null : (btn.dataset.variant || null);

      if (action === 'remove') {
        await removeFromCart(id, variant);
      } else if (action === 'qty-inc' || action === 'qty-dec') {
        const row = btn.closest('.cart-item');
        const input = row?.querySelector('.quantity-input');
        if (!input) return;
        let next = Number(input.value || 1) + (action === 'qty-inc' ? 1 : -1);
        next = Math.max(1, next);
        await updateQuantity(id, next, variant);
      }
    });

    root.addEventListener('change', async (e) => {
      const input = e.target.closest('.quantity-input');
      if (!input) return;
      const id = Number(input.dataset.id);
      const variant = input.dataset.variant === 'null' ? null : (input.dataset.variant || null);
      await updateQuantity(id, Number(input.value || 1), variant);
    });

    // Discount apply
    const form = $('#cartDiscountForm');
    if (form) form.addEventListener('submit', onApplyDiscount);

    // Checkout
    $('#checkoutBtn')?.addEventListener('click', () => {
      window.location.href = '/checkout';
    });
  }

  async function onApplyDiscount(e) {
    e.preventDefault();
    const input  = $('#cartDiscountCodeInput');
    const button = $('#cartDiscountApplyBtn');
    const msg    = $('#cart-discount-message');

    const code = input?.value.trim().toUpperCase();
    if (!code) return;

    button.disabled = true;

    try {
      const res = await fetch('/api/cart/apply-discount', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRF()
        },
        body: JSON.stringify({ code })
      });

      const data = await res.json();
      if (!res.ok || data.success === false) {
        throw new Error(data.error || 'Invalid or expired discount code.');
      }

      localStorage.setItem(LS_DISCOUNT_KEY, code);

      if (msg) {
        msg.style.display = '';
        msg.style.color = 'var(--success-text, #166534)';
        msg.textContent = `Discount ${code} applied.`;
      }
      if (window.showToast) showToast(`Discount ${code} applied`, 'success');

      await refreshCartSummary();
      enforceAlreadyAppliedState();
    } catch (err) {
      if (msg) {
        msg.style.display = '';
        msg.style.color = '#b91c1c';
        msg.textContent = err.message;
      }
      if (window.showToast) showToast(err.message, 'error');
    } finally {
      button.disabled = false;
    }
  }

  function enforceAlreadyAppliedState() {
    const applied = localStorage.getItem(LS_DISCOUNT_KEY);
    const input  = $('#cartDiscountCodeInput');
    const button = $('#cartDiscountApplyBtn');
    const msg    = $('#cart-discount-message');

    if (applied && input && button) {
      input.disabled = true;
      input.value = applied;
      input.placeholder = 'Discount already applied';
      button.disabled = true;
      if (msg) {
        msg.style.display = '';
        msg.style.color = 'var(--muted-color)';
        msg.textContent = `Code ${applied} is active on your cart.`;
      }
    }
  }

  // --- Server calls ---
  async function updateQuantity(productId, newQty, variantId = null) {
    if (newQty < 1) return removeFromCart(productId, variantId);

    const body = { product_id: productId, quantity: Number(newQty) };
    if (variantId) body.variant_id = variantId;

    const res = await fetch('/api/cart/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
      body: JSON.stringify(body)
    });

    const data = await res.json();
    if (!res.ok) {
      if (window.showToast) showToast(data.error || 'Failed to update quantity', 'error');
      return loadCart(); // revert UI to server state
    }

    if (data.message && window.showToast) showToast('Cart updated', 'success');
    if (window.updateCartCount) updateCartCount();
    await loadCart();
  }

  async function removeFromCart(productId, variantId = null) {
    const body = { product_id: productId };
    if (variantId) body.variant_id = variantId;

    await fetch('/api/cart/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
      body: JSON.stringify(body)
    });

    if (window.updateCartCount) updateCartCount();
    await loadCart();
  }

  // Legacy global (if anything still calls it)
  window.proceedToCheckout = () => { window.location.href = '/checkout'; };
})();
