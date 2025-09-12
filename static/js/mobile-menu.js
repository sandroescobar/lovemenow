/**
 * Mobile Menu Functionality for LoveMeNow
 * Handles mobile navigation toggle and interactions
 */

class MobileMenu {
    constructor() {
        this.isOpen = false;
        this.init();
    }

    init() {
        this.createMobileNavOverlay();
        this.bindEvents();
        this.handleResize();
    }

    createMobileNavOverlay() {
        // Check if overlay already exists
        if (document.getElementById('mobile-nav-overlay')) {
            return;
        }

        const overlay = document.createElement('div');
        overlay.id = 'mobile-nav-overlay';
        overlay.className = 'mobile-nav-overlay';
        
        // Get navigation links from desktop nav
        const desktopNavLinks = document.querySelectorAll('.nav-links .nav-link');
        const navButtons = document.querySelector('.nav-buttons');
        
        let mobileNavHTML = `
            <div class="mobile-nav-content">
                <div class="mobile-nav-header">
                    <h3>Menu</h3>
                    <button class="mobile-nav-close" onclick="mobileMenu.close()">&times;</button>
                </div>
                <ul class="mobile-nav-links">
        `;
        
        // Add navigation links
        desktopNavLinks.forEach(link => {
            const href = link.getAttribute('href');
            const text = link.textContent.trim();
            const isActive = link.classList.contains('active') ? 'active' : '';
            mobileNavHTML += `<li><a class="nav-link ${isActive}" href="${href}">${text}</a></li>`;
        });
        
        mobileNavHTML += `
                </ul>
                <div class="mobile-nav-actions">
        `;
        
        // Add action buttons
        if (navButtons) {
            const buttons = navButtons.querySelectorAll('.btn, .nav-icon-btn');
            buttons.forEach(button => {
                if (button.classList.contains('nav-icon-btn')) {
                    // Handle icon buttons (cart, wishlist)
                    const icon = button.querySelector('i');
                    const badge = button.querySelector('.icon-badge');
                    const title = button.getAttribute('title') || '';
                    const onclick = button.getAttribute('onclick') || '';
                    
                    let badgeHTML = '';
                    if (badge && badge.style.display !== 'none') {
                        badgeHTML = `<span class="icon-badge">${badge.textContent}</span>`;
                    }
                    
                    mobileNavHTML += `
                        <button class="btn btn-outline" onclick="${onclick}; mobileMenu.close();" title="${title}">
                            ${icon ? icon.outerHTML : ''} ${title} ${badgeHTML}
                        </button>
                    `;
                } else if (button.classList.contains('btn')) {
                    // Handle regular buttons (Sign Up, Account)
                    const onclick = button.getAttribute('onclick') || '';
                    const text = button.textContent.trim();
                    
                    mobileNavHTML += `
                        <button class="btn btn-primary" onclick="${onclick}; mobileMenu.close();">
                            ${text}
                        </button>
                    `;
                }
            });
        }
        
        mobileNavHTML += `
                </div>
            </div>
        `;
        
        overlay.innerHTML = mobileNavHTML;
        document.body.appendChild(overlay);
        
        // Add click handler to close menu when clicking overlay
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.close();
            }
        });
    }

    bindEvents() {
        // Mobile menu toggle button
        const toggleButton = document.querySelector('.mobile-menu-toggle');
        if (toggleButton) {
            toggleButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggle();
            });
        }

        // Close menu on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });

        // Handle window resize
        window.addEventListener('resize', () => {
            this.handleResize();
        });

        // Close menu when clicking on mobile nav links
        document.addEventListener('click', (e) => {
            if (e.target.matches('.mobile-nav-links .nav-link')) {
                // Small delay to allow navigation to start
                setTimeout(() => this.close(), 100);
            }
        });
    }

    handleResize() {
        // Close mobile menu if window becomes wide enough for desktop nav
        if (window.innerWidth > 768 && this.isOpen) {
            this.close();
        }
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    open() {
        const overlay = document.getElementById('mobile-nav-overlay');
        const toggleButton = document.querySelector('.mobile-menu-toggle');
        
        if (overlay && toggleButton) {
            this.isOpen = true;
            
            // Add active classes
            overlay.classList.add('active');
            toggleButton.classList.add('active');
            
            // Prevent body scrolling
            document.body.style.overflow = 'hidden';
            
            // Focus management for accessibility
            const firstLink = overlay.querySelector('.mobile-nav-links .nav-link');
            if (firstLink) {
                setTimeout(() => firstLink.focus(), 100);
            }
            
            // Update cart count in mobile menu
            this.updateMobileCartCount();
        }
    }

    close() {
        const overlay = document.getElementById('mobile-nav-overlay');
        const toggleButton = document.querySelector('.mobile-menu-toggle');
        
        if (overlay && toggleButton) {
            this.isOpen = false;
            
            // Remove active classes
            overlay.classList.remove('active');
            toggleButton.classList.remove('active');
            
            // Restore body scrolling
            document.body.style.overflow = '';
            
            // Return focus to toggle button for accessibility
            toggleButton.focus();
        }
    }

    updateMobileCartCount() {
        // Update cart count in mobile menu from localStorage
        try {
            const storedCount = localStorage.getItem('cartCount');
            const count = parseInt(storedCount, 10) || 0;
            
            const mobileCartBadges = document.querySelectorAll('.mobile-nav-actions .icon-badge');
            mobileCartBadges.forEach(badge => {
                if (count > 0) {
                    badge.textContent = count;
                    badge.style.display = 'inline';
                } else {
                    badge.style.display = 'none';
                }
            });
        } catch (e) {
            console.warn('Could not update mobile cart count:', e);
        }
    }

    // Public method to update cart count from external scripts
    updateCartCount(count) {
        this.updateMobileCartCount();
    }
}

// Initialize mobile menu when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if we're on a mobile-capable device
    if (window.innerWidth <= 768 || 'ontouchstart' in window) {
        window.mobileMenu = new MobileMenu();
        
        // Make it globally accessible for other scripts
        window.updateMobileCartCount = function(count) {
            if (window.mobileMenu) {
                window.mobileMenu.updateCartCount(count);
            }
        };
        
        // Mobile-specific wishlist modal close functionality
        initializeMobileWishlistModal();
    }
});

// Mobile-specific wishlist modal functionality
function initializeMobileWishlistModal() {
    // Only run on mobile devices
    if (window.innerWidth > 768) return;
    
    // Close wishlist modal function for mobile
    window.closeWishlistModal = function() {
        const modal = document.getElementById('wishlistModal');
        if (modal) {
            modal.classList.remove('active');
            modal.style.display = 'none';
        }
    };
    
    // Set up event listeners for wishlist modal close
    const wishlistModal = document.getElementById('wishlistModal');
    if (wishlistModal) {
        // Close button
        const closeButton = wishlistModal.querySelector('.modal-close');
        if (closeButton) {
            closeButton.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                window.closeWishlistModal();
            });
        }
        
        // Click outside to close
        wishlistModal.addEventListener('click', function(e) {
            if (e.target === wishlistModal) {
                window.closeWishlistModal();
            }
        });
        
        // ESC key to close
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && wishlistModal.style.display !== 'none') {
                window.closeWishlistModal();
            }
        });
    }
}

// Handle dynamic cart count updates
document.addEventListener('cartUpdated', function(e) {
    if (window.mobileMenu) {
        window.mobileMenu.updateCartCount(e.detail.count);
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MobileMenu;
}