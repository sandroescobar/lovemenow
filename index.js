// Global variables
let currentSlides = {};
let quickViewImages = [];
let currentQuickViewIndex = 0;
let productImages = {};
let cartCount = 0;

// Wishlist functionality
function viewLikedItems() {
    // Close the account modal first
    closeAccountModal();
    
    // Small delay to allow account modal to close before opening wishlist modal
    setTimeout(() => {
        openWishlistModal();
    }, 100);
}

window.openWishlistModal = function openWishlistModal() {
    const modal = document.getElementById('wishlistModal');
    const wishlistModalElement = modal.querySelector('.wishlist-modal');
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
        .then(response => response.json())
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
            console.error('Error loading wishlist:', error);
            // Hide loading and show empty state on error
            if (loadingElement) loadingElement.style.display = 'none';
            if (itemsContainer) itemsContainer.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
        });
}

function closeWishlistModal() {
    console.log('closeWishlistModal called');
    const modal = document.getElementById('wishlistModal');
    const wishlistModalElement = modal ? modal.querySelector('.wishlist-modal') : null;
    
    if (modal && wishlistModalElement) {
        console.log('Closing wishlist modal');
        wishlistModalElement.classList.remove('show');
        modal.classList.remove('active');

        setTimeout(() => {
            modal.style.display = 'none';
            console.log('Modal hidden');
        }, 300);
    } else {
        console.log('Modal or modal element not found');
    }
}

function populateWishlistModal(products) {
    const container = document.getElementById('wishlistItems');
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
    fetch('/api/cart/add', {
        method: 'POST',
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
            updateCartCount();
            closeQuickViewModal();
        }
    })
    .catch(error => {
        console.error('Error adding to cart:', error);
    });

    // Optional: Remove from wishlist after adding to cart
    // removeFromWishlistModal(productId, productName);
}

function removeFromWishlistModal(productId, productName) {
    // Get current count before removal for optimistic update
    const countElement = document.getElementById('wishlistModalCount');
    const currentCountText = countElement.textContent;
    const currentCount = parseInt(currentCountText.match(/\d+/)[0]);
    const newCount = Math.max(0, currentCount - 1);

    // Immediately remove the item from modal (optimistic update)
    const wishlistContainer = document.getElementById('wishlistItems');
    const item = wishlistContainer.querySelector(`.wishlist-item[data-product-id="${productId}"]`);
    if (item) {
        // Add a fade-out animation
        item.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
        item.style.opacity = '0';
        item.style.transform = 'translateX(-20px)';
        
        // Remove after animation
        setTimeout(() => {
            if (item.parentNode) {
                item.remove();
            }
        }, 200);
    }

    // Immediately update count
    countElement.textContent = `${newCount} item${newCount !== 1 ? 's' : ''} saved`;

    // Immediately update global wishlist count
    updateWishlistCount(newCount);

    // Show empty state if no items left
    if (newCount === 0) {
        setTimeout(() => {
            document.getElementById('wishlistItems').style.display = 'none';
            document.getElementById('emptyWishlistModal').style.display = 'block';
        }, 200);
    }

    // Update wishlist buttons on other pages immediately
    updateWishlistButtons();

    // Now make the API call in the background
    fetch('/api/wishlist/remove', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ product_id: productId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            // Sync the count with server response (in case of discrepancy)
            const finalCountElement = document.getElementById('wishlistModalCount');
            finalCountElement.textContent = `${data.count} item${data.count !== 1 ? 's' : ''} saved`;
            updateWishlistCount(data.count);

            // Update empty state based on actual count
            if (data.count === 0) {
                document.getElementById('wishlistItems').style.display = 'none';
                document.getElementById('emptyWishlistModal').style.display = 'block';
            }
        } else {
            // If API call failed, we need to revert the optimistic changes
            // Re-add the item (this is complex, so we'll just reload the modal)
            loadWishlistItems();
            showToast('Error removing from wishlist', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        // Revert optimistic changes by reloading
        loadWishlistItems();
        showToast('Error removing from wishlist', 'error');
    });
}

