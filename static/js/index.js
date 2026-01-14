/* ============================================================================
   index.js (cleaned + consolidated)
   - Discount UI unified
   - No duplicate listeners
   - Auth toast shown once (via showStoredAuthMessage)
   - Centralized CSRF handling for POSTs
   - Toast animation uses toastSlideOutRight to match CSS
   ============================================================================ */

'use strict';

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------
let currentSlides = {};
let productImages = {};
const productImageIndexes = {};

// Debug: Log when script loads
console.log('index.js is loading...');

// Initialize cart count IMMEDIATELY when script loads (not waiting for DOM)
(function () {
  const storedCount = localStorage.getItem('cartCount');
  if (storedCount !== null) {
    const count = parseInt(storedCount, 10) || 0;
    const cartCountElement = document.getElementById('cartCount');
    if (cartCountElement) {
      cartCountElement.textContent = count;
      cartCountElement.style.display = count > 0 ? 'inline' : 'none';
      if (count > 0) cartCountElement.classList.add('has-items');
      else cartCountElement.classList.remove('has-items');
    }
  }
})();

// ---------------------------------------------------------------------------
// CSRF helpers (centralize token + fetch)
// ---------------------------------------------------------------------------
function getCSRFToken() {
  return (
    document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
    document.querySelector('meta[name="csrf_token"]')?.getAttribute('content') ||
    document.querySelector('input[name="csrf_token"]')?.value ||
    (document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)?.[1]) ||
    ''
  );
}

function csrfFetch(url, options = {}) {
  const opts = { credentials: 'same-origin', ...options };
  const method = (opts.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD') {
    const token = getCSRFToken();
    opts.headers = {
      ...(opts.headers || {}),
      ...(token ? { 'X-CSRFToken': token, 'X-CSRF-Token': token } : {})
    };
  }
  return fetch(url, opts);
}

function jsonFetch(url, method = 'POST', body = {}) {
  return csrfFetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

// ---------------------------------------------------------------------------
// DISCOUNT CODE UI (PDP + Cart) - unified
// ---------------------------------------------------------------------------
function disableDiscountUI(root) {
  const form = root.querySelector ? root.querySelector('.discount-form') : null;
  const scope = form ? form : (root.closest ? root.closest('.discount-form') : null);
  const container = scope || document;
  const input = container.querySelector('#pdpDiscountInput, #discountCodeInput, .discount-form input[type="text"]');
  const btn = container.querySelector('.discount-form button[type="submit"]');
  if (input) { input.disabled = true; input.setAttribute('aria-disabled', 'true'); }
  if (btn) { btn.disabled = true; btn.classList.add('disabled'); btn.innerHTML = '<i class="fas fa-badge-check"></i> Applied'; }
}

async function applyDiscount(code, ctxLabel = '') {
  code = (code || '').trim();
  if (!code) { showToast('Please enter a discount code.', 'error'); return; }

  // Require at least one item in cart
  try {
    const resCount = await fetch('/api/cart/count', { credentials: 'same-origin' });
    const dataCount = await resCount.json();
    if (!dataCount || !dataCount.count) {
      showToast('Add an item to your cart first.', 'info');
      return;
    }
  } catch (_) {}

  try {
    const res = await jsonFetch('/api/cart/apply-discount', 'POST', { code });
    const data = await res.json();

    if (!res.ok) {
      showToast(data?.message || 'Could not apply discount.', 'error');
      return;
    }

    if (data.already_attached) {
      showToast(data.message || `Promo ${code} is already attached.`, 'info');
    } else {
      const leftTxt = (typeof data.remaining_uses === 'number') ? ` • ${data.remaining_uses} left` : '';
      showToast(`Discount applied! ${code}${leftTxt}. It will reflect in your cart.`, 'success');
    }

    // Disable all discount forms
    document.querySelectorAll('.discount-form').forEach(f => disableDiscountUI(f));

    // If cart UI is open, refresh it
    try {
      if (document.getElementById('cartModal')?.classList.contains('active')) {
        loadCartContents?.();
      }
      if (document.getElementById('cartContent')) {
        loadCart?.();
      }
    } catch (_) {}

  } catch {
    showToast('Network error applying discount.', 'error');
  }
}

function wireDiscountForm(form) {
  if (!form || form.__wiredDiscount) return;
  form.__wiredDiscount = true;

  const input = form.querySelector('#pdpDiscountInput, #discountCodeInput, input[type="text"]');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const raw = (input?.value || '').trim();
    if (!raw) { showToast('Please enter a discount code.', 'error'); return; }
    applyDiscount(raw, form.id === 'pdpDiscountForm' ? 'pdp' : 'cart');
  });
}

async function initDiscountForms() {
  document.querySelectorAll('.discount-form').forEach(wireDiscountForm);
  // If a discount is already attached, disable inputs
  try {
    const res = await fetch('/api/cart/status', { credentials: 'same-origin' });
    if (res.ok) {
      const data = await res.json();
      if (data?.has_discount) {
        document.querySelectorAll('.discount-form').forEach(f => disableDiscountUI(f));
      }
    }
  } catch (_) {}
}

// Call once on DOM ready
document.addEventListener('DOMContentLoaded', () => { initDiscountForms(); });

// ---------------------------------------------------------------------------
// PAGE-LEVEL INIT (age-gate + counts + wishlist boot)
// ---------------------------------------------------------------------------
function initializeCartCountFromStorage() {
  const storedCount = localStorage.getItem('cartCount');
  if (storedCount !== null) {
    const count = parseInt(storedCount, 10) || 0;
    cartCountCache = count;
    updateCartCountDisplay(count);
  }
}

document.addEventListener('DOMContentLoaded', function () {
  // Age verification overlay (blocks page until verified)
  const ageVerificationOverlay = document.getElementById('ageVerificationOverlay');
  if (ageVerificationOverlay) {
    ageVerificationOverlay.style.display = 'flex';
    ageVerificationOverlay.style.visibility = 'visible';
    ageVerificationOverlay.style.opacity = '1';
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';
    document.body.classList.add('no-scroll');

    const yesButton = ageVerificationOverlay.querySelector('.age-btn-yes');
    if (yesButton) setTimeout(() => yesButton.focus(), 100);

    ageVerificationOverlay.addEventListener('click', function (e) {
      if (e.target === ageVerificationOverlay) {
        e.preventDefault();
        e.stopPropagation();
        const modal = ageVerificationOverlay.querySelector('.age-verification-modal');
        if (modal) {
          modal.style.animation = 'shake 0.5s ease-in-out';
          setTimeout(() => { modal.style.animation = ''; }, 500);
        }
      }
    });

    // Stop here (age gate is mandatory)
    return;
  }

  // Initialize cart count from localStorage first
  initializeCartCountFromStorage();

  // Then update from server in background
  updateCartCount(false).catch(() => {
    if (cartCountCache === null) updateCartCountDisplay(0);
  });

  updateWishlistCount();
  initializeWishlistButtons();
  setupButtonEventListeners();
});

// Handle BFCache / visibility
window.addEventListener('pageshow', function (event) {
  if (event.persisted) {
    updateCartCount(true);
    updateWishlistCount();
    initializeWishlistButtons();
  }
});

document.addEventListener('visibilitychange', function () {
  if (!document.hidden) {
    const now = Date.now();
    if (!window.lastVisibilityChange || (now - window.lastVisibilityChange) > 5000) {
      updateCartCount(true);
      updateWishlistCount();
      initializeWishlistButtons();
    }
    window.lastVisibilityChange = now;
  }
});

// Initialize wishlist button states
function initializeWishlistButtons() {
  const wishlistButtons = document.querySelectorAll('.btn-wishlist[data-product-id], .product-card-wishlist[data-product-id]');
  wishlistButtons.forEach(button => {
    const productId = button.dataset.productId;
    if (productId) checkWishlistStatus(productId, button);
  });
}

