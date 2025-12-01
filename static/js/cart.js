// static/js/cart.js
// Cart rendering + server-truth discount UI + event wiring (updated)
// With cache-busting for browser consistency (Chrome vs Safari pricing)

(() => {
  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const fmt = (n) => `$${Number(n || 0).toFixed(2)}`;

  // Cache-busting: add timestamp to API calls to force fresh data
  const bustCache = () => `t=${Date.now()}`;

  const getCSRF = () =>
    (typeof window.getCSRFToken === 'function'
      ? window.getCSRFToken()
      : document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')) || '';

  // Clear old cached data (fixes browser cache issues like Chrome vs Safari pricing differences)
  function clearOldCaches() {
    try {
      // Clear localStorage discount-related data
      const keysToRemove = Object.keys(localStorage).filter(k => 
        k.includes('discount') || k.includes('cart') || k.includes('price')
      );
      keysToRemove.forEach(k => localStorage.removeItem(k));
      console.log('✨ Cleared old cached pricing data');
    } catch (e) {
      console.warn('Could not clear localStorage:', e);
    }
    
    // Clear service worker caches if available
    if ('caches' in window) {
      caches.keys().then(cacheNames => {
        cacheNames.forEach(cacheName => {
          if (cacheName.includes('cart') || cacheName.includes('api')) {
            caches.delete(cacheName).catch(() => {});
          }
        });
      }).catch(() => {});
    }
  }

  // ---- Boot ----
  document.addEventListener('DOMContentLoaded', () => {
    clearOldCaches(); // Clear stale cache on page load
    loadCart();
    // react to discount applied/removed from promo modal or DiscountManager
    window.addEventListener('lmn:discount:applied', syncDiscountUIFromServer, { passive: true });
    document.addEventListener('discountApplied',     syncDiscountUIFromServer, { passive: true });
    document.addEventListener('discountRemoved',     syncDiscountUIFromServer, { passive: true });
  });

  // ---- Load + Render ----
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
      // Force fresh data with cache-busting parameter and headers
      const res = await fetch(`/api/cart/?${bustCache()}`, { 
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate' }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      renderCart(mount, data);
      attachHandlers();
      await refreshCartSummary();          // pulls /api/cart/totals
      await syncDiscountUIFromServer();    // fills input/sets button state from server
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
      // If cart empty, ensure discount input is unlocked on this page (user must re-enter)
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

          <div class="discount-code-section cart-discount-section">
            <div class="discount-label">Have a discount code?</div>
            <form id="cartDiscountForm" class="discount-form">
              <div class="discount-input-group">
                <input type="text"
                       class="discount-input"
                       id="cartDiscountCodeInput"
                       placeholder="Enter discount code">
                <button type="submit" class="discount-submit-btn apply-discount-btn" id="cartDiscountApplyBtn">
                  <i class="fas fa-check"></i> Apply
                </button>
              </div>
            </form>
            <small class="discount-message" id="cart-discount-message" style="display:none;"></small>
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

  // ---- Totals (server-truth) ----
  async function refreshCartSummary() {
    try {
      // Force fresh data with cache-busting and no-cache headers
      const res = await fetch(`/api/cart/totals?${bustCache()}`, { 
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate' }
      });
      if (!res.ok) throw new Error('no totals endpoint');
      const t = await res.json();

      const subtotal = t.subtotal ?? 0;
      const tax      = t.tax ?? t.tax_amount ?? 0;
      const discount = t.discount_amount ?? 0;
      const code     = t.discount_code ?? '';
      const ship     = t.delivery_fee ?? t.shipping_fee ?? null;
      const total    = t.total ?? 0;

      $('#subtotal')?.replaceChildren(document.createTextNode(fmt(subtotal)));
      $('#tax-amount')?.replaceChildren(document.createTextNode(fmt(tax)));
      $('#total')?.replaceChildren(document.createTextNode(fmt(total)));
      if ($('#shipping-amount') && ship != null) $('#shipping-amount').textContent = fmt(ship);

      if (discount && discount > 0) {
        $('#discount-row').style.display = '';
        $('#discount-amount').textContent = `-${fmt(discount).replace('$', '$')}`;
        if ($('#discount-code-label')) $('#discount-code-label').textContent = code ? `(${code})` : '';
      } else {
        $('#discount-row').style.display = 'none';
      }
    } catch {
      // minimal fallback (no server)
      const subText = $('#subtotal')?.textContent || '$0.00';
      const sub = Number(subText.replace(/[^0-9.]/g, '') || 0);
      const tax = sub * 0.0875;
      $('#tax-amount') && ($('#tax-amount').textContent = fmt(tax));
      $('#total') && ($('#total').textContent = fmt(sub + tax));
    }
  }

  // ---- Discount UI syncing (server is source of truth) ----
  async function getServerDiscount() {
    // 1) Prefer the canonical discount endpoint (has_discount flag)
    try {
      const r = await fetch(`/api/cart/discount-status?${bustCache()}`, { 
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate' }
      });
      if (r.ok) {
        const d = await r.json();
        if (d.success && d.has_discount && d.discount?.code) {
          return {
            code: String(d.discount.code).toUpperCase(),
            amount: Number(d.discount.discount_amount || d.discount.amount || 0)
          };
        }
      }
    } catch {}

    // 2) Fallback to totals
    try {
      const r = await fetch(`/api/cart/totals?${bustCache()}`, { 
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate' }
      });
      if (r.ok) {
        const t = await r.json();
        if ((t.discount_amount || 0) > 0 && t.discount_code) {
          return {
            code: String(t.discount_code).toUpperCase(),
            amount: Number(t.discount_amount)
          };
        }
      }
    } catch {}

    return null;
  }

  async function getSubtotal() {
    try {
      const r = await fetch(`/api/cart/totals?${bustCache()}`, { 
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache, no-store, must-revalidate' }
      });
      if (r.ok) {
        const t = await r.json();
        return Number(t.subtotal || 0);
      }
    } catch {}
    return 0;
  }

  async function syncDiscountUIFromServer() {
    const section = $('.cart-discount-section');
    if (!section) return;

    const input  = section.querySelector('#cartDiscountCodeInput');
    const button = section.querySelector('#cartDiscountApplyBtn');
    const msg    = section.querySelector('.discount-message');

    // If subtotal is 0, always unlock/clear (user must re-enter after empty cart + refresh)
    const subtotal = await getSubtotal();
    if (subtotal <= 0) {
      unlockInput(); clearMessage(); return;
    }

    const d = await getServerDiscount();

    if (d) {
      // server says: discount is active
      if (input) {
        input.value = d.code;
        input.disabled = true;
        input.placeholder = 'Discount already applied';
      }
      if (button) {
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-badge-check"></i> Applied';
      }
      if (msg) {
        msg.style.display = '';
        msg.style.color = 'var(--muted-color)';
        msg.textContent = `Code ${d.code} is active on your cart.`;
      }
    } else {
      // no active discount → allow typing
      unlockInput(); clearMessage();
    }

    function unlockInput() {
      if (input) {
        input.disabled = false;
        input.value = '';
        input.placeholder = 'Enter discount code';
      }
      if (button) {
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-check"></i> Apply';
      }
    }
    function clearMessage() {
      if (msg) { msg.style.display = 'none'; msg.textContent = ''; }
    }
  }

  // ---- Handlers ----
  function attachHandlers() {
    const root = $('.cart-content');
    if (!root) return;

    // qty + remove (Safari fix: use event delegation with proper target detection)
    root.addEventListener('click', async (e) => {
      // IMPORTANT: In Safari, clicks on nested elements (i, svg) need special handling
      let btn = null;
      
      // Try to find button by data-action attribute
      if (e.target.hasAttribute && e.target.hasAttribute('data-action')) {
        btn = e.target;
      } else {
        // Safari fix: climb up the DOM tree looking for a button with data-action
        let current = e.target;
        while (current && current !== root) {
          if (current.nodeType === Node.ELEMENT_NODE) {
            if (current.tagName === 'BUTTON' && current.hasAttribute('data-action')) {
              btn = current;
              break;
            }
          }
          current = current.parentNode;
        }
      }
      
      if (!btn || !btn.hasAttribute('data-action')) return;

      const action  = btn.dataset.action;
      const id      = Number(btn.dataset.id);
      const variant = btn.dataset.variant === 'null' ? null : (btn.dataset.variant || null);

      if (action === 'remove') {
        e.preventDefault();
        e.stopPropagation();
        await removeFromCart(id, variant);
      } else if (action === 'qty-inc' || action === 'qty-dec') {
        e.preventDefault();
        e.stopPropagation();
        const row = btn.closest('.cart-item');
        const input = row?.querySelector('.quantity-input');
        if (!input) {
          console.error('⚠️ Quantity input not found for cart item');
          return;
        }
        let current = Number(input.value || 1);
        let next = action === 'qty-inc' ? current + 1 : current - 1;
        next = Math.max(0, Math.min(next, Number(input.max || 999)));

        // Only call update if the quantity actually changed
        if (next !== current) {
          console.log(`🛒 Updating quantity: ${current} → ${next} (variant: ${variant})`);
          await updateQuantity(id, next, variant);
        }
      }
    }, { passive: false });

    root.addEventListener('change', async (e) => {
      const input = e.target.closest('.quantity-input');
      if (!input) return;
      const id = Number(input.dataset.id);
      const variant = input.dataset.variant === 'null' ? null : (input.dataset.variant || null);
      await updateQuantity(id, Number(input.value || 1), variant);
    });

    // Apply discount (cart)
    const form = $('#cartDiscountForm');
    if (form) form.addEventListener('submit', onApplyDiscount);

    // Checkout
    $('#checkoutBtn')?.addEventListener('click', () => { window.location.href = '/checkout'; });
  }

  async function onApplyDiscount(e) {
    e.preventDefault();
    const section = $('.cart-discount-section');
    const input  = section?.querySelector('#cartDiscountCodeInput');
    const button = section?.querySelector('#cartDiscountApplyBtn');
    const msg    = section?.querySelector('.discount-message');

    const code = input?.value.trim().toUpperCase();
    if (!code) return;

    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying…';

    try {
      // Validate then apply — same endpoints as promo modal / PDP
      let r = await fetch('/api/validate-discount', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        body: JSON.stringify({ code, cart_total: await getCurrentCartTotal() })
      });
      const v = await r.json();
      if (!r.ok || v.valid === false || v.success === false) {
        throw new Error(v.error || v.message || 'Invalid or ineligible discount code.');
      }

      r = await fetch('/api/cart/apply-discount', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        body: JSON.stringify({ code, cart_total: await getCurrentCartTotal() })
      });
      const a = await r.json();
      if (!r.ok || a.success === false) {
        throw new Error(a.error || a.message || 'Could not apply the code.');
      }

      if (msg) {
        msg.style.display = '';
        msg.style.color = 'var(--success-text, #166534)';
        msg.textContent = `Discount ${code} applied.`;
      }
      if (typeof window.showToast === 'function') window.showToast(`Discount ${code} applied`, 'success');

      await refreshCartSummary();
      await syncDiscountUIFromServer();

      // Tell other scripts (PDP / checkout)
      document.dispatchEvent(new CustomEvent('discountApplied', { detail: { code } }));
      window.dispatchEvent(new CustomEvent('lmn:discount:applied', { detail: { code } }));
    } catch (err) {
      if (msg) {
        msg.style.display = '';
        msg.style.color = '#b91c1c';
        msg.textContent = err.message;
      }
      if (typeof window.showToast === 'function') window.showToast(err.message, 'error');
      // Re-enable so user can retry
      if (button) {
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-check"></i> Apply';
      }
    }
  }

  // ---- Server calls: qty / remove ----
  async function updateQuantity(productId, newQty, variantId = null) {
    if (newQty < 1) return removeFromCart(productId, variantId);

    const body = { product_id: productId, quantity: Number(newQty) };
    if (variantId) body.variant_id = variantId;

    try {
      const res = await fetch('/api/cart/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        body: JSON.stringify(body)
      });

      const data = await res.json();
      if (!res.ok) {
        console.error('❌ Cart update failed:', data);
        if (window.showToast) window.showToast(data.error || 'Failed to update quantity', 'error');
        return;
      }

      console.log('✅ Cart updated successfully:', data);
      await loadCart();           // re-render items
      await refreshCartSummary(); // re-calc totals
      await syncDiscountUIFromServer();
    } catch (err) {
      console.error('💥 Cart update error:', err);
      if (window.showToast) window.showToast('Error updating cart: ' + err.message, 'error');
    }
  }

  async function removeFromCart(productId, variantId = null) {
    const body = { product_id: productId };
    if (variantId) body.variant_id = variantId;

    try {
      console.log('🗑️ Removing item:', body);
      const res = await fetch('/api/cart/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) {
        console.error('❌ Remove failed:', data);
        if (window.showToast) window.showToast(data.error || 'Failed to remove item', 'error');
        return;
      }

      console.log('✅ Item removed successfully:', data);
      await loadCart();
      await refreshCartSummary();
      await syncDiscountUIFromServer();
    } catch (err) {
      console.error('💥 Remove error:', err);
      if (window.showToast) window.showToast('Error removing item: ' + err.message, 'error');
    }
  }

  // ---- Helpers ----
  async function getCurrentCartTotal() {
    try {
      const res = await fetch('/api/cart/totals', { cache: 'no-store' });
      if (res.ok) {
        const t = await res.json();
        return Number(t.subtotal || 0);
      }
    } catch {}
    // fallback: parse UI
    const totalEl = $('#subtotal');
    if (!totalEl) return 0;
    return Number((totalEl.textContent || '').replace(/[^0-9.]/g, '')) || 0;
  }
})();