function addToWishlist(productId, productName) {
    fetch('/api/wishlist/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ product_id: productId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            updateWishlistCount(data.count);
            updateWishlistButtons();
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function removeFromWishlist(productId, productName = '') {
    fetch('/api/wishlist/remove', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ product_id: productId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            updateWishlistCount(data.count);
            updateWishlistButtons();
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function updateWishlistCount(count) {
    const badges = document.querySelectorAll('#wishlistCount, #wishlistBadge, #accountWishlistCount');
    badges.forEach(badge => {
        badge.textContent = count || 0; // Ensure it shows 0 if count is undefined
        badge.style.display = 'inline-block'; // Always show the badge
    });
}

function updateCartCount() {
    console.log('updateCartCount called');
    fetch('/api/cart/count')
        .then(response => response.json())
        .then(data => {
            console.log('Cart count data:', data);
            const cartCountElements = document.querySelectorAll('#cartCount, .cart-count, #accountCartCount');
            console.log('Found cart count elements:', cartCountElements.length);
            cartCountElements.forEach(element => {
                if (element) {
                    element.textContent = data.count || 0;
                    element.style.display = 'inline-block';
                    console.log('Updated element:', element, 'with count:', data.count);
                }
            });
        })
        .catch(error => {
            console.error('Error updating cart count:', error);
        });
}

function updateWishlistButtons() {
    // Update wishlist button states on product cards
    document.querySelectorAll('.btn-wishlist, .btn-wishlist-detail, .wishlist-heart').forEach(button => {
        const productId = parseInt(button.dataset.productId);
        if (productId) {
            checkWishlistStatus(productId, button);
        }
    });
}

function checkWishlistStatus(productId, button) {
    fetch(`/api/wishlist/check/${productId}`)
    .then(response => response.json())
    .then(data => {
        if (button) {
            if (data.in_wishlist) {
                button.classList.add('in-wishlist');

                // Update icon for heart buttons
                const icon = button.querySelector('i');
                if (icon && icon.classList.contains('far')) {
                    icon.classList.remove('far');
                    icon.classList.add('fas');
                }

                // Update button text for detail page
                if (button.classList.contains('btn-wishlist-detail')) {
                    button.innerHTML = `<i class="fas fa-heart"></i> Remove from Wishlist`;
                }
            } else {
                button.classList.remove('in-wishlist');

                // Update icon for heart buttons
                const icon = button.querySelector('i');
                if (icon && icon.classList.contains('fas')) {
                    icon.classList.remove('fas');
                    icon.classList.add('far');
                }

                // Update button text for detail page
                if (button.classList.contains('btn-wishlist-detail')) {
                    button.innerHTML = `<i class="far fa-heart"></i> Add to Wishlist`;
                }
            }
        }
        updateWishlistCount(data.count);
    })
    .catch(error => console.error('Error checking wishlist status:', error));
}

window.toggleWishlist = function toggleWishlist(productId, productName, button) {
    console.log('Toggle wishlist called:', productId, productName);

    const isInWishlist = button.classList.contains('in-wishlist');

    // Provide immediate visual feedback BEFORE API call
    if (isInWishlist) {
        // Immediately update UI for removing from wishlist
        button.classList.remove('in-wishlist');
        
        // Update icon for heart buttons
        const icon = button.querySelector('i');
        if (icon && icon.classList.contains('fas')) {
            icon.classList.remove('fas');
            icon.classList.add('far');
        }

        // Update text for detail page buttons
        if (button.classList.contains('btn-wishlist-detail')) {
            button.innerHTML = `<i class="far fa-heart"></i> Add to Wishlist`;
        }
    } else {
        // Immediately update UI for adding to wishlist
        button.classList.add('in-wishlist');
        
        // Update icon for heart buttons
        const icon = button.querySelector('i');
        if (icon && icon.classList.contains('far')) {
            icon.classList.remove('far');
            icon.classList.add('fas');
        }

        // Update text for detail page buttons
        if (button.classList.contains('btn-wishlist-detail')) {
            button.innerHTML = `<i class="fas fa-heart"></i> Remove from Wishlist`;
        }
    }

    // Add subtle loading state (less opacity change since UI already updated)
    button.style.opacity = '0.8';
    button.style.pointerEvents = 'none';

    if (isInWishlist) {
        // Remove from wishlist API call
        fetch('/api/wishlist/remove', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ product_id: productId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                updateWishlistCount(data.count);
            } else {
                // Revert UI changes if API call failed
                button.classList.add('in-wishlist');
                const icon = button.querySelector('i');
                if (icon && icon.classList.contains('far')) {
                    icon.classList.remove('far');
                    icon.classList.add('fas');
                }
                if (button.classList.contains('btn-wishlist-detail')) {
                    button.innerHTML = `<i class="fas fa-heart"></i> Remove from Wishlist`;
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            // Revert UI changes on error
            button.classList.add('in-wishlist');
            const icon = button.querySelector('i');
            if (icon && icon.classList.contains('far')) {
                icon.classList.remove('far');
                icon.classList.add('fas');
            }
            if (button.classList.contains('btn-wishlist-detail')) {
                button.innerHTML = `<i class="fas fa-heart"></i> Remove from Wishlist`;
            }
        })
        .finally(() => {
            // Remove loading state
            button.style.opacity = '1';
            button.style.pointerEvents = 'auto';
        });
    } else {
        // Add to wishlist API call
        fetch('/api/wishlist/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ product_id: productId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                updateWishlistCount(data.count);
            } else {
                // Revert UI changes if API call failed
                button.classList.remove('in-wishlist');
                const icon = button.querySelector('i');
                if (icon && icon.classList.contains('fas')) {
                    icon.classList.remove('fas');
                    icon.classList.add('far');
                }
                if (button.classList.contains('btn-wishlist-detail')) {
                    button.innerHTML = `<i class="far fa-heart"></i> Add to Wishlist`;
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            // Revert UI changes on error
            button.classList.remove('in-wishlist');
            const icon = button.querySelector('i');
            if (icon && icon.classList.contains('fas')) {
                icon.classList.remove('fas');
                icon.classList.add('far');
            }
            if (button.classList.contains('btn-wishlist-detail')) {
                button.innerHTML = `<i class="far fa-heart"></i> Add to Wishlist`;
            }
        })
        .finally(() => {
            // Remove loading state
            button.style.opacity = '1';
            button.style.pointerEvents = 'auto';
        });
    }
}

function showToast(message, type = 'info') {
    // Simple toast notification
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <button class="flash_message_close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
        ${message}
    `;

    let stack = document.getElementById('flashStack');
    if (!stack) {
        stack = document.createElement('div');
        stack.id = 'flashStack';
        stack.className = 'toast-stack';
        document.body.appendChild(stack);
    }

    stack.appendChild(toast);

    // Auto remove after 3 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 3000);
}

// Initialize wishlist status on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded - initializing wishlist');

    // DEBUG: Add click listeners to all buttons to see what's happening
    document.querySelectorAll('.btn-add-cart').forEach(button => {
        console.log('Found add to cart button:', button);
        button.addEventListener('click', function(e) {
            console.log('🔥 ADD TO CART BUTTON CLICKED!', e.target);
            console.log('Button onclick attribute:', this.getAttribute('onclick'));
        });
    });

    document.querySelectorAll('.btn-wishlist').forEach(button => {
        console.log('Found wishlist button:', button);
        button.addEventListener('click', function(e) {
            console.log('💖 WISHLIST BUTTON CLICKED!', e.target);
            console.log('Button onclick attribute:', this.getAttribute('onclick'));
        });
    });

    // Initialize counts
    updateWishlistCount(0);
    updateCartCount();

    // Check wishlist status for all products on the page
    updateWishlistButtons();

    // Get initial wishlist count
    fetch('/api/wishlist')
    .then(response => response.json())
    .then(data => {
        updateWishlistCount(data.count || 0);
    })
    .catch(error => {
        console.error('Error getting wishlist count:', error);
        updateWishlistCount(0); // Fallback to 0 on error
    });

    // Add click handler for navigation wishlist icon
    const wishlistIcons = document.querySelectorAll('button[title="Wishlist"], .nav-icon-btn[title="Wishlist"]');
    wishlistIcons.forEach(icon => {
        console.log('Setting up wishlist icon click handler');
        // Don't remove onclick, just add event listener as backup
        icon.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Navigation wishlist icon clicked');
            openWishlistModal();
        });
    });

    // Add click handler for wishlist modal overlay to close modal
    const wishlistModal = document.getElementById('wishlistModal');
    if (wishlistModal) {
        wishlistModal.addEventListener('click', function(e) {
            // Close modal if clicking on the overlay (not the modal content)
            if (e.target === wishlistModal) {
                closeWishlistModal();
            }
        });

        // Add click handler for the close button (X)
        const closeButton = wishlistModal.querySelector('.modal-close');
        if (closeButton) {
            closeButton.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('Close button clicked');
                closeWishlistModal();
            });
        }

        // Add click handler for the "Continue Shopping" button
        const continueShoppingBtn = wishlistModal.querySelector('.empty-wishlist-modal .btn');
        if (continueShoppingBtn) {
            continueShoppingBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                closeWishlistModal();
                // Navigate to products page
                window.location.href = '/products';
            });
        }
    }

    // Add keyboard event handler for Escape key to close modal
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const wishlistModal = document.getElementById('wishlistModal');
            if (wishlistModal && wishlistModal.style.display !== 'none') {
                closeWishlistModal();
            }
        }
    });

    // Add click handlers for product wishlist buttons (heart icons on cards)
    const productWishlistBtns = document.querySelectorAll('.btn-wishlist');
    productWishlistBtns.forEach(btn => {
        btn.removeAttribute('onclick');
        const productId = parseInt(btn.dataset.productId);
        if (productId) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('Product wishlist button clicked:', productId);

                // Get product name from the card
                const productCard = btn.closest('.product-card, .clean-product-card');
                const productNameElement = productCard ? productCard.querySelector('.product-title a, .clean-product-title') : null;
                const productName = productNameElement ? productNameElement.textContent.trim() : 'Product';

                toggleWishlist(productId, productName, btn);
            });
        }
    });
});

function viewCart() {
    // Close the account modal first
    closeAccountModal();
    
    // Small delay before opening cart modal
    setTimeout(() => {
        openCartModal();
    }, 100);
}

function viewSettings() {
    // Close the account modal first
    closeAccountModal();
    
    // Navigate to settings page
    setTimeout(() => {
        window.location.href = '/settings';
    }, 100);
}

function viewOrders() {
    alert('Previous orders functionality coming soon!');
}

// Password toggle function
function togglePasswordVisibility(inputId, toggleButton) {
    const input = document.getElementById(inputId);
    const icon = toggleButton.querySelector('i');

    if (input && icon) {
        if (input.type === 'password') {
            input.type = 'text';
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        } else {
            input.type = 'password';
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        }
    }
}

// Document ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize modals
    initializeModals();

    // Initialize slideshows
    initializeSlideshows();

    // Initialize search and filters
    initializeFilters();

    // Initialize product interactions
    initializeProductInteractions();

    // Initialize Miami map
    initializeMiamiMap();

    // Folium map is now loaded via iframe, no initialization needed

    // Setup additional functionality
    setupSearchAndFilter();
    setupProductGrid();
    setupQuickView();
    setupAuthModals();
    setupToastNotifications();
    setupFormValidation();
    setupSlideshow();

    // Call the missing functions
    initializeSearchAndFilter();
    initializeProductGrid();

    // Initialize color tooltips
    initializeColorTooltips();

    // Initialize color filters
    initializeColorFilters();

    // Close color dropdown when clicking outside
    document.addEventListener('click', function(event) {
        const colorDropdown = document.querySelector('.color-filter-dropdown');
        const colorMenu = document.getElementById('colorDropdownMenu');
        const colorToggle = document.querySelector('.color-dropdown-toggle');

        if (colorDropdown && !colorDropdown.contains(event.target)) {
            colorMenu.classList.remove('show');
            colorToggle.classList.remove('active');
        }
    });

    // Auto-hide flash messages after 5 seconds
    setTimeout(() => {
        document.querySelectorAll('.toast').forEach(toast => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        });
    }, 5000);
});

// Initialize all modals
function initializeModals() {
    // Sign in button
    const signInBtn = document.getElementById('signInButton');
    if (signInBtn) {
        signInBtn.addEventListener('click', () => showModal('loginModal'));
    }

    // Account button (for logged-in users)
    const userMenuBtn = document.getElementById('userMenuButton');
    if (userMenuBtn) {
        userMenuBtn.addEventListener('click', () => showModal('loggedModal'));
    }

    // Modal close buttons
    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', hideModals);
    });

    // Overlay click to close
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                e.preventDefault();
                e.stopPropagation();
                hideModals();
            }
        });
    });

    // Switch between login and register
    const showRegister = document.getElementById('showRegisterModal');
    const showLogin = document.getElementById('showLoginModal');

    if (showRegister) {
        showRegister.addEventListener('click', (e) => {
            e.preventDefault();
            showModal('registerModal');
        });
    }

    if (showLogin) {
        showLogin.addEventListener('click', (e) => {
            e.preventDefault();
            showModal('loginModal');
        });
    }


}

// Initialize slideshow functionality
function initializeSlideshows() {
    document.querySelectorAll('.product-slideshow').forEach(slideshow => {
        const productId = slideshow.dataset.productId;
        if (!currentSlides[productId]) {
            currentSlides[productId] = 0;
        }
    });
}

// Clear search function
function clearSearch() {
    document.getElementById('productSearch').value = '';
    const clearBtn = document.querySelector('.clear-search-btn');
    clearBtn.style.display = 'none';
    handleSearch(); // Reset to show all products
}

// Show/hide clear button based on search input
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('productSearch');
    const clearBtn = document.querySelector('.clear-search-btn');

    if (searchInput && clearBtn) {
        searchInput.addEventListener('input', function() {
            clearBtn.style.display = this.value ? 'block' : 'none';
        });
    }
});

// Initialize search and filter functionality
function initializeFilters() {
    const searchInput = document.getElementById('productSearch');
    const clearBtn = document.getElementById('clearSearch');

    if (searchInput) {
        searchInput.addEventListener('input', handleSearch);
        searchInput.addEventListener('input', () => {
            clearBtn.style.display = searchInput.value ? 'flex' : 'none';
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            searchInput.value = '';
            clearBtn.style.display = 'none';
            handleSearch();
        });
    }

    // Category filters
    document.querySelectorAll('[data-filter]').forEach(filter => {
        filter.addEventListener('click', (e) => {
            e.preventDefault();
            const category = e.target.dataset.filter;
            filterProducts(category);
        });
    });

    // Handle dropdown menu clicks for category filtering
    document.addEventListener('click', function(e) {
        // Handle dropdown items with onclick attributes
        if (e.target.getAttribute('onclick') && e.target.getAttribute('onclick').includes('filterProducts')) {
            e.preventDefault();
            e.stopPropagation();
            // Extract category from onclick attribute
            const onclickValue = e.target.getAttribute('onclick');
            const categoryMatch = onclickValue.match(/filterProducts\('([^']+)'\)/);
            if (categoryMatch) {
                const category = categoryMatch[1];
                filterProducts(category);
            }
        }

        // Handle dropdown toggles
        if (e.target.closest('.dropdown-toggle')) {
            e.preventDefault();
            e.stopPropagation();
            const toggle = e.target.closest('.dropdown-toggle');
            const dropdown = toggle.closest('.nav-dropdown');
            const menu = dropdown.querySelector('.dropdown-menu');

            if (menu) {
                const isVisible = menu.style.opacity === '1' || menu.classList.contains('show');

                // Close all other dropdowns first
                document.querySelectorAll('.dropdown-menu').forEach(otherMenu => {
                    if (otherMenu !== menu) {
                        otherMenu.style.opacity = '0';
                        otherMenu.style.visibility = 'hidden';
                        otherMenu.style.transform = 'translateY(-10px)';
                        otherMenu.classList.remove('show');
                    }
                });

                // Toggle current dropdown
                if (isVisible) {
                    menu.style.opacity = '0';
                    menu.style.visibility = 'hidden';
                    menu.style.transform = 'translateY(-10px)';
                    menu.classList.remove('show');
                } else {
                    menu.style.opacity = '1';
                    menu.style.visibility = 'visible';
                    menu.style.transform = 'translateY(0)';
                    menu.classList.add('show');
                }
            }
        }

        // Close dropdowns when clicking outside
        if (!e.target.closest('.nav-dropdown')) {
            document.querySelectorAll('.dropdown-menu').forEach(menu => {
                menu.style.opacity = '0';
                menu.style.visibility = 'hidden';
                menu.style.transform = 'translateY(-10px)';
                menu.classList.remove('show');
            });
        }
    });

    // Price and brand filters
    const priceFilter = document.getElementById('priceSort');
    const brandFilter = document.getElementById('brandFilter');
    const inStockFilter = document.getElementById('inStockFilter');

    if (priceFilter) {
        priceFilter.addEventListener('change', handlePriceSort);
    }

    if (brandFilter) {
        brandFilter.addEventListener('change', handleBrandFilter);
    }

    if (inStockFilter) {
        inStockFilter.addEventListener('change', handleInStockFilter);
    }
}

// Initialize product interactions
function initializeProductInteractions() {
    // Quick view modal
    const quickViewModal = document.getElementById('quickViewModal');
    const quickViewClose = document.getElementById('quickViewClose');

    if (quickViewClose) {
        quickViewClose.addEventListener('click', closeQuickView);
    }

    if (quickViewModal) {
        quickViewModal.addEventListener('click', (e) => {
            if (e.target === quickViewModal) closeQuickView();
        });
    }
}

// Modal functions
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.add('active');
        setTimeout(() => {
            const modalContent = modal.querySelector('.modal');
            if (modalContent) {
                modalContent.style.transform = 'scale(1) translateY(0)';
            }
        }, 10);
    }
}

function hideModals() {
    const modals = document.querySelectorAll('.modal-overlay');
    modals.forEach(modal => {
        modal.classList.remove('active');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    });
}

function closeAccountModal() {
    const accountModal = document.getElementById('loggedModal');
    if (accountModal) {
        accountModal.classList.remove('active');
        setTimeout(() => {
            accountModal.style.display = 'none';
        }, 300);
    }
}

function closeModal() {
    hideModals();
}

function switchModal(type, event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    // Close current modal immediately
    const currentModals = document.querySelectorAll('.modal-overlay.active');
    currentModals.forEach(modal => {
        modal.classList.remove('active');
        modal.style.display = 'none';
    });

    // Show new modal immediately
    if (type === 'register') {
        showModal('registerModal');
    } else if (type === 'login') {
        showModal('loginModal');
    }
}

// Search functionality - using the comprehensive filter system

// Global filter state
let activeFilters = {
    category: 'all',
    inStock: false,
    minPrice: 0,
    maxPrice: 500,
    colors: [],
    rating: 0,
    brand: '',
    search: ''
};

// Initialize colors for filter
function initializeColorFilters() {
    const colorGrid = document.getElementById('colorGrid');
    if (!colorGrid) {
        console.log('No color grid found, creating color filter functionality for existing elements');
        return;
    }

    // Fetch colors from database
    fetch('/api/colors')
        .then(response => response.json())
        .then(dbColors => {
            // Clear existing content
            colorGrid.innerHTML = '';

            // Add "All Colors" option first
            const allColorsDot = document.createElement('div');
            allColorsDot.className = 'color-grid-dot all-colors selected';
            allColorsDot.dataset.color = '';
            allColorsDot.onclick = () => selectGridColor('');
            allColorsDot.title = 'All Colors';

            // Add hover event listeners for tooltip
            allColorsDot.addEventListener('mouseenter', function() {
                showColorTooltip(this, 'All Colors');
            });
            allColorsDot.addEventListener('mouseleave', function() {
                hideColorTooltip(this);
            });

            colorGrid.appendChild(allColorsDot);

            // Add color dots for each database color
            dbColors.forEach(color => {
                const colorDot = document.createElement('div');
                colorDot.className = 'color-grid-dot';
                colorDot.dataset.color = color.slug;
                colorDot.dataset.colorName = color.name;
                colorDot.onclick = () => selectGridColor(color.slug);

                // Use actual hex color from database
                colorDot.style.backgroundColor = color.hex;
                colorDot.title = color.name;

                // Add hover event listeners for tooltip
                colorDot.addEventListener('mouseenter', function() {
                    showColorTooltip(this, color.name);
                });
                colorDot.addEventListener('mouseleave', function() {
                    hideColorTooltip(this);
                });

                colorGrid.appendChild(colorDot);
            });

            console.log('Color filtering initialized successfully');
        })
        .catch(error => {
            console.error('Error fetching colors:', error);
            // Fallback to existing behavior if API fails
            initializeColorFiltersFallback();
        });
}

// Fallback function in case API fails
function initializeColorFiltersFallback() {
    const colorGrid = document.getElementById('colorGrid');
    if (!colorGrid) return;

    // Get unique colors from all products
    const allColors = new Set();
    document.querySelectorAll('.product-card').forEach(card => {
        const colors = card.dataset.colors;
        if (colors) {
            colors.split(',').forEach(color => {
                if (color.trim()) allColors.add(color.trim());
            });
        }
    });

    // Add "All Colors" option first
    const allColorsDot = document.createElement('div');
    allColorsDot.className = 'color-grid-dot all-colors selected';
    allColorsDot.dataset.color = '';
    allColorsDot.onclick = () => selectGridColor('');
    allColorsDot.title = 'All Colors';
    colorGrid.appendChild(allColorsDot);

    // Add color dots for each unique color (fallback)
    allColors.forEach(colorSlug => {
        const colorDot = document.createElement('div');
        colorDot.className = 'color-grid-dot';
        colorDot.dataset.color = colorSlug;
        colorDot.onclick = () => selectGridColor(colorSlug);
        colorDot.style.backgroundColor = '#6B7280'; // grey fallback
        colorDot.title = colorSlug;
        colorGrid.appendChild(colorDot);
    });
}

// Toggle color dropdown
function toggleColorDropdown() {
    const dropdown = document.getElementById('colorDropdownMenu');
    const toggle = document.querySelector('.color-dropdown-toggle');

    dropdown.classList.toggle('show');
    toggle.classList.toggle('active');
}

// Select color from grid
function selectGridColor(color) {
    const label = document.getElementById('colorFilterLabel');
    const selectedDot = document.querySelector(`[data-color="${color}"]`);

    console.log('Selecting color:', color);

    // Handle "All Colors" selection
    if (color === '') {
        // Clear all color selections
        document.querySelectorAll('.color-grid-dot').forEach(dot => {
            dot.classList.remove('selected');
        });
        if (selectedDot) selectedDot.classList.add('selected');
        if (label) label.textContent = 'Colors';
        activeFilters.colors = [];
    } else {
        // Remove "All Colors" selection if any specific color is selected
        const allColorsDot = document.querySelector('.color-grid-dot.all-colors');
        if (allColorsDot) {
            allColorsDot.classList.remove('selected');
        }

        // Toggle the clicked color
        if (selectedDot && selectedDot.classList.contains('selected')) {
            // Remove this color from selection
            selectedDot.classList.remove('selected');
            const colorIndex = activeFilters.colors.indexOf(color);
            if (colorIndex > -1) {
                activeFilters.colors.splice(colorIndex, 1);
            }
        } else {
            // Add this color to selection
            if (selectedDot) selectedDot.classList.add('selected');
            if (!activeFilters.colors.includes(color)) {
                activeFilters.colors.push(color);
            }
        }

        // Update label based on selected colors
        if (activeFilters.colors.length === 0) {
            if (label) label.textContent = 'Colors';
            // Re-select "All Colors" if no colors are selected
            if (allColorsDot) {
                allColorsDot.classList.add('selected');
            }
        } else if (activeFilters.colors.length === 1) {
            const colorName = selectedDot ? (selectedDot.dataset.colorName || selectedDot.title) : color;
            if (label) label.textContent = colorName;
        } else {
            if (label) label.textContent = `${activeFilters.colors.length} colors`;
        }
    }

    // Close dropdown
    const dropdown = document.getElementById('colorDropdownMenu');
    const toggle = document.querySelector('.color-dropdown-toggle');
    if (dropdown) dropdown.classList.remove('show');
    if (toggle) toggle.classList.remove('active');

    console.log('Active color filters:', activeFilters.colors);

    // Apply filters
    applyAllFilters();
}

// Legacy function for compatibility
function selectColor(color) {
    selectGridColor(color);
}

// Handle price range filter
function handlePriceRangeFilter() {
    const priceRange = document.getElementById('priceRangeFilter').value;

    if (priceRange === '') {
        activeFilters.minPrice = 0;
        activeFilters.maxPrice = 999999;
    } else {
        const [min, max] = priceRange.split('-').map(Number);
        activeFilters.minPrice = min;
        activeFilters.maxPrice = max || 999999;
    }

    applyAllFilters();
}

// Filter functions
function filterProducts(category) {
    activeFilters.category = category;
    applyAllFilters();

    // Close any open dropdowns after selection
    document.querySelectorAll('.dropdown-menu').forEach(menu => {
        menu.style.opacity = '0';
        menu.style.visibility = 'hidden';
        menu.style.transform = 'translateY(-10px)';
        menu.classList.remove('show');
    });
}

function handleInStockFilter() {
    activeFilters.inStock = document.getElementById('inStockFilter').checked;
    applyAllFilters();
}

function updatePriceRange() {
    const minSlider = document.getElementById('minPriceRange');
    const maxSlider = document.getElementById('maxPriceRange');
    const minValue = document.getElementById('minPriceValue');
    const maxValue = document.getElementById('maxPriceValue');

    if (!minSlider || !maxSlider || !minValue || !maxValue) return;

    let min = parseInt(minSlider.value);
    let max = parseInt(maxSlider.value);

    // Ensure min doesn't exceed max
    if (min >= max) {
        min = max - 5;
        minSlider.value = min;
    }

    // Ensure max doesn't go below min
    if (max <= min) {
        max = min + 5;
        maxSlider.value = max;
    }

    activeFilters.minPrice = min;    activeFilters.maxPrice = max;

    minValue.textContent = `$${min}`;
    maxValue.textContent = `$${max}`;

    // Apply filters with a small delay to avoid too many calls
    clearTimeout(window.priceFilterTimeout);
    window.priceFilterTimeout = setTimeout(() => {
        applyAllFilters();
    }, 300);
}

function toggleColorFilter(color) {
    const colorDot = document.querySelector(`[data-color="${color}"]`);
    const index = activeFilters.colors.indexOf(color);

    if (index > -1) {
        activeFilters.colors.splice(index, 1);
        colorDot.classList.remove('selected');
    } else {
        activeFilters.colors.push(color);
        colorDot.classList.add('selected');
    }

    applyAllFilters();
}

function handleRatingFilter() {
    const rating = document.getElementById('ratingFilter').value;
    activeFilters.rating = rating ? parseFloat(rating) : 0;
    applyAllFilters();
}

function handlePriceSort() {
    const sortValue = document.getElementById('priceSort').value;
    const products = Array.from(document.querySelectorAll('.product-card:not([style*="display: none"])'));
    const container = document.getElementById('productGrid');

    if (sortValue === 'low-high') {
        products.sort((a, b) => {
            return parseFloat(a.dataset.price) - parseFloat(b.dataset.price);
        });
    } else if (sortValue === 'high-low') {
        products.sort((a, b) => {
            return parseFloat(b.dataset.price) - parseFloat(a.dataset.price);
        });
    }

    // Re-append sorted products while maintaining filter visibility
    products.forEach(product => {
        container.appendChild(product);
    });
}

function handleBrandFilter() {
    const brand = document.getElementById('brandFilter').value;
    activeFilters.brand = brand;
    applyAllFilters();
}

function handleSearch() {
    const searchTerm = document.getElementById('productSearch').value.toLowerCase();
    activeFilters.search = searchTerm;
    applyAllFilters();
}

function applyAllFilters() {
    const products = document.querySelectorAll('.product-card, .clean-product-card');
    let visibleCount = 0;

    console.log('Applying filters to', products.length, 'products');
    console.log('Active filters:', activeFilters);

    products.forEach(product => {
        let isVisible = true;

        // Category filter
        if (activeFilters.category !== 'all') {
            const productCategory = product.dataset.category;
            const parentCategory = product.dataset.parentCategory;

            // Check if product matches the selected category or parent category
            if (productCategory !== activeFilters.category && parentCategory !== activeFilters.category) {
                isVisible = false;
            }
        }

        // In-stock filter
        if (activeFilters.inStock && product.dataset.inStock === 'false') {
            isVisible = false;
        }

        // Price range filter
        const price = parseFloat(product.dataset.price);
        if (price < activeFilters.minPrice || price > activeFilters.maxPrice) {
            isVisible = false;
        }

        // Color filter - if any selected colors match any product colors, show the product
        if (activeFilters.colors.length > 0) {
            const productColors = product.dataset.colors ? product.dataset.colors.split(',').map(c => c.trim()).filter(c => c) : [];
            console.log('Product colors:', productColors, 'Selected colors:', activeFilters.colors);

            const hasMatchingColor = activeFilters.colors.some(selectedColor =>
                productColors.some(productColor => {
                    // Check for exact match
                    if (productColor === selectedColor) {
                        return true;
                    }

                    // Handle split colors (like "black-green" or "black-purple")
                    if (productColor.includes('-')) {
                        const splitColors = productColor.split('-').map(c => c.trim());
                        return splitColors.includes(selectedColor);
                    }

                    // Handle if selected color contains the product color
                    if (selectedColor.includes('-')) {
                        const selectedSplitColors = selectedColor.split('-').map(c => c.trim());
                        return selectedSplitColors.includes(productColor);
                    }

                    // Fallback: check if either contains the other
                    return productColor.includes(selectedColor) || selectedColor.includes(productColor);
                })
            );

            if (!hasMatchingColor) {
                isVisible = false;
            }
        }

        // Rating filter
        if (activeFilters.rating > 0) {
            const rating = parseFloat(product.dataset.rating) || 0;
            if (rating < activeFilters.rating) {
                isVisible = false;
            }
        }

        // Brand filter
        if (activeFilters.brand) {
            const productBrand = product.dataset.brand;
            if (productBrand !== activeFilters.brand) {
                isVisible = false;
            }
        }

        // Search filter
        if (activeFilters.search) {
            const titleElement = product.querySelector('.product-title, .clean-product-title');
            const title = titleElement ? titleElement.textContent.toLowerCase() : '';
            const descriptionElement = product.querySelector('.product-description, .clean-product-subtitle');
            const descText = descriptionElement ? descriptionElement.textContent.toLowerCase() : '';

            if (!title.includes(activeFilters.search) && !descText.includes(activeFilters.search)) {
                isVisible = false;
            }
        }

        // Show/hide product
        if (isVisible) {
            product.style.display = 'block';
            visibleCount++;
        } else {
            product.style.display = 'none';
        }
    });

    updateResultCount(visibleCount);
}

function clearAllFilters() {
    // Find actual price range from products
    const prices = Array.from(document.querySelectorAll('.product-card')).map(p => parseFloat(p.dataset.price)).filter(p => !isNaN(p));
    const minPrice = Math.floor(Math.min(...prices));
    const maxPrice = Math.ceil(Math.max(...prices));

    // Reset all filter values
    activeFilters = {
        category: 'all',
        inStock: false,
        minPrice: minPrice,
        maxPrice: maxPrice,
        colors: [],
        rating: 0,
        brand: '',
        search: ''
    };

    // Reset UI elements
    const searchInput = document.getElementById('productSearch');
    const inStockFilter = document.getElementById('inStockFilter');
    const priceSort = document.getElementById('priceSort');
    const brandFilter = document.getElementById('brandFilter');
    const ratingFilter = document.getElementById('ratingFilter');

    if (searchInput) searchInput.value = '';
    if (inStockFilter) inStockFilter.checked = false;
    if (priceSort) priceSort.value = '';
    if (brandFilter) brandFilter.value = '';
    if (ratingFilter) ratingFilter.value = '';

    // Reset price range sliders
    const minSlider = document.getElementById('minPriceRange');
    const maxSlider = document.getElementById('maxPriceRange');
    const minValue = document.getElementById('minPriceValue');
    const maxValue = document.getElementById('maxPriceValue');

    if (minSlider && maxSlider && minValue && maxValue) {
        minSlider.value = minPrice;
        maxSlider.value = maxPrice;
        minValue.textContent = `$${minPrice}`;
        maxValue.textContent = `$${maxPrice}`;
    }

    // Reset color grid
    const colorLabel = document.getElementById('colorFilterLabel');
    if (colorLabel) colorLabel.textContent = 'Colors';

    document.querySelectorAll('.color-grid-dot').forEach(dot => {
        dot.classList.remove('selected');
    });

    const allColorsDot = document.querySelector('.color-grid-dot.all-colors');
    if (allColorsDot) {
        allColorsDot.classList.add('selected');
    }

    // Hide clear search button
    const clearBtn = document.querySelector('.clear-search-btn');
    if (clearBtn) {
        clearBtn.style.display = 'none';
    }

    // Close any open dropdowns
    document.querySelectorAll('.dropdown-menu').forEach(menu => {
        menu.style.opacity = '0';
        menu.style.visibility = 'hidden';
        menu.style.transform = 'translateY(-10px)';
        menu.classList.remove('show');
    });

    const colorDropdown = document.getElementById('colorDropdownMenu');
    const colorToggle = document.querySelector('.color-dropdown-toggle');
    if (colorDropdown) colorDropdown.classList.remove('show');
    if (colorToggle) colorToggle.classList.remove('active');

    // Apply filters (will show all products)
    applyAllFilters();
}

function updateResultCount(count) {
    const resultCount = document.getElementById('resultCount');
    if (resultCount) {
        resultCount.textContent = `${count} product${count !== 1 ? 's' : ''}`;
    }
}

// Slideshow functions
function changeSlide(productId, direction) {
    const slideshow = document.querySelector(`[data-product-id="${productId}"]`);
    if (!slideshow) return;

    const slides = slideshow.querySelectorAll('.slideshow-image');
    const indicators = slideshow.querySelectorAll('.indicator');

    if (slides.length <= 1) return;

    // Remove active class from current slide
    slides[currentSlides[productId]].classList.remove('active');
    if (indicators[currentSlides[productId]]) {
        indicators[currentSlides[productId]].classList.remove('active');
    }

    // Calculate new slide index
    currentSlides[productId] += direction;

    if (currentSlides[productId] >= slides.length) {
        currentSlides[productId] = 0;
    } else if (currentSlides[productId] < 0) {
        currentSlides[productId] = slides.length - 1;
    }

    // Add active class to new slide
    slides[currentSlides[productId]].classList.add('active');
    if (indicators[currentSlides[productId]]) {
        indicators[currentSlides[productId]].classList.add('active');
    }
}

function goToSlide(productId, slideIndex) {
    const slideshow = document.querySelector(`[data-product-id="${productId}"]`);
    if (!slideshow) return;

    const slides = slideshow.querySelectorAll('.slideshow-image');
    const indicators = slideshow.querySelectorAll('.indicator');

    // Remove active class from current slide
    slides[currentSlides[productId]].classList.remove('active');
    if (indicators[currentSlides[productId]]) {
        indicators[currentSlides[productId]].classList.remove('active');
    }

    // Set new slide
    currentSlides[productId] = slideIndex;

    // Add active class to new slide
    slides[currentSlides[productId]].classList.add('active');
    if (indicators[currentSlides[productId]]) {
        indicators[currentSlides[productId]].classList.add('active');
    }
}

// Quick view functions
function openQuickView(productId) {
    fetch(`/api/product/${productId}`)
        .then(response => response.json())
        .then(data => {
            populateQuickView(data);
            document.getElementById('quickViewModal').style.display = 'flex';
        })
        .catch(error => {
            console.error('Error fetching product details:', error);
        });
}

function closeQuickView() {
    document.getElementById('quickViewModal').style.display = 'none';
}

function changeQuickViewQuantity(delta) {
    const input = document.getElementById('quickViewQuantity');
    if (input) {
        const currentValue = parseInt(input.value) || 1;
        const newValue = Math.max(1, Math.min(currentValue + delta, parseInt(input.max) || 99));
        input.value = newValue;
    }
}

function populateQuickView(product) {
    // Update product details
    document.getElementById('quickViewProductName').textContent = product.name;
    document.getElementById('quickViewPrice').textContent = `$${product.price.toFixed(2)}`;
    document.getElementById('quickViewDescription').textContent = product.description;
    
    // Update stock status
    const stockStatus = document.getElementById('quickViewStockStatus');
    const stockText = document.getElementById('quickViewStockText');
    const stockIcon = stockStatus.querySelector('i');
    
    if (product.in_stock) {
        stockStatus.className = 'stock-status in-stock';
        stockText.textContent = 'In Stock';
        stockIcon.className = 'fas fa-check-circle';
    } else {
        stockStatus.className = 'stock-status out-of-stock';
        stockText.textContent = 'Out of Stock';
        stockIcon.className = 'fas fa-times-circle';
    }

    // Update main image
    const mainImage = document.getElementById('quickViewMainImage');
    if (product.images && product.images.length > 0) {
        mainImage.src = product.images[0].url;
        mainImage.alt = product.name;
    }

    // Update thumbnails
    updateQuickViewThumbnails(product.images);

    // Update view full details link
    const viewFullBtn = document.getElementById('quickViewViewFull');
    if (viewFullBtn) {
        viewFullBtn.onclick = () => {
            window.location.href = `/product/${product.id}`;
        };
    }
    
    // Update add to cart button
    const addToCartBtn = document.getElementById('quickViewAddToCart');
    if (addToCartBtn) {
        if (product.in_stock) {
            addToCartBtn.disabled = false;
            addToCartBtn.innerHTML = '<i class="fas fa-shopping-cart"></i> Add to Cart';
            addToCartBtn.onclick = () => {
                const quantityInput = document.getElementById('quickViewQuantity');
                const quantity = quantityInput ? parseInt(quantityInput.value) || 1 : 1;
                addToCartWithQuantity(product.id, product.name, product.price, quantity);
            };
        } else {
            addToCartBtn.disabled = true;
            addToCartBtn.innerHTML = '<i class="fas fa-times"></i> Out of Stock';
            addToCartBtn.onclick = null;
        }
    }
    
    // Update wishlist button
    const wishlistBtn = document.getElementById('quickViewAddToWishlist');
    if (wishlistBtn) {
        wishlistBtn.onclick = () => {
            toggleWishlist(product.id, product.name, wishlistBtn);
        };
        // Check current wishlist status
        checkWishlistStatus(product.id, wishlistBtn);
    }
}

function updateQuickViewThumbnails(images) {
    const container = document.getElementById('quickViewThumbnails');
    if (!container || !images) return;

    container.innerHTML = '';
    quickViewImages = images;

    images.forEach((image, index) => {
        const thumb = document.createElement('img');
        thumb.src = image.url;
        thumb.alt = image.alt_text || 'Product image';
        thumb.className = `quick-view-thumbnail ${index === 0 ? 'active' : ''}`;
        thumb.onclick = () => switchQuickViewImage(index);
        container.appendChild(thumb);
    });
}

function switchQuickViewImage(index) {
    const mainImage = document.getElementById('quickViewMainImage');
    const thumbnails = document.querySelectorAll('.quick-view-thumbnail');

    // Update main image
    if (quickViewImages[index]) {
        mainImage.src = quickViewImages[index].url;
        currentQuickViewIndex = index;
    }

    // Update thumbnail active states
    thumbnails.forEach((thumb, i) => {
        thumb.classList.toggle('active', i === index);
    });
}

// Test function to verify JavaScript is loaded
window.testCartFunction = function() {
    console.log('✅ JavaScript is loaded and functions are accessible');
    console.log('addToCart function exists:', typeof addToCart);
    console.log('toggleWishlist function exists:', typeof toggleWishlist);
    console.log('showToast function exists:', typeof showToast);
    showToast('JavaScript test successful!', 'success');
    return true;
};

// Test the addToCart function directly
window.testAddToCart = function() {
    console.log('🧪 Testing addToCart function...');
    if (typeof addToCart === 'function') {
        addToCart(1, 'Test Product', 19.99);
        return true;
    } else {
        console.error('❌ addToCart function not found!');
        return false;
    }
};

// Cart and wishlist functions
window.addToCart = function addToCart(productId, productName, price) {
    console.log('🛒 addToCart called with:', productId, productName, price);
    addToCartWithQuantity(productId, productName, price, 1);
}

function addToCartWithQuantity(productId, productName, price, quantity = 1) {
    console.log('🛒 addToCartWithQuantity called with:', productId, productName, price, quantity);
    
    // Check if product is in stock by looking at the product card data
    const productCard = document.querySelector(`.product-card[data-product-id="${productId}"]`);
    const isInStock = productCard ? productCard.dataset.inStock === 'true' : true;
    
    if (!isInStock) {
        showToast('This item is currently out of stock', 'error');
        return;
    }
    
    fetch('/api/cart/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            product_id: productId,
            quantity: quantity
        })
    })
    .then(response => {
        console.log('Response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Response data:', data);
        if (data.message) {
            updateCartCount();
            // Silent add to cart - no toast message
        } else if (data.error) {
            showToast(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error adding to cart:', error);
        showToast('Error adding to cart', 'error');
    });
}



function addToWishlist(productId, productName) {
    fetch('/api/wishlist/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ product_id: productId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            updateWishlistCount(data.count);
            updateWishlistButtons();
            // Silent wishlist add - no toast message
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error adding to wishlist', 'error');
    });
}

// Color tooltip functionality
function showColorTooltip(element, colorName) {
    // Remove any existing tooltips
    hideAllColorTooltips();

    // Create tooltip
    const tooltip = document.createElement('div');
    tooltip.className = 'color-tooltip';
    tooltip.textContent = colorName;

    // Position tooltip relative to document body to avoid overflow issues
    document.body.appendChild(tooltip);

    // Position the tooltip
    const rect = element.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();

    tooltip.style.position = 'fixed';
    tooltip.style.left = `${rect.right + 10}px`; // Position to the right of the color dot
    tooltip.style.top = `${rect.top + (rect.height / 2) - (tooltipRect.height / 2)}px`; // Center vertically
    tooltip.style.zIndex = '10000';

    // Show tooltip with a slight delay for smooth animation
    requestAnimationFrame(() => {
        tooltip.classList.add('show');
    });
}

function hideColorTooltip(element) {
    hideAllColorTooltips();
}

function hideAllColorTooltips() {
    document.querySelectorAll('.color-tooltip').forEach(tooltip => {
        tooltip.classList.remove('show');
        setTimeout(() => {
            if (tooltip && tooltip.parentNode) {
                tooltip.parentNode.removeChild(tooltip);
            }
        }, 200);
    });
}

// Initialize color tooltips
function initializeColorTooltips() {
    // Add hover events to all color dots
    document.querySelectorAll('.color-dot, .product-color-dot').forEach(dot => {
        dot.addEventListener('mouseenter', function() {
            const colorName = this.getAttribute('data-color-name') || this.getAttribute('title');
            if (colorName) {
                showColorTooltip(this, colorName);
            }
        });

        dot.addEventListener('mouseleave', function() {
            hideColorTooltip(this);
        });
    });
}

// Make functions globally available
window.showColorTooltip = showColorTooltip;
window.hideColorTooltip = hideColorTooltip;

// Color selection functionality
document.addEventListener('DOMContentLoaded', function() {
    // Handle color dot selection
    document.querySelectorAll('.color-dot').forEach(dot => {
        dot.addEventListener('click', function(e) {
            e.stopPropagation();

            // Remove active class from siblings
            const parentColorOptions = this.parentElement;
            parentColorOptions.querySelectorAll('.color-dot').forEach(d => {
                d.classList.remove('active');
            });

            // Add active class to clicked dot
            this.classList.add('active');

            // Optional: Update product image based on color
            const color = this.dataset.color;
            console.log(`Selected color: ${color}`);

            // You can add logic here to change the product image based on selected color
        });
    });

    // Handle wishlist heart toggle
    document.querySelectorAll('.wishlist-heart').forEach(heart => {
        heart.addEventListener('click', function(e) {
            e.stopPropagation();

            const productId = parseInt(this.dataset.productId);
            if (productId) {
                // Get product name from the card
                const productCard = this.closest('.product-card, .clean-product-card');
                const productNameElement = productCard ? productCard.querySelector('.product-title a, .clean-product-title') : null;
                const productName = productNameElement ? productNameElement.textContent.trim() : 'Product';

                toggleWishlist(productId, productName, this);
            }
        });
    });
});
// Interactive Miami Map functionality
function initializeMiamiMap() {
    const deliveryAreas = document.querySelectorAll('.delivery-area');
    const tooltip = document.getElementById('areaTooltip');

    if (!tooltip) return;

    deliveryAreas.forEach(area => {
        area.addEventListener('mouseenter', (e) => {
            const areaName = e.target.dataset.area;
            const deliveryTime = e.target.dataset.time;

            tooltip.querySelector('.tooltip-title').textContent = areaName;
            tooltip.querySelector('.tooltip-time').textContent = `Delivery: ${deliveryTime}`;
            tooltip.classList.add('show');
        });

        area.addEventListener('mousemove', (e) => {
            const rect = e.target.closest('.interactive-miami-map').getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            tooltip.style.left = `${x + 15}px`;
            tooltip.style.top = `${y - 10}px`;
        });

        area.addEventListener('mouseleave', () => {
            tooltip.classList.remove('show');
        });

        area.addEventListener('click', (e) => {
            const areaName = e.target.dataset.area;
            console.log(`Selected delivery area: ${areaName}`);
        });
    });
}

// Folium map is now loaded via iframe, no initialization needed

// Helper function to calculate polygon center
function getPolygonCenter(coordinates) {
    let x = 0, y = 0;
    const numPoints = coordinates.length - 1; // Exclude the closing point

    for (let i = 0; i < numPoints; i++) {
        x += coordinates[i][0];
        y += coordinates[i][1];
    }

    return [x / numPoints, y / numPoints];
}

// Function to handle delivery area selection
function selectDeliveryArea(areaName) {
    console.log(`Selected delivery area: ${areaName}`);
    alert(`You selected ${areaName} for delivery!`);
    // You can add more functionality here like updating a form or redirecting
}

// Setup search and filter functionality (placeholder for products page)
function setupSearchAndFilter() {
    console.log('Search and filter setup initialized');
    // This function can be expanded for the products page
}

function setupProductGrid() {
    console.log('Product grid initialized');

    // Handle product card interactions
    document.querySelectorAll('.clean-product-card').forEach(card => {
        const productId = card.dataset.productId;

        // Add hover effects
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
}

function setupQuickView() {
    console.log('Quick view initialized');
}

function setupAuthModals() {
    console.log('Auth modals initialized');
}

function setupToastNotifications() {
    console.log('Toast notifications initialized');
}

function setupFormValidation() {
    console.log('Form validation initialized');
}

function setupSlideshow() {
    // This commit adds the missing initializeSearchAndFilter and initializeProductGrid functions as requested.
console.log('Slideshow initialized');
}

function showForgotPassword(event) {
    if (event) event.preventDefault();
    alert('Forgot password functionality will be implemented soon.');
}

function socialLogin(provider) {
    console.log(`Social login with ${provider}`);
    // Implement social login logic
}

// Product detail page functions
function changeMainImage(direction) {
    // Implementation for changing main product image
    console.log(`Changing main image by ${direction}`);
}

function setMainImage(index) {
    // Implementation for setting specific main image
    console.log(`Setting main image to index ${index}`);
}

function toggleProductDropdown(section) {
    // Implementation for toggling product dropdown sections
    console.log(`Toggling dropdown for ${section}`);
    const dropdown = document.querySelector(`[data-section="${section}"]`);
    if (dropdown) {
        dropdown.classList.toggle('active');
    }
}



// Initialize search and filter functionality
function initializeSearchAndFilter() {
    console.log('Search and filter setup initialized');
    if (typeof initializeColorFilters === 'function') {
        initializeColorFilters();
    }
}

// Initialize product grid functionality
function initializeProductGrid() {
    console.log('Product grid initialized');
}


/* ------------------------------------------------------------------
   Delegated close button for ANY modal that has .modal-close
   ------------------------------------------------------------------ */
document.addEventListener('click', function (e) {
    const closeBtn = e.target.closest('.modal-close');
    if (!closeBtn) return;                 // click wasn’t on a close button

    e.preventDefault();
    e.stopPropagation();

    // If it’s the wishlist modal, call its dedicated closer
    if (closeBtn.closest('#wishlistModal')) {
        closeWishlistModal();
    } else {
        // fallback for login/register/etc.
        hideModals();
    }
});

// Close cart modal when clicking outside
document.addEventListener('click', function(e) {
    const cartModal = document.getElementById('cartModal');
    if (cartModal && e.target === cartModal) {
        closeCartModal();
    }
});

// ─── ADD-ADDRESS HANDLERS ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

  // open modal
  const addBtn = document.getElementById('addAddressButton');
  addBtn?.addEventListener('click', () => showModal('addressModal'));

  // cancel button inside modal
  document.getElementById('cancelAddressBtn')
          ?.addEventListener('click', hideModals);

  // form submission
  const frm = document.getElementById('addressForm');
  frm?.addEventListener('submit', async (e) => {
      e.preventDefault();

      // gather data
      const formData = new FormData(frm);
      const payload  = Object.fromEntries(formData.entries());

      try {
          const res  = await fetch('/api/addresses', {
              method : 'POST',
              headers: { 'Content-Type': 'application/json' },
              body   : JSON.stringify(payload)
          });
          const data = await res.json();

          if (res.ok) {
              appendAddressCard(data.address_html);
              hideModals();
              showToast('Address added!', 'success');
          } else {
              throw new Error(data.message || 'Could not save');
          }
      } catch (err) {
          console.error(err);
          showToast(err.message, 'error');
      }
  });
});

/* helper: inject the returned address snippet */
function appendAddressCard(html) {
    const list = document.querySelector('.saved-addresses-list');
    const placeholder = document.querySelector('.no-addresses-placeholder');
    
    // Hide placeholder if it exists
    if (placeholder) {
        placeholder.style.display = 'none';
    }
    
    // Add the new address card
    if (list) {
        list.insertAdjacentHTML('beforeend', html);
    } else {
        console.error('Could not find .saved-addresses-list element');
    }
}

// Address management functions
function editAddress(addressId) {
    const addressItem = document.querySelector(`[data-address-id="${addressId}"]`);
    const addressDetails = addressItem.querySelector('.address-details');
    const editBtn = addressItem.querySelector('.btn-address-action.edit');
    const deleteBtn = addressItem.querySelector('.btn-address-action.delete');
    const saveBtn = addressItem.querySelector('.btn-address-action.save');
    const cancelBtn = addressItem.querySelector('.btn-address-action.cancel');
    
    // Store original values
    const originalData = {
        address: addressDetails.querySelector('[data-field="address"]').textContent,
        suite: addressDetails.querySelector('[data-field="suite"]')?.textContent.replace('Suite ', '') || '',
        cityStateZip: addressDetails.querySelector('[data-field="city-state-zip"]').textContent,
        country: addressDetails.querySelector('[data-field="country"]').textContent
    };
    
    // Parse city, state, zip
    const cityStateZipMatch = originalData.cityStateZip.match(/^(.+),\s*([A-Z]{2})\s+(.+)$/);
    if (cityStateZipMatch) {
        originalData.city = cityStateZipMatch[1];
        originalData.state = cityStateZipMatch[2];
        originalData.zip = cityStateZipMatch[3];
    }
    
    // Store original data on the element
    addressItem.dataset.originalData = JSON.stringify(originalData);
    
    // Convert to editable form
    addressDetails.innerHTML = `
        <div class="form-group">
            <label>Street Address</label>
            <input type="text" class="form-control" name="address" value="${originalData.address}">
        </div>
        <div class="form-group">
            <label>Suite/Apt (optional)</label>
            <input type="text" class="form-control" name="suite" value="${originalData.suite}">
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>City</label>
                <input type="text" class="form-control" name="city" value="${originalData.city || ''}">
            </div>
            <div class="form-group">
                <label>State</label>
                <input type="text" class="form-control" name="state" value="${originalData.state || ''}" maxlength="2">
            </div>
            <div class="form-group">
                <label>ZIP</label>
                <input type="text" class="form-control" name="zip" value="${originalData.zip || ''}" maxlength="10">
            </div>
        </div>
        <div class="form-group">
            <label>Country</label>
            <select class="form-control" name="country">
                <option value="US" ${originalData.country === 'US' ? 'selected' : ''}>United States</option>
                <option value="CA" ${originalData.country === 'CA' ? 'selected' : ''}>Canada</option>
                <option value="UK" ${originalData.country === 'UK' ? 'selected' : ''}>United Kingdom</option>
            </select>
        </div>
    `;
    
    // Toggle button visibility
    editBtn.style.display = 'none';
    deleteBtn.style.display = 'none';
    saveBtn.style.display = 'inline-block';
    if (cancelBtn) cancelBtn.style.display = 'inline-block';
}

function cancelEdit(addressId) {
    const addressItem = document.querySelector(`[data-address-id="${addressId}"]`);
    const addressDetails = addressItem.querySelector('.address-details');
    const editBtn = addressItem.querySelector('.btn-address-action.edit');
    const deleteBtn = addressItem.querySelector('.btn-address-action.delete');
    const saveBtn = addressItem.querySelector('.btn-address-action.save');
    const cancelBtn = addressItem.querySelector('.btn-address-action.cancel');
    
    // Restore original data
    const originalData = JSON.parse(addressItem.dataset.originalData);
    
    addressDetails.innerHTML = `
        <p class="address-line" data-field="address">${originalData.address}</p>
        ${originalData.suite ? `<p class="address-line" data-field="suite">Suite ${originalData.suite}</p>` : ''}
        <p class="address-line" data-field="city-state-zip">${originalData.cityStateZip}</p>
        <p class="address-line" data-field="country">${originalData.country}</p>
    `;
    
    // Toggle button visibility
    editBtn.style.display = 'inline-block';
    deleteBtn.style.display = 'inline-block';
    saveBtn.style.display = 'none';
    if (cancelBtn) cancelBtn.style.display = 'none';
}

async function saveAddress(addressId) {
    const addressItem = document.querySelector(`[data-address-id="${addressId}"]`);
    const addressDetails = addressItem.querySelector('.address-details');
    
    // Collect form data
    const formData = {
        address: addressDetails.querySelector('[name="address"]').value,
        suite: addressDetails.querySelector('[name="suite"]').value,
        city: addressDetails.querySelector('[name="city"]').value,
        state: addressDetails.querySelector('[name="state"]').value,
        zip: addressDetails.querySelector('[name="zip"]').value,
        country: addressDetails.querySelector('[name="country"]').value
    };
    
    try {
        const response = await fetch(`/api/addresses/${addressId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Update the display
            addressDetails.innerHTML = `
                <p class="address-line" data-field="address">${formData.address}</p>
                ${formData.suite ? `<p class="address-line" data-field="suite">Suite ${formData.suite}</p>` : ''}
                <p class="address-line" data-field="city-state-zip">${formData.city}, ${formData.state} ${formData.zip}</p>
                <p class="address-line" data-field="country">${formData.country}</p>
            `;
            
            // Toggle button visibility
            const editBtn = addressItem.querySelector('.btn-address-action.edit');
            const deleteBtn = addressItem.querySelector('.btn-address-action.delete');
            const saveBtn = addressItem.querySelector('.btn-address-action.save');
            const cancelBtn = addressItem.querySelector('.btn-address-action.cancel');
            
            editBtn.style.display = 'inline-block';
            deleteBtn.style.display = 'inline-block';
            saveBtn.style.display = 'none';
            if (cancelBtn) cancelBtn.style.display = 'none';
            
            showToast('Address updated successfully!', 'success');
        } else {
            showToast(result.message || 'Failed to update address', 'error');
        }
    } catch (error) {
        console.error('Error updating address:', error);
        showToast('Error updating address', 'error');
    }
}

async function deleteAddress(addressId) {
    if (!confirm('Are you sure you want to delete this address?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/addresses/${addressId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Remove the address item from DOM
            const addressItem = document.querySelector(`[data-address-id="${addressId}"]`);
            addressItem.remove();
            
            // Check if there are any addresses left
            const addressesList = document.querySelector('.saved-addresses-list');
            const remainingAddresses = addressesList.querySelectorAll('.saved-address-item');
            
            if (remainingAddresses.length === 0) {
                // Show placeholder
                addressesList.innerHTML = `
                    <div class="no-addresses-placeholder">
                        <div class="placeholder-content">
                            <i class="fas fa-map-marker-alt"></i>
                            <p>No saved addresses yet</p>
                            <small>Add your first address above to get started</small>
                        </div>
                    </div>
                `;
            }
            
            showToast('Address deleted successfully!', 'success');
        } else {
            showToast(result.message || 'Failed to delete address', 'error');
        }
    } catch (error) {
        console.error('Error deleting address:', error);
        showToast('Error deleting address', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════
// CHANGE PASSWORD MODAL FUNCTIONALITY
// ═══════════════════════════════════════════════════════════════════

// Open change password modal
function openChangePasswordModal() {
    const modal = document.getElementById('changePasswordModal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('active');
        modal.style.display = 'flex';
        
        // Clear any previous messages
        clearPasswordMessages();
        
        // Clear form fields
        document.getElementById('changePasswordForm').reset();
        
        // Focus on first input
        setTimeout(() => {
            const firstInput = modal.querySelector('#currentPassword');
            if (firstInput) {
                firstInput.focus();
            }
        }, 100);
    }
}

// Close change password modal
function closePasswordModal() {
    const modal = document.getElementById('changePasswordModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('active');
        modal.style.display = 'none';
        
        // Clear form and messages
        document.getElementById('changePasswordForm').reset();
        clearPasswordMessages();
    }
}

// Clear password messages
function clearPasswordMessages() {
    const errorDiv = document.getElementById('passwordError');
    const successDiv = document.getElementById('passwordSuccess');
    
    if (errorDiv) {
        errorDiv.textContent = '';
        errorDiv.style.display = 'none';
    }
    
    if (successDiv) {
        successDiv.textContent = '';
        successDiv.style.display = 'none';
    }
}

// Show password message
function showPasswordMessage(message, type = 'error') {
    const errorDiv = document.getElementById('passwordError');
    const successDiv = document.getElementById('passwordSuccess');
    
    // Clear both first
    clearPasswordMessages();
    
    if (type === 'success') {
        successDiv.textContent = message;
        successDiv.style.display = 'block';
    } else {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }
}

// Handle change password form submission
document.addEventListener('DOMContentLoaded', function() {
    // Add click handler for change password button
    const changePasswordBtn = document.getElementById('changePassword');
    if (changePasswordBtn) {
        changePasswordBtn.addEventListener('click', openChangePasswordModal);
    }
    
    // Handle form submission
    const changePasswordForm = document.getElementById('changePasswordForm');
    if (changePasswordForm) {
        changePasswordForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            
            // Show loading state
            submitBtn.textContent = 'Updating...';
            submitBtn.disabled = true;
            
            try {
                const response = await fetch('/change_password', {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    },
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showPasswordMessage(result.message, 'success');
                    
                    // Close modal after 2 seconds
                    setTimeout(() => {
                        closePasswordModal();
                        showToast('Password updated successfully!', 'success');
                    }, 2000);
                } else {
                    showPasswordMessage(result.message, 'error');
                }
            } catch (error) {
                console.error('Error changing password:', error);
                showPasswordMessage('An error occurred while updating your password', 'error');
            } finally {
                // Restore button state
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
            }
        });
    }
    
    // Handle modal close button
    const changePasswordModal = document.getElementById('changePasswordModal');
    if (changePasswordModal) {
        const closeBtn = changePasswordModal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', closePasswordModal);
        }
        
        // Close on overlay click
        changePasswordModal.addEventListener('click', function(e) {
            if (e.target === this) {
                closePasswordModal();
            }
        });
        
        // Add password toggle functionality
        const passwordToggles = changePasswordModal.querySelectorAll('.password-toggle');
        passwordToggles.forEach(toggle => {
            toggle.addEventListener('click', function() {
                const inputGroup = this.closest('.input-group');
                const passwordInput = inputGroup.querySelector('.form-control');
                
                if (passwordInput.type === 'password') {
                    passwordInput.type = 'text';
                    this.classList.remove('fa-eye-slash');
                    this.classList.add('fa-eye');
                } else {
                    passwordInput.type = 'password';
                    this.classList.remove('fa-eye');
                    this.classList.add('fa-eye-slash');
                }
            });
            
            // Add keyboard support for accessibility
            toggle.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.click();
                }
            });
        });
    }
});

