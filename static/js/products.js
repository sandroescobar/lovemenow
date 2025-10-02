// static/js/products.js
// Page-scoped helpers for /products (image fallback + Quick View)

(function () {
  'use strict';

  // ------------------------------------------------------------
  // 1) Robust image fallback used by: <img onerror="handleImageError(this)">
  // ------------------------------------------------------------
  window.handleImageError = function (img) {
    try {
      const original = img.getAttribute('data-original-src') || img.src || '';
      if (!img.getAttribute('data-original-src')) img.setAttribute('data-original-src', original);

      const candidates = [
        s => s.replace('__alpha.webp', '.jpg'),
        s => s.replace('_alpha.webp',  '.jpg'),
        s => s.endsWith('.webp') ? s.slice(0, -5) + '.jpg' : s
      ];

      let i = 0;
      function tryNext() {
        if (i >= candidates.length) return genericFallback(img);
        img.onerror = tryNext;
        img.src = candidates[i++](original);
      }
      tryNext();
    } catch (_) {
      genericFallback(img);
    }
  };

  function genericFallback(img) {
    if (!img || !img.parentNode) return;
    img.style.display = 'none';
    const ph = document.createElement('div');
    ph.className = 'image-placeholder';
    ph.style.cssText = 'width:100%;height:240px;background:#f0f0f0;display:flex;align-items:center;justify-content:center;color:#666;font-size:14px;';
    ph.textContent = 'Image not available';
    img.parentNode.insertBefore(ph, img);
  }

  // ------------------------------------------------------------
  // 2) Lightweight Quick View modal
  //    Called by cards: onclick="openQuickView(PRODUCT_ID)"
  // ------------------------------------------------------------

  const CACHE_MS = 5 * 60 * 1000;
  const cache = new Map(); // key -> { data, t }

  // Public API (used by inline handlers)
  window.openQuickView = async function openQuickView(productId) {
    if (!productId) return;

    // toast helper (no-op if toast.js not loaded)
    const toast = (msg, type = 'info', opts = {}) =>
      (window.showFlash ? window.showFlash(msg, type, opts) : void 0);

    // cache
    const key = `product:${productId}`;
    const cached = cache.get(key);
    if (cached && (Date.now() - cached.t) < CACHE_MS) {
      renderQuickView(cached.data);
      return;
    }

    // fetch with timeout
    toast('Loading product…', 'info', { timeout: 1200 });
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);

    try {
      const res = await fetch(`/api/product/${productId}`, {
        credentials: 'same-origin',
        signal: ctrl.signal
      });
      clearTimeout(timer);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const product = await res.json();
      cache.set(key, { data: product, t: Date.now() });
      renderQuickView(product);
    } catch (err) {
      clearTimeout(timer);
      console.error('QuickView fetch failed:', err);
      toast('Could not load product. Please try again.', 'error');
    }
  };

  // helpers for modal
  function ensureQuickViewStyles() {
    if (document.getElementById('quickview-styles')) return;
    const style = document.createElement('style');
    style.id = 'quickview-styles';
    style.textContent = `
      .qm-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:2147483000}
      .qm{background:var(--card-bg, #0b0b0c);color:var(--card-fg, #fff);width:min(920px,92vw);max-height:92vh;border-radius:16px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.45)}
      .qm-body{display:grid;grid-template-columns:1.1fr 1fr;gap:20px;padding:20px}
      .qm-header{display:flex;justify-content:flex-end;padding:10px}
      .qm-close{background:transparent;border:0;color:inherit;font-size:22px;cursor:pointer;opacity:.85}
      .qm-close:hover{opacity:1}
      .qm-img{display:flex;flex-direction:column;gap:10px}
      .qm-main{width:100%;aspect-ratio:1/1;object-fit:contain;background:#111;border-radius:12px}
      .qm-thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(56px,1fr));gap:8px}
      .qm-thumb{width:100%;aspect-ratio:1/1;object-fit:cover;background:#111;border-radius:8px;cursor:pointer;opacity:.85}
      .qm-thumb.active{outline:2px solid hsl(var(--primary-color, 270 80% 60%));opacity:1}
      .qm-info h2{margin:0 0 6px;font-size:20px}
      .qm-price{font-weight:700;margin:4px 0 16px}
      .qm-qty{display:flex;align-items:center;gap:8px;margin:12px 0}
      .qm-qty input{width:64px;padding:6px 8px;border-radius:8px;border:1px solid #333;background:#0f0f10;color:inherit;text-align:center}
      .qm-actions{display:flex;gap:10px;margin-top:10px}
      .qm-primary{background:hsl(var(--primary-color, 270 80% 60%));color:#fff;border:0;border-radius:10px;padding:10px 14px;cursor:pointer}
      .qm-secondary{background:transparent;border:1px solid #444;color:inherit;border-radius:10px;padding:10px 14px;text-decoration:none;text-align:center}
      @media (max-width:820px){ .qm-body{grid-template-columns:1fr} }
    `;
    document.head.appendChild(style);
  }

  function imagesFromProduct(p) {
    // Try several shapes to be robust to API differences
    const arrs = [
      p?.images?.map?.(x => (typeof x === 'string' ? x : x.url)),
      p?.all_image_urls,
      p?.image_urls,
      p?.default_variant?.images?.map?.(x => x.url)
    ].filter(Boolean);
    const flat = [].concat(...arrs).filter(Boolean);
    // de-dupe but keep order
    return [...new Set(flat)];
  }

  function renderQuickView(p) {
    ensureQuickViewStyles();

    const imgs = imagesFromProduct(p);
    const name = p?.name || 'Product';
    const price = (p?.price != null) ? Number(p.price).toFixed(2) : '';

    // overlay
    const overlay = document.createElement('div');
    overlay.className = 'qm-overlay';
    overlay.id = 'quickViewModal';
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeQuickViewModal();
    });

    // modal
    const modal = document.createElement('div');
    modal.className = 'qm';
    modal.innerHTML = `
      <div class="qm-header">
        <button class="qm-close" aria-label="Close">&times;</button>
      </div>
      <div class="qm-body">
        <div class="qm-img">
          <img class="qm-main" id="qmMain" src="${imgs[0] || ''}" alt="${name}" onerror="handleImageError(this)">
          <div class="qm-thumbs" id="qmThumbs"></div>
        </div>
        <div class="qm-info">
          <h2>${name}</h2>
          <div class="qm-price">${price ? `$${price}` : ''}</div>
          <div class="qm-qty">
            <label for="qmQty">Qty</label>
            <input id="qmQty" type="number" min="1" value="1">
          </div>
          <div class="qm-actions">
            <button class="qm-primary" id="qmAdd">Add to Cart</button>
            <a class="qm-secondary" href="/product/${p.id}">View Details</a>
          </div>
        </div>
      </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // close handlers
    modal.querySelector('.qm-close').addEventListener('click', closeQuickViewModal);
    window.addEventListener('keydown', escCloseOnce);

    // thumbnails
    const thumbs = modal.querySelector('#qmThumbs');
    imgs.forEach((src, i) => {
      const t = document.createElement('img');
      t.className = 'qm-thumb' + (i === 0 ? ' active' : '');
      t.src = src;
      t.alt = `${name} ${i + 1}`;
      t.onerror = function () { this.style.display = 'none'; };
      t.addEventListener('click', () => {
        modal.querySelector('#qmMain').src = src;
        [...thumbs.children].forEach(el => el.classList.remove('active'));
        t.classList.add('active');
      });
      thumbs.appendChild(t);
    });

    // add to cart
    modal.querySelector('#qmAdd').addEventListener('click', () => {
      const qty = Math.max(1, parseInt(document.getElementById('qmQty').value || '1', 10));
      // If your index.js exposes addToCartWithQuantity, use it; else fall back to addToCart *qty* times.
      const nameSafe = p.name || 'Product';
      if (typeof window.addToCartWithQuantity === 'function') {
        window.addToCartWithQuantity(p.id, nameSafe, Number(p.price || 0), qty, null, p.default_variant?.id || null);
      } else if (typeof window.addToCart === 'function') {
        for (let i = 0; i < qty; i++) window.addToCart(p.id, nameSafe, Number(p.price || 0), p.default_variant?.id || null);
      }
      if (window.showFlash) window.showFlash('Added to cart', 'success', { timeout: 1500 });
      closeQuickViewModal();
    });
  }

  function escCloseOnce(e) {
    if (e.key === 'Escape') {
      closeQuickViewModal();
    }
  }

  // Public API to close
  window.closeQuickViewModal = function closeQuickViewModal() {
    const overlay = document.getElementById('quickViewModal');
    if (overlay) overlay.remove();
    window.removeEventListener('keydown', escCloseOnce);
  };

  // Optional: hook for products page initialization
  document.addEventListener('DOMContentLoaded', () => {
    // If your index.js exposes search/filter functions, nothing else to do here.
    // This file only supplies image fallback + quick view.
  });
})();
