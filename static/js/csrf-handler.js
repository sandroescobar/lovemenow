/**
 * CSRF Protection Handler
 * Automatically handles CSRF tokens for all AJAX requests
 * Works transparently with existing code - no changes needed to existing JavaScript
 */

(function() {
    'use strict';
    
    // Get CSRF token from meta tag or generate one
    function getCSRFToken() {
        // First try to get from meta tag
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken) {
            return metaToken.getAttribute('content');
        }
        
        // If not available, try to get from a hidden input (fallback)
        const hiddenInput = document.querySelector('input[name="csrf_token"]');
        if (hiddenInput) {
            return hiddenInput.value;
        }
        
        // If still not available, make a synchronous request to get one
        // This is a fallback and should rarely be needed
        try {
            const xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/csrf-token', false); // Synchronous request
            xhr.send();
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                return response.csrf_token;
            }
        } catch (e) {
            console.warn('Failed to get CSRF token:', e);
        }
        
        return null;
    }
    
    // Store the current token
    let currentCSRFToken = getCSRFToken();
    
    // Function to refresh CSRF token
    function refreshCSRFToken() {
        fetch('/api/csrf-token')
            .then(response => response.json())
            .then(data => {
                currentCSRFToken = data.csrf_token;
                // Update meta tag if it exists
                const metaToken = document.querySelector('meta[name="csrf-token"]');
                if (metaToken) {
                    metaToken.setAttribute('content', currentCSRFToken);
                }
            })
            .catch(error => {
                console.warn('Failed to refresh CSRF token:', error);
            });
    }
    
    // Override XMLHttpRequest to automatically add CSRF tokens
    const originalXHROpen = XMLHttpRequest.prototype.open;
    const originalXHRSend = XMLHttpRequest.prototype.send;
    
    XMLHttpRequest.prototype.open = function(method, url, async, user, password) {
        this._method = method;
        this._url = url;
        return originalXHROpen.apply(this, arguments);
    };
    
    XMLHttpRequest.prototype.send = function(data) {
        // Add CSRF token for POST, PUT, DELETE, PATCH requests
        if (this._method && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(this._method.toUpperCase())) {
            // Skip for webhook URLs or external URLs
            if (!this._url.includes('/webhooks/') && !this._url.startsWith('http')) {
                // Add CSRF token to headers
                if (currentCSRFToken) {
                    this.setRequestHeader('X-CSRFToken', currentCSRFToken);
                }
                
                // If sending JSON data, add token to the data as well
                if (data && typeof data === 'string') {
                    try {
                        const jsonData = JSON.parse(data);
                        if (typeof jsonData === 'object' && jsonData !== null) {
                            jsonData.csrf_token = currentCSRFToken;
                            data = JSON.stringify(jsonData);
                        }
                    } catch (e) {
                        // Not JSON data, that's fine
                    }
                }
                
                // If sending FormData, add token to it
                if (data instanceof FormData && currentCSRFToken) {
                    data.append('csrf_token', currentCSRFToken);
                }
            }
        }
        
        return originalXHRSend.call(this, data);
    };
    
    // Override fetch to automatically add CSRF tokens
    const originalFetch = window.fetch;
    window.fetch = function(url, options = {}) {
        // Add CSRF token for POST, PUT, DELETE, PATCH requests
        if (options.method && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method.toUpperCase())) {
            // Skip for webhook URLs or external URLs
            if (!url.includes('/webhooks/') && !url.startsWith('http')) {
                // Add CSRF token to headers
                options.headers = options.headers || {};
                if (currentCSRFToken) {
                    options.headers['X-CSRFToken'] = currentCSRFToken;
                }
                
                // If sending JSON data, add token to the data
                if (options.body && typeof options.body === 'string') {
                    try {
                        const jsonData = JSON.parse(options.body);
                        if (typeof jsonData === 'object' && jsonData !== null) {
                            jsonData.csrf_token = currentCSRFToken;
                            options.body = JSON.stringify(jsonData);
                        }
                    } catch (e) {
                        // Not JSON data, that's fine
                    }
                }
                
                // If sending FormData, add token to it
                if (options.body instanceof FormData && currentCSRFToken) {
                    options.body.append('csrf_token', currentCSRFToken);
                }
            }
        }
        
        return originalFetch(url, options).then(response => {
            // If we get a CSRF error, try to refresh the token and retry once
            if (response.status === 400) {
                return response.clone().json().then(data => {
                    if (data.csrf_error) {
                        refreshCSRFToken();
                        
                        // Retry the request once with the new token
                        if (currentCSRFToken && options.headers) {
                            options.headers['X-CSRFToken'] = currentCSRFToken;
                            
                            // Update JSON body if needed
                            if (options.body && typeof options.body === 'string') {
                                try {
                                    const jsonData = JSON.parse(options.body);
                                    if (typeof jsonData === 'object' && jsonData !== null) {
                                        jsonData.csrf_token = currentCSRFToken;
                                        options.body = JSON.stringify(jsonData);
                                    }
                                } catch (e) {
                                    // Not JSON data
                                }
                            }
                            
                            return originalFetch(url, options);
                        }
                    }
                    return response;
                }).catch(() => response);
            }
            return response;
        });
    };
    
    // Add CSRF token to all forms automatically
    function addCSRFToForms() {
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            // Skip if form already has a CSRF token
            if (form.querySelector('input[name="csrf_token"]')) {
                return;
            }
            
            // Skip for GET forms
            const method = (form.method || 'GET').toUpperCase();
            if (method === 'GET') {
                return;
            }
            
            // Skip for webhook forms or external forms
            const action = form.action || '';
            if (action.includes('/webhooks/') || action.startsWith('http')) {
                return;
            }
            
            // Add CSRF token as hidden input
            if (currentCSRFToken) {
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrf_token';
                csrfInput.value = currentCSRFToken;
                form.appendChild(csrfInput);
            }
        });
    }
    
    // Add CSRF tokens to forms when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addCSRFToForms);
    } else {
        addCSRFToForms();
    }
    
    // Also add CSRF tokens to dynamically created forms
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) { // Element node
                    if (node.tagName === 'FORM') {
                        // A form was added
                        const method = (node.method || 'GET').toUpperCase();
                        const action = node.action || '';
                        
                        if (method !== 'GET' && !action.includes('/webhooks/') && !action.startsWith('http')) {
                            if (!node.querySelector('input[name="csrf_token"]') && currentCSRFToken) {
                                const csrfInput = document.createElement('input');
                                csrfInput.type = 'hidden';
                                csrfInput.name = 'csrf_token';
                                csrfInput.value = currentCSRFToken;
                                node.appendChild(csrfInput);
                            }
                        }
                    } else if (node.querySelectorAll) {
                        // Check for forms within the added node
                        const forms = node.querySelectorAll('form');
                        forms.forEach(form => {
                            const method = (form.method || 'GET').toUpperCase();
                            const action = form.action || '';
                            
                            if (method !== 'GET' && !action.includes('/webhooks/') && !action.startsWith('http')) {
                                if (!form.querySelector('input[name="csrf_token"]') && currentCSRFToken) {
                                    const csrfInput = document.createElement('input');
                                    csrfInput.type = 'hidden';
                                    csrfInput.name = 'csrf_token';
                                    csrfInput.value = currentCSRFToken;
                                    form.appendChild(csrfInput);
                                }
                            }
                        });
                    }
                }
            });
        });
    });
    
    // Only observe if document.body exists
    if (document.body) {
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    } else {
        // Wait for DOM to be ready
        document.addEventListener('DOMContentLoaded', function() {
            if (document.body) {
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            }
        });
    }
    
    // Refresh CSRF token periodically (every 30 minutes)
    setInterval(refreshCSRFToken, 30 * 60 * 1000);
    
    // Expose function to manually refresh token if needed
    window.refreshCSRFToken = refreshCSRFToken;
    
})();