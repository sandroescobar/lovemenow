// static/js/filters.js
(() => {
  'use strict';

  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // CSS.escape polyfill
  if (!window.CSS) window.CSS = {};
  if (typeof window.CSS.escape !== 'function') {
    window.CSS.escape = s => String(s).replace(/[^a-zA-Z0-9_\-]/g, "\\$&");
  }

  const sheet = $('#categorySheet');
  if (!sheet) return;

  const panel    = $('.sheet-panel', sheet);
  const openBtn  = $('#openCategorySheet');
  const closeBtn = $('.sheet-close', sheet);
  const backdrop = $('.sheet-backdrop', sheet);
  const applyBtn = $('#applyCategory');

  // ---- id/slug maps (prefer global if present) ----
  const ID_BY_SLUG = (window.categoryMap && typeof window.categoryMap === 'object')
    ? window.categoryMap
    : {
        'men': 'men', 'women': 'women',
        'bdsm': 1, 'toys': 2, 'kits': 3, 'lubricant': 4, 'lingerie': 5,
        'anal-toys': 58, 'sexual-enhancements': 59
      };
  const SLUG_BY_ID = Object.fromEntries(Object.entries(ID_BY_SLUG).map(([slug, id]) => [String(id), slug]));

  function setToolbarLabel(txt) {
    const labelEl = $('#mobileCategoryLabel');
    if (labelEl) {
      labelEl.textContent = (txt === 'All Products') ? '👆 Click to filter/sort' : txt;
    }
  }

  function resolveCategoryName(slug) {
    if (!slug || slug === 'all') return 'All Products';
    const row = sheet.querySelector(`.row[data-category="${CSS.escape(slug)}"] .label`);
    if (row) return row.textContent.trim();
    return null;
  }

  function markSelected() {
    $$('.category-list .row', sheet).forEach(r => r.classList.remove('is-selected'));
    const sel = selected.slug;
    if (sel) {
      $(`.row[data-category="${CSS.escape(sel)}"]`, sheet)?.classList.add('is-selected');
    }
  }

  function scrollCurrentIntoView() {
    const row = sheet.querySelector('.row.is-selected');
    row?.scrollIntoView?.({ block: 'nearest' });
  }

  // ---- seed selected ----
  const CF = (window.current_filters || {});
  let selected = { slug: 'all', label: 'All Products' };

  (function seedSelected() {
    if (typeof CF.category_name === 'string' && CF.category_name.trim()) {
      selected.label = CF.category_name.trim();
    }
    const catStr = (CF.category === 0 || CF.category) ? String(CF.category).trim() : '';
    let slug = null;
    if (catStr) slug = /^\d+$/.test(catStr) ? (SLUG_BY_ID[catStr] || null) : catStr;
    if (slug) {
      selected.slug = slug;
      if (!CF.category_name) {
        const name = resolveCategoryName(slug);
        if (name) selected.label = name;
      }
    }
  })();

  function syncFooterButton() {
    if (!applyBtn) return;
    applyBtn.disabled = false; // Ensure it's never disabled
    if (selected.slug && selected.slug !== 'all') {
      applyBtn.textContent = 'Clear Filter';
      applyBtn.dataset.action = 'clear';
    } else {
      applyBtn.textContent = 'Close';
      applyBtn.dataset.action = 'close';
    }
  }

  function openSheet(e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    sheet.classList.add('is-open');
    sheet.setAttribute('aria-hidden', 'false');
    document.body.classList.add('sheet-open');

    requestAnimationFrame(() => {
      panel?.focus?.();
      markSelected();
      scrollCurrentIntoView();
      syncFooterButton();
    });
  }

  function closeSheet(e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    sheet.classList.remove('is-open');
    sheet.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('sheet-open');
  }

  // Clicks inside panel
  $('.sheet-panel', sheet)?.addEventListener('click', e => e.stopPropagation());
  openBtn?.addEventListener('click', openSheet);
  closeBtn?.addEventListener('click', closeSheet);
  backdrop?.addEventListener('click', closeSheet);

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && sheet.classList.contains('is-open')) closeSheet(e);
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 768 && sheet.classList.contains('is-open')) closeSheet();
  });

  // Handle category clicks (everything except sort items)
  $('.sheet-content', sheet)?.addEventListener('click', e => {
    const btn = e.target.closest('.row');
    if (!btn || btn.classList.contains('mobile-sort-item')) return;
    
    e.preventDefault(); e.stopPropagation();

    const cat  = btn.dataset.category;
    const name = btn.dataset.categoryName || btn.querySelector('.label')?.textContent?.trim() || 'Category';

    selected = { slug: cat, label: name };
    setToolbarLabel(name);
    syncFooterButton();
    closeSheet(e);

    if (typeof window.filterProducts === 'function') window.filterProducts(cat);
  });

  // Footer button (Clear / Close)
  applyBtn?.addEventListener('click', e => {
    e.preventDefault(); e.stopPropagation();
    const action = applyBtn.dataset.action;
    if (action === 'clear') {
      selected = { slug: 'all', label: 'All Products' };
      setToolbarLabel('All Products');
      syncFooterButton();
      closeSheet(e);
      if (typeof window.filterProducts === 'function') window.filterProducts('all');
    } else {
      closeSheet(e);
    }
  });

  // Initial state
  setToolbarLabel(selected.label || 'All Products');
  syncFooterButton();
})();
