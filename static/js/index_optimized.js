// Optimized JavaScript for better performance
// Uses modern techniques: debouncing, lazy loading, efficient DOM manipulation

// Performance optimizations
const DEBOUNCE_DELAY = 300;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

// Cache for API responses
const apiCache = new Map();

// Debounce utility
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Efficient DOM ready
function ready(fn) {
    if (document.readyState !== 'loading') {
        fn();
    } else {
        document.addEventListener('DOMContentLoaded', fn);
    }
}

// Optimized cart count management
class CartManager {
    constructor() {
        this.count = 0;
        this.lastUpdate = 0;
        this.updateCallbacks = new Set();
        this.init();
    }

    init() {
        // Load from localStorage immediately (synchronous)
        const stored = localStorage.getItem('cartCount');
        if (stored !== null) {
            this.count = parseInt(stored, 10) || 0;
            this.updateDisplay();
        }

        // Debounced server sync
        this.syncWithServer = debounce(this.syncWithServer.bind(this), DEBOUNCE_DELAY);
    }

    updateDisplay() {
        const element = document.getElementById('cartCount');
        if (element) {
            element.textContent = this.count;
            element.style.display = this.count > 0 ? 'inline' : 'none';
            element.classList.toggle('has-items', this.count > 0);
        }
        
        // Notify callbacks
        this.updateCallbacks.forEach(callback => callback(this.count));
    }

    async syncWithServer() {
        const now = Date.now();
        if (now - this.lastUpdate < CACHE_DURATION) {
            return; // Skip if recently updated
        }

        try {
            const cacheKey = 'cart-count';
            const cached = apiCache.get(cacheKey);
            
            if (cached && now - cached.timestamp < CACHE_DURATION) {
                this.count = cached.data;
                this.updateDisplay();
                return;
            }

            const response = await fetch('/api/cart/count', {
                method: 'GET',
                credentials: 'same-origin',
                signal: AbortSignal.timeout(3000) // 3 second timeout
            });

            if (response.ok) {
                const data = await response.json();
                this.count = data.count || 0;
                
                // Cache the result
                apiCache.set(cacheKey, {
                    data: this.count,
                    timestamp: now
                });
                
                // Persist to localStorage
                localStorage.setItem('cartCount', this.count.toString());
                this.updateDisplay();
                this.lastUpdate = now;
            }
        } catch (error) {
            console.warn('Cart sync failed:', error.message);
            // Keep existing count on error
        }
    }

    async addItem(productId, productName, productPrice, quantity = 1) {
        try {
            const response = await fetch('/api/cart/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    product_id: productId,
                    quantity: quantity
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.count = data.cart_count || (this.count + quantity);
                localStorage.setItem('cartCount', this.count.toString());
                this.updateDisplay();
                
                showToast(`${productName} added to cart!`, 'success');
                return true;
            } else {
                const error = await response.json();
                showToast(error.message || 'Failed to add item to cart', 'error');
                return false;
            }
        } catch (error) {
            console.error('Add to cart error:', error);
            showToast('Network error. Please try again.', 'error');
            return false;
        }
    }

    onUpdate(callback) {
        this.updateCallbacks.add(callback);
    }

    offUpdate(callback) {
        this.updateCallbacks.delete(callback);
    }
}

// Optimized wishlist management
class WishlistManager {
    constructor() {
        this.items = new Set();
        this.init();
    }

    init() {
        // Load from localStorage
        const stored = localStorage.getItem('wishlist');
        if (stored) {
            try {
                const items = JSON.parse(stored);
                this.items = new Set(items);
            } catch (e) {
                console.warn('Invalid wishlist data in localStorage');
            }
        }
    }

