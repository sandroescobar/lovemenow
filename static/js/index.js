// Global variables
let currentSlides = {};
let productImages = {};

// Debug: Log when script loads

// Initialize cart count IMMEDIATELY when script loads (not waiting for DOM)
(function() {
    const storedCount = localStorage.getItem('cartCount');
    if (storedCount !== null) {
        const count = parseInt(storedCount, 10) || 0;
        // Try to update display immediately if element exists
        const cartCountElement = document.getElementById('cartCount');
        if (cartCountElement) {
            cartCountElement.textContent = count;
            cartCountElement.style.display = count > 0 ? 'inline' : 'none';
            if (count > 0) {
                cartCountElement.classList.add('has-items');
            } else {
                cartCountElement.classList.remove('has-items');
            }
        }
    }
})();

// Initialize cart count from localStorage function
function initializeCartCountFromStorage() {
    const storedCount = localStorage.getItem('cartCount');
    if (storedCount !== null) {
        const count = parseInt(storedCount, 10) || 0;
        cartCountCache = count;
        updateCartCountDisplay(count);
    }
}

// Initialize page when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    
    // Check for age verification modal and ensure it's working
    const ageVerificationOverlay = document.getElementById('ageVerificationOverlay');
    if (ageVerificationOverlay) {
        // Ensure the modal is visible and blocks interaction
        ageVerificationOverlay.style.display = 'flex';
        ageVerificationOverlay.style.visibility = 'visible';
        ageVerificationOverlay.style.opacity = '1';
        
        // Block page scrolling
        document.body.style.overflow = 'hidden';
        document.documentElement.style.overflow = 'hidden';
        document.body.classList.add('no-scroll');
        
        // Focus on the "I am 18+" button for accessibility
        const yesButton = ageVerificationOverlay.querySelector('.age-btn-yes');
        if (yesButton) {
            setTimeout(() => yesButton.focus(), 100);
        }
        
        // Prevent clicking outside the modal to close it (age verification is mandatory)
        ageVerificationOverlay.addEventListener('click', function(e) {
            if (e.target === ageVerificationOverlay) {
                e.preventDefault();
                e.stopPropagation();
                
                // Shake the modal to indicate it can't be closed
                const modal = ageVerificationOverlay.querySelector('.age-verification-modal');
                if (modal) {
                    modal.style.animation = 'shake 0.5s ease-in-out';
                    setTimeout(() => {
                        modal.style.animation = '';
                    }, 500);
                }
            }
        });
        
        // Prevent any other interactions until age is verified
        return;
    }
    
    // Initialize cart count from localStorage first
    initializeCartCountFromStorage();
    
    // Then update from server in background (don't force refresh if we have recent cache)
    updateCartCount(false).catch(error => {
        // Fallback: keep the stored value or set to 0
        if (cartCountCache === null) {
            updateCartCountDisplay(0);
        }
    });
    
    updateWishlistCount();
    
    // Initialize wishlist button states for all products on the page
    initializeWishlistButtons();
    
    // Set up event delegation for buttons
    setupButtonEventListeners();
    
    // Check for stored auth messages
    const authMessage = sessionStorage.getItem('authMessage');
    const authMessageType = sessionStorage.getItem('authMessageType');
    if (authMessage) {
        showToast(authMessage, authMessageType || 'info');
        sessionStorage.removeItem('authMessage');
        sessionStorage.removeItem('authMessageType');
    }
});

// Essential cart count updates - minimal but functional
window.addEventListener('pageshow', function(event) {
    // This fires when page is loaded from cache (back/forward navigation)
    if (event.persisted) {
        updateCartCount(true);
        updateWishlistCount();
        initializeWishlistButtons();
    }
});