// ═══════════════════════════════════════════════════════════════════
// CART MODAL FUNCTIONALITY
// ═══════════════════════════════════════════════════════════════════

// Open cart modal
function openCartModal() {
    const modal = document.getElementById('cartModal');
    if (modal) {
        modal.style.display = 'flex';
        loadCartModal();
    }
}

// Close cart modal
function closeCartModal() {
    const modal = document.getElementById('cartModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Load cart data into modal
function loadCartModal() {
    const loading = document.getElementById('cartLoading');
    const items = document.getElementById('cartItems');
    const empty = document.getElementById('emptyCartModal');
    const summary = document.getElementById('cartSummary');
    
    // Show loading state
    loading.style.display = 'block';
    items.style.display = 'none';
    empty.style.display = 'none';
    summary.style.display = 'none';
    
    fetch('/api/cart')
        .then(response => response.json())
        .then(data => {
            loading.style.display = 'none';
            
            if (!data.items || data.items.length === 0) {
                empty.style.display = 'block';
                document.getElementById('cartModalCount').textContent = '0 items in cart';
            } else {
                displayCartItems(data);
                items.style.display = 'block';
                summary.style.display = 'block';
                document.getElementById('cartModalCount').textContent = `${data.count} item${data.count !== 1 ? 's' : ''} in cart`;
            }
        })
        .catch(error => {
            console.error('Error loading cart:', error);
            loading.style.display = 'none';
            empty.style.display = 'block';
        });
}

// Display cart items in modal
function displayCartItems(cartData) {
    const itemsContainer = document.getElementById('cartItems');
    const subtotal = cartData.total;
    const taxRate = 0.0875; // 8.75% Miami-Dade tax
    const taxAmount = subtotal * taxRate;
    const shippingAmount = subtotal > 50 ? 0 : 9.99;
    const total = subtotal + taxAmount + shippingAmount;
    
    itemsContainer.innerHTML = cartData.items.map(item => `
        <div class="cart-item-modal" data-product-id="${item.id}">
            <div class="cart-item-image-modal">
                <img src="${item.image_url || '/static/img/placeholder.svg'}" alt="${item.name}" onerror="this.src='/static/img/placeholder.svg'">
            </div>
            <div class="cart-item-details-modal">
                <h4>${item.name}</h4>
                <div class="cart-item-price-modal">$${item.price.toFixed(2)} each</div>
                <div class="cart-item-quantity-modal">
                    <button class="quantity-btn-modal" onclick="updateCartItemQuantity(${item.id}, ${item.quantity - 1})">-</button>
                    <span class="quantity-display-modal">${item.quantity}</span>
                    <button class="quantity-btn-modal" onclick="updateCartItemQuantity(${item.id}, ${item.quantity + 1})">+</button>
                </div>
            </div>
            <button class="cart-item-remove-modal" onclick="removeCartItem(${item.id})" title="Remove item">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    `).join('');
    
    // Update summary
    document.getElementById('cartSubtotal').textContent = `$${subtotal.toFixed(2)}`;
    document.getElementById('cartTax').textContent = `$${taxAmount.toFixed(2)}`;
    document.getElementById('cartShipping').textContent = subtotal > 50 ? 'FREE' : `$${shippingAmount.toFixed(2)}`;
    document.getElementById('cartTotal').textContent = `$${total.toFixed(2)}`;
}

// Update cart item quantity
function updateCartItemQuantity(productId, newQuantity) {
    if (newQuantity <= 0) {
        removeCartItem(productId);
        return;
    }
    
    fetch('/api/cart/update', {
        method: 'POST',
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
            loadCartModal(); // Reload cart modal
            updateCartCount(); // Update cart count in navbar
        }
    })
    .catch(error => {
        console.error('Error updating cart:', error);
        showToast('Error updating cart', 'error');
    });
}

// Remove item from cart
function removeCartItem(productId) {
    fetch('/api/cart/remove', {
        method: 'POST',
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
            loadCartModal(); // Reload cart modal
            updateCartCount(); // Update cart count in navbar
            showToast('Item removed from cart', 'success');
        }
    })
    .catch(error => {
        console.error('Error removing from cart:', error);
        showToast('Error removing from cart', 'error');
    });
}