// ---------------------------------------------------------------------------
// CLICK DELEGATION
// ---------------------------------------------------------------------------
function setupButtonEventListeners() {
  console.log('setupButtonEventListeners called - JavaScript is loading!');

  // Add to cart
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('.btn-add-cart');
    if (!btn) return;
    e.preventDefault();

    const productId = parseInt(btn.dataset.productId);
    const productName = btn.dataset.productName;
    const productPrice = parseFloat(btn.dataset.productPrice);
    const variantId = (btn.dataset.variantId !== undefined && btn.dataset.variantId !== '')
      ? (parseInt(btn.dataset.variantId) || null)
      : null;

    console.log('Add to cart button clicked!');
    console.log('Button element:', btn);
    console.log('Extracted data:', { productId, variantId, productName, productPrice });

    if (!(productId && productName && Number.isFinite(productPrice))) {
      console.log('Missing required data, not calling addToCart');
      return;
    }

    // PDP main button or explicitly marked detail button → pass variant
    if (btn.id === 'addToCartBtn' || btn.classList.contains('btn-add-to-cart-detail')) {
      console.log('Calling addToCartDetail for product detail page...');
      addToCartDetail(productId, productName, productPrice, variantId);
    } else {
      console.log('Calling addToCart for regular product card...');
      addToCart(productId, productName, productPrice, variantId);
    }
  });

  // Wishlist toggle (handles both .btn-wishlist and .product-card-wishlist)
  // Safari fix: handle SVG/nested elements by traversing up to button
  document.addEventListener('click', function (e) {
    let wbtn = e.target.closest('.btn-wishlist, .product-card-wishlist');
    
    // Safari compatibility: if SVG or icon is clicked, find parent button
    if (!wbtn) {
      wbtn = e.target.closest('svg')?.closest('.btn-wishlist, .product-card-wishlist') ||
             e.target.closest('i')?.closest('.btn-wishlist, .product-card-wishlist');
    }
    
    if (!wbtn) return;
    e.preventDefault();
    const productId = parseInt(wbtn.dataset.productId);
    const productName = wbtn.dataset.productName;
    if (productId && productName) toggleWishlist(productId, productName, wbtn);
  });

  // Wishlist remove (list page)
  document.addEventListener('click', function (e) {
    const rbtn = e.target.closest('.btn-remove-wishlist');
    if (!rbtn) return;
    e.preventDefault();
    const productId = parseInt(rbtn.dataset.productId);
    const productName = rbtn.dataset.productName;
    if (productId && productName) removeFromWishlist(productId, productName, rbtn);
  });
}

// (Removed the duplicate: document.addEventListener('DOMContentLoaded', setupButtonEventListeners);)

// ---------------------------------------------------------------------------
// TEST UTIL
// ---------------------------------------------------------------------------
window.testJS = function () {
  const overlay = document.getElementById('authOverlay');
  return 'JavaScript test complete!';
};

// ---------------------------------------------------------------------------
// AUTH MODAL
// ---------------------------------------------------------------------------
window.openAuthModal = function (mode = 'login') {
  const overlay = document.getElementById('authOverlay');
  if (!overlay) return;

  overlay.hidden = false;
  document.body.classList.add('no-scroll');
  document.body.style.overflow = 'hidden';

  const firstInput = mode === 'register'
    ? overlay.querySelector('#regFirst')
    : overlay.querySelector('#loginEmail');
  if (firstInput) firstInput.focus();
};

window.closeAuthModal = function () {
  const overlay = document.getElementById('authOverlay');
  if (!overlay) return;

  overlay.hidden = true;
  document.body.classList.remove('no-scroll');
  document.body.style.overflow = 'auto';

  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  if (loginForm) loginForm.reset();
  if (registerForm) registerForm.reset();
};

window.scrollToLogin = function () {
  const loginPanel = document.querySelector('.login-panel');
  const registerPanel = document.querySelector('.register-panel');

  if (loginPanel) {
    if (window.innerWidth <= 768) {
      if (registerPanel) registerPanel.style.display = 'none';
      loginPanel.style.display = 'block';
      const mobileRegisterLink = document.querySelector('.mobile-register-link');
      if (mobileRegisterLink) mobileRegisterLink.style.display = 'block';
      const emailField = document.getElementById('loginEmail');
      if (emailField) setTimeout(() => emailField.focus(), 100);
    } else {
      loginPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      const emailField = document.getElementById('loginEmail');
      if (emailField) setTimeout(() => emailField.focus(), 300);
    }
  }
};

window.scrollToRegister = function () {
  const loginPanel = document.querySelector('.login-panel');
  const registerPanel = document.querySelector('.register-panel');

  if (registerPanel) {
    if (window.innerWidth <= 768) {
      if (loginPanel) loginPanel.style.display = 'none';
      registerPanel.style.display = 'block';
      const mobileRegisterLink = document.querySelector('.mobile-register-link');
      if (mobileRegisterLink) mobileRegisterLink.style.display = 'none';
      const firstNameField = document.getElementById('regFirst');
      if (firstNameField) setTimeout(() => firstNameField.focus(), 100);
    } else {
      registerPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      const firstNameField = document.getElementById('regFirst');
      if (firstNameField) setTimeout(() => firstNameField.focus(), 300);
    }
  }
};

// Auth inline messages
function showAuthMessage(elementId, message, ok) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = message;
  el.style.display = 'block';
  const siblingId = elementId.replace(ok ? 'Success' : 'Error', ok ? 'Error' : 'Success');
  document.getElementById(siblingId)?.style.setProperty('display', 'none');
}
function showAuthError(id, msg) { showAuthMessage(id, msg, false); }
function showAuthSuccess(id, msg) { showAuthMessage(id, msg, true); }

// ---------------------------------------------------------------------------
// TOASTS
// ---------------------------------------------------------------------------
function showToast(message, type = 'success', opts = {}) {
  const t = (['success','error','info','warning','danger'].includes(type) ? type : 'info');

  // Prefer page-local controller if present (index.html)
  if (typeof window.showFlash === 'function') {
    return window.showFlash(String(message), t, opts);
    // The page-local showFlash already uses 'toastSlideOutRight'
  }

  let toastStack = document.getElementById('flashStack');
  if (!toastStack) {
    toastStack = document.createElement('div');
    toastStack.id = 'flashStack';
    toastStack.className = 'toast-stack';
    document.body.appendChild(toastStack);
  }

  const el = document.createElement('div');
  // add BOTH forms to be future-proof: "toast-success" and "success"
  el.className = `toast toast-${t} ${t}`;
  el.innerHTML = `
    <button class="flash_message_close" onclick="this.parentElement.remove()">
      <i class="fas fa-times"></i>
    </button>
    ${String(message)}
  `;
  toastStack.appendChild(el);

  const ttl = Number(opts.ttl || 3000);
  setTimeout(() => {
    // Match CSS keyframe name
    el.style.animation = 'toastSlideOutRight .35s forwards';
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }, ttl);

  return el;
}

function closeToast(toast) {
  if (toast && toast.parentElement) {
    toast.style.animation = 'toastSlideOutRight 0.4s forwards';
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  }
}

// ---------------------------------------------------------------------------
// ACCOUNT MODAL + LOGOUT
// ---------------------------------------------------------------------------
window.openAccountModal = function () {
  const overlay = document.getElementById('loggedModal');
  const panel = overlay?.querySelector('.logged-modal');
  if (!overlay || !panel) return;

  overlay.style.display = 'flex';
  requestAnimationFrame(() => {
    overlay.classList.add('active');
    panel.classList.add('active');
  });
  document.body.classList.add('no-scroll');
  updateAccountModalCounts();
};

window.closeAccountModal = function () {
  const overlay = document.getElementById('loggedModal');
  const panel = overlay?.querySelector('.logged-modal');
  if (!overlay || !panel) return;

  overlay.classList.remove('active');
  panel.classList.remove('active');

  setTimeout(() => {
    overlay.style.display = 'none';
    document.body.classList.remove('no-scroll');
  }, 300);
};

function updateAccountModalCounts() {
  // Wishlist count
  fetch('/api/wishlist/count')
    .then(safeJson)
    .then(data => {
      const el = document.getElementById('accountWishlistCount');
      if (el) el.textContent = data.count;
    });

  // Cart count
  fetch('/api/cart/count', { credentials: 'same-origin' })
    .then(safeJson)
    .then(data => {
      const el = document.getElementById('accountCartCount');
      if (el) el.textContent = data.count;
    });
}