// Update cart count when page becomes visible (for login/logout state changes)
document.addEventListener('visibilitychange', function() {
    if (!document.hidden) {
        // Only update if page has been hidden for more than 5 seconds (avoid spam)
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
    const wishlistButtons = document.querySelectorAll('.btn-wishlist[data-product-id]');
    
    wishlistButtons.forEach(button => {
        const productId = button.dataset.productId;
        if (productId) {
            checkWishlistStatus(productId, button);
        }
    });
}

// Set up event delegation for buttons
function setupButtonEventListeners() {
    
    // Event delegation for add to cart buttons
    document.addEventListener('click', function(e) {
        if (e.target.closest('.btn-add-cart')) {
            e.preventDefault();
            const button = e.target.closest('.btn-add-cart');
            const productId = parseInt(button.dataset.productId);
            const productName = button.dataset.productName;
            const productPrice = parseFloat(button.dataset.productPrice);
            
            if (productId && productName && productPrice) {
                addToCart(productId, productName, productPrice);
            }
        }
        
        // Event delegation for product detail add to cart button
        if (e.target.closest('.btn-add-to-cart-detail')) {
            e.preventDefault();
            const button = e.target.closest('.btn-add-to-cart-detail');
            const productId = parseInt(button.dataset.productId);
            const productName = button.dataset.productName;
            const productPrice = parseFloat(button.dataset.productPrice);
            
            if (productId && productName && productPrice) {
                addToCartDetail(productId, productName, productPrice);
            }
        }
    });
    
    // Event delegation for wishlist buttons
    document.addEventListener('click', function(e) {
        if (e.target.closest('.btn-wishlist')) {
            e.preventDefault();
            const button = e.target.closest('.btn-wishlist');
            const productId = parseInt(button.dataset.productId);
            const productName = button.dataset.productName;
            
            if (productId && productName) {
                toggleWishlist(productId, productName, button);
            }
        }
        
        // Event delegation for remove from wishlist buttons (on wishlist page)
        if (e.target.closest('.btn-remove-wishlist')) {
            e.preventDefault();
            const button = e.target.closest('.btn-remove-wishlist');
            const productId = parseInt(button.dataset.productId);
            const productName = button.dataset.productName;
            
            if (productId && productName) {
                removeFromWishlist(productId, productName, button);
            }
        }
    });
}

// Test function to verify JavaScript is working
window.testJS = function() {
    const overlay = document.getElementById('authOverlay');
    return 'JavaScript test complete!';
};

// ============================================================================
// AUTH MODAL FUNCTIONS
// ============================================================================

/**
 * Open the combined auth modal and lock page scrolling
 * @param {'login'|'register'} mode
 */
window.openAuthModal = function (mode = 'login') {
    const overlay = document.getElementById('authOverlay');
    if (!overlay) {
        return;
    }

    // Show the modal
    overlay.hidden = false;
    document.body.classList.add('no-scroll');
    document.body.style.overflow = 'hidden';
    
    // Focus the appropriate field based on mode
    const firstInput = mode === 'register' ? 
        overlay.querySelector('#regFirst') : 
        overlay.querySelector('#loginEmail');
    if (firstInput) firstInput.focus();
};

/**
 * Close the auth modal (with graceful fade-out)
 */
window.closeAuthModal = function () {
    const overlay = document.getElementById('authOverlay');
    if (!overlay) return;

    overlay.hidden = true;
    document.body.classList.remove('no-scroll');
    document.body.style.overflow = 'auto';

    // Reset forms
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    if (loginForm) loginForm.reset();
    if (registerForm) registerForm.reset();
};

// Helper: blank out auth success / error banners
function clearAuthMessages() {
    document.querySelectorAll('#authOverlay .error-message, #authOverlay .success-message')
        .forEach(el => { 
            el.textContent = ''; 
            el.style.display = 'none'; 
        });
}

// Small utilities for showing inline messages
function showAuthError(id, msg) { 
    showAuthMessage(id, msg, false); 
}
function showAuthSuccess(id, msg) { 
    showAuthMessage(id, msg, true); 
}
function showAuthMessage(elementId, message, ok) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = message;
    el.style.display = 'block';
    // Hide the sibling (error ↔ success)
    const siblingId = elementId.replace(ok ? 'Success' : 'Error', ok ? 'Error' : 'Success');
    document.getElementById(siblingId)?.style.setProperty('display', 'none');
}

// Toast notification system
function showToast(message, type = 'success') {
    // Create toast stack if it doesn't exist
    let toastStack = document.getElementById('flashStack');
    if (!toastStack) {
        toastStack = document.createElement('div');
        toastStack.id = 'flashStack';
        toastStack.className = 'toast-stack';
        document.body.appendChild(toastStack);
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <button class="flash_message_close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
        ${message}
    `;
    
    // Add to stack
    toastStack.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 5000);
}

// ============================================================================
// ACCOUNT MODAL FUNCTIONS
// ============================================================================

/**
 * Update the counts in the account modal
 */
function updateAccountModalCounts() {
    // Update wishlist count
    const wishlistCount = document.getElementById('accountWishlistCount');
    const mainWishlistCount = document.getElementById('wishlistCount');
    if (wishlistCount && mainWishlistCount) {
        wishlistCount.textContent = mainWishlistCount.textContent || '0';
    }
    
    // Update cart count
    const cartCount = document.getElementById('accountCartCount');
    const mainCartCount = document.getElementById('cartCount');
    if (cartCount && mainCartCount) {
        cartCount.textContent = mainCartCount.textContent || '0';
    }
}

/**
 * Handle logout with proper POST request
 */
window.handleLogout = async function() {
    try {
        
        // Close the account modal immediately
        closeAccountModal();
        
        const response = await fetch('/auth/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin' // Ensure cookies are sent
        });
        
        const result = await response.json();
        
        if (response.ok) {
            
            // Clear any local storage/session data
            sessionStorage.removeItem('cart');
            sessionStorage.removeItem('wishlist');
            localStorage.removeItem('cart');
            localStorage.removeItem('wishlist');
            
            // Store logout message for after page reload
            sessionStorage.setItem('authMessage', 'Logged out successfully!');
            sessionStorage.setItem('authMessageType', 'success');
            
            // Update UI immediately to show logged out state
            const userMenuButton = document.getElementById('userMenuButton');
            const authButton = document.getElementById('authButton');
            
            if (userMenuButton) {
                userMenuButton.style.display = 'none';
            }
            if (authButton) {
                authButton.style.display = 'inline-block';
                authButton.textContent = 'Sign Up';
                authButton.onclick = () => openAuthModal('login');
            }
            
            // Reset cart and wishlist counts
            const cartCount = document.getElementById('cartCount');
            const wishlistCount = document.getElementById('wishlistCount');
            if (cartCount) {
                cartCount.textContent = '0';
                cartCount.classList.remove('has-items');
            }
            if (wishlistCount) {
                wishlistCount.textContent = '0';
                wishlistCount.style.display = 'none';
            }
            
            // Wait a moment to ensure the logout is processed, then reload
            setTimeout(() => {
                // Force a complete page reload with cache bypass
                window.location.reload(true);
            }, 100);
            
        } else {
            showToast('Logout failed. Please try again.', 'error');
        }
    } catch (error) {
        showToast('Logout failed. Please try again.', 'error');
    }
}

// ============================================================================
// CART FUNCTIONS
// ============================================================================

window.addToCart = function addToCart(productId, productName, price) {

    // Find the button that was clicked to check stock
    const button = document.querySelector(`button[data-product-id="${productId}"]`);
    const quantityOnHand = button ? parseInt(button.dataset.quantityOnHand) || 0 : 0;
    
    // Check if product is in stock
    if (quantityOnHand <= 0) {
        showToast('This item is currently out of stock', 'error');
        return;
    }

    // Check if we're on a product detail page and get quantity from input
    const quantityInput = document.getElementById('quantityInput');
    const quantity = quantityInput ? parseInt(quantityInput.value) || 1 : 1;
    
    // Validate quantity doesn't exceed stock
    if (quantity > quantityOnHand) {
        showToast(`Only ${quantityOnHand} items available in stock`, 'error');
        return;
    }

    // Check if user is authenticated for wishlist functionality
    // Cart should work for both authenticated and guest users
    addToCartWithQuantity(productId, productName, price, quantity, button);
}

// Product detail page specific add to cart function
window.addToCartDetail = function addToCartDetail(productId, productName, price) {

    // Validate input parameters
    if (!productId || !productName || !price) {
        showToast('Error: Invalid product information', 'error');
        return;
    }

    // Get quantity from the quantity selector if it exists
    const quantityInput = document.getElementById('quantityInput');
    const quantity = quantityInput ? parseInt(quantityInput.value) || 1 : 1;
    
    // Find the add to cart button
    const button = document.getElementById('addToCartBtn') || document.querySelector(`button[data-product-id="${productId}"]`);
    const quantityOnHand = button ? parseInt(button.dataset.quantityOnHand) || 0 : 0;
    
    
    // Check if button is disabled
    if (button && button.disabled) {
        showToast('This item is currently unavailable', 'error');
        return;
    }
    
    // Check if product is in stock
    if (quantityOnHand <= 0) {
        showToast('This item is currently out of stock', 'error');
        return;
    }

    // Check if requested quantity is available
    if (quantity > quantityOnHand) {
        showToast(`Only ${quantityOnHand} items available in stock`, 'error');
        return;
    }
    addToCartWithQuantity(productId, productName, price, quantity, button);
}

function addToCartWithQuantity(productId, productName, price, quantity = 1, buttonElement = null) {

    // Check if product is in stock
    const productCard = document.querySelector(`.product-card[data-product-id="${productId}"]`);
    const button = buttonElement || document.querySelector(`button[data-product-id="${productId}"]`);
    const isInStock = productCard ? productCard.dataset.inStock !== 'false' : true;

    if (!isInStock) {
        showToast('This item is currently out of stock', 'error');
        return;
    }

    // Show immediate visual feedback
    const cartCountElement = document.getElementById('cartCount');
    if (cartCountElement) {
        cartCountElement.style.transform = 'scale(1.2)';
        setTimeout(() => {
            cartCountElement.style.transform = 'scale(1)';
        }, 150);
    }

    // Send request to server
    fetch('/api/cart/add', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            product_id: productId,
            quantity: quantity
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            // Update cart count cache and display with server response
            const newCount = data.count || 0;
            cartCountCache = newCount;
            cartCountLastFetch = Date.now();
            updateCartCountDisplay(newCount);
            // Store in localStorage for persistence across page loads
            localStorage.setItem('cartCount', newCount.toString());
            
            showToast(`${productName} added to cart!`, 'success');
        } else if (data.error) {
            showToast(data.error, 'error');
            // Refresh cart count on error to ensure accuracy
            updateCartCount(true);
        }
    })
    .catch(error => {
        showToast('Error adding to cart', 'error');
        // Refresh cart count on error to ensure accuracy
        updateCartCount(true);
    });
}

// Global cart count management - reliable and fast with caching and retry logic
let cartCountCache = null;
let cartCountLastFetch = 0;
let cartCountFetching = false;
const CART_COUNT_CACHE_DURATION = 1000; // 1 second cache for faster updates

// Initialize cart count from localStorage immediately
function initializeCartCountFromStorage() {
    const storedCount = localStorage.getItem('cartCount');
    if (storedCount !== null) {
        const count = parseInt(storedCount, 10) || 0;
        cartCountCache = count;
        updateCartCountDisplay(count);
    }
}

function updateCartCount(forceRefresh = false) {
    const now = Date.now();
    
    // Return cached value if recent and not forcing refresh
    if (!forceRefresh && cartCountCache !== null && (now - cartCountLastFetch) < CART_COUNT_CACHE_DURATION) {
        updateCartCountDisplay(cartCountCache);
        return Promise.resolve(cartCountCache);
    }
    
    // Prevent multiple simultaneous requests
    if (cartCountFetching && !forceRefresh) {
        return new Promise((resolve) => {
            setTimeout(() => resolve(cartCountCache || 0), 100);
        });
    }
    
    cartCountFetching = true;
    
    return fetch('/api/cart/count', {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
            'Cache-Control': 'no-cache'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        const count = data.count || 0;
        cartCountCache = count;
        cartCountLastFetch = now;
        cartCountFetching = false;
        updateCartCountDisplay(count);
        // Store in localStorage for persistence across page loads
        localStorage.setItem('cartCount', count.toString());
        return count;
    })
    .catch(error => {
        cartCountFetching = false;
        
        // Return cached value or 0 - no retry to prevent race conditions
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
        
        // Visual feedback
        if (count > 0) {
            cartCountElement.classList.add('has-items');
        } else {
            cartCountElement.classList.remove('has-items');
        }
    }
}

// Remove item from cart function (global)
window.removeFromCart = function removeFromCart(productId) {
    fetch('/api/cart/remove', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            product_id: productId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            // Update cart count cache and display with server response
            const newCount = data.count || 0;
            cartCountCache = newCount;
            cartCountLastFetch = Date.now();
            updateCartCountDisplay(newCount);
            // Store in localStorage for persistence across page loads
            localStorage.setItem('cartCount', newCount.toString());
            
            // If we're on the cart page, reload the cart
            if (typeof loadCart === 'function') {
                loadCart();
            }
        } else if (data.error) {
            showToast(data.error, 'error');
        }
    })
    .catch(error => {
        showToast('Error removing item from cart', 'error');
        updateCartCount();
    });
}

// Update cart item quantity function (for cart modal)
window.updateCartItemQuantity = function updateCartItemQuantity(productId, newQuantity) {
    if (newQuantity <= 0) {
        removeFromCart(productId);
        return;
    }

    fetch('/api/cart/update', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            product_id: productId,
            quantity: newQuantity
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            // Update cart count with server response
            const newCount = data.count || 0;
            cartCountCache = newCount;
            cartCountLastFetch = Date.now();
            updateCartCountDisplay(newCount);
            // Store in localStorage for persistence across page loads
            localStorage.setItem('cartCount', newCount.toString());
            
            // Reload cart contents to reflect changes
            loadCartContents();
        } else if (data.error) {
            showToast(data.error, 'error');
        }
    })
    .catch(error => {
        showToast('Error updating cart', 'error');
        updateCartCount();
    });
}

// ============================================================================
// CART MODAL FUNCTIONS
// ============================================================================

window.openCartModal = function openCartModal() {
    const modal = document.getElementById('cartModal');
    if (!modal) {
        return;
    }
    
    modal.style.display = 'flex';
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    
    // Load cart contents
    loadCartContents();
}

window.closeCartModal = function closeCartModal() {
    const modal = document.getElementById('cartModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

function loadCartContents() {
    const cartLoading = document.getElementById('cartLoading');
    const cartItems = document.getElementById('cartItems');
    const emptyCartModal = document.getElementById('emptyCartModal');
    const cartSummary = document.getElementById('cartSummary');
    const cartModalCount = document.getElementById('cartModalCount');
    
    // Minimize loading state visibility for faster perceived performance
    if (cartLoading) cartLoading.style.display = 'block';
    if (cartItems) cartItems.style.display = 'none';
    if (emptyCartModal) emptyCartModal.style.display = 'none';
    if (cartSummary) cartSummary.style.display = 'none';
    
    fetch('/api/cart/', {
        credentials: 'same-origin'
    })
        .then(response => response.json())
        .then(data => {
            // Hide loading immediately
            if (cartLoading) cartLoading.style.display = 'none';
            
            if (data.products && data.products.length > 0) {
                // Build cart items HTML efficiently
                const cartHTML = data.products.map(product => `
                    <div class="cart-item" data-product-id="${product.id}">
                        <img src="${product.image_url || '/static/images/placeholder.jpg'}" alt="${product.name}" class="cart-item-image">
                        <div class="cart-item-details">
                            <h4>${product.name}</h4>
                            <p class="cart-item-price">$${product.price.toFixed(2)}</p>
                            <div class="cart-item-quantity">
                                <button onclick="updateCartItemQuantity(${product.id}, ${product.quantity - 1})" ${product.quantity <= 1 ? 'disabled' : ''}>-</button>
                                <span>${product.quantity}</span>
                                <button onclick="updateCartItemQuantity(${product.id}, ${product.quantity + 1})" ${product.quantity >= product.max_quantity ? 'disabled' : ''}>+</button>
                            </div>
                        </div>
                        <div class="cart-item-total">$${product.item_total.toFixed(2)}</div>
                        <button class="cart-item-remove" onclick="removeFromCart(${product.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                `).join('');
                
                if (cartItems) {
                    cartItems.innerHTML = cartHTML;
                    cartItems.style.display = 'block';
                }
                
                // Update summary
                if (cartSummary) {
                    const totalElement = document.getElementById('cartTotalAmount');
                    if (totalElement) totalElement.textContent = data.total.toFixed(2);
                    cartSummary.style.display = 'block';
                }
                
                // Update count
                if (cartModalCount) cartModalCount.textContent = `${data.count} item${data.count !== 1 ? 's' : ''}`;
            } else {
                // Show empty cart
                if (emptyCartModal) emptyCartModal.style.display = 'block';
                if (cartModalCount) cartModalCount.textContent = '0 items';
            }
        })
        .catch(error => {
            if (cartLoading) cartLoading.style.display = 'none';
            if (emptyCartModal) emptyCartModal.style.display = 'block';
        });
}