// attach Add‑to‑Cart listeners (no inline JS needed)
document.querySelectorAll('.btn-add-cart').forEach(btn => {
    btn.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();

        addToCart(
            parseInt(btn.dataset.productId, 10),
            btn.dataset.productName,
            parseFloat(btn.dataset.productPrice)
        );
    });
});



// Stripe integration is now handled in checkout.html

// ═══════════════════════════════════════════════════════════════════
// ENHANCED FILTER SYSTEM UX IMPROVEMENTS
// ═══════════════════════════════════════════════════════════════════

// Enhanced search with debouncing and better UX
let searchTimeout;
function handleSearch() {
    const searchInput = document.getElementById('productSearch');
    const clearBtn = document.querySelector('.clear-search-btn');
    
    if (!searchInput) return;
    
    const searchValue = searchInput.value.trim();
    
    // Show/hide clear button
    if (clearBtn) {
        clearBtn.style.display = searchValue ? 'block' : 'none';
    }
    
    // Add loading state
    searchInput.style.background = searchValue ? 'linear-gradient(90deg, rgba(168, 85, 247, 0.1) 0%, rgba(168, 85, 247, 0.05) 100%)' : '';
    
    // Debounce search
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        activeFilters.search = searchValue.toLowerCase();
        applyAllFilters();
        
        // Remove loading state
        searchInput.style.background = '';
        
        // Update URL without page reload
        updateURLWithFilters();
        
        // Show search results feedback
        showSearchFeedback(searchValue);
    }, 300);
}