window.handleLogout = async function () {
  try {
    closeAccountModal();
    showToast('Logging out...', 'info');
    sessionStorage.clear();
    localStorage.removeItem('cart');
    localStorage.removeItem('wishlist');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    await csrfFetch('/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    window.location.assign('/');
  } catch {
    window.location.assign('/');
  }
};

// ---------------------------------------------------------------------------
// CART (global helpers)
// ---------------------------------------------------------------------------
function getCurrentCartQuantity(productId, variantId = null) { return 0; }

window.addToCart = function addToCart(productId, productName, price, variantId = null) {
  console.log('🛒 addToCart called with:', { productId, productName, price, variantId });

  const button = document.querySelector(`button.btn-add-cart[data-product-id="${productId}"]`);
  const isProductDetailPage = document.getElementById('quantityInput') !== null;
  const currentVariantId = isProductDetailPage ? null : (button ? parseInt(button.dataset.variantId) || null : variantId);

  const quantityInput = document.getElementById('quantityInput');
  const quantity = quantityInput ? parseInt(quantityInput.value) || 1 : 1;

  console.log('🚀 Calling addToCartWithQuantity - backend will validate stock and cart limits');
  addToCartWithQuantity(productId, productName, price, quantity, button, currentVariantId);
};

// Product detail page specific add to cart (now forwards variantId)
window.addToCartDetail = function addToCartDetail(productId, productName, price, variantId = null) {
  if (!productId || !productName || !Number.isFinite(Number(price))) {
    showToast('Error: Invalid product information', 'error');
    return;
  }

  const quantityInput = document.getElementById('quantityInput');
  const quantity = quantityInput ? parseInt(quantityInput.value) || 1 : 1;

  const button = document.getElementById('addToCartBtn') || document.querySelector(`button[data-product-id="${productId}"]`);
  if (button && button.disabled) {
    showToast('This item is currently unavailable', 'error');
    return;
  }

  addToCartWithQuantity(productId, productName, price, quantity, button, variantId);
};

function addToCartWithQuantity(productId, productName, price, quantity = 1, buttonElement = null, variantId = null) {
  const cartCountElement = document.getElementById('cartCount');
  if (cartCountElement) {
    cartCountElement.style.transform = 'scale(1.2)';
    setTimeout(() => { cartCountElement.style.transform = 'scale(1)'; }, 150);
  }

  const requestBody = { product_id: productId, quantity };
  if (variantId) requestBody.variant_id = variantId;

  jsonFetch('/api/cart/add', 'POST', requestBody)
    .then(response => response.json().then(data => ({ status: response.status, data })))
    .then(({ status, data }) => {
      if (status === 200 && (data.message || data.success)) {
        const backendCartCount = data.count || 0;
        cartCountCache = backendCartCount;
        cartCountLastFetch = Date.now();
        updateCartCountDisplay(backendCartCount);
        localStorage.setItem('cartCount', backendCartCount.toString());
        showToast(data.message || `${productName} added to cart!`, 'success');
      } else if (status === 400 || data.error) {
        showToast(data.error, 'error');
        if (data.max_additional !== undefined) {
          const quantityInput = document.getElementById('quantityInput');
          if (quantityInput) {
            if (data.max_additional > 0) {
              quantityInput.value = data.max_additional;
              quantityInput.max = data.max_additional;
              setTimeout(() => { showToast(`You can add ${data.max_additional} more of this item`, 'info'); }, 2000);
            } else {
              quantityInput.value = 1;
            }
          }
        }
        updateCartCount(true);
      }
    })
    .catch(() => {
      showToast('Error adding to cart', 'error');
      updateCartCount(true);
    });
}

// ---------------------------------------------------------------------------
// PRODUCT VARIANT SWITCHING (Color selector on product cards)
// ---------------------------------------------------------------------------
window.switchCardVariant = function switchCardVariant(event, productId, variantId, colorHex, colorName) {
  event?.preventDefault?.();
  event?.stopPropagation?.();

  // Find the button element that triggered this
  const colorButton = event?.target?.closest?.('.card-color-option');
  if (colorButton) {
    colorButton.classList.add('active');
    // Remove active class from sibling color buttons
    const siblings = colorButton.parentElement?.querySelectorAll?.('.card-color-option') || [];
    siblings.forEach(btn => {
      if (btn !== colorButton) btn.classList.remove('active');
    });
  }

  // Find the product card container (must include .product-card class to avoid matching color buttons)
  const productCard = document.querySelector(`[data-product-id="${productId}"].product-card`);
  if (!productCard) return;

  // Fetch variant data to get accurate stock status
  fetch(`/api/variant/${variantId}`, { credentials: 'same-origin' })
    .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
    .then(variant => {
      // Get the add-to-cart button in this card
      const addButton = productCard.querySelector('.btn-add-cart');
      if (!addButton) {
        console.warn(`[VARIANT SWITCH] Could not find .btn-add-cart in product card ${productId}`);
        return;
      }

      console.log(`[VARIANT SWITCH] Product ${productId}, Variant ${variantId}:`, {
        is_available: variant.is_available,
        color: variant.color_name,
        qty: variant.quantity_on_hand
      });

      addButton.dataset.variantId = variantId;
      addButton.dataset.isAvailable = String(variant.is_available).toLowerCase();
      const baseName = addButton.dataset.productBaseName || addButton.dataset.productName;
      const label = (variant.color_name || variant.variant_name || '').trim();
      let variantName = variant.display_name || variant.product_name || baseName;
      if (baseName && label) {
        const hasParen = baseName.includes('(') && baseName.endsWith(')');
        if (hasParen) {
          const head = baseName.slice(0, baseName.lastIndexOf('(')).trimEnd();
          variantName = `${head} (${label})`;
        } else {
          variantName = `${baseName} (${label})`;
        }
      }
      if (variantName) {
        addButton.dataset.productName = variantName;
        const titleLink = productCard.querySelector('.product-title a');
        if (titleLink) titleLink.textContent = variantName;
      }

      if (variant.is_available) {
        // In stock: enable button, set to purple/pink color, show "Add to Cart"
        addButton.disabled = false;
        addButton.classList.remove('out-of-stock');
        addButton.classList.add('in-stock');
        console.log(`[VARIANT SWITCH] Added .in-stock class, button classes:`, addButton.className);
        const btnText = addButton.querySelector('.btn-text');
        if (btnText) btnText.innerHTML = 'Add&nbsp;to&nbsp;Cart';
      } else {
        // Out of stock: disable button, set to grey color, show "Out of Stock"
        addButton.disabled = true;
        addButton.classList.remove('in-stock');
        addButton.classList.add('out-of-stock');
        console.log(`[VARIANT SWITCH] Added .out-of-stock class, button classes:`, addButton.className);
        const btnText = addButton.querySelector('.btn-text');
        if (btnText) btnText.innerHTML = 'Out&nbsp;of&nbsp;Stock';
      }

      // Update the card's data-in-stock attribute to show/hide the red "OUT OF STOCK" badge
      productCard.dataset.inStock = String(variant.is_available).toLowerCase();
      console.log(`[VARIANT SWITCH] Updated card.dataset.inStock to: ${productCard.dataset.inStock}`);

      // ========== UPDATE PRODUCT IMAGES FOR NEW VARIANT ==========
      if (variant.images && variant.images.length > 0) {
        const slideshow = productCard.querySelector('.product-card-slideshow');
        if (slideshow) {
          const slides = slideshow.querySelectorAll('.product-slide');
          
          // Update each slide with the new variant's images
          slides.forEach((slide, index) => {
            slide.classList.remove('active');
            if (variant.images[index]) {
              // Update both src (for <img>) and srcset if it's in a <picture>
              slide.src = variant.images[index].url;
              const picture = slide.closest('picture');
              if (picture) {
                const source = picture.querySelector('source[type="image/webp"]');
                if (source) {
                  source.srcset = variant.images[index].url.replace('.png', '__alpha.webp').replace('.jpg', '__alpha.webp').replace('.jpeg', '__alpha.webp');
                }
              }
            }
          });
          
          // Activate the first slide
          if (slides.length > 0) slides[0].classList.add('active');
          
          // Update the image counter
          const counter = slideshow.querySelector('.product-card-image-counter');
          if (counter) {
            const currentSpan = counter.querySelector('.current-image');
            const totalSpan = counter.querySelector('.total-images');
            if (currentSpan) currentSpan.textContent = '1';
            if (totalSpan) totalSpan.textContent = variant.images.length;
          }
          
          console.log(`[VARIANT SWITCH] Updated ${variant.images.length} images for variant ${variantId}`);
        }
      }
    })
    .catch(err => {
      console.error('[VARIANT SWITCH] Error:', err);
      // Fallback: keep current button state if API fails
    });
};

// Cart count management
let cartCountCache = null;
let cartCountLastFetch = 0;
let cartCountFetching = false;
const CART_COUNT_CACHE_DURATION = 1000;

function updateCartCount(forceRefresh = false) {
  const now = Date.now();
  if (!forceRefresh && cartCountCache !== null && (now - cartCountLastFetch) < CART_COUNT_CACHE_DURATION) {
    updateCartCountDisplay(cartCountCache);
    return Promise.resolve(cartCountCache);
  }
  if (cartCountFetching && !forceRefresh) {
    return new Promise((resolve) => setTimeout(() => resolve(cartCountCache || 0), 100));
  }

  cartCountFetching = true;

  return fetch('/api/cart/count', {
    method: 'GET',
    credentials: 'same-origin',
    headers: { 'Cache-Control': 'no-cache' }
  })
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(data => {
      const count = data.count || 0;
      cartCountCache = count;
      cartCountLastFetch = now;
      cartCountFetching = false;
      updateCartCountDisplay(count);
      localStorage.setItem('cartCount', count.toString());
      return count;
    })
    .catch(() => {
      cartCountFetching = false;
      const fallbackCount = cartCountCache !== null ? cartCountCache : 0;
      updateCartCountDisplay(fallbackCount);
      return fallbackCount;
    });
}

function updateCartCountDisplay(count) {
  const cartCountElement = document.getElementById('cartCount');
  if (cartCountElement) {
    cartCountElement.textContent = count;
    cartCountElement.style.display = count > 0 ? 'inline' : 'none';
    if (count > 0) cartCountElement.classList.add('has-items');
    else cartCountElement.classList.remove('has-items');
  }
}

// Shared remove/update cart (usable by modal + cart page)
window.removeFromCart = function removeFromCart(productId, variantId = null) {
  const requestBody = { product_id: productId };
  if (variantId && variantId !== 'null') requestBody.variant_id = variantId;

  jsonFetch('/api/cart/remove', 'POST', requestBody)
    .then(r => r.json())
    .then(data => {
      if (data.message) {
        const newCount = data.count || 0;
        cartCountCache = newCount;
        cartCountLastFetch = Date.now();
        updateCartCountDisplay(newCount);
        localStorage.setItem('cartCount', newCount.toString());
        if (typeof loadCart === 'function') loadCart();
        if (typeof loadCartContents === 'function') loadCartContents();
        showToast('Item removed from cart', 'success');
      } else if (data.error) {
        showToast(data.error, 'error');
      }
    })
    .catch(() => {
      showToast('Error removing item from cart', 'error');
      updateCartCount();
    });
};

window.updateCartItemQuantity = function updateCartItemQuantity(productId, newQuantity, variantId = null) {
  if (newQuantity <= 0) { removeFromCart(productId, variantId); return; }

  const requestBody = { product_id: productId, quantity: newQuantity };
  if (variantId && variantId !== 'null') requestBody.variant_id = variantId;

  jsonFetch('/api/cart/update', 'POST', requestBody)
    .then(r => r.json())
    .then(data => {
      if (data.message) {
        const newCount = data.count || 0;
        cartCountCache = newCount;
        cartCountLastFetch = Date.now();
        updateCartCountDisplay(newCount);
        localStorage.setItem('cartCount', newCount.toString());
        if (typeof loadCartContents === 'function') loadCartContents();
        if (typeof loadCart === 'function') loadCart();
      } else if (data.error) {
        showToast(data.error, 'error');
      }
    })
    .catch(() => {
      showToast('Error updating cart', 'error');
      updateCartCount();
    });
};

// ---------------------------------------------------------------------------
// CART MODAL
// ---------------------------------------------------------------------------
window.openCartModal = function openCartModal() {
  const modal = document.getElementById('cartModal');
  if (!modal) return;
  modal.style.display = 'flex';
  modal.classList.add('active');
  document.body.style.overflow = 'hidden';
  loadCartContents();
};

window.closeCartModal = function closeCartModal() {
  const modal = document.getElementById('cartModal');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }
};