// Initialize cart modal close functionality
document.addEventListener('DOMContentLoaded', function() {
    const cartModal = document.getElementById('cartModal');
    if (cartModal) {
        // Close modal when clicking outside
        cartModal.addEventListener('click', function(e) {
            if (e.target === cartModal) {
                closeCartModal();
            }
        });
        
        // Close modal when clicking close button
        const closeButton = cartModal.querySelector('.modal-close');
        if (closeButton) {
            closeButton.addEventListener('click', closeCartModal);
        }
    }
});

// ============================================================================
// WISHLIST FUNCTIONS
// ============================================================================

window.toggleWishlist = function toggleWishlist(productId, productName, buttonElement) {

    const isCurrentlyLiked = buttonElement.classList.contains('liked') || buttonElement.classList.contains('in-wishlist');
    
    if (isCurrentlyLiked) {
        removeFromWishlist(productId, productName, buttonElement);
    } else {
        addToWishlist(productId, productName, buttonElement);
    }
}

function addToWishlist(productId, productName, buttonElement) {
    // Instant UI update - make button red to show it's in wishlist
    buttonElement.classList.add('liked');
    buttonElement.classList.add('in-wishlist');
    updateAllWishlistButtons(productId, true);
    
    // Optimistically update count
    const currentCount = parseInt(document.getElementById('wishlistCount')?.textContent || '0');
    updateWishlistCount(currentCount + 1);
    
    fetch('/api/wishlist/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ product_id: productId })
    })
    .then(safeJson)
    .then(data => {
        if (data.message) {
            // Update with actual count from server
            updateWishlistCount(data.count);
        } else if (data.error) {
            // Revert optimistic update on error
            buttonElement.classList.remove('liked');
            buttonElement.classList.remove('in-wishlist');
            updateAllWishlistButtons(productId, false);
            updateWishlistCount(currentCount);
            showToast(data.error, 'error');
        }
    })
    .catch(error => {
        // Revert optimistic update on error
        buttonElement.classList.remove('liked');
        buttonElement.classList.remove('in-wishlist');
        updateAllWishlistButtons(productId, false);
        updateWishlistCount(currentCount);
        showToast('Error adding to wishlist', 'error');
    });
}