// Clear search with animation
function clearSearch() {
    const searchInput = document.getElementById('productSearch');
    const clearBtn = document.querySelector('.clear-search-btn');
    
    if (searchInput) {
        searchInput.value = '';
        searchInput.style.transform = 'scale(0.98)';
        setTimeout(() => {
            searchInput.style.transform = '';
        }, 150);
    }
    
    if (clearBtn) {
        clearBtn.style.display = 'none';
    }
    
    activeFilters.search = '';
    applyAllFilters();
    updateURLWithFilters();
}

// Enhanced filter products with visual feedback
function filterProducts(category) {
    // Add visual feedback to clicked category
    document.querySelectorAll('.dropdown-toggle').forEach(toggle => {
        toggle.classList.remove('active-category');
    });
    
    // Find and highlight the active category
    const activeToggle = document.querySelector(`[onclick="filterProducts('${category}')"]`);
    if (activeToggle) {
        activeToggle.classList.add('active-category');
        
        // Add pulse effect
        activeToggle.style.transform = 'scale(0.95)';
        setTimeout(() => {
            activeToggle.style.transform = '';
        }, 150);
    }
    
    activeFilters.category = category;
    applyAllFilters();
    
    // Close dropdowns with animation
    closeAllDropdowns();
    
    // Update URL
    updateURLWithFilters();
    
    // Show category feedback
    showCategoryFeedback(category);
}

