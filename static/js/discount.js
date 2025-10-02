/**
 * Discount Code Management System
 * Re-validates against the server whenever the cart changes so the amount
 * always matches the current subtotal.
 */

class DiscountManager {
  constructor() {
    this.currentDiscount = null;
    this.isProcessing = false;
    this.init();
  }

  // -------------------------
  // boot
  // -------------------------
  init() {
    this.loadCurrentDiscount();   // pull state on page load
    this.setupEventListeners();
  }

  setupEventListeners() {
    // Let cart.js own clicks inside the cart’s discount section
    document.addEventListener('click', (e) => {
      if (e.target.closest('.cart-discount-section')) return;

      if (e.target.matches('#applyDiscountBtn, .apply-discount-btn')) {
        e.preventDefault();
        this.handleApplyDiscount(e.target);
      }
      if (e.target.matches('#removeDiscountBtn, .remove-discount-btn')) {
        e.preventDefault();
        this.handleRemoveDiscount();
      }
    });

    // Enter key support for general discount inputs
    document.addEventListener('keypress', (e) => {
      if (e.target.matches('#discountCode, .discount-input') && e.key === 'Enter') {
        e.preventDefault();
        const applyBtn = e.target.closest('form, .discount-input-group, body')
          ?.querySelector('.apply-discount-btn, #applyDiscountBtn');
        if (applyBtn) this.handleApplyDiscount(applyBtn);
      }
    });

    // Any time the cart changes, re-sync from server so percent discounts update
    document.addEventListener('cartUpdated', () => this.syncFromServer());
    document.addEventListener('discountApplied', () => this.syncFromServer());
    document.addEventListener('discountRemoved', () => this.syncFromServer());
    window.addEventListener('lmn:discount:applied', () => this.syncFromServer());
  }

  // -------------------------
  // server helpers
  // -------------------------
  getCSRFToken() {
    const t = document.querySelector('meta[name="csrf-token"]');
    return t ? t.getAttribute('content') : '';
  }

  async safeJSON(res) {
    const text = await res.text();
    try { return JSON.parse(text); }
    catch { throw new Error(`${res.status} ${res.statusText}: Non-JSON response`); }
  }

  async fetchDiscountStatus() {
    const res = await fetch('/api/cart/discount-status', {
      method: 'GET',
      cache: 'no-store',
      headers: { 'X-CSRFToken': this.getCSRFToken() }
    });
    const data = await this.safeJSON(res);
    if (!res.ok) throw new Error(data?.message || 'Failed to get discount status');
    return data;
  }

  async fetchTotals() {
    const res = await fetch('/api/cart/totals', { cache: 'no-store' });
    const data = await this.safeJSON(res);
    if (!res.ok) throw new Error('Failed to get cart totals');
    return data;
  }

  // Pull both status + totals and update UI
  async syncFromServer() {
    try {
      const [status, totals] = await Promise.all([
        this.fetchDiscountStatus(),
        this.fetchTotals()
      ]);

      if (status?.has_discount && status?.discount?.code) {
        this.currentDiscount = {
          code: String(status.discount.code).toUpperCase(),
          discount_amount: Number(totals?.discount_amount || status.discount.discount_amount || 0),
          new_total: Number(totals?.total || 0),
          original_total: Number(totals?.subtotal || 0),
          description: status.discount.description || ''
        };
      } else {
        this.currentDiscount = null;
      }

      this.updateDiscountDisplay();
      this.updateCartSummaryFromTotals(totals);
    } catch (err) {
      console.error('syncFromServer error:', err);
    }
  }

  // -------------------------
  // initial load
  // -------------------------
  async loadCurrentDiscount() {
    await this.syncFromServer();
  }