function removeFromWishlist(productId, productName, buttonElement) {
    // Instant UI update - remove red color to show it's not in wishlist
    buttonElement.classList.remove('liked');
    buttonElement.classList.remove('in-wishlist');
    updateAllWishlistButtons(productId, false);
    
    // Optimistically update count
    const currentCount = parseInt(document.getElementById('wishlistCount')?.textContent || '0');
    updateWishlistCount(Math.max(0, currentCount - 1));
    
    fetch('/api/wishlist/remove', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ product_id: productId })
    })
    .then(safeJson)
    .then(data => {
        if (data.message) {
            // Update with actual count from server
            updateWishlistCount(data.count);
            
            // If we're on the wishlist page, remove the item from the DOM
            const wishlistItem = buttonElement.closest('.wishlist-item');
            if (wishlistItem) {
                wishlistItem.style.transition = 'opacity 0.3s ease';
                wishlistItem.style.opacity = '0';
                setTimeout(() => {
                    wishlistItem.remove();
                    
                    // Check if wishlist is now empty
                    const remainingItems = document.querySelectorAll('.wishlist-item');
                    if (remainingItems.length === 0) {
                        // Show empty wishlist message
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
            // Revert optimistic update on error
            buttonElement.classList.add('liked');
            buttonElement.classList.add('in-wishlist');
            updateAllWishlistButtons(productId, true);
            updateWishlistCount(currentCount);
            showToast(data.error, 'error');
        }
    })
    .catch(error => {
        // Revert optimistic update on error
        buttonElement.classList.add('liked');
        buttonElement.classList.add('in-wishlist');
        updateAllWishlistButtons(productId, true);
        updateWishlistCount(currentCount);
        showToast('Error removing from wishlist', 'error');
    });
}

function updateWishlistCount(count) {
    if (arguments.length > 0) {
        // If count is provided, use it directly
        const wishlistCountElement = document.getElementById('wishlistCount');
        if (wishlistCountElement) {
            wishlistCountElement.textContent = count || 0;
            wishlistCountElement.style.display = count > 0 ? 'inline' : 'none';
        }
        return;
    }
    
    // Otherwise fetch from server
    fetch('/api/wishlist/count')
        .then(safeJson)
        .then(data => {
            const wishlistCountElement = document.getElementById('wishlistCount');
            if (wishlistCountElement) {
                wishlistCountElement.textContent = data.count || 0;
                wishlistCountElement.style.display = data.count > 0 ? 'inline' : 'none';
            }
        })
        .catch(error => {
        });
}

function checkWishlistStatus(productId, buttonElement) {
    fetch(`/api/wishlist/check/${productId}`)
        .then(safeJson)
        .then(data => {
            if (data.in_wishlist) {
                buttonElement.classList.add('liked');
                buttonElement.classList.add('in-wishlist');
            } else {
                buttonElement.classList.remove('liked');
                buttonElement.classList.remove('in-wishlist');
            }
        })
        .catch(error => {
        });
}

// Update all wishlist buttons for a specific product across the site
function updateAllWishlistButtons(productId, inWishlist) {
    
    const buttons = document.querySelectorAll(`.btn-wishlist[data-product-id="${productId}"]`);
    buttons.forEach(button => {
        if (inWishlist) {
            button.classList.add('liked');
            button.classList.add('in-wishlist');
        } else {
            button.classList.remove('liked');
            button.classList.remove('in-wishlist');
        }
    });
}

// ============================================================================
// WISHLIST MODAL FUNCTIONS
// ============================================================================

window.openWishlistModal = function openWishlistModal() {
    const modal = document.getElementById('wishlistModal');
    const wishlistModalElement = modal ? modal.querySelector('.wishlist-modal') : null;
    if (modal && wishlistModalElement) {
        modal.style.display = 'block';
        modal.classList.add('active');

        // Small delay to trigger animation
        setTimeout(() => {
            wishlistModalElement.classList.add('show');
        }, 10);

        loadWishlistItems();
    }
}

function closeWishlistModal() {
    const modal = document.getElementById('wishlistModal');
    const wishlistModalElement = modal ? modal.querySelector('.wishlist-modal') : null;
    
    if (modal && wishlistModalElement) {
        wishlistModalElement.classList.remove('show');
        modal.classList.remove('active');

        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    } else {
    }
}

function loadWishlistItems() {
    const loadingElement = document.getElementById('wishlistLoading');
    const itemsContainer = document.getElementById('wishlistItems');
    const emptyState = document.getElementById('emptyWishlistModal');
    const countElement = document.getElementById('wishlistModalCount');

    // Show loading state
    if (loadingElement) loadingElement.style.display = 'block';
    if (itemsContainer) itemsContainer.style.display = 'none';
    if (emptyState) emptyState.style.display = 'none';

    fetch('/api/wishlist')
        .then(safeJson)
        .then(data => {
            // Hide loading
            if (loadingElement) loadingElement.style.display = 'none';

            if (data.products && data.products.length > 0) {
                // Show items
                if (itemsContainer) itemsContainer.style.display = 'block';
                if (emptyState) emptyState.style.display = 'none';

                // Update count
                if (countElement) {
                    countElement.textContent = `${data.count} item${data.count !== 1 ? 's' : ''} saved`;
                }

                // Populate items
                populateWishlistModal(data.products);
            } else {
                // Show empty state
                if (itemsContainer) itemsContainer.style.display = 'none';
                if (emptyState) emptyState.style.display = 'block';

                // Update count
                if (countElement) {
                    countElement.textContent = '0 items saved';
                }
            }
        })
        .catch(error => {
            // Hide loading and show empty state on error
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
                ${product.image_url ?
                    `<img src="${product.image_url.startsWith('http') || product.image_url.startsWith('/static/') ? product.image_url : '/static/' + product.image_url.replace(/^\/+/, '')}" alt="${product.name}" onerror="this.src='/static/img/placeholder.svg'">` :
                    `<div class="wishlist-item-placeholder"><i class="fas fa-image"></i></div>`
                }
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
    // Show immediate visual feedback
    const cartCountElement = document.getElementById('cartCount');
    if (cartCountElement) {
        cartCountElement.style.transform = 'scale(1.2)';
        setTimeout(() => {
            cartCountElement.style.transform = 'scale(1)';
        }, 150);
    }

    fetch('/api/cart/add', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            product_id: productId,
            quantity: 1
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            // Update cart count with server response
            updateCartCountDisplay(data.count || 0);
        } else if (data.error) {
            showToast(data.error, 'error');
            updateCartCount();
        }
    })
    .catch(error => {
        showToast('Error adding to cart', 'error');
        updateCartCount();
    });
}

async function safeJson(response) {
    try {
        const ct = response.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
            const text = await response.text();
            if (text.trim() === '') {
                console.warn('Empty JSON response');
                return {};
            }
            return JSON.parse(text);
        }
        // empty body (204) or unexpected content → avoid SyntaxError
        const text = await response.text();
        return {};          // keeps caller logic intact
    } catch (error) {
        return {};
    }
}

function removeFromWishlistModal(productId, productName) {
    fetch('/api/wishlist/remove', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ product_id: productId })
    })
    .then(safeJson)
    .then(data => {
        if (data.message) {
            // Update the wishlist button in the main grid
            const gridBtn = document.querySelector(
                `.btn-wishlist[data-product-id="${productId}"]`);
            if (gridBtn) {
                gridBtn.classList.remove('liked');
            }

            // Remove the item from the wishlist modal
            const modalItem = document.querySelector(`#wishlistItems .wishlist-item[data-product-id="${productId}"]`);
            if (modalItem) {
                modalItem.remove();
            }
            
            // Update wishlist count
            updateWishlistCount(data.count);
            
            // Update the modal count display
            const countElement = document.getElementById('wishlistModalCount');
            if (countElement) {
                countElement.textContent = `${data.count} item${data.count !== 1 ? 's' : ''} saved`;
            }
            
            // If no items left, show empty state
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
    .catch(error => {
        showToast('Error removing from wishlist', 'error');
    });
}



// ============================================================================
// TOAST NOTIFICATION FUNCTIONS
// ============================================================================

// ============================================================================
// INITIALIZATION
// ============================================================================

// Show stored auth messages after page reload
function showStoredAuthMessage() {
    const message = sessionStorage.getItem('authMessage');
    const messageType = sessionStorage.getItem('authMessageType');
    
    if (message && messageType) {
        showToast(message, messageType);
        // Clear the stored message
        sessionStorage.removeItem('authMessage');
        sessionStorage.removeItem('authMessageType');
    }
}

function initializeAuthForms() {
    const registerForm = document.getElementById('registerForm');
    registerForm?.addEventListener('submit', async e => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(registerForm));

        if (data.password !== data.passwordCon) {
            return showAuthError('registerError', 'Passwords do not match');
        }
        
        // Combine first_name and last_name into full_name for JSON requests
        if (data.first_name && data.last_name) {
            data.full_name = `${data.first_name.trim()} ${data.last_name.trim()}`;
        }
        
        try {
            const res = await fetch('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(r => r.json());

            if (res.error) showAuthError('registerError', res.error);
            else {
                showAuthSuccess('registerSuccess', res.message || 'Registration successful!');
                // Store success message for after page reload
                sessionStorage.setItem('authMessage', 'Account created successfully! Welcome to LoveMeNow!');
                sessionStorage.setItem('authMessageType', 'success');
                setTimeout(() => { closeAuthModal(); location.reload(); }, 1500);
            }
        } catch (err) { 
            showAuthError('registerError', 'Registration failed'); 
        }
    });

    const loginForm = document.getElementById('loginForm');
    loginForm?.addEventListener('submit', async e => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(loginForm));
        try {
            const res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(r => r.json());

            if (res.error) showAuthError('loginError', res.error);
            else {
                showAuthSuccess('loginSuccess', res.message || 'Login successful!');
                // Store success message for after page reload
                sessionStorage.setItem('authMessage', `Welcome back, ${res.user.full_name}!`);
                sessionStorage.setItem('authMessageType', 'success');
                
                // Update cart count immediately with server response
                if (res.cart_count !== undefined) {
                    cartCountCache = res.cart_count;
                    cartCountLastFetch = Date.now();
                    updateCartCountDisplay(res.cart_count);
                } else {
                    // Clear cart count cache to force refresh after login
                    cartCountCache = null;
                    cartCountLastFetch = 0;
                }
                
                setTimeout(() => { 
                    closeAuthModal(); 
                    location.reload(); 
                }, 1500);
            }
        } catch (err) { 
            showAuthError('loginError', 'Login failed'); 
        }
    });
}