function loadCartContents() {
  const cartLoading = document.getElementById('cartLoading');
  const cartItems = document.getElementById('cartItems');
  const emptyCartModal = document.getElementById('emptyCartModal');
  const cartSummary = document.getElementById('cartSummary');
  const cartModalCount = document.getElementById('cartModalCount');

  if (cartLoading) cartLoading.style.display = 'block';
  if (cartItems) cartItems.style.display = 'none';
  if (emptyCartModal) emptyCartModal.style.display = 'none';
  if (cartSummary) cartSummary.style.display = 'none';

  fetch('/api/cart/', { credentials: 'same-origin' })
    .then(response => {
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return response.json();
    })
    .then(data => {
      if (cartLoading) cartLoading.style.display = 'none';

      if (data.products && data.products.length > 0) {
        const cartHTML = data.products.map(product => `
          <div class="cart-item" data-product-id="${product.id}">
            <img src="${product.image_url || '/static/images/placeholder.jpg'}" alt="${product.name}" class="cart-item-image">
            <div class="cart-item-details">
              <h4>${product.name}</h4>
              <p class="cart-item-price">$${product.price.toFixed(2)}</p>
              <div class="cart-item-quantity">
                <button onclick="updateCartItemQuantity(${product.id}, ${product.quantity - 1}, ${product.variant_id || 'null'})" ${product.quantity <= 1 ? 'disabled' : ''}>-</button>
                <span>${product.quantity}</span>
                <button onclick="updateCartItemQuantity(${product.id}, ${product.quantity + 1}, ${product.variant_id || 'null'})" ${product.quantity >= product.max_quantity ? 'disabled' : ''}>+</button>
              </div>
            </div>
            <div class="cart-item-total">$${product.item_total.toFixed(2)}</div>
            <button class="cart-item-remove" onclick="removeFromCart(${product.id}, ${product.variant_id || 'null'})">
              <i class="fas fa-trash"></i>
            </button>
          </div>
        `).join('');

        if (cartItems) { cartItems.innerHTML = cartHTML; cartItems.style.display = 'block'; }
        if (cartSummary) {
          const totalElement = document.getElementById('cartTotalAmount');
          if (totalElement) totalElement.textContent = data.total.toFixed(2);
          cartSummary.style.display = 'block';
        }
        if (cartModalCount) cartModalCount.textContent = `${data.count} item${data.count !== 1 ? 's' : ''}`;
      } else {
        if (emptyCartModal) emptyCartModal.style.display = 'block';
        if (cartModalCount) cartModalCount.textContent = '0 items';
      }
    })
    .catch(() => {
      if (cartLoading) cartLoading.style.display = 'none';
      if (emptyCartModal) emptyCartModal.style.display = 'block';
    });
}

document.addEventListener('DOMContentLoaded', function () {
  const cartModal = document.getElementById('cartModal');
  if (cartModal) {
    cartModal.addEventListener('click', function (e) {
      if (e.target === cartModal) closeCartModal();
    });
    const closeButton = cartModal.querySelector('.modal-close');
    if (closeButton) closeButton.addEventListener('click', closeCartModal);
  }
});

// ---------------------------------------------------------------------------
// WISHLIST (grid + modal)
// ---------------------------------------------------------------------------
window.toggleWishlist = function toggleWishlist(productId, productName, buttonElement) {
  const isCurrentlyLiked = buttonElement.classList.contains('liked') || buttonElement.classList.contains('in-wishlist');
  if (isCurrentlyLiked) removeFromWishlist(productId, productName, buttonElement);
  else addToWishlist(productId, productName, buttonElement);
};

