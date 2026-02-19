/* ============================================================
   Filter Bar v2 – JS Controller
   ============================================================ */
(function() {
  'use strict';

  // ── Helpers ──
  function getParams() { return new URLSearchParams(window.location.search); }
  function navigate(params) {
    params.delete('page'); // reset to page 1
    window.location.search = params.toString();
  }
  function param(key) { return getParams().get(key) || ''; }

  // ── Search ──
  const searchInput = document.getElementById('fb2Search');
  const clearSearchBtn = document.getElementById('fb2ClearSearch');
  let searchTimer = null;

  function syncClearBtn() {
    if (clearSearchBtn) clearSearchBtn.style.display = searchInput && searchInput.value.trim() ? 'block' : 'none';
  }
  if (searchInput) {
    syncClearBtn();
    searchInput.addEventListener('input', function() {
      syncClearBtn();
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function() {
        var p = getParams();
        var v = searchInput.value.trim();
        if (v) p.set('search', v); else p.delete('search');
        navigate(p);
      }, 600);
    });
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        clearTimeout(searchTimer);
        var p = getParams();
        var v = searchInput.value.trim();
        if (v) p.set('search', v); else p.delete('search');
        navigate(p);
      }
    });
  }
  if (clearSearchBtn) {
    clearSearchBtn.addEventListener('click', function() {
      if (searchInput) searchInput.value = '';
      var p = getParams();
      p.delete('search');
      navigate(p);
    });
  }

  // ── Category Pills ──
  document.querySelectorAll('.fb2-cat-pill').forEach(function(pill) {
    pill.addEventListener('click', function(e) {
      e.preventDefault();
      var cat = this.dataset.category;
      var p = getParams();
      if (!cat || cat === 'all') {
        p.delete('category');
      } else {
        p.set('category', cat);
      }
      navigate(p);
    });
  });

  // ── More Dropdown ──
  var moreWrap = document.querySelector('.fb2-more-wrap');
  var moreTrigger = moreWrap ? moreWrap.querySelector('.fb2-pill') : null;
  if (moreTrigger) {
    moreTrigger.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      moreWrap.classList.toggle('open');
      // Close others if open
      var sw = document.querySelector('.fb2-sort-wrap');
      if (sw) sw.classList.remove('open');
      var pw = document.querySelector('.fb2-price-wrap');
      if (pw) pw.classList.remove('open');
    });
  }
  document.querySelectorAll('.fb2-more-dropdown .fb2-dd-item').forEach(function(item) {
    item.addEventListener('click', function(e) {
      e.preventDefault();
      var cat = this.dataset.category;
      if (!cat) return;
      var p = getParams();
      p.set('category', cat);
      navigate(p);
    });
  });

  // ── Sort Dropdown ──
  var sortWrap = document.querySelector('.fb2-sort-wrap');
  var sortTrigger = sortWrap ? sortWrap.querySelector('.fb2-pill') : null;
  if (sortTrigger) {
    sortTrigger.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      sortWrap.classList.toggle('open');
      if (moreWrap) moreWrap.classList.remove('open');
      var pw = document.querySelector('.fb2-price-wrap');
      if (pw) pw.classList.remove('open');
    });
  }
  document.querySelectorAll('.fb2-sort-dropdown .fb2-dd-item').forEach(function(item) {
    item.addEventListener('click', function(e) {
      e.preventDefault();
      var sort = this.dataset.sort;
      var p = getParams();
      if (sort) p.set('sort', sort); else p.delete('sort');
      navigate(p);
    });
  });

  // ── Best Sellers ──
  var bestBtn = document.getElementById('fb2BestSellers');
  if (bestBtn) {
    bestBtn.addEventListener('click', function(e) {
      e.preventDefault();
      var p = getParams();
      if (p.get('sort') === 'bestseller') {
        p.delete('sort');
      } else {
        p.set('sort', 'bestseller');
      }
      navigate(p);
    });
  }

  // ── Price Dropdown ──
  var priceWrap = document.querySelector('.fb2-price-wrap');
  var priceTrigger = document.getElementById('fb2PriceBtn');
  if (priceTrigger) {
    priceTrigger.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      priceWrap.classList.toggle('open');
      if (moreWrap) moreWrap.classList.remove('open');
      if (sortWrap) sortWrap.classList.remove('open');
    });
  }
  document.querySelectorAll('.fb2-price-dropdown .fb2-dd-item').forEach(function(item) {
    item.addEventListener('click', function(e) {
      e.preventDefault();
      var min = this.dataset.min;
      var max = this.dataset.max;
      var p = getParams();
      var curMin = p.get('min_price') || '';
      var curMax = p.get('max_price') || '';
      // Toggle off if same
      if (curMin === min && curMax === max) {
        p.delete('min_price');
        p.delete('max_price');
      } else {
        if (min) p.set('min_price', min); else p.delete('min_price');
        if (max) p.set('max_price', max); else p.delete('max_price');
      }
      navigate(p);
    });
  });

  // ── In Stock Toggle ──
  var stockPill = document.getElementById('fb2InStock');
  if (stockPill) {
    stockPill.addEventListener('click', function(e) {
      e.preventDefault();
      var p = getParams();
      if (p.get('in_stock') === 'true') {
        p.delete('in_stock');
      } else {
        p.set('in_stock', 'true');
      }
      navigate(p);
    });
  }

  // ── Active state sync on load ──
  (function syncActiveStates() {
    var currentCat = param('category') || 'all';
    var currentSort = param('sort');
    var currentMinPrice = param('min_price');
    var currentMaxPrice = param('max_price');
    var currentInStock = param('in_stock');

    // Category pills
    document.querySelectorAll('.fb2-cat-pill').forEach(function(pill) {
      var cat = pill.dataset.category || 'all';
      pill.classList.toggle('active', cat === currentCat);
    });
    // More dropdown items
    document.querySelectorAll('.fb2-more-dropdown .fb2-dd-item').forEach(function(item) {
      item.classList.toggle('active', item.dataset.category === currentCat);
    });
    // If current category is in More dropdown, highlight "More" pill
    if (moreWrap) {
      var inMore = moreWrap.querySelector('.fb2-dd-item[data-category="' + currentCat + '"]');
      var morePill = moreWrap.querySelector('.fb2-pill');
      if (morePill) morePill.classList.toggle('active', !!inMore);
    }

    // Sort
    document.querySelectorAll('.fb2-sort-dropdown .fb2-dd-item').forEach(function(item) {
      item.classList.toggle('active', item.dataset.sort === currentSort);
    });
    // Sort pill label
    if (currentSort && currentSort !== 'bestseller') {
      var activeSort = document.querySelector('.fb2-sort-dropdown .fb2-dd-item[data-sort="' + currentSort + '"]');
      var sortLabel = document.getElementById('fb2SortLabel');
      if (activeSort && sortLabel) sortLabel.textContent = activeSort.textContent.trim();
    }

    // Best sellers
    if (bestBtn) bestBtn.classList.toggle('active', currentSort === 'bestseller');

    // Price dropdown
    document.querySelectorAll('.fb2-price-dropdown .fb2-dd-item').forEach(function(item) {
      var min = item.dataset.min;
      var max = item.dataset.max;
      item.classList.toggle('active', currentMinPrice === min && currentMaxPrice === max);
    });
    // Update price label if active
    if (currentMinPrice || currentMaxPrice) {
      var priceLabel = document.getElementById('fb2PriceLabel');
      if (priceLabel) {
        if (!currentMinPrice && currentMaxPrice) priceLabel.textContent = '<$' + currentMaxPrice;
        else if (currentMinPrice && currentMaxPrice) priceLabel.textContent = '$' + currentMinPrice + '–$' + currentMaxPrice;
        else if (currentMinPrice && !currentMaxPrice) priceLabel.textContent = '$' + currentMinPrice + '+';
      }
      if (priceTrigger) priceTrigger.classList.add('active');
    }

    // In stock
    if (stockPill) stockPill.classList.toggle('active', currentInStock === 'true');
  })();

  // ── Active filter chips ──
  (function buildChips() {
    var container = document.getElementById('fb2ActiveFilters');
    if (!container) return;
    var chips = [];
    var p = getParams();

    if (p.get('category') && p.get('category') !== 'all') {
      var catName = p.get('category');
      // Try to find display name
      var catPill = document.querySelector('.fb2-cat-pill[data-category="' + catName + '"]');
      var displayName = catPill ? catPill.dataset.label || catPill.textContent.trim() : catName;
      if (!catPill) {
        var ddItem = document.querySelector('.fb2-dd-item[data-category="' + catName + '"]');
        if (ddItem) displayName = ddItem.textContent.trim();
      }
      chips.push({ label: displayName, remove: 'category' });
    }
    if (p.get('search')) {
      chips.push({ label: 'Search: "' + p.get('search') + '"', remove: 'search' });
    }
    if (p.get('sort')) {
      var sortNames = { 'name': 'A-Z', 'low-high': 'Price ↑', 'high-low': 'Price ↓', 'newest': 'Newest', 'bestseller': 'Best Sellers' };
      chips.push({ label: sortNames[p.get('sort')] || p.get('sort'), remove: 'sort' });
    }
    if (p.get('min_price') || p.get('max_price')) {
      var label = '';
      var min = p.get('min_price'), max = p.get('max_price');
      if (!min && max) label = '<$' + max;
      else if (min && max) label = '$' + min + '–$' + max;
      else if (min && !max) label = '$' + min + '+';
      chips.push({ label: label, remove: 'price' });
    }
    if (p.get('in_stock') === 'true') {
      chips.push({ label: 'In Stock', remove: 'in_stock' });
    }

    if (chips.length === 0) return;

    chips.forEach(function(c) {
      var el = document.createElement('span');
      el.className = 'fb2-chip';
      el.innerHTML = c.label + ' <i class="fas fa-times fb2-chip-x" data-remove="' + c.remove + '"></i>';
      container.appendChild(el);
    });

    // Clear all
    if (chips.length > 1) {
      var clearAll = document.createElement('span');
      clearAll.className = 'fb2-chip';
      clearAll.style.cursor = 'pointer';
      clearAll.innerHTML = 'Clear All <i class="fas fa-times fb2-chip-x" data-remove="all"></i>';
      container.appendChild(clearAll);
    }

    container.addEventListener('click', function(e) {
      var x = e.target.closest('[data-remove]');
      if (!x) return;
      var key = x.dataset.remove;
      var pp = getParams();
      if (key === 'all') {
        window.location.href = window.location.pathname;
        return;
      }
      if (key === 'price') {
        pp.delete('min_price');
        pp.delete('max_price');
      } else {
        pp.delete(key);
      }
      navigate(pp);
    });
  })();

  // ── Close dropdowns on outside click ──
  document.addEventListener('click', function(e) {
    if (moreWrap && !moreWrap.contains(e.target)) moreWrap.classList.remove('open');
    if (sortWrap && !sortWrap.contains(e.target)) sortWrap.classList.remove('open');
    if (priceWrap && !priceWrap.contains(e.target)) priceWrap.classList.remove('open');
  });

  // ── Mobile toolbar open sheet ──
  var mobileFilterBtn = document.getElementById('fb2MobileFilter');
  if (mobileFilterBtn) {
    mobileFilterBtn.addEventListener('click', function(e) {
      e.preventDefault();
      // Trigger existing sheet
      var openBtn = document.getElementById('openCategorySheet');
      if (openBtn) openBtn.click();
    });
  }

  // ── Expose filterProducts for mobile sheet compatibility ──
  window.filterProducts = function(slug) {
    var p = getParams();
    if (!slug || slug === 'all') {
      p.delete('category');
    } else {
      p.set('category', slug);
    }
    navigate(p);
  };
  window.clearCategoryFilter = function() {
    var p = getParams();
    p.delete('category');
    navigate(p);
  };
  window.clearAllFilters = function() {
    window.location.href = window.location.pathname;
  };

  // ── Search handlers for backward compat ──
  window.handleSearch = function() {
    // handled by input event above
  };
  window.clearSearch = function() {
    if (clearSearchBtn) clearSearchBtn.click();
  };
})();