function initializeAuthModalHandlers() {
    const authOverlay = document.getElementById('authOverlay');
    const authButton = document.getElementById('authButton');
    
    if (!authOverlay) {
        return;
    }

    // Ensure modal is hidden by default
    authOverlay.hidden = true;

    // Auth button click handler
    if (authButton) {
        authButton.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            openAuthModal('login');
        });
    } else {
    }

    // Close buttons inside modal
    authOverlay.querySelectorAll('.auth-close, [data-close-auth]').forEach(btn => {
        btn.onclick = e => { 
            e.preventDefault(); 
            e.stopPropagation(); 
            closeAuthModal(); 
        };
    });

    // Click on backdrop closes
    authOverlay.addEventListener('click', e => {
        if (e.target === authOverlay) {
            closeAuthModal();
        }
    });

    // ESC closes
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && !authOverlay.hidden) {
            closeAuthModal();
        }
    });
}



function initializeWishlistModalHandlers() {
    const wishlistModal = document.getElementById('wishlistModal');
    if (!wishlistModal) return;

    // Close buttons
    wishlistModal.querySelectorAll('.modal-close').forEach(btn => {
        btn.onclick = e => { 
            e.preventDefault(); 
            e.stopPropagation(); 
            closeWishlistModal(); 
        };
    });

    // Click on backdrop closes
    wishlistModal.addEventListener('click', e => {
        if (e.target === wishlistModal) closeWishlistModal();
    });

    // ESC closes
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && wishlistModal.classList.contains('active')) closeWishlistModal();
    });
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    
    // Test if modal exists
    const overlay = document.getElementById('authOverlay');
    if (overlay) {
    }
    
    // Test if button exists
    const authButton = document.getElementById('authButton');
    
    // Show any stored auth messages first
    showStoredAuthMessage();
    
    // Initialize auth functionality
    initializeAuthForms();
    initializeAuthModalHandlers();
    
    // Initialize modal handlers
    initializeWishlistModalHandlers();
    
    // Update counts on page load
    updateCartCount();
    
    // Initialize wishlist count and button states
    fetch('/api/wishlist/count')
        .then(safeJson)
        .then(data => {
            updateWishlistCount(data.count);
        })
        .catch(error => {
        });
    
    // Initialize wishlist button states for all products on the page
    document.querySelectorAll('.btn-wishlist[data-product-id]').forEach(button => {
        const productId = parseInt(button.dataset.productId);
        if (productId) {
            checkWishlistStatus(productId, button);
        }
    });
    
});

