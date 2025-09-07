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
    // Create modal HTML
    const modalHTML = `
        <div id="quickViewModal" class="modal-overlay" style="display: flex;">
            <div class="modal-content quick-view-modal">
                <button class="modal-close" onclick="closeQuickViewModal()">&times;</button>
                
                <div class="quick-view-grid">
                    <!-- Product Images -->
                    <div class="quick-view-images">
                        <div class="main-image">
                            <img id="quickViewMainImage" src="" alt="${product.name}">
                        </div>
                        <div class="image-thumbnails" id="quickViewThumbnails">
                            <!-- Thumbnails will be populated by JavaScript -->
                        </div>
                    </div>
                    
                    <!-- Product Info -->
                    <div class="quick-view-info">
                        <h2>${product.name}</h2>
                        <div class="price">$${product.price}</div>
                        
                        <!-- Colors -->
                        <div class="color-selection" id="quickViewColors">
                            <!-- Colors will be populated by JavaScript -->
                        </div>
                        
                        <!-- Quantity -->
                        <div class="quantity-section">
                            <label>Quantity:</label>
                            <div class="quantity-controls">
                                <button onclick="changeQuickViewQuantity(-1)">-</button>
                                <input type="number" id="quickViewQuantity" value="1" min="1" max="${product.quantity_on_hand || 1}">
                                <button onclick="changeQuickViewQuantity(1)">+</button>
                            </div>
                        </div>
                        
                        <!-- Actions -->
                        <div class="quick-view-actions">
                            <button class="btn-primary" onclick="addToCartFromQuickView(${product.id})">
                                <i class="fas fa-shopping-cart"></i> Add to Cart
                            </button>
                            <a href="/product/${product.id}" class="btn-secondary">View Details</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('quickViewModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Initialize quick view with color-specific images
    initializeQuickView(product);
}

function initializeQuickView(product) {
    // Build variant-specific image data (same logic as product detail page)
    const variantImages = {};
    let quickViewAllImages = [];
    let currentQuickViewImageIndex = 0;
    
    // Build variant images object
    if (product.variants) {
        product.variants.forEach(variant => {
            if (variant.color && variant.images && variant.images.length > 0) {
                variantImages[variant.color.id] = variant.images.map(img => img.url);
            }
        });
    }
    
    console.log('🎯 QUICK VIEW INIT:', {
        productName: product.name,
        variantImages: variantImages,
        colors: product.colors
    });
    
    // Set initial images (first color)
    if (product.colors && product.colors.length > 0) {
        const firstColorId = product.colors[0].id;
        quickViewAllImages = variantImages[firstColorId] || [];
    }
    
    // Set main image
    const mainImage = document.getElementById('quickViewMainImage');
    if (mainImage && quickViewAllImages.length > 0) {
        mainImage.src = quickViewAllImages[0];
    }
    
    // Build color options
    const colorsContainer = document.getElementById('quickViewColors');
    if (colorsContainer && product.colors) {
        let colorsHTML = '<label>Color:</label><div class="color-options">';
        
        product.colors.forEach((color, index) => {
            const isActive = index === 0 ? 'active' : '';
            colorsHTML += `
                <div class="color-option ${isActive}" 
                     onclick="selectQuickViewColor(this, '${color.name}', ${color.id})"
                     style="background-color: ${color.hex || '#ccc'};"
                     title="${color.name}">
                </div>
            `;
        });
        
        colorsHTML += '</div>';
        colorsContainer.innerHTML = colorsHTML;
    }
    
    // Build thumbnails
    buildQuickViewThumbnails();
    
    // Store data globally for color switching
    window.quickViewData = {
        variantImages: variantImages,
        allImages: quickViewAllImages,
        currentImageIndex: currentQuickViewImageIndex
    };
}

function selectQuickViewColor(colorElement, colorName, colorId) {
    console.log('🎨 QUICK VIEW COLOR SWITCH:', {
        colorName: colorName,
        colorId: colorId,
        availableImages: window.quickViewData.variantImages[colorId]
    });
    
    // Update active color
    document.querySelectorAll('#quickViewColors .color-option').forEach(c => c.classList.remove('active'));
    colorElement.classList.add('active');
    
    // Switch to images for this color variant
    if (window.quickViewData.variantImages[colorId]) {
        window.quickViewData.allImages = window.quickViewData.variantImages[colorId];
        window.quickViewData.currentImageIndex = 0;
        
        // Update main image
        const mainImage = document.getElementById('quickViewMainImage');
        if (mainImage && window.quickViewData.allImages.length > 0) {
            mainImage.src = window.quickViewData.allImages[0];
            console.log('📸 Quick view main image updated to:', window.quickViewData.allImages[0]);
        }
        
        // Rebuild thumbnails
        buildQuickViewThumbnails();
    }
}

function buildQuickViewThumbnails() {
    const thumbnailContainer = document.getElementById('quickViewThumbnails');
    if (!thumbnailContainer || !window.quickViewData) return;
    
    // Clear existing thumbnails
    thumbnailContainer.innerHTML = '';
    
    // Only show thumbnails if there are multiple images
    if (window.quickViewData.allImages.length > 1) {
        window.quickViewData.allImages.forEach((imageUrl, index) => {
            const thumbnailDiv = document.createElement('div');
            thumbnailDiv.className = `thumbnail ${index === 0 ? 'active' : ''}`;
            thumbnailDiv.onclick = () => changeQuickViewImage(imageUrl, index);
            
            const thumbnailImg = document.createElement('img');
            thumbnailImg.src = imageUrl;
            thumbnailImg.alt = `Product image ${index + 1}`;
            
            thumbnailDiv.appendChild(thumbnailImg);
            thumbnailContainer.appendChild(thumbnailDiv);
        });
    }
}

function changeQuickViewImage(imageUrl, index) {
    const mainImage = document.getElementById('quickViewMainImage');
    if (mainImage) {
        mainImage.src = imageUrl;
    }
    
    // Update active thumbnail
    document.querySelectorAll('#quickViewThumbnails .thumbnail').forEach((thumb, i) => {
        thumb.classList.toggle('active', i === index);
    });
    
    if (window.quickViewData) {
        window.quickViewData.currentImageIndex = index;
    }
}

function changeQuickViewQuantity(delta) {
    const input = document.getElementById('quickViewQuantity');
    if (input) {
        const newValue = parseInt(input.value) + delta;
        const max = parseInt(input.getAttribute('max'));
        
        if (newValue >= 1 && newValue <= max) {
            input.value = newValue;
        }
    }
}

function addToCartFromQuickView(productId) {
    const quantityInput = document.getElementById('quickViewQuantity');
    const quantity = quantityInput ? parseInt(quantityInput.value) : 1;
    
    // Get selected color/variant if available
    const selectedColorDot = document.querySelector('.quick-view-info .color-option.active');
    const variantId = selectedColorDot ? selectedColorDot.dataset.variantId : null;
    
    // Prepare request body
    const requestBody = {
        product_id: productId,
        quantity: quantity
    };
    
    if (variantId) {
        requestBody.variant_id = variantId;
    }
    
    // Use existing cart functionality
    fetch('/api/cart/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        credentials: 'same-origin',
        body: JSON.stringify(requestBody)
    })
    .then(response => response.json())
    .then(data => {
        if (data.message || data.success) {
            // Handle cart count locally
            const currentCount = parseInt(localStorage.getItem('cartCount') || '0', 10);
            const newCount = currentCount + quantity;
            localStorage.setItem('cartCount', newCount.toString());
            
            // Update cart display if cartManager exists
            if (window.cartManager) {
                window.cartManager.count = newCount;
                window.cartManager.updateDisplay();
            }
            
            showToast(data.message || 'Added to cart!', 'success');
            closeQuickViewModal();
        } else if (data.error) {
            showToast(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Add to cart error:', error);
        showToast('Error adding to cart', 'error');
    });
}

function closeQuickViewModal() {
    const modal = document.getElementById('quickViewModal');
    if (modal) {
        modal.remove();
    }
    // Clean up global data
    if (window.quickViewData) {
        delete window.quickViewData;
    }
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
window.selectQuickViewColor = selectQuickViewColor;
window.changeQuickViewImage = changeQuickViewImage;
window.changeQuickViewQuantity = changeQuickViewQuantity;
window.addToCartFromQuickView = addToCartFromQuickView;
window.closeQuickViewModal = closeQuickViewModal;