  // -------------------------
  // apply / remove
  // -------------------------
  async handleApplyDiscount(button) {
    if (this.isProcessing) return;

    const container = button.closest('.pdp-discount-section, .cart-discount-section, .checkout-discount-section');
    const input     = container?.querySelector('#discountCode, .discount-input');
    const messageEl = container?.querySelector('#discountMessage, .discount-message');

    const code = (input?.value || '').trim().toUpperCase();
    if (!code) { this.showMessage(messageEl, 'Please enter a discount code', 'error'); return; }

    // You can apply even with subtotal $0 (e.g., pre-cart), but we’ll warn:
    const totalsBefore = await this.fetchTotals().catch(() => null);
    const cartTotal = Number(totalsBefore?.subtotal || 0);
    if (cartTotal <= 0) {
      this.showMessage(messageEl, 'Your cart is empty', 'error');
      // You can still try to apply; comment out the return below to allow it:
      return;
    }

    this.isProcessing = true;
    button.disabled = true;
    button.textContent = 'Applying…';

    try {
      // 1) validate
      let res = await fetch('/api/validate-discount', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCSRFToken() },
        body: JSON.stringify({ code, cart_total: cartTotal })
      });
      let validateData = await this.safeJSON(res);
      if (!res.ok || validateData.success === false || validateData.valid === false) {
        throw new Error(validateData?.message || 'Invalid or ineligible discount code.');
      }