// ============================================================================
// ACCOUNT MODAL FUNCTIONS
// ============================================================================

/**
 * Open the account modal for logged-in users
 */
// ===  OPEN  =========================================================
window.openAccountModal = function () {
  const overlay = document.getElementById('loggedModal');          // backdrop
  const panel   = overlay?.querySelector('.logged-modal');         // sliding card
  if (!overlay || !panel) return;

  overlay.style.display = 'flex';                                  // show backdrop

  // one paint, then play both transitions
  requestAnimationFrame(() => {
      overlay.classList.add('active');     // if you fade / blur the backdrop
      panel.classList.add('active');       // <- THIS is the slide‑in class
  });

  document.body.classList.add('no-scroll');
  updateAccountModalCounts();
};

// ===  CLOSE  ========================================================
window.closeAccountModal = function () {
  const overlay = document.getElementById('loggedModal');
  const panel   = overlay?.querySelector('.logged-modal');
  if (!overlay || !panel) return;

  overlay.classList.remove('active');
  panel.classList.remove('active');

  setTimeout(() => {                          // match CSS transition‑time
      overlay.style.display = 'none';
      document.body.classList.remove('no-scroll');
  }, 300);
};
/**
 * Update counts in the account modal
 */
function updateAccountModalCounts() {
    // Update wishlist count
    fetch('/api/wishlist/count')
        .then(safeJson)
        .then(data => {
            const wishlistCount = document.getElementById('accountWishlistCount');
            if (wishlistCount) {
                wishlistCount.textContent = data.count;
            }
        })
    
    // Update cart count
    fetch('/api/cart/count', {
        credentials: 'same-origin'
    })
        .then(safeJson)
        .then(data => {
            const cartCount = document.getElementById('accountCartCount');
            if (cartCount) {
                cartCount.textContent = data.count;
            }
        })
}

// ============================================================================
// PASSWORD MODAL FUNCTIONS
// ============================================================================

/**
 * Open the change password modal
 */
window.openPasswordModal = function() {
    const modal = document.getElementById('changePasswordModal');
    if (!modal) {
        return;
    }
    
    modal.classList.remove('hidden');
    modal.classList.add('active');
    document.body.classList.add('no-scroll');
    document.body.style.overflow = 'hidden';
    
    // Focus the first input
    const firstInput = modal.querySelector('#currentPassword');
    if (firstInput) firstInput.focus();
};

/**
 * Close the change password modal
 */
window.closePasswordModal = function() {
    const modal = document.getElementById('changePasswordModal');
    if (!modal) return;
    
    modal.classList.add('hidden');
    modal.classList.remove('active');
    document.body.classList.remove('no-scroll');
    document.body.style.overflow = 'auto';
    
    // Reset form
    const form = document.getElementById('changePasswordForm');
    if (form) form.reset();
    
    // Clear messages
    const errorMsg = document.getElementById('passwordError');
    const successMsg = document.getElementById('passwordSuccess');
    if (errorMsg) {
        errorMsg.style.display = 'none';
        errorMsg.textContent = '';
    }
    if (successMsg) {
        successMsg.style.display = 'none';
        successMsg.textContent = '';
    }
};

// ============================================================================
// PASSWORD VISIBILITY TOGGLE
// ============================================================================

/**
 * Toggle password visibility
 * @param {string} inputId - The ID of the password input
 * @param {HTMLElement} toggleButton - The toggle button element
 */
