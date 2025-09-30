/**
 * Discount Code Management System
 * Handles cart-wide discount application, validation, and persistence
 */

class DiscountManager {
    constructor() {
        this.currentDiscount = null;
        this.isProcessing = false;
        this.init();
    }

    init() {
        // Load existing discount on page load
        this.loadCurrentDiscount();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Update cart display if discount exists
        this.updateCartDisplay();
    }

    setupEventListeners() {
        // Apply discount button listeners
        document.addEventListener('click', (e) => {
            if (e.target.matches('#applyDiscountBtn, .apply-discount-btn')) {
                e.preventDefault();
                this.handleApplyDiscount(e.target);
            }
            
            if (e.target.matches('#removeDiscountBtn, .remove-discount-btn')) {
                e.preventDefault();
                this.handleRemoveDiscount();
            }
        });

        // Enter key support for discount input
        document.addEventListener('keypress', (e) => {
            if (e.target.matches('#discountCode, .discount-input') && e.key === 'Enter') {
                e.preventDefault();
                const applyBtn = e.target.parentElement.querySelector('.apply-discount-btn, #applyDiscountBtn');
                if (applyBtn) {
                    this.handleApplyDiscount(applyBtn);
                }
            }
        });

        // Listen for cart updates to recalculate discount
        document.addEventListener('cartUpdated', () => {
            this.updateCartDisplay();
        });
    }

    async loadCurrentDiscount() {
        try {
            const response = await fetch('/api/get-cart-discount', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                }
            });

            const data = await response.json();
            