      // 2) persist code
      res = await fetch('/api/cart/apply-discount', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCSRFToken() },
        body: JSON.stringify({ code, cart_total: cartTotal })
      });
      const applyData = await this.safeJSON(res);
      if (!res.ok || applyData.success === false) {
        throw new Error(applyData?.message || 'Could not apply the code.');
      }

      // 3) re-pull status + totals so amount matches *current* subtotal
      await this.syncFromServer();

      if (messageEl) this.showMessage(messageEl, applyData.message || `Discount "${code}" applied!`, 'success');
      if (typeof window.showToast === 'function') {
        const amt = this.currentDiscount ? Number(this.currentDiscount.discount_amount || 0).toFixed(2) : '0.00';
        window.showToast(`Discount "${code}" applied! You save $${amt}`, 'success');
      }

      // broadcast so cart.js / checkout can react
      document.dispatchEvent(new CustomEvent('discountApplied', { detail: { code } }));
      window.dispatchEvent(new CustomEvent('lmn:discount:applied', { detail: { code } }));

      if (input) input.value = '';
    } catch (err) {
      console.error('Error applying discount:', err);
      this.showMessage(messageEl, err.message || 'Error applying discount code. Please try again.', 'error');
    } finally {
      this.isProcessing = false;
      button.disabled = false;
      button.textContent = 'Apply';
    }
  }

  async handleRemoveDiscount() {
    if (this.isProcessing) return;

    this.isProcessing = true;
    try {
      const res = await fetch('/api/cart/remove-discount', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCSRFToken() }
      });
      const data = await this.safeJSON(res);
      if (!res.ok || data.success === false) throw new Error(data?.message || 'Error removing discount.');

      this.currentDiscount = null;
      await this.syncFromServer();

      if (typeof window.showToast === 'function') window.showToast('Discount removed', 'info');
      document.dispatchEvent(new CustomEvent('discountRemoved'));
    } catch (err) {
      console.error('Error removing discount:', err);
    } finally {
      this.isProcessing = false;
    }
  }

  // -------------------------
  // UI updates
  // -------------------------
  updateDiscountDisplay() {
    const sections = document.querySelectorAll('.pdp-discount-section, .cart-discount-section, .checkout-discount-section');

    sections.forEach(section => {
      const input    = section.querySelector('#discountCode, .discount-input');
      const applyBtn = section.querySelector('#applyDiscountBtn, .apply-discount-btn');
      const msg      = section.querySelector('#discountMessage, .discount-message');
      const savings  = section.querySelector('#discountSavings, .discount-savings');
      const amountEl = section.querySelector('#savingsAmount, .savings-amount');

      if (this.currentDiscount) {
        const code = (this.currentDiscount.code || '').toUpperCase();

        if (savings) {
          if (amountEl) amountEl.textContent = `$${Number(this.currentDiscount.discount_amount || 0).toFixed(2)}`;
          savings.style.display = 'flex';
        }

        if (input) {
          input.value = code;
          input.disabled = true;
          input.placeholder = 'Discount already applied';
          input.style.display = 'block';
        }
        if (applyBtn) {
          applyBtn.disabled = true;
          applyBtn.textContent = 'Applied';
          applyBtn.style.display = 'inline-block';
        }
        if (msg) { msg.textContent = ''; msg.className = 'discount-message'; }
      } else {
        if (savings) savings.style.display = 'none';
        if (input) {
          input.disabled = false;
          // don't wipe cart prefill; only clear on non-cart sections
          if (!section.classList.contains('cart-discount-section')) input.value = '';
          input.placeholder = 'Enter discount code';
          input.style.display = 'block';
        }
        if (applyBtn) {
          applyBtn.disabled = false;
          applyBtn.textContent = 'Apply';
          applyBtn.style.display = 'inline-block';
        }
        if (msg) { msg.textContent = ''; msg.className = 'discount-message'; }
      }
    });
  }

  // If the page exposes cart summary fields, keep them synced
  updateCartSummaryFromTotals(totals) {
    if (!totals || typeof document === 'undefined') return;

    const fmt = (n) => `$${Number(n || 0).toFixed(2)}`;

    const subtotalEl = document.querySelector('#subtotal');
    const taxEl      = document.querySelector('#tax-amount');
    const totalEl    = document.querySelector('#total');
    const shipEl     = document.querySelector('#shipping-amount');
    const discRow    = document.querySelector('#discount-row');
    const discAmtEl  = document.querySelector('#discount-amount');
    const discCodeLb = document.querySelector('#discount-code-label');

    if (subtotalEl) subtotalEl.textContent = fmt(totals.subtotal);
    if (taxEl)      taxEl.textContent      = fmt(totals.tax ?? totals.tax_amount);
    if (totalEl)    totalEl.textContent    = fmt(totals.total);
    if (shipEl && (totals.delivery_fee != null)) shipEl.textContent = fmt(totals.delivery_fee);

    const hasDisc = Number(totals.discount_amount || 0) > 0;
    if (discRow) discRow.style.display = hasDisc ? '' : 'none';
    if (discAmtEl) discAmtEl.textContent = `-${fmt(totals.discount_amount).replace('$', '$')}`;
    if (discCodeLb) discCodeLb.textContent = totals.discount_code ? `(${String(totals.discount_code).toUpperCase()})` : '';
  }

  // -------------------------
  // utilities
  // -------------------------
  async getCurrentCartTotal() {
    // Prefer server truth
    try {
      const t = await this.fetchTotals();
      return Number(t.subtotal || 0);
    } catch { /* fall through */ }

    // Fallbacks if needed
    const el = document.querySelector('.cart-total, .checkout-total, #cart-total');
    if (el) {
      const n = parseFloat((el.textContent || '').replace(/[^0-9.]/g, ''));
      if (!isNaN(n)) return n;
    }

    // Last-ditch: compute from DOM items
    let total = 0;
    document.querySelectorAll('.cart-item').forEach(item => {
      const priceEl = item.querySelector('.item-price, .product-price');
      const qtyEl   = item.querySelector('.quantity-input, .item-quantity');
      if (!priceEl || !qtyEl) return;
      const price = parseFloat(priceEl.textContent.replace(/[^0-9.]/g, '')) || 0;
      const qty   = parseInt(qtyEl.value || qtyEl.textContent) || 0;
      total += price * qty;
    });
    return total;
  }

  showMessage(el, msg, type = 'info') {
    if (!el) return;
    el.textContent = msg;
    el.className = `discount-message discount-message-${type}`;
    if (type === 'success') {
      setTimeout(() => { el.textContent = ''; el.className = 'discount-message'; }, 3000);
    }
  }

  // public helpers
  getCurrentDiscount() { return this.currentDiscount; }
  hasDiscount() { return !!this.currentDiscount; }

  async finalizeDiscount(orderId) {
    if (!this.currentDiscount || !orderId) return;
    try {
      const res = await fetch('/api/finalize-discount', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCSRFToken() },
        body: JSON.stringify({ order_id: orderId })
      });
      await this.safeJSON(res).catch(() => ({}));
      // intentionally ignore result; backend should record usage there
      this.currentDiscount = null;
    } catch (e) {
      console.error('Error finalizing discount:', e);
    }
  }
}

// Boot
document.addEventListener('DOMContentLoaded', () => {
  window.discountManager = new DiscountManager();
});

// CommonJS export (tests)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DiscountManager;
}