window.togglePasswordVisibility = function(inputId, toggleButton) {
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

// ============================================================================
// ADDRESS MODAL FUNCTIONS
// ============================================================================

/**
 * Open the add address modal
 */
window.openAddressModal = function() {
    const modal = document.getElementById('addressModal');
    if (!modal) {
        return;
    }
    
    modal.classList.remove('hidden');
    modal.classList.add('active');
    document.body.classList.add('no-scroll');
    document.body.style.overflow = 'hidden';
    
    // Focus the first input
    const firstInput = modal.querySelector('input[type="text"]');
    if (firstInput) firstInput.focus();
};

/**
 * Close the add address modal
 */
window.closeAddressModal = function() {
    const modal = document.getElementById('addressModal');
    if (!modal) return;
    
    modal.classList.add('hidden');
    modal.classList.remove('active');
    document.body.classList.remove('no-scroll');
    document.body.style.overflow = 'auto';
    
    // Reset form
    const form = modal.querySelector('form');
    if (form) form.reset();
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================



/**
 * View liked items (redirect to wishlist)
 */
window.viewLikedItems = function() {
    closeAccountModal();
    window.location.href = '/wishlist';
};

/**
 * View cart (redirect to cart)
 */
window.viewCart = function() {
    window.location.href = '/cart';
};

/**
 * View orders (placeholder)
 */
window.viewOrders = function() {
    closeAccountModal();
    showToast('Order history feature coming soon!', 'info');
};

// ============================================================================
// PRODUCT FILTERING FUNCTIONS
// ============================================================================

window.filterProducts = function filterProducts(categorySlug) {
    
    if (categorySlug === 'all') {
        // Redirect to products page without category filter
        window.location.href = '/products';
    } else {
        // Updated mapping from slug to category ID based on actual database
        const categoryMap = {
            // Main categories
            'bdsm': 1,
            'toys': 2,
            'kits': 3,
            'lubricant': 4,
            'lingerie': 5,
            
            // BDSM subcategories
            'masks': 7,
            'restraints': 10,
            'collars-nipple-clamps': 40,
            'nipple-clamps': 50,
            
            // Toys subcategories
            'butt-plug': 11,
            'dildos': 33,
            'masturbators': 34,
            'cock-pumps': 35,
            'vibrators': 36,
            'penis-extensions': 37,
            'anal-beads': 38,
            'wands': 39,
            
            // Kits subcategories
            'roleplay-kit': 6,
            'bondage-kit': 9,
            
            // Lubricant subcategories
            'anal-numbing-gel': 22,
            'douches-and-enemas': 51
        };
        
        const categoryId = categoryMap[categorySlug];
        if (categoryId) {
            // Redirect to products page with category filter
            window.location.href = `/products?category=${categoryId}`;
        } else {
            console.warn('Unknown category slug:', categorySlug);
            window.location.href = '/products';
        }
    }
}

// Search functionality
window.handleSearch = function handleSearch() {
    const searchInput = document.getElementById('productSearch');
    const clearButton = document.querySelector('.clear-search-btn');
    
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.trim();
    
    // Show/hide clear button
    if (clearButton) {
        clearButton.style.display = searchTerm ? 'block' : 'none';
    }
    
    // Debounce search to avoid too many requests
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
        if (searchTerm.length >= 2 || searchTerm.length === 0) {
            // Redirect to products page with search parameter
            const url = new URL('/products', window.location.origin);
            if (searchTerm) {
                url.searchParams.set('search', searchTerm);
            }
            window.location.href = url.toString();
        }
    }, 500); // 500ms delay
}

window.clearSearch = function clearSearch() {
    const searchInput = document.getElementById('productSearch');
    const clearButton = document.querySelector('.clear-search-btn');
    
    if (searchInput) {
        searchInput.value = '';
        if (clearButton) {
            clearButton.style.display = 'none';
        }
        // Redirect to products page without search
        window.location.href = '/products';
    }
}

// Clear all filters function
window.clearAllFilters = function clearAllFilters() {
    
    // Clear search input
    const searchInput = document.getElementById('productSearch');
    if (searchInput) {
        searchInput.value = '';
    }
    
    // Clear filter dropdowns
    const inStockFilter = document.getElementById('inStockFilter');
    const brandFilter = document.getElementById('brandFilter');
    const priceSort = document.getElementById('priceSort');
    
    if (inStockFilter) inStockFilter.checked = false;
    if (brandFilter) brandFilter.value = '';
    if (priceSort) priceSort.value = '';
    
    // Clear color selections (if any)
    const colorDots = document.querySelectorAll('.color-dot.selected');
    colorDots.forEach(dot => dot.classList.remove('selected'));
    
    // Redirect to products page without any filters
    window.location.href = '/products';
}

// Additional filter functions that might be called from the template
window.handleInStockFilter = function handleInStockFilter() {
    const checkbox = document.getElementById('inStockFilter');
    const url = new URL(window.location);
    
    if (checkbox && checkbox.checked) {
        url.searchParams.set('in_stock', 'true');
    } else {
        url.searchParams.delete('in_stock');
    }
    
    window.location.href = url.toString();
}

window.handleBrandFilter = function handleBrandFilter() {
    const select = document.getElementById('brandFilter');
    const url = new URL(window.location);
    
    if (select && select.value) {
        url.searchParams.set('brand', select.value);
    } else {
        url.searchParams.delete('brand');
    }
    
    window.location.href = url.toString();
}

window.handlePriceSort = function handlePriceSort() {
    const select = document.getElementById('priceSort');
    const url = new URL(window.location);
    
    if (select && select.value) {
        url.searchParams.set('sort', select.value);
    } else {
        url.searchParams.delete('sort');
    }
    
    window.location.href = url.toString();
}

// Individual filter clear functions
window.clearCategoryFilter = function clearCategoryFilter() {
    const url = new URL(window.location);
    url.searchParams.delete('category');
    window.location.href = url.toString();
}

window.clearBrandFilter = function clearBrandFilter() {
    const brandSelect = document.getElementById('brandFilter');
    if (brandSelect) {
        brandSelect.value = '';
    }
    const url = new URL(window.location);
    url.searchParams.delete('brand');
    window.location.href = url.toString();
}

window.clearPriceSortFilter = function clearPriceSortFilter() {
    const priceSelect = document.getElementById('priceSort');
    if (priceSelect) {
        priceSelect.value = '';
    }
    const url = new URL(window.location);
    url.searchParams.delete('sort');
    window.location.href = url.toString();
}

window.clearInStockFilter = function clearInStockFilter() {
    const checkbox = document.getElementById('inStockFilter');
    if (checkbox) {
        checkbox.checked = false;
    }
    const url = new URL(window.location);
    url.searchParams.delete('in_stock');
    window.location.href = url.toString();
}