            if (data.success && data.has_discount) {
                this.currentDiscount = data.discount;
                this.updateDiscountDisplay();
                this.updateCartDisplay();
            }
        } catch (error) {
            console.error('Error loading current discount:', error);
        }
    }

    async handleApplyDiscount(button) {
        if (this.isProcessing) return;

        const container = button.closest('.pdp-discount-section, .cart-discount-section, .checkout-discount-section');
        const input = container.querySelector('#discountCode, .discount-input');
        const messageEl = container.querySelector('#discountMessage, .discount-message');
        
        const code = input.value.trim();
        
        if (!code) {
            this.showMessage(messageEl, 'Please enter a discount code', 'error');
            return;
        }

        // Get current cart total
        const cartTotal = await this.getCurrentCartTotal();
        
        if (cartTotal <= 0) {
            this.showMessage(messageEl, 'Your cart is empty', 'error');
            return;
        }

        this.isProcessing = true;
        button.disabled = true;
        button.textContent = 'Applying...';

        try {
            // First validate the discount
            const validateResponse = await fetch('/api/validate-discount', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken(),
                },
                body: JSON.stringify({
                    code: code,
                    cart_total: cartTotal
                })
            });

            const validateData = await validateResponse.json();

            if (!validateData.success) {
                this.showMessage(messageEl, validateData.message, 'error');
                return;
            }

            // If validation successful, apply the discount
            const applyResponse = await fetch('/api/apply-discount', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken(),
                },
                body: JSON.stringify({
                    code: code,
                    cart_total: cartTotal
                })
            });

            const applyData = await applyResponse.json();

            if (applyData.success) {
                this.currentDiscount = {
                    code: code,
                    discount_amount: applyData.discount_amount,
                    new_total: applyData.new_total,
                    description: applyData.description,
                    original_total: cartTotal
                };

                this.showMessage(messageEl, applyData.message, 'success');
                this.updateDiscountDisplay();
                this.updateCartDisplay();
                
                // Clear input
                input.value = '';
                
                // Show success toast
                if (typeof showToast === 'function') {
                    showToast(`Discount "${code}" applied! You save $${applyData.discount_amount}`, 'success');
                }
                
                // Trigger cart update event
                document.dispatchEvent(new CustomEvent('discountApplied', {
                    detail: { discount: this.currentDiscount }
                }));
                
            } else {
                this.showMessage(messageEl, applyData.message, 'error');
            }

        } catch (error) {
            console.error('Error applying discount:', error);
            this.showMessage(messageEl, 'Error applying discount code. Please try again.', 'error');
        } finally {
            this.isProcessing = false;
            button.disabled = false;
            button.textContent = 'Apply';
        }
    }

    async handleRemoveDiscount() {
        if (this.isProcessing || !this.currentDiscount) return;

        this.isProcessing = true;

        try {
            const response = await fetch('/api/remove-discount', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken(),
                }
            });

            const data = await response.json();

            if (data.success) {
                this.currentDiscount = null;
                this.updateDiscountDisplay();
                this.updateCartDisplay();
                
                if (typeof showToast === 'function') {
                    showToast('Discount removed', 'info');
                }
                
                // Trigger cart update event
                document.dispatchEvent(new CustomEvent('discountRemoved'));
            } else {
                console.error('Error removing discount:', data.message);
            }

        } catch (error) {
            console.error('Error removing discount:', error);
        } finally {
            this.isProcessing = false;
        }
    }

    updateDiscountDisplay() {
        const discountSections = document.querySelectorAll('.pdp-discount-section, .cart-discount-section, .checkout-discount-section');
        
        discountSections.forEach(section => {
            const savingsEl = section.querySelector('#discountSavings, .discount-savings');
            const messageEl = section.querySelector('#discountMessage, .discount-message');
            const inputEl = section.querySelector('#discountCode, .discount-input');
            const applyBtn = section.querySelector('#applyDiscountBtn, .apply-discount-btn');
            
            if (this.currentDiscount) {
                // Show savings display
                if (savingsEl) {
                    const amountEl = savingsEl.querySelector('#savingsAmount, .savings-amount');
                    if (amountEl) {
                        amountEl.textContent = `$${this.currentDiscount.discount_amount.toFixed(2)}`;
                    }
                    savingsEl.style.display = 'flex';
                }
                
                // Hide input and apply button
                if (inputEl) inputEl.style.display = 'none';
                if (applyBtn) applyBtn.style.display = 'none';
                
                // Clear any error messages
                if (messageEl) {
                    messageEl.textContent = '';
                    messageEl.className = 'discount-message';
                }
                
            } else {
                // Hide savings display
                if (savingsEl) {
                    savingsEl.style.display = 'none';
                }
                
                // Show input and apply button
                if (inputEl) inputEl.style.display = 'block';
                if (applyBtn) applyBtn.style.display = 'inline-block';
            }
        });
    }

    updateCartDisplay() {
        if (!this.currentDiscount) return;

        // Update cart totals in various places
        const cartTotalElements = document.querySelectorAll('.cart-total, .checkout-total, #cart-total');
        const originalTotalElements = document.querySelectorAll('.original-total');
        const discountAmountElements = document.querySelectorAll('.discount-amount');

        cartTotalElements.forEach(el => {
            if (el) {
                el.textContent = `$${this.currentDiscount.new_total.toFixed(2)}`;
            }
        });

        originalTotalElements.forEach(el => {
            if (el) {
                el.textContent = `$${this.currentDiscount.original_total.toFixed(2)}`;
                el.style.textDecoration = 'line-through';
                el.style.opacity = '0.7';
            }
        });

        discountAmountElements.forEach(el => {
            if (el) {
                el.textContent = `-$${this.currentDiscount.discount_amount.toFixed(2)}`;
                el.style.color = '#10b981';
            }
        });
    }

    async getCurrentCartTotal() {
        // Try to get cart total from various possible sources
        let total = 0;

        // Check if there's a cart total element
        const cartTotalEl = document.querySelector('.cart-total, .checkout-total, #cart-total');
        if (cartTotalEl) {
            const totalText = cartTotalEl.textContent.replace(/[^0-9.]/g, '');
            total = parseFloat(totalText) || 0;
        }

        // If no total found, calculate from cart items
        if (total === 0) {
            const cartItems = document.querySelectorAll('.cart-item');
            cartItems.forEach(item => {
                const priceEl = item.querySelector('.item-price, .product-price');
                const quantityEl = item.querySelector('.quantity-input, .item-quantity');
                
                if (priceEl && quantityEl) {
                    const price = parseFloat(priceEl.textContent.replace(/[^0-9.]/g, '')) || 0;
                    const quantity = parseInt(quantityEl.value || quantityEl.textContent) || 0;
                    total += price * quantity;
                }
            });
        }

        // If still no total, try to get from global cart data
        if (total === 0 && typeof window.cartData !== 'undefined') {
            total = window.cartData.total || 0;
        }

        // If still no total, fetch from server (for product detail pages)
        if (total === 0) {
            try {
                const response = await fetch('/api/cart/');
                const cartData = await response.json();
                if (cartData && cartData.subtotal) {
                    total = cartData.subtotal;
                }
            } catch (error) {
                console.error('Error fetching cart total:', error);
            }
        }

        return total;
    }

    showMessage(messageEl, message, type = 'info') {
        if (!messageEl) return;

        messageEl.textContent = message;
        messageEl.className = `discount-message discount-message-${type}`;
        
        // Auto-hide success messages after 3 seconds
        if (type === 'success') {
            setTimeout(() => {
                messageEl.textContent = '';
                messageEl.className = 'discount-message';
            }, 3000);
        }
    }

    getCSRFToken() {
        const token = document.querySelector('meta[name="csrf-token"]');
        return token ? token.getAttribute('content') : '';
    }

    // Public method to get current discount info
    getCurrentDiscount() {
        return this.currentDiscount;
    }

    // Public method to check if discount is applied
    hasDiscount() {
        return this.currentDiscount !== null;
    }

    // Public method to finalize discount on checkout
    async finalizeDiscount(orderId) {
        if (!this.currentDiscount || !orderId) return;

        try {
            const response = await fetch('/api/finalize-discount', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken(),
                },
                body: JSON.stringify({
                    order_id: orderId
                })
            });

            const data = await response.json();
            
            if (data.success) {
                console.log('Discount finalized successfully');
                this.currentDiscount = null;
            }
            
        } catch (error) {
            console.error('Error finalizing discount:', error);
        }
    }
}

// Initialize discount manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.discountManager = new DiscountManager();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DiscountManager;
}