// Enhanced apply filters with better performance and UX
function applyAllFilters() {
    const products = document.querySelectorAll('.product-card, .clean-product-card');
    let visibleCount = 0;
    const totalProducts = products.length;
    
    // Show loading state for large product sets
    if (totalProducts > 50) {
        showFilterLoading(true);
    }
    
    // Batch DOM updates for better performance
    const updates = [];
    
    products.forEach((product, index) => {
        let isVisible = true;
        
        // Category filter
        if (activeFilters.category !== 'all') {
            const productCategory = product.dataset.category;
            const parentCategory = product.dataset.parentCategory;
            
            if (productCategory !== activeFilters.category && parentCategory !== activeFilters.category) {
                isVisible = false;
            }
        }
        
        // In-stock filter
        if (activeFilters.inStock && product.dataset.inStock === 'false') {
            isVisible = false;
        }
        
        // Price range filter
        const price = parseFloat(product.dataset.price);
        if (price < activeFilters.minPrice || price > activeFilters.maxPrice) {
            isVisible = false;
        }
        
        // Color filter
        if (activeFilters.colors.length > 0) {
            const productColors = product.dataset.colors ? 
                product.dataset.colors.split(',').map(c => c.trim()).filter(c => c) : [];
            
            const hasMatchingColor = activeFilters.colors.some(selectedColor =>
                productColors.some(productColor => {
                    if (productColor === selectedColor) return true;
                    if (productColor.includes('-')) {
                        return productColor.split('-').map(c => c.trim()).includes(selectedColor);
                    }
                    if (selectedColor.includes('-')) {
                        return selectedColor.split('-').map(c => c.trim()).includes(productColor);
                    }
                    return productColor.includes(selectedColor) || selectedColor.includes(productColor);
                })
            );
            
            if (!hasMatchingColor) {
                isVisible = false;
            }
        }
        
        // Rating filter
        if (activeFilters.rating > 0) {
            const rating = parseFloat(product.dataset.rating) || 0;
            if (rating < activeFilters.rating) {
                isVisible = false;
            }
        }
        
        // Brand filter
        if (activeFilters.brand) {
            const productBrand = product.dataset.brand;
            if (productBrand !== activeFilters.brand) {
                isVisible = false;
            }
        }
        
        // Search filter with better matching
        if (activeFilters.search) {
            const titleElement = product.querySelector('.product-title, .clean-product-title');
            const title = titleElement ? titleElement.textContent.toLowerCase() : '';
            const descriptionElement = product.querySelector('.product-description, .clean-product-subtitle');
            const descText = descriptionElement ? descriptionElement.textContent.toLowerCase() : '';
            const brand = product.dataset.brand ? product.dataset.brand.toLowerCase() : '';
            
            const searchTerms = activeFilters.search.split(' ').filter(term => term.length > 0);
            const hasMatch = searchTerms.every(term => 
                title.includes(term) || descText.includes(term) || brand.includes(term)
            );
            
            if (!hasMatch) {
                isVisible = false;
            }
        }
        
        // Store update for batch processing
        updates.push({ product, isVisible, index });
        
        if (isVisible) {
            visibleCount++;
        }
    });
    
    // Apply all updates in batch
    requestAnimationFrame(() => {
        updates.forEach(({ product, isVisible }) => {
            if (isVisible) {
                product.style.display = 'block';
                product.style.opacity = '0';
                product.style.transform = 'translateY(10px)';
                
                // Stagger animations for better UX
                setTimeout(() => {
                    product.style.transition = 'all 0.3s ease';
                    product.style.opacity = '1';
                    product.style.transform = 'translateY(0)';
                }, Math.random() * 100);
            } else {
                product.style.transition = 'all 0.2s ease';
                product.style.opacity = '0';
                product.style.transform = 'translateY(-10px)';
                
                setTimeout(() => {
                    product.style.display = 'none';
                }, 200);
            }
        });
        
        // Update results count with animation
        updateResultsCount(visibleCount, totalProducts);
        
        // Hide loading state
        showFilterLoading(false);
        
        // Update active filter indicators
        updateActiveFilterIndicators();
    });
}