function addToWishlist(productId, productName, buttonElement) {
  buttonElement.classList.add('liked', 'in-wishlist');
  updateAllWishlistButtons(productId, true);

  const currentCount = parseInt(document.getElementById('wishlistCount')?.textContent || '0');
  updateWishlistCount(currentCount + 1);

  jsonFetch('/api/wishlist/add', 'POST', { product_id: productId })
    .then(safeJson)
    .then(data => {
      if (data.message) {
        updateWishlistCount(data.count);
      } else if (data.error) {
        buttonElement.classList.remove('liked', 'in-wishlist');
        updateAllWishlistButtons(productId, false);
        updateWishlistCount(currentCount);
        showToast(data.error, 'error');
      }
    })
    .catch(() => {
      buttonElement.classList.remove('liked', 'in-wishlist');
      updateAllWishlistButtons(productId, false);
      updateWishlistCount(currentCount);
      showToast('Error adding to wishlist', 'error');
    });
}

function removeFromWishlist(productId, productName, buttonElement) {
  buttonElement.classList.remove('liked', 'in-wishlist');
  updateAllWishlistButtons(productId, false);

  const currentCount = parseInt(document.getElementById('wishlistCount')?.textContent || '0');
  updateWishlistCount(Math.max(0, currentCount - 1));

  jsonFetch('/api/wishlist/remove', 'POST', { product_id: productId })
    .then(safeJson)
    .then(data => {
      if (data.message) {
        updateWishlistCount(data.count);
        const wishlistItem = buttonElement.closest('.wishlist-item');
        if (wishlistItem) {
          wishlistItem.style.transition = 'opacity 0.3s ease';
          wishlistItem.style.opacity = '0';
          setTimeout(() => {
            wishlistItem.remove();
            const remainingItems = document.querySelectorAll('.wishlist-item');
            if (remainingItems.length === 0) {
              const wishlistGrid = document.querySelector('.wishlist-grid');
              if (wishlistGrid) {
                wishlistGrid.innerHTML = `
                  <div class="empty-wishlist">
                    <div class="empty-state">
                      <i class="fas fa-heart-broken"></i>
                      <h2>Your wishlist is empty</h2>
                      <p>Save items you love by clicking the heart icon on any product.</p>
                      <a href="/products" class="btn btn-primary">
                        <i class="fas fa-shopping-bag"></i>
                        Start Shopping
                      </a>
                    </div>
                  </div>
                `;
              }
            }
          }, 300);
        }
      } else if (data.error) {
        buttonElement.classList.add('liked', 'in-wishlist');
        updateAllWishlistButtons(productId, true);
        updateWishlistCount(currentCount);
        showToast(data.error, 'error');
      }
    })
    .catch(() => {
      buttonElement.classList.add('liked', 'in-wishlist');
      updateAllWishlistButtons(productId, true);
      updateWishlistCount(currentCount);
      showToast('Error removing from wishlist', 'error');
    });
}

function updateWishlistCount(count) {
  if (arguments.length > 0) {
    const wishlistCountElement = document.getElementById('wishlistCount');
    if (wishlistCountElement) {
      wishlistCountElement.textContent = count || 0;
      wishlistCountElement.style.display = count > 0 ? 'inline' : 'none';
    }
    return;
  }
  fetch('/api/wishlist/count')
    .then(safeJson)
    .then(data => {
      const wishlistCountElement = document.getElementById('wishlistCount');
      if (wishlistCountElement) {
        wishlistCountElement.textContent = data.count || 0;
        wishlistCountElement.style.display = data.count > 0 ? 'inline' : 'none';
      }
    })
    .catch(() => { });
}

function checkWishlistStatus(productId, buttonElement) {
  fetch(`/api/wishlist/check/${productId}`)
    .then(safeJson)
    .then(data => {
      if (data.in_wishlist) {
        buttonElement.classList.add('liked', 'in-wishlist');
      } else {
        buttonElement.classList.remove('liked', 'in-wishlist');
      }
    })
    .catch(() => { });
}

function updateAllWishlistButtons(productId, inWishlist) {
  const buttons = document.querySelectorAll(`.btn-wishlist[data-product-id="${productId}"]`);
  buttons.forEach(button => {
    if (inWishlist) button.classList.add('liked', 'in-wishlist');
    else button.classList.remove('liked', 'in-wishlist');
  });
}

/* ===== Wishlist modal ===== */
window.openWishlistModal = function openWishlistModal() {
  const modal = document.getElementById('wishlistModal');
  const wishlistModalElement = modal ? modal.querySelector('.wishlist-modal') : null;
  if (modal && wishlistModalElement) {
    modal.style.display = 'block';
    modal.classList.add('active');
    setTimeout(() => { wishlistModalElement.classList.add('show'); }, 10);
    loadWishlistItems();
  }
};

function closeWishlistModal() {
  const modal = document.getElementById('wishlistModal');
  if (modal) {
    modal.classList.remove('active');
    modal.style.display = 'none';
  }
}
window.closeWishlistModal = closeWishlistModal;

function loadWishlistItems() {
  const loadingElement = document.getElementById('wishlistLoading');
  const itemsContainer = document.getElementById('wishlistItems');
  const emptyState = document.getElementById('emptyWishlistModal');
  const countElement = document.getElementById('wishlistModalCount');

  if (loadingElement) loadingElement.style.display = 'block';
  if (itemsContainer) itemsContainer.style.display = 'none';
  if (emptyState) emptyState.style.display = 'none';

  fetch('/api/wishlist')
    .then(safeJson)
    .then(data => {
      if (loadingElement) loadingElement.style.display = 'none';

      if (data.products && data.products.length > 0) {
        if (itemsContainer) itemsContainer.style.display = 'block';
        if (emptyState) emptyState.style.display = 'none';
        if (countElement) countElement.textContent = `${data.count} item${data.count !== 1 ? 's' : ''} saved`;
        populateWishlistModal(data.products);
      } else {
        if (itemsContainer) itemsContainer.style.display = 'none';
        if (emptyState) emptyState.style.display = 'block';
        if (countElement) countElement.textContent = '0 items saved';
      }
    })
    .catch(() => {
      if (loadingElement) loadingElement.style.display = 'none';
      if (itemsContainer) itemsContainer.style.display = 'none';
      if (emptyState) emptyState.style.display = 'block';
    });
}

function populateWishlistModal(products) {
  const container = document.getElementById('wishlistItems');
  if (!container) return;
  container.innerHTML = '';
  products.forEach(product => {
    const item = document.createElement('div');
    item.className = 'wishlist-item';
    item.dataset.productId = product.id;
    item.innerHTML = `
      <div class="wishlist-item-image">
        ${product.image_url
        ? `<img src="${product.image_url.startsWith('http') || product.image_url.startsWith('/static/') ? product.image_url : '/static/' + product.image_url.replace(/^\/+/, '')}" alt="${product.name}" onerror="this.src='/static/img/placeholder.svg'">`
        : `<div class="wishlist-item-placeholder"><i class="fas fa-image"></i></div>`}
      </div>
      <div class="wishlist-item-info">
        <div class="wishlist-item-details">
          <h4>${product.name}</h4>
          <div class="wishlist-item-price">$${parseFloat(product.price).toFixed(2)}</div>
          <div class="wishlist-item-stock ${product.in_stock ? 'in-stock' : 'out-of-stock'}">
            <i class="fas fa-${product.in_stock ? 'check-circle' : 'times-circle'}"></i>
            ${product.in_stock ? 'In Stock' : 'Out of Stock'}
          </div>
        </div>
        <div class="wishlist-item-actions">
          <button class="btn-modal-add-cart" onclick="addToCartFromModal(${product.id}, '${product.name.replace(/'/g, "\\'")}', ${product.price})">
            <i class="fas fa-shopping-cart"></i>
            Add to Cart
          </button>
          <button class="btn-modal-remove" onclick="removeFromWishlistModal(${product.id}, '${product.name.replace(/'/g, "\\'")}')">
            <i class="fas fa-trash"></i>
            Remove
          </button>
        </div>
      </div>
    `;
    container.appendChild(item);
  });
}