    async toggle(productId, productName, button) {
        const isInWishlist = this.items.has(productId);
        
        try {
            const response = await fetch(`/api/wishlist/${isInWishlist ? 'remove' : 'add'}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                credentials: 'same-origin',
                body: JSON.stringify({ product_id: productId })
            });

            if (response.ok) {
                if (isInWishlist) {
                    this.items.delete(productId);
                    button.classList.remove('active');
                    showToast(`${productName} removed from wishlist`, 'info');
                } else {
                    this.items.add(productId);
                    button.classList.add('active');
                    showToast(`${productName} added to wishlist!`, 'success');
                }
                
                // Update localStorage
                localStorage.setItem('wishlist', JSON.stringify([...this.items]));
                this.updateCount();
            } else {
                const error = await response.json();
                showToast(error.message || 'Wishlist update failed', 'error');
            }
        } catch (error) {
            console.error('Wishlist error:', error);
            showToast('Network error. Please try again.', 'error');
        }
    }

    updateCount() {
        const element = document.getElementById('wishlistCount');
        if (element) {
            element.textContent = this.items.size;
            element.style.display = this.items.size > 0 ? 'inline' : 'none';
        }
    }

    initializeButtons() {
        const buttons = document.querySelectorAll('.btn-wishlist[data-product-id]');
        buttons.forEach(button => {
            const productId = parseInt(button.dataset.productId);
            if (this.items.has(productId)) {
                button.classList.add('active');
            }
        });
    }
}

// Global instances
let cartManager;
let wishlistManager;

// Utility functions
function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

// Optimized toast system
const toastQueue = [];
let isShowingToast = false;

function showToast(message, type = 'success') {
    toastQueue.push({ message, type });
    if (!isShowingToast) {
        processToastQueue();
    }
}

function processToastQueue() {
    if (toastQueue.length === 0) {
        isShowingToast = false;
        return;
    }

    isShowingToast = true;
    const { message, type } = toastQueue.shift();

    // Create or get toast container
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // Create toast
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
        ${message}
    `;

    container.appendChild(toast);

    // Auto-remove and process next
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
        setTimeout(processToastQueue, 100); // Small delay between toasts
    }, 3000);
}

// Event delegation for better performance
function setupEventDelegation() {
    document.addEventListener('click', function(e) {
        // Add to cart buttons
        const addCartBtn = e.target.closest('.btn-add-cart');
        if (addCartBtn && !addCartBtn.disabled) {
            e.preventDefault();
            const productId = parseInt(addCartBtn.dataset.productId);
            const productName = addCartBtn.dataset.productName;
            const productPrice = parseFloat(addCartBtn.dataset.productPrice);
            
            if (productId && productName && productPrice) {
                cartManager.addItem(productId, productName, productPrice);
            }
            return;
        }

        // Wishlist buttons
        const wishlistBtn = e.target.closest('.btn-wishlist');
        if (wishlistBtn) {
            e.preventDefault();
            const productId = parseInt(wishlistBtn.dataset.productId);
            const productName = wishlistBtn.dataset.productName;
            
            if (productId && productName) {
                wishlistManager.toggle(productId, productName, wishlistBtn);
            }
            return;
        }

        // Quick view buttons
        const quickViewBtn = e.target.closest('.btn-quick-view');
        if (quickViewBtn) {
            e.preventDefault();
            const productId = parseInt(quickViewBtn.dataset.productId);
            if (productId) {
                openQuickView(productId);
            }
            return;
        }
    });
}

// Lazy load images
function setupLazyLoading() {
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    observer.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    } else {
        // Fallback for older browsers
        document.querySelectorAll('img[data-src]').forEach(img => {
            img.src = img.dataset.src;
        });
    }
}

// Quick view modal (optimized)
async function openQuickView(productId) {
    try {
        // Check cache first
        const cacheKey = `product-${productId}`;
        const cached = apiCache.get(cacheKey);
        
        if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
            displayQuickView(cached.data);
            return;
        }

        // Show loading state
        showToast('Loading product details...', 'info');

        const response = await fetch(`/api/product/${productId}`, {
            credentials: 'same-origin',
            signal: AbortSignal.timeout(5000)
        });

        if (response.ok) {
            const product = await response.json();
            
            // Cache the result
            apiCache.set(cacheKey, {
                data: product,
                timestamp: Date.now()
            });
            
            displayQuickView(product);
        } else {
            showToast('Failed to load product details', 'error');
        }
    } catch (error) {
        console.error('Quick view error:', error);
        showToast('Network error. Please try again.', 'error');
    }
}

function displayQuickView(product) {
    // Implementation for displaying quick view modal
    // This would create and show the modal with product details
    console.log('Displaying quick view for:', product);
}

// Initialize when deferred content is loaded
window.initializeDeferredJS = function() {
    // Initialize managers
    cartManager = new CartManager();
    wishlistManager = new WishlistManager();
    
    // Setup event delegation
    setupEventDelegation();
    
    // Setup lazy loading
    setupLazyLoading();
    
    // Initialize wishlist button states
    wishlistManager.initializeButtons();
    
    // Sync cart count with server (debounced)
    cartManager.syncWithServer();
    
    console.log('Deferred JavaScript initialized');
};

// Initialize immediately if DOM is ready
ready(function() {
    // Only initialize critical functionality immediately
    cartManager = new CartManager();
    wishlistManager = new WishlistManager();
    
    // Age verification handling
    const ageVerificationOverlay = document.getElementById('ageVerificationOverlay');
    if (ageVerificationOverlay) {
        ageVerificationOverlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        
        const yesButton = ageVerificationOverlay.querySelector('.age-btn-yes');
        if (yesButton) {
            setTimeout(() => yesButton.focus(), 100);
        }
    }
});

// Performance monitoring
if ('performance' in window) {
    window.addEventListener('load', function() {
        setTimeout(function() {
            const perfData = performance.getEntriesByType('navigation')[0];
            console.log('Page load performance:', {
                domContentLoaded: perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart,
                loadComplete: perfData.loadEventEnd - perfData.loadEventStart,
                totalTime: perfData.loadEventEnd - perfData.fetchStart
            });
        }, 0);
    });
}

// Export for global access
window.cartManager = cartManager;
window.wishlistManager = wishlistManager;
window.openQuickView = openQuickView;
window.showToast = showToast;