window.clearColorFilter = function clearColorFilter() {
    // Clear selected color dots
    const colorDots = document.querySelectorAll('.color-dot.selected');
    colorDots.forEach(dot => dot.classList.remove('selected'));
    
    const url = new URL(window.location);
    url.searchParams.delete('color');
    window.location.href = url.toString();
}

// Make functions globally available for onclick handlers
window.closeQuickViewModal = closeQuickViewModal;
window.closeQuickView = closeQuickViewModal; // Alias for backward compatibility
window.closeWishlistModal = closeWishlistModal;
window.changeQuickViewImage = changeQuickViewImage;
window.addToCartFromModal = addToCartFromModal;
window.removeFromWishlistModal = removeFromWishlistModal;

/* ═══════════════════════════════════════════════════════════════════
   CART PAGE FUNCTIONS
   ═══════════════════════════════════════════════════════════════════ */

// Cart page specific functions
function loadCart() {
    
    // Show loading state immediately
    const cartContent = document.getElementById('cartContent');
    if (!cartContent) {
        return;
    }
    
    cartContent.innerHTML = `
        <div class="loading-cart" style="text-align: center; padding: 2rem;">
            <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: hsl(var(--primary-color)); margin-bottom: 1rem;"></i>
            <p>Loading your cart...</p>
        </div>
    `;
    
    fetch('/api/cart/', {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            displayCart(data);
        })
        .catch(error => {
            // Show error message to user
            const cartContent = document.getElementById('cartContent');
            if (cartContent) {
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
            }
        });
}

function displayCart(cartData) {
    
    const cartContent = document.getElementById('cartContent');
    
    if (!cartContent) {
        return;
    }
    
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
    const taxRate = 0.0875; // 8.75% Miami-Dade tax
    const taxAmount = subtotal * taxRate;
    const shippingAmount = cartData.shipping;
    const total = cartData.total + taxAmount;

    cartContent.innerHTML = `
        <div class="cart-content">
            <div class="cart-items">
                ${cartData.products.map(item => {
                    // Determine size display
                    let sizeDisplay = '';
                    if (item.dimensions && item.dimensions.trim()) {
                        sizeDisplay = `<div class="cart-item-size"><strong>Size:</strong> ${item.dimensions}</div>`;
                    } else {
                        sizeDisplay = `<div class="cart-item-size"><strong>Sizing:</strong> One size fits all / Adjustable</div>`;
                    }
                    
                    return `
                    <div class="cart-item" data-product-id="${item.id}">
                        <div class="cart-item-image">
                            <img src="${item.image_url || '/static/IMG/placeholder.jpg'}" alt="${item.name}" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iODAiIHZpZXdCb3g9IjAgMCA4MCA4MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjgwIiBmaWxsPSIjZjBmMGYwIi8+CjxwYXRoIGQ9Ik0yNSAzNUgzNVYyNUg0NVYzNUg1NVY0NUg0NVY1NUgzNVY0NUgyNVYzNVoiIGZpbGw9IiNjY2MiLz4KPC9zdmc+'">
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
                <div class="summary-row">
                    <span>Subtotal:</span>
                    <span>$${subtotal.toFixed(2)}</span>
                </div>
                <div class="summary-row">
                    <span>Tax (8.75%):</span>
                    <span>$${taxAmount.toFixed(2)}</span>
                </div>
                <div class="summary-row">
                    <span>Shipping:</span>
                    <span>${shippingAmount === 0 ? 'FREE' : '$' + shippingAmount.toFixed(2)}</span>
                </div>
                ${subtotal < 50 ? '<p style="font-size: 0.9rem; color: hsl(var(--muted-color)); margin: 0.5rem 0;">Free shipping on orders over $50</p>' : ''}
                <div class="summary-row total">
                    <span>Total:</span>
                    <span>$${total.toFixed(2)}</span>
                </div>
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
    if (newQuantity < 1) {
        removeFromCart(productId);
        return;
    }

    fetch('/api/cart/update', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            product_id: productId,
            quantity: parseInt(newQuantity)
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errorData => {
                throw new Error(errorData.error || 'Failed to update quantity');
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.message) {
            loadCart(); // Reload cart
            updateCartCount();
            showToast('Cart updated successfully', 'success');
        }
    })
    .catch(error => {
        showToast(error.message, 'error');
        loadCart(); // Reload cart to revert any changes
    });
}

function removeFromCart(productId) {
    fetch('/api/cart/remove', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            product_id: productId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            loadCart(); // Reload cart
            updateCartCount();
        }
    })
    .catch(error => {
    });
}

function proceedToCheckout() {
    window.location.href = '/checkout';
}

// Make cart functions globally available
window.loadCart = loadCart;
window.displayCart = displayCart;
window.updateQuantity = updateQuantity;
window.removeFromCart = removeFromCart;
window.proceedToCheckout = proceedToCheckout;

/* ═══════════════════════════════════════════════════════════════════
   PRODUCTS PAGE FUNCTIONS
   ═══════════════════════════════════════════════════════════════════ */

// Product image navigation functionality
const productImageIndexes = {};

function initializeProductImageNavigation() {
    // Initialize all product image indexes to 0
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
    try {
        allImages = JSON.parse(imagesDataScript.textContent);
    } catch (e) {
        return;
    }
    
    if (allImages.length <= 1) return;
    
    // Get current index or initialize to 0
    let currentIndex = productImageIndexes[productId] || 0;
    
    // Calculate new index
    let newIndex = currentIndex + direction;
    
    // Handle looping
    if (newIndex >= allImages.length) {
        newIndex = 0;
    } else if (newIndex < 0) {
        newIndex = allImages.length - 1;
    }
    
    // Update stored index
    productImageIndexes[productId] = newIndex;
    
    // Update main image
    const mainImage = productImage.querySelector('.product-main-image');
    if (mainImage && allImages[newIndex]) {
        mainImage.src = allImages[newIndex];
    }
    
    // Update counter
    const counterElement = productImage.querySelector('.current-image-index');
    if (counterElement) {
        counterElement.textContent = newIndex + 1;
    }
}

function initializeProductsPageSearch() {
    const searchInput = document.getElementById('productSearch');
    const clearButton = document.querySelector('.clear-search-btn');
    
    // Show clear button if there's a search term
    if (searchInput && clearButton) {
        if (searchInput.value.trim()) {
            clearButton.style.display = 'block';
        }
    }
    
    // Initialize product image navigation
    initializeProductImageNavigation();
}

// Make products page functions globally available
window.initializeProductImageNavigation = initializeProductImageNavigation;
window.navigateProductImage = navigateProductImage;
window.initializeProductsPageSearch = initializeProductsPageSearch;