function addToCartFromModal(productId, productName, price) {
  const cartCountElement = document.getElementById('cartCount');
  if (cartCountElement) {
    cartCountElement.style.transform = 'scale(1.2)';
    setTimeout(() => { cartCountElement.style.transform = 'scale(1)'; }, 150);
  }

  jsonFetch('/api/cart/add', 'POST', { product_id: productId, quantity: 1 })
    .then(r => r.json())
    .then(data => {
      if (data.message) {
        updateCartCountDisplay(data.count || 0);
      } else if (data.error) {
        showToast(data.error, 'error');
        updateCartCount();
      }
    })
    .catch(() => {
      showToast('Error adding to cart', 'error');
      updateCartCount();
    });
}

async function safeJson(response) {
  try {
    const ct = response.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      const text = await response.text();
      if (text.trim() === '') return {};
      return JSON.parse(text);
    }
    await response.text();
    return {};
  } catch {
    return {};
  }
}

function removeFromWishlistModal(productId, productName) {
  jsonFetch('/api/wishlist/remove', 'POST', { product_id: productId })
    .then(safeJson)
    .then(data => {
      if (data.message) {
        const gridBtn = document.querySelector(`.btn-wishlist[data-product-id="${productId}"]`);
        if (gridBtn) gridBtn.classList.remove('liked');
        const modalItem = document.querySelector(`#wishlistItems .wishlist-item[data-product-id="${productId}"]`);
        if (modalItem) modalItem.remove();
        updateWishlistCount(data.count);
        const countElement = document.getElementById('wishlistModalCount');
        if (countElement) countElement.textContent = `${data.count} item${data.count !== 1 ? 's' : ''} saved`;
        if (data.count === 0) {
          const itemsContainer = document.getElementById('wishlistItems');
          const emptyState = document.getElementById('emptyWishlistModal');
          if (itemsContainer) itemsContainer.style.display = 'none';
          if (emptyState) emptyState.style.display = 'block';
        }
      } else if (data.error) {
        showToast(data.error, 'error');
      }
    })
    .catch(() => { showToast('Error removing from wishlist', 'error'); });
}

// ---------------------------------------------------------------------------
// AUTH FORM INIT + MODAL HANDLERS
// ---------------------------------------------------------------------------
function showStoredAuthMessage() {
  const message = sessionStorage.getItem('authMessage');
  const messageType = sessionStorage.getItem('authMessageType');
  if (message && messageType) {
    showToast(message, messageType);
    sessionStorage.removeItem('authMessage');
    sessionStorage.removeItem('authMessageType');
  }
}

function initializeAuthForms() {
  // REGISTER
  const registerForm = document.getElementById('registerForm');
  if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const data = Object.fromEntries(new FormData(registerForm));
      if (data.password !== data.passwordCon) {
        return showAuthError('registerError', 'Passwords do not match');
      }
      if (data.first_name && data.last_name) {
        data.full_name = `${data.first_name.trim()} ${data.last_name.trim()}`;
      }

      try {
        const resp = await jsonFetch('/auth/register', 'POST', data);
        const res = await resp.json();
        if (!resp.ok || res.error) {
          return showAuthError('registerError', res.error || 'Registration failed');
        }

        // ✅ success
        showAuthSuccess('registerSuccess', res.message || 'Registration successful!');
        sessionStorage.setItem('authMessage', res.message || 'Registration successful!');
        sessionStorage.setItem('authMessageType', 'success');

        // ⛳️ IMPORTANT: skip promo once on the auth-triggered reload
        sessionStorage.setItem('lmn_skip_promo_once', '1');

        setTimeout(() => { closeAuthModal(); location.reload(); }, 1200);
      } catch {
        showAuthError('registerError', 'Registration failed');
      }
    });
  }

  // LOGIN
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const data = Object.fromEntries(new FormData(loginForm));

      try {
        const resp = await jsonFetch('/auth/login', 'POST', data);
        const res = await resp.json();
        if (!resp.ok || res.error) {
          return showAuthError('loginError', res.error || 'Login failed');
        }

        // ✅ success
        showAuthSuccess('loginSuccess', res.message || 'Login successful!');
        sessionStorage.setItem('authMessage', `Welcome back, ${res.user?.full_name || 'there'}!`);
        sessionStorage.setItem('authMessageType', 'success');

        // Optional: sync cart bubble
        if (typeof res.cart_count === 'number') {
          cartCountCache = res.cart_count;
          cartCountLastFetch = Date.now();
          updateCartCountDisplay(res.cart_count);
        } else {
          cartCountCache = null;
          cartCountLastFetch = 0;
        }

        // ⛳️ IMPORTANT: skip promo once on the auth-triggered reload
        sessionStorage.setItem('lmn_skip_promo_once', '1');

        setTimeout(() => { closeAuthModal(); location.reload(); }, 1200);
      } catch {
        showAuthError('loginError', 'Login failed');
      }
    });
  }
}


function initializeAuthModalHandlers() {
  const authOverlay = document.getElementById('authOverlay');
  const authButton = document.getElementById('authButton');
  if (!authOverlay) return;
  authOverlay.hidden = true;

  if (authButton) {
    authButton.addEventListener('click', function (e) {
      e.preventDefault(); e.stopPropagation(); openAuthModal('login');
    });
  }

  authOverlay.querySelectorAll('.auth-close, [data-close-auth]').forEach(btn => {
    btn.onclick = e => { e.preventDefault(); e.stopPropagation(); closeAuthModal(); };
  });

  authOverlay.addEventListener('click', e => { if (e.target === authOverlay) closeAuthModal(); });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !authOverlay.hidden) closeAuthModal();
  });
}

function initializeWishlistModalHandlers() {
  const wishlistModal = document.getElementById('wishlistModal');
  if (!wishlistModal) return;

  wishlistModal.querySelectorAll('.modal-close').forEach(btn => {
    btn.onclick = e => { e.preventDefault(); e.stopPropagation(); closeWishlistModal(); };
  });

  wishlistModal.addEventListener('click', e => { if (e.target === wishlistModal) closeWishlistModal(); });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && wishlistModal.classList.contains('active')) closeWishlistModal();
  });
}

document.addEventListener('DOMContentLoaded', function () {
  showStoredAuthMessage();
  initializeAuthForms();
  initializeAuthModalHandlers();
  initializeWishlistModalHandlers();

  updateCartCount();

  fetch('/api/wishlist/count')
    .then(safeJson)
    .then(data => updateWishlistCount(data.count))
    .catch(() => { });

  document.querySelectorAll('.btn-wishlist[data-product-id]').forEach(button => {
    const productId = parseInt(button.dataset.productId);
    if (productId) checkWishlistStatus(productId, button);
  });
});

// ---------------------------------------------------------------------------
// PASSWORD MODAL + TOGGLE
// ---------------------------------------------------------------------------
window.openPasswordModal = function () {
  const modal = document.getElementById('changePasswordModal');
  if (!modal) return;
  modal.classList.remove('hidden');
  modal.classList.add('active');
  document.body.classList.add('no-scroll');
  document.body.style.overflow = 'hidden';
  const firstInput = modal.querySelector('#currentPassword');
  if (firstInput) firstInput.focus();
};