// Show/hide filter loading state
function showFilterLoading(show) {
    let loader = document.getElementById('filterLoader');
    
    if (show && !loader) {
        loader = document.createElement('div');
        loader.id = 'filterLoader';
        loader.innerHTML = `
            <div style="
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: rgba(34, 40, 49, 0.95);
                padding: 1rem 2rem;
                border-radius: 25px;
                color: white;
                z-index: 9999;
                backdrop-filter: blur(10px);
                border: 2px solid rgba(168, 85, 247, 0.3);
            ">
                <i class="fas fa-spinner fa-spin" style="margin-right: 0.5rem;"></i>
                Filtering products...
            </div>
        `;
        document.body.appendChild(loader);
    } else if (!show && loader) {
        loader.style.opacity = '0';
        setTimeout(() => {
            if (loader.parentNode) {
                loader.parentNode.removeChild(loader);
            }
        }, 300);
    }
}

// Update results count with better UX
function updateResultsCount(visibleCount, totalProducts) {
    const resultElement = document.getElementById('resultCount');
    if (!resultElement) return;
    
    // Add counting animation
    resultElement.style.transform = 'scale(0.9)';
    resultElement.style.opacity = '0.7';
    
    setTimeout(() => {
        const text = visibleCount === totalProducts ? 
            `${visibleCount} product${visibleCount !== 1 ? 's' : ''}` :
            `${visibleCount} of ${totalProducts} product${totalProducts !== 1 ? 's' : ''}`;
        
        resultElement.textContent = text;
        resultElement.style.transform = 'scale(1)';
        resultElement.style.opacity = '1';
        resultElement.style.transition = 'all 0.3s ease';
        
        // Add color coding
        if (visibleCount === 0) {
            resultElement.style.color = '#ff4757';
        } else if (visibleCount < totalProducts * 0.3) {
            resultElement.style.color = '#ffa502';
        } else {
            resultElement.style.color = 'hsl(var(--text-color))';
        }
    }, 150);
}

// Show search feedback
function showSearchFeedback(searchTerm) {
    if (!searchTerm) return;
    
    const feedback = document.createElement('div');
    feedback.style.cssText = `
        position: fixed;
        top: 120px;
        right: 20px;
        background: linear-gradient(135deg, rgba(168, 85, 247, 0.9), rgba(236, 72, 153, 0.9));
        color: white;
        padding: 0.75rem 1.5rem;
        border-radius: 25px;
        z-index: 9999;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(168, 85, 247, 0.3);
        transform: translateX(100%);
        transition: all 0.3s ease;
    `;
    feedback.innerHTML = `<i class="fas fa-search" style="margin-right: 0.5rem;"></i>Searching for "${searchTerm}"`;
    
    document.body.appendChild(feedback);
    
    setTimeout(() => {
        feedback.style.transform = 'translateX(0)';
    }, 100);
    
    setTimeout(() => {
        feedback.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.parentNode.removeChild(feedback);
            }
        }, 300);
    }, 2000);
}

// Show category feedback
function showCategoryFeedback(category) {
    const categoryName = category === 'all' ? 'All Products' : 
        category.charAt(0).toUpperCase() + category.slice(1).replace('-', ' ');
    
    const feedback = document.createElement('div');
    feedback.style.cssText = `
        position: fixed;
        top: 120px;
        left: 20px;
        background: linear-gradient(135deg, rgba(34, 40, 49, 0.95), rgba(44, 50, 59, 0.95));
        color: white;
        padding: 0.75rem 1.5rem;
        border-radius: 25px;
        z-index: 9999;
        backdrop-filter: blur(10px);
        border: 2px solid rgba(168, 85, 247, 0.3);
        transform: translateX(-100%);
        transition: all 0.3s ease;
    `;
    feedback.innerHTML = `<i class="fas fa-filter" style="margin-right: 0.5rem;"></i>Filtering: ${categoryName}`;
    
    document.body.appendChild(feedback);
    
    setTimeout(() => {
        feedback.style.transform = 'translateX(0)';
    }, 100);
    
    setTimeout(() => {
        feedback.style.transform = 'translateX(-100%)';
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.parentNode.removeChild(feedback);
            }
        }, 300);
    }, 2000);
}

// Close all dropdowns with animation
function closeAllDropdowns() {
    document.querySelectorAll('.dropdown-menu').forEach(menu => {
        menu.style.opacity = '0';
        menu.style.visibility = 'hidden';
        menu.style.transform = 'translateY(-10px) scale(0.95)';
        menu.classList.remove('show');
    });
}

