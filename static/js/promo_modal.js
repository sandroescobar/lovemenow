// static/js/promo_modal.js
// Behavior:
// - Show ONLY on home page
// - Show ONLY immediately after age verification (short-lived cookie set by /verify-age)
// - Show ONLY once per browser session (reappears only after the browser is closed)
// - Do not alter modal gating or existing cart functionality; only wire the modal's Apply button to existing APIs

(() => {
  const LOG = (...args) => { try { console.log('[PROMO]', ...args); } catch {} };
  const TRIGGER_COOKIE = 'lmn_show_promo';              // set to '1' by /verify-age for ~5 minutes
  const SESSION_SEEN = 'lmn_promo_seen_session';        // session cookie (no max-age)

  function getCookie(name) {
    const m = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : null;
  }

  function setSessionCookie(name, value) {
    document.cookie = `${name}=${encodeURIComponent(value)}; path=/; samesite=Lax`;
  }

  function deleteCookie(name) {
    document.cookie = `${name}=; Max-Age=0; path=/; samesite=Lax`;
  }

  function onHome() {
    const p = location.pathname.replace(/\/+$/, '');
    return (
      p === '' ||
      p === '/' ||
      p === '/index' ||
      p === '/index.html' ||
      p === '/home' ||
      p === '/index_optimized' ||
      p === '/index_optimized.html'
    );
  }

  function selectOverlay() {
    // Prefer ID, but fall back to class selector to handle markup variants
    return document.getElementById('promoOverlay') || document.querySelector('.promo-overlay');
  }

  function openOverlay(overlay) {
    if (!overlay) return;
    overlay.hidden = false;
    overlay.setAttribute('aria-hidden', 'false');
  }

  function closeOverlay(overlay) {
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute('aria-hidden', 'true');
  }

  function wireCloseHandlers(overlay) {
    if (!overlay) return;
    const dialog = overlay.querySelector('.promo-dialog');
    const byId = (id) => overlay.querySelector(`#${id}`);
    const closeBtn = byId('promoCloseBtn');
    const laterBtn = byId('promoLaterBtn');

    closeBtn && closeBtn.addEventListener('click', () => closeOverlay(overlay));
    laterBtn && laterBtn.addEventListener('click', () => closeOverlay(overlay));

    overlay.addEventListener('click', (e) => {
      if (!dialog) return;
      if (!dialog.contains(e.target)) closeOverlay(overlay);
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && overlay && overlay.hidden === false) closeOverlay(overlay);
    });
  }

  // Minimal server helpers (mirrors discount.js behavior)
  function getCSRFToken() {
    const t = document.querySelector('meta[name="csrf-token"]');
    return t ? t.getAttribute('content') : '';
  }

  async function safeJSON(res) {
    const text = await res.text();
    try { return JSON.parse(text); }
    catch { throw new Error(`${res.status} ${res.statusText}: Non-JSON response`); }
  }

  async function fetchTotals() {
    const res = await fetch('/api/cart/totals', { cache: 'no-store' });
    const data = await safeJSON(res);
    if (!res.ok) throw new Error('Failed to get cart totals');
    return data;
  }

  async function validateCode(code, cartTotal) {
    const res = await fetch('/api/validate-discount', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
      body: JSON.stringify({ code, cart_total: cartTotal })
    });
    const data = await safeJSON(res);
    if (!res.ok || data.success === false || data.valid === false) {
      throw new Error(data?.message || 'Invalid or ineligible discount code.');
    }
    return data;
  }

  async function applyCode(code, cartTotal) {
    const res = await fetch('/api/cart/apply-discount', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
      body: JSON.stringify({ code, cart_total: cartTotal })
    });
    const data = await safeJSON(res);
    if (!res.ok || data.success === false) {
      throw new Error(data?.message || 'Could not apply the code.');
    }
    return data;
  }

  function wireApplyHandler(overlay) {
    const applyBtn = overlay.querySelector('#promoApplyBtn');
    const input = overlay.querySelector('#promoCodeInput');
    if (!applyBtn || !input) return;

    applyBtn.addEventListener('click', async () => {
      const code = (input.value || '').trim().toUpperCase();
      if (!code) return;
      if (applyBtn.disabled) return;

      const originalText = applyBtn.textContent;
      try {
        // Apply even if cart is empty — persist code now; totals will update when items are added
        const cartTotal = 0;

        applyBtn.disabled = true;
        applyBtn.textContent = 'Applying…';

        await validateCode(code, cartTotal);
        const res = await applyCode(code, cartTotal);

        // Reflect applied state locally
        applyBtn.textContent = 'Applied';

        // Global notifications and sync so existing UIs update themselves
        if (typeof window.showToast === 'function') window.showToast(res.message || `Discount "${code}" applied!`, 'success');
        document.dispatchEvent(new CustomEvent('discountApplied', { detail: { code } }));
        window.dispatchEvent(new CustomEvent('lmn:discount:applied', { detail: { code } }));
        if (window.discountManager && typeof window.discountManager.syncFromServer === 'function') {
          window.discountManager.syncFromServer();
        }

        // Lock button to avoid re-applying
        applyBtn.disabled = true;
      } catch (e) {
        console.error('[PROMO] apply error', e);
        if (typeof window.showToast === 'function') window.showToast(e.message || 'Error applying discount code. Please try again.', 'error');
        applyBtn.disabled = false;
        applyBtn.textContent = originalText;
      }
    });
  }

  // Decide if we should show the promo now.
  // Primary: show on home, once per session, and immediately after AV when trigger cookie is set.
  // Fallback: if we're on the home page and the overlay is present (server renders it only after AV)
  // and it hasn't shown this session, show once even if the short-lived trigger cookie was dropped by the browser.
  function shouldShow(hasOverlay = false) {
    if (!onHome()) return false;
    if (getCookie(SESSION_SEEN) === '1') return false; // already shown in this browser session
    const triggered = (getCookie(TRIGGER_COOKIE) === '1');
    if (triggered) return true;
    // Fallback path: server only renders the overlay after AV, so if it's present, allow showing once.
    return !!hasOverlay;
  }

  function init() {
    const overlay = selectOverlay();
    if (!overlay) {
      LOG('Promo overlay not found');
      return;
    }

    wireCloseHandlers(overlay);
    wireApplyHandler(overlay);

    if (shouldShow(true)) {
      openOverlay(overlay);
      setSessionCookie(SESSION_SEEN, '1'); // mark shown for this browser session
      deleteCookie(TRIGGER_COOKIE);        // consume one-time AV trigger
      LOG('Promo shown (home + post-AV).');
    } else {
      LOG('Promo not shown (conditions not met).');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();