window.closePasswordModal = function () {
  const modal = document.getElementById('changePasswordModal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.classList.remove('active');
  document.body.classList.remove('no-scroll');
  document.body.style.overflow = 'auto';
  const form = document.getElementById('changePasswordForm');
  if (form) form.reset();
  const errorMsg = document.getElementById('passwordError');
  const successMsg = document.getElementById('passwordSuccess');
  if (errorMsg) { errorMsg.style.display = 'none'; errorMsg.textContent = ''; }
  if (successMsg) { successMsg.style.display = 'none'; successMsg.textContent = ''; }
};

window.togglePasswordVisibility = function (inputId, toggleButton) {
  const input = document.getElementById(inputId);
  if (!input || !toggleButton) return;
  if (input.type === 'password') {
    input.type = 'text';
    toggleButton.classList.remove('fa-eye-slash');
    toggleButton.classList.add('fa-eye');
    toggleButton.setAttribute('aria-label', 'Hide password');
  } else {
    input.type = 'password';
    toggleButton.classList.remove('fa-eye');
    toggleButton.classList.add('fa-eye-slash');
    toggleButton.setAttribute('aria-label', 'Show password');
  }
};

// ---------------------------------------------------------------------------
// ADDRESS MODAL
// ---------------------------------------------------------------------------
window.openAddressModal = function () {
  const modal = document.getElementById('addressModal');
  if (!modal) return;
  modal.classList.remove('hidden');
  modal.classList.add('active');
  document.body.classList.add('no-scroll');
  document.body.style.overflow = 'hidden';
  const firstInput = modal.querySelector('input[type="text"]');
  if (firstInput) firstInput.focus();
};

window.closeAddressModal = function () {
  const modal = document.getElementById('addressModal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.classList.remove('active');
  document.body.classList.remove('no-scroll');
  document.body.style.overflow = 'auto';
  const form = modal.querySelector('form');
  if (form) form.reset();
};

// ---------------------------------------------------------------------------
// SIMPLE NAV UTILS
// ---------------------------------------------------------------------------
window.viewLikedItems = function () { closeAccountModal(); window.location.href = '/wishlist'; };
window.viewCart = function () { window.location.assign('/cart'); };
window.viewOrders = function () { closeAccountModal(); window.location.href = '/my-orders'; };

// ---------------------------------------------------------------------------
// PRODUCT FILTERS + SEARCH
// ---------------------------------------------------------------------------
window.filterProducts = function filterProducts(categorySlug) {
  if (categorySlug === 'all') { window.location.href = '/products'; return; }

  const categoryMap = {
    // Gender categories (pass slug directly - backend will look up by slug)
    'men': 'men',
    'women': 'women',
    // Main categories
    'bdsm': 1,
    'toys': 2,
    'kits': 3,
    'lubricant': 4,
    'lingerie': 5,
    'anal-toys': 58,
    'sexual-enhancements': 59,
    // Subcategories
    'roleplay-kit': 6,
    'masks': 7,
    'bondage-kit': 9,
    'restraints': 10,
    'butt-plug': 11,
    'anal-numbing-gel': 22,
    'dildos': 33,
    'masturbators': 34,
    'cock-pumps': 35,
    'penis-extensions': 37,
    'anal-beads': 38,
    'collars-nipple-clamps': 40,
    'nipple-clamps': 50,
    'douches-and-enemas': 51,
    'strap-on-kits': 54,
    'Water Based Lubricant': 55,
    'oil based': 56,
    'Massage Oil': 57,
    // Toys subcategories reported missing
    'vibrators': 36,
    'wands': 39,
    'cock-rings': 60
  };

  const categoryId = categoryMap[categorySlug];
  if (categoryId) window.location.href = `/products?category=${categoryId}`;
  else window.location.href = '/products';
};

window.handleSearch = function handleSearch() {
  const searchInput = document.getElementById('productSearch');
  const clearButton = document.querySelector('.clear-search-btn');
  if (!searchInput) return;
  const searchTerm = searchInput.value.trim();
  if (clearButton) clearButton.style.display = searchTerm ? 'block' : 'none';

  clearTimeout(window.searchTimeout);
  window.searchTimeout = setTimeout(() => {
    if (searchTerm.length >= 2 || searchTerm.length === 0) {
      const url = new URL('/products', window.location.origin);
      if (searchTerm) url.searchParams.set('search', searchTerm);
      window.location.href = url.toString();
    }
  }, 1500);
};

window.clearSearch = function clearSearch() {
  const searchInput = document.getElementById('productSearch');
  const clearButton = document.querySelector('.clear-search-btn');
  if (searchInput) {
    searchInput.value = '';
    if (clearButton) clearButton.style.display = 'none';
    window.location.href = '/products';
  }
};

window.clearAllFilters = function clearAllFilters() { window.location.href = '/products'; };
window.clearCategoryFilter = function clearCategoryFilter() {
  const url = new URL(window.location);
  url.searchParams.delete('category');
  window.location.href = url.toString();
};

// ---------------------------------------------------------------------------
// QUICK VIEW
// ---------------------------------------------------------------------------
function closeQuickViewModal() {
  const modal = document.getElementById('quickViewModal');
  if (modal) { modal.style.display = 'none'; modal.classList.remove('active'); }
}
function changeQuickViewImage(imageUrl) {
  const mainImage = document.querySelector('#quickViewModal .main-image img');
  if (mainImage) mainImage.src = imageUrl;
}
window.closeQuickViewModal = closeQuickViewModal;
window.closeQuickView = closeQuickViewModal;
window.changeQuickViewImage = changeQuickViewImage;
window.addToCartFromModal = addToCartFromModal;
window.removeFromWishlistModal = removeFromWishlistModal;

// ---------------------------------------------------------------------------
// CART PAGE (full page)
// ---------------------------------------------------------------------------
function loadCart() {
  const cartContent = document.getElementById('cartContent');
  if (!cartContent) return;
  cartContent.innerHTML = `
    <div class="loading-cart" style="text-align: center; padding: 2rem;">
      <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: hsl(var(--primary-color)); margin-bottom: 1rem;"></i>
      <p>Loading your cart...</p>
    </div>
  `;

  fetch('/api/cart/', {
    method: 'GET',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' }
  })
    .then(response => {
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return response.json();
    })
    .then(data => displayCart(data))
    .catch(error => {
      if (!cartContent) return;
      cartContent.innerHTML = `
        <div class="empty-cart">
          <i class="fas fa-exclamation-triangle"></i>
          <h2>Error loading cart</h2>
          <p>Please refresh the page or try again later.</p>
          <p style="font-size: 0.8rem; color: #666;">Error: ${error.message}</p>
          <button onclick="loadCart()" class="continue-shopping">
            <i class="fas fa-refresh"></i>
            Retry
          </button>
        </div>
      `;
    });
}

function displayCart(cartData) {
  const cartContent = document.getElementById('cartContent');
  if (!cartContent) return;

  if (!cartData.products || cartData.products.length === 0) {
    cartContent.innerHTML = `
      <div class="empty-cart">
        <i class="fas fa-shopping-cart"></i>
        <h2>Your cart is empty</h2>
        <p>Add some products to get started!</p>
        <a href="${window.location.origin}/products" class="continue-shopping">
          <i class="fas fa-arrow-left"></i>
          Continue Shopping
        </a>
      </div>
    `;
    return;
  }

  const subtotal = cartData.subtotal;
  const taxRate = 0.0875;
  const taxAmount = subtotal * taxRate;
  const shippingAmount = cartData.shipping;
  const total = cartData.total + taxAmount;

  cartContent.innerHTML = `
    <div class="cart-content">
      <div class="cart-items">
        ${cartData.products.map(item => {
          const sizeDisplay = (item.dimensions && item.dimensions.trim())
            ? `<div class="cart-item-size"><strong>Size:</strong> ${item.dimensions}</div>`
            : `<div class="cart-item-size"><strong>Sizing:</strong> One size fits all / Adjustable</div>`;
          return `
            <div class="cart-item" data-product-id="${item.id}">
              <div class="cart-item-image">
                <img src="${item.image_url || '/static/IMG/placeholder.jpg'}" alt="${item.name}"
                     onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHZpZXdCb3g9IjAgMCA4MCA4MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIiBmaWxsPSIjZjBmMGYwIi8+CjxwYXRoIGQ9Ik0yNSAzNUgzNVYyNUg0NVYzNUg1NVY0NUg0NVY1NUgzNVY0NUgyNVYzNVoiIGZpbGw9IiNjY2MiLz4KPC9zdmc+'">
              </div>
              <div class="cart-item-details">
                <h3>${item.name}</h3>
                ${sizeDisplay}
                <div class="cart-item-price">$${item.price.toFixed(2)}</div>
              </div>
              <div class="quantity-controls">
                <input type="number" class="quantity-input" value="${item.quantity}"
                       onchange="updateQuantity(${item.id}, this.value)"
                       min="1" max="${item.max_quantity}">
                <div class="quantity-buttons">
                  <button class="quantity-btn" onclick="updateQuantity(${item.id}, ${item.quantity - 1})">
                    <i class="fas fa-minus"></i>
                  </button>
                  <button class="quantity-btn" onclick="updateQuantity(${item.id}, ${item.quantity + 1})"
                          ${item.quantity >= item.max_quantity ? 'disabled' : ''}>
                    <i class="fas fa-plus"></i>
                  </button>
                </div>
                ${item.max_quantity <= 5 ? `<small style="color: #ff6b6b; font-size: 0.8rem; margin-top: 0.25rem;">Only ${item.max_quantity} left in stock</small>` : ''}
              </div>
              <div class="cart-item-total">$${item.item_total.toFixed(2)}</div>
              <button class="remove-btn" onclick="removeFromCart(${item.id})">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          `;
        }).join('')}
      </div>

      <div class="cart-summary">
        <h3>Order Summary</h3>
        <div class="summary-row"><span>Subtotal:</span><span>$${subtotal.toFixed(2)}</span></div>
        <div class="summary-row"><span>Tax (8.75%):</span><span>$${taxAmount.toFixed(2)}</span></div>
        <div class="summary-row"><span>Shipping:</span><span>${shippingAmount === 0 ? 'FREE' : '$' + shippingAmount.toFixed(2)}</span></div>
        ${subtotal < 50 ? '<p style="font-size: 0.9rem; color: hsl(var(--muted-color)); margin: 0.5rem 0;">Free shipping on orders over $50</p>' : ''}
        <div class="summary-row total"><span>Total:</span><span>$${total.toFixed(2)}</span></div>
        <button class="checkout-btn" onclick="proceedToCheckout()">
          <i class="fas fa-lock"></i>
          Secure Checkout
        </button>
        <a href="${window.location.origin}/products" class="continue-shopping" style="width: 100%; justify-content: center; margin-top: 1rem;">
          <i class="fas fa-arrow-left"></i>
          Continue Shopping
        </a>
      </div>
    </div>
  `;
}

function updateQuantity(productId, newQuantity) {
  if (newQuantity < 1) { removeFromCart(productId); return; }
  const requestBody = { product_id: productId, quantity: parseInt(newQuantity) };
  jsonFetch('/api/cart/update', 'POST', requestBody)
    .then(response => {
      if (!response.ok) return response.json().then(errorData => { throw new Error(errorData.error || 'Failed to update quantity'); });
      return response.json();
    })
    .then(data => {
      if (data.message) {
        loadCart();
        updateCartCount();
        showToast('Cart updated successfully', 'success');
      }
    })
    .catch(error => {
      showToast(error.message, 'error');
      loadCart();
    });
}

function proceedToCheckout() { window.location.href = '/checkout'; }

window.loadCart = loadCart;
window.displayCart = displayCart;
window.updateQuantity = updateQuantity;
window.proceedToCheckout = proceedToCheckout;

// ---------------------------------------------------------------------------
// PRODUCTS PAGE (image nav + cards)
// ---------------------------------------------------------------------------
function initializeProductImageNavigation() {
  document.querySelectorAll('.product-image[data-product-id]').forEach(productImage => {
    const productId = productImage.getAttribute('data-product-id');
    productImageIndexes[productId] = 0;
  });
}
function navigateProductImage(productId, direction) {
  const productImage = document.querySelector(`.product-image[data-product-id="${productId}"]`);
  if (!productImage) return;

  const imagesDataScript = productImage.querySelector('.product-images-data');
  if (!imagesDataScript) return;

  let allImages;
  try { allImages = JSON.parse(imagesDataScript.textContent); }
  catch { return; }
  if (allImages.length <= 1) return;

  let currentIndex = productImageIndexes[productId] || 0;
  let newIndex = currentIndex + direction;
  if (newIndex >= allImages.length) newIndex = 0;
  else if (newIndex < 0) newIndex = allImages.length - 1;

  productImageIndexes[productId] = newIndex;

  const mainImage = productImage.querySelector('.product-main-image');
  if (mainImage && allImages[newIndex]) mainImage.src = allImages[newIndex];

  const counterElement = productImage.querySelector('.current-image-index');
  if (counterElement) counterElement.textContent = newIndex + 1;
}

function initializeProductsPageSearch() {
  const searchInput = document.getElementById('productSearch');
  const clearButton = document.querySelector('.clear-search-btn');
  if (searchInput && clearButton && searchInput.value.trim()) clearButton.style.display = 'block';
  initializeProductImageNavigation();
  initializeEnhancedProductCards();
}

window.initializeProductImageNavigation = initializeProductImageNavigation;
window.navigateProductImage = navigateProductImage;
window.initializeProductsPageSearch = initializeProductsPageSearch;

/* ===== Enhanced product cards ===== */
function navigateProductCardImage(productId, direction) {
  const slideshow = document.querySelector(`.product-card-slideshow[data-product-id="${productId}"]`);
  if (!slideshow) return;
  const slides = slideshow.querySelectorAll('.product-slide');
  if (slides.length <= 1) return;

  let currentIndex = 0;
  slides.forEach((slide, index) => { if (slide.classList.contains('active')) currentIndex = index; });

  let newIndex = currentIndex + direction;
  if (newIndex >= slides.length) newIndex = 0;
  if (newIndex < 0) newIndex = slides.length - 1;

  slides[currentIndex].classList.remove('active');
  slides[newIndex].classList.add('active');

  const counter = slideshow.querySelector('.product-card-image-counter');
  if (counter) {
    const currentSpan = counter.querySelector('.current-image');
    if (currentSpan) currentSpan.textContent = newIndex + 1;
  }
}

function selectProductColor(productId, variantId, colorHex, colorName) {
  const productCard = document.querySelector(`.product-card[data-product-id="${productId}"]`);
  if (!productCard) return;

  const colorSwatches = productCard.querySelectorAll('.color-swatch');
  colorSwatches.forEach(swatch => {
    swatch.classList.remove('active');
    if (swatch.dataset.variantId == variantId) swatch.classList.add('active');
  });

  const addToCartBtn = productCard.querySelector('.btn-add-cart');
  if (addToCartBtn) addToCartBtn.dataset.variantId = variantId;

  const slideshow = productCard.querySelector('.product-card-slideshow');
  if (slideshow && productCard.dataset.hasVariants === 'true') {
    const variantScript = productCard.querySelector('script[type="application/json"]');
    if (variantScript) {
      try {
        const productData = JSON.parse(variantScript.textContent);
        const selectedVariant = productData.variants.find(v => v.id == variantId);
        if (selectedVariant && selectedVariant.images && selectedVariant.images.length > 0) {
          const slides = slideshow.querySelectorAll('.product-slide');
          slides.forEach((slide, index) => {
            slide.classList.remove('active');
            if (selectedVariant.images[index]) {
              slide.src = selectedVariant.images[index];
              if (index === 0) slide.classList.add('active');
            }
          });
          const counter = slideshow.querySelector('.product-card-image-counter');
          if (counter) {
            const currentSpan = counter.querySelector('.current-image');
            const totalSpan = counter.querySelector('.total-images');
            if (currentSpan) currentSpan.textContent = '1';
            if (totalSpan) totalSpan.textContent = selectedVariant.images.length;
          }
        }
      } catch (e) {
        console.warn('Could not parse variant data:', e);
      }
    }
  }

  console.log(`Selected color: ${colorName} (${colorHex}) for product ${productId}, variant ${variantId}`);
}

function initializeEnhancedProductCards() {
  const slideshows = document.querySelectorAll('.product-card-slideshow');
  slideshows.forEach(slideshow => {
    const slides = slideshow.querySelectorAll('.product-slide');
    if (slides.length > 1) {
      slides[0].classList.add('active');
      const counter = slideshow.querySelector('.product-card-image-counter');
      if (counter) {
        const currentSpan = counter.querySelector('.current-image');
        const totalSpan = counter.querySelector('.total-images');
        if (currentSpan) currentSpan.textContent = '1';
        if (totalSpan) totalSpan.textContent = slides.length;
      }
    }
  });

  const productCards = document.querySelectorAll('.product-card[data-has-variants="true"]');
  productCards.forEach(card => {
    const colorSwatches = card.querySelectorAll('.color-swatch');
    if (colorSwatches.length > 0) colorSwatches[0].classList.add('active');
  });
}

window.navigateProductCardImage = navigateProductCardImage;
window.selectProductColor = selectProductColor;
window.initializeEnhancedProductCards = initializeEnhancedProductCards;