// Update URL with current filters (for bookmarking/sharing)
function updateURLWithFilters() {
    const url = new URL(window.location);
    
    // Clear existing filter params
    url.searchParams.delete('category');
    url.searchParams.delete('search');
    url.searchParams.delete('inStock');
    url.searchParams.delete('brand');
    url.searchParams.delete('colors');
    url.searchParams.delete('minPrice');
    url.searchParams.delete('maxPrice');
    
    // Add current filters
    if (activeFilters.category !== 'all') {
        url.searchParams.set('category', activeFilters.category);
    }
    if (activeFilters.search) {
        url.searchParams.set('search', activeFilters.search);
    }
    if (activeFilters.inStock) {
        url.searchParams.set('inStock', 'true');
    }
    if (activeFilters.brand) {
        url.searchParams.set('brand', activeFilters.brand);
    }
    if (activeFilters.colors.length > 0) {
        url.searchParams.set('colors', activeFilters.colors.join(','));
    }
    if (activeFilters.minPrice > 0) {
        url.searchParams.set('minPrice', activeFilters.minPrice);
    }
    if (activeFilters.maxPrice < 500) {
        url.searchParams.set('maxPrice', activeFilters.maxPrice);
    }
    
    // Update URL without page reload
    window.history.replaceState({}, '', url);
}

// Load filters from URL on page load
function loadFiltersFromURL() {
    const url = new URL(window.location);
    
    if (url.searchParams.get('category')) {
        activeFilters.category = url.searchParams.get('category');
    }
    if (url.searchParams.get('search')) {
        activeFilters.search = url.searchParams.get('search');
        const searchInput = document.getElementById('productSearch');
        if (searchInput) {
            searchInput.value = activeFilters.search;
        }
    }
    if (url.searchParams.get('inStock') === 'true') {
        activeFilters.inStock = true;
        const inStockFilter = document.getElementById('inStockFilter');
        if (inStockFilter) {
            inStockFilter.checked = true;
        }
    }
    if (url.searchParams.get('brand')) {
        activeFilters.brand = url.searchParams.get('brand');
        const brandFilter = document.getElementById('brandFilter');
        if (brandFilter) {
            brandFilter.value = activeFilters.brand;
        }
    }
    if (url.searchParams.get('colors')) {
        activeFilters.colors = url.searchParams.get('colors').split(',');
    }
    if (url.searchParams.get('minPrice')) {
        activeFilters.minPrice = parseInt(url.searchParams.get('minPrice'));
    }
    if (url.searchParams.get('maxPrice')) {
        activeFilters.maxPrice = parseInt(url.searchParams.get('maxPrice'));
    }
    
    // Apply loaded filters
    applyAllFilters();
}

// Update active filter indicators
function updateActiveFilterIndicators() {
    const clearAllBtn = document.getElementById('clearAllFilters');
    const hasActiveFilters = 
        activeFilters.category !== 'all' ||
        activeFilters.search ||
        activeFilters.inStock ||
        activeFilters.brand ||
        activeFilters.colors.length > 0 ||
        activeFilters.minPrice > 0 ||
        activeFilters.maxPrice < 500;
    
    if (clearAllBtn) {
        if (hasActiveFilters) {
            clearAllBtn.style.display = 'flex';
            clearAllBtn.style.background = 'linear-gradient(135deg, rgba(255, 71, 87, 0.2), rgba(255, 71, 87, 0.3))';
            clearAllBtn.style.borderColor = '#ff4757';
            clearAllBtn.style.color = '#ff4757';
        } else {
            clearAllBtn.style.display = 'none';
        }
    }
    
    // Add visual indicators to active filters
    document.querySelectorAll('.dropdown-toggle').forEach(toggle => {
        toggle.classList.remove('has-active-filter');
    });
    
    if (activeFilters.category !== 'all') {
        const activeToggle = document.querySelector(`[onclick="filterProducts('${activeFilters.category}')"]`);
        if (activeToggle) {
            activeToggle.classList.add('has-active-filter');
        }
    }
}

// Enhanced clear all filters
function clearAllFilters() {
    // Get price range from products
    const products = document.querySelectorAll('.product-card, .clean-product-card');
    let minPrice = 0;
    let maxPrice = 500;
    
    if (products.length > 0) {
        const prices = Array.from(products).map(p => parseFloat(p.dataset.price)).filter(p => !isNaN(p));
        if (prices.length > 0) {
            minPrice = Math.floor(Math.min(...prices));
            maxPrice = Math.ceil(Math.max(...prices));
        }
    }
    
    // Reset all filters with animation
    activeFilters = {
        category: 'all',
        inStock: false,
        minPrice: minPrice,
        maxPrice: maxPrice,
        colors: [],
        rating: 0,
        brand: '',
        search: ''
    };
    
    // Reset UI elements with animations
    const searchInput = document.getElementById('productSearch');
    const inStockFilter = document.getElementById('inStockFilter');
    const brandFilter = document.getElementById('brandFilter');
    const clearBtn = document.querySelector('.clear-search-btn');
    
    if (searchInput) {
        searchInput.value = '';
        searchInput.style.transform = 'scale(0.95)';
        setTimeout(() => { searchInput.style.transform = ''; }, 150);
    }
    
    if (clearBtn) clearBtn.style.display = 'none';
    if (inStockFilter) inStockFilter.checked = false;
    if (brandFilter) brandFilter.value = '';
    
    // Reset color selections
    document.querySelectorAll('.color-grid-dot').forEach(dot => {
        dot.classList.remove('selected');
    });
    
    // Apply filters
    applyAllFilters();
    updateURLWithFilters();
    
    // Show feedback
    const feedback = document.createElement('div');
    feedback.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) scale(0.8);
        background: linear-gradient(135deg, rgba(34, 40, 49, 0.95), rgba(44, 50, 59, 0.95));
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 25px;
        z-index: 9999;
        backdrop-filter: blur(10px);
        border: 2px solid rgba(168, 85, 247, 0.3);
        text-align: center;
        opacity: 0;
        transition: all 0.3s ease;
    `;
    feedback.innerHTML = `
        <i class="fas fa-broom" style="font-size: 2rem; color: hsl(var(--primary-color)); margin-bottom: 0.5rem;"></i>
        <div style="font-weight: 600; margin-bottom: 0.25rem;">Filters Cleared!</div>
        <div style="font-size: 0.9rem; color: hsl(var(--muted-color));">Showing all products</div>
    `;
    
    document.body.appendChild(feedback);
    
    setTimeout(() => {
        feedback.style.opacity = '1';
        feedback.style.transform = 'translate(-50%, -50%) scale(1)';
    }, 100);
    
    setTimeout(() => {
        feedback.style.opacity = '0';
        feedback.style.transform = 'translate(-50%, -50%) scale(0.8)';
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.parentNode.removeChild(feedback);
            }
        }, 300);
    }, 2000);
}

// Initialize enhanced filters on page load
document.addEventListener('DOMContentLoaded', function() {
    // Load filters from URL
    loadFiltersFromURL();
    
    // Initialize color grid if it exists
    initializeColorGrid();
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K to focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.getElementById('productSearch');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
        
        // Escape to clear search
        if (e.key === 'Escape') {
            const searchInput = document.getElementById('productSearch');
            if (searchInput && document.activeElement === searchInput) {
                clearSearch();
                searchInput.blur();
            }
        }
    });
    
    // Add smooth scrolling to results after filtering
    let filterTimeout;
    const originalApplyFilters = applyAllFilters;
    applyAllFilters = function() {
        originalApplyFilters.call(this);
        
        clearTimeout(filterTimeout);
        filterTimeout = setTimeout(() => {
            const firstVisibleProduct = document.querySelector('.product-card:not([style*="display: none"]), .clean-product-card:not([style*="display: none"])');
            if (firstVisibleProduct) {
                firstVisibleProduct.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'nearest',
                    inline: 'nearest'
                });
            }
        }, 500);
    };
});

// Initialize color grid with available colors
function initializeColorGrid() {
    const colorGrid = document.getElementById('colorGrid');
    if (!colorGrid) return;
    
    // Extract unique colors from products
    const products = document.querySelectorAll('.product-card, .clean-product-card');
    const allColors = new Set();
    
    products.forEach(product => {
        const colors = product.dataset.colors;
        if (colors) {
            colors.split(',').forEach(color => {
                const trimmedColor = color.trim();
                if (trimmedColor) {
                    allColors.add(trimmedColor);
                }
            });
        }
    });
    
    // Create color dots
    colorGrid.innerHTML = '';
    
    // Add "All Colors" option
    const allColorsDot = document.createElement('div');
    allColorsDot.className = 'color-grid-dot all-colors selected';
    allColorsDot.style.background = 'linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4, #feca57, #ff9ff3)';
    allColorsDot.title = 'All Colors';
    allColorsDot.onclick = () => toggleColorFilter('all');
    colorGrid.appendChild(allColorsDot);
    
    // Add individual color dots
    Array.from(allColors).sort().forEach(color => {
        const dot = document.createElement('div');
        dot.className = 'color-grid-dot';
        dot.dataset.color = color;
        dot.title = color.charAt(0).toUpperCase() + color.slice(1);
        dot.onclick = () => toggleColorFilter(color);
        
        // Set color based on name
        const colorMap = {
            'black': '#2c2c2c',
            'white': '#f8f9fa',
            'red': '#e74c3c',
            'blue': '#3498db',
            'green': '#2ecc71',
            'yellow': '#f1c40f',
            'purple': '#9b59b6',
            'pink': '#e91e63',
            'orange': '#f39c12',
            'brown': '#8d6e63',
            'gray': '#95a5a6',
            'grey': '#95a5a6',
            'silver': '#bdc3c7',
            'gold': '#f1c40f'
        };
        
        dot.style.background = colorMap[color.toLowerCase()] || `var(--${color}-color, #${color.replace(/[^a-f0-9]/gi, '').padEnd(6, '0')})`;
        
        colorGrid.appendChild(dot);
    });
}

// ═══════════════════════════════════════════════════════════════════
// SIMPLIFIED FILTER FUNCTIONS FOR PROFESSIONAL NAVBAR
// ═══════════════════════════════════════════════════════════════════

// Simple filter functions that work with the professional navbar
function handleInStockFilter() {
    const checkbox = document.getElementById('inStockFilter');
    activeFilters.inStock = checkbox.checked;
    applyAllFilters();
    updateActiveFilterIndicators();
}

function handleBrandFilter() {
    const select = document.getElementById('brandFilter');
    activeFilters.brand = select.value;
    applyAllFilters();
    updateActiveFilterIndicators();
}

function handlePriceSort() {
    const select = document.getElementById('priceSort');
    const sortValue = select.value;
    
    const products = Array.from(document.querySelectorAll('.product-card'));
    const productGrid = document.getElementById('productGrid');
    
    if (sortValue === 'low-high') {
        products.sort((a, b) => parseFloat(a.dataset.price) - parseFloat(b.dataset.price));
    } else if (sortValue === 'high-low') {
        products.sort((a, b) => parseFloat(b.dataset.price) - parseFloat(a.dataset.price));
    } else {
        // Default order - no sorting needed
        return;
    }
    
    // Re-append sorted products
    products.forEach(product => {
        productGrid.appendChild(product);
    });
}

function toggleColorFilter(color) {
    if (color === 'all') {
        activeFilters.colors = [];
        document.querySelectorAll('.color-grid-dot').forEach(dot => {
            dot.classList.remove('selected');
        });
        document.querySelector('.color-grid-dot.all-colors').classList.add('selected');
    } else {
        const index = activeFilters.colors.indexOf(color);
        if (index > -1) {
            activeFilters.colors.splice(index, 1);
        } else {
            activeFilters.colors.push(color);
        }
        
        // Update UI
        document.querySelector('.color-grid-dot.all-colors').classList.remove('selected');
        document.querySelectorAll('.color-grid-dot').forEach(dot => {
            if (dot.dataset.color === color) {
                dot.classList.toggle('selected');
            }
        });
        
        // If no colors selected, select "all"
        if (activeFilters.colors.length === 0) {
            document.querySelector('.color-grid-dot.all-colors').classList.add('selected');
        }
    }
    
    applyAllFilters();
    updateActiveFilterIndicators();
}

