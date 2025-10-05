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
  const backBtn  = $('.sheet-back', sheet);
  const backdrop = $('.sheet-backdrop', sheet);

  const level1   = $('#catLevel1');
  const level2   = $('#catLevel2');
  const applyBtn = $('#applyCategory'); // we'll repurpose this

  // Section headers
  const subHeader      = $('#subHeader');
  const subHeaderName  = $('#subHeaderName');
  const sectionDivider = $('#sectionDivider');

  // ---- id/slug maps (prefer global if present) ----
  const ID_BY_SLUG = (window.categoryMap && typeof window.categoryMap === 'object')
    ? window.categoryMap
    : {
        'bdsm': 1, 'toys': 2, 'kits': 3, 'lubricant': 4, 'lingerie': 5,
        'anal-toys': 58, 'sexual-enhancements': 59,
        'roleplay-kit': 6, 'masks': 7, 'bondage-kit': 9, 'restraints': 10,
        'butt-plug': 11, 'anal-numbing-gel': 22, 'dildos': 33, 'masturbators': 34,
        'cock-pumps': 35, 'penis-extensions': 37, 'anal-beads': 38,
        'collars-nipple-clamps': 40, 'nipple-clamps': 50,
        'douches-and-enemas': 51, 'strap-on-kits': 54,
        'Water Based Lubricant': 55, 'oil based': 56, 'Massage Oil': 57
      };
  const SLUG_BY_ID = Object.fromEntries(Object.entries(ID_BY_SLUG).map(([slug, id]) => [String(id), slug]));

  function setToolbarLabel(txt) {
    const labelEl = $('#mobileCategoryLabel');
    if (labelEl) labelEl.textContent = `Category · ${txt}`;
  }
  function resolveCategoryName(slug) {
    if (!slug || slug === 'all') return 'All Products';
    const main = sheet.querySelector(`.level-1 .row[data-category="${CSS.escape(slug)}"] .label`);
    if (main) return main.textContent.trim();
    for (const p of $$('.level-1 .row', sheet)) {
      try {
        const children = JSON.parse(p.dataset.children || '[]');
        const hit = children.find(ch => ch.slug === slug);
        if (hit?.name) return hit.name;
      } catch {}
    }
    return null;
  }
  function markSelected() {
    $$('.category-list .row', sheet).forEach(r => r.classList.remove('is-selected'));
    const sel = selected.slug;
    $(`.level-1 .row[data-category="${CSS.escape(sel)}"]`, sheet)?.classList.add('is-selected');
    $(`.level-2 .row[data-category="${CSS.escape(sel)}"]`, sheet)?.classList.add('is-selected');
  }
  function scrollCurrentIntoView(listEl) {
    const row = listEl?.querySelector('.row.is-selected') || listEl?.querySelector('.row');
    row?.scrollIntoView?.({ block: 'nearest' });
  }
  function showSubHeader(name) {
    if (subHeaderName) subHeaderName.textContent = name;
    if (sectionDivider) sectionDivider.hidden = false;
    if (subHeader) subHeader.hidden = false;
  }
  function hideSubHeader() {
    if (sectionDivider) sectionDivider.hidden = true;
    if (subHeader) subHeader.hidden = true;
  }

  // ---- seed selected (handles numeric IDs and slugs) ----
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

  // ---- footer button logic (Clear/Close) ----
  function syncFooterButton() {
    if (!applyBtn) return;
    if (selected.slug && selected.slug !== 'all') {
      applyBtn.textContent = 'Clear Filter';
      applyBtn.dataset.action = 'clear';
      applyBtn.disabled = false;
    } else {
      applyBtn.textContent = 'Close';
      applyBtn.dataset.action = 'close';
      applyBtn.disabled = false;
    }
  }

  // ---- open/close sheet ----
  function openSheet(e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    sheet.classList.add('is-open');
    sheet.setAttribute('aria-hidden', 'false');
    document.body.classList.add('sheet-open');

    level2.hidden = true;
    hideSubHeader();
    backBtn.hidden = true;
    $('.sheet-title', sheet).textContent = 'Choose Category';

    requestAnimationFrame(() => panel?.focus?.());
    markSelected();
    scrollCurrentIntoView(level1);
    syncFooterButton();
  }
  function closeSheet(e) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    try { document.activeElement?.blur?.(); } catch {}
    sheet.classList.remove('is-open');
    sheet.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('sheet-open');
  }

  // ---- build subs ----
  function rowHTML(slug, name) {
    return `
      <li>
        <button type="button" class="row" data-category="${slug}" data-category-name="${name}">
          <span class="label">${name}</span><span class="check" aria-hidden="true"></span>
        </button>
      </li>
    `;
  }
  function buildLevel2(parentName, childrenJson, parentSlug) {
    let children = [];
    try { children = typeof childrenJson === 'string' ? JSON.parse(childrenJson) : (childrenJson || []); }
    catch {}
    level2.innerHTML = '';
    level2.insertAdjacentHTML('beforeend', rowHTML(parentSlug, `All ${parentName}`));
    children.forEach(ch => level2.insertAdjacentHTML('beforeend', rowHTML(ch.slug || '', ch.name || '')));
    showSubHeader(parentName);
    level2.hidden  = false;
    backBtn.hidden = false;
    $('.sheet-title', sheet).textContent = parentName;
    markSelected();
    scrollCurrentIntoView(level2);
    // footer stays Clear/Close based on current selection
    syncFooterButton();
  }

  // Keep clicks inside panel; backdrop closes
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

  // Level 1 (parents)
  level1?.addEventListener('click', e => {
    const btn = e.target.closest('.row');
    if (!btn) return;
    e.preventDefault(); e.stopPropagation();

    const cat   = btn.dataset.category;
    const name  = btn.dataset.categoryName || btn.querySelector('.label')?.textContent?.trim() || 'Category';
    const json  = btn.dataset.children || '[]';

    if (cat === 'all') {
      selected = { slug: 'all', label: 'All Products' };
      setToolbarLabel(selected.label);
      syncFooterButton();
      closeSheet(e);
      if (typeof window.filterProducts === 'function') window.filterProducts('all');
      return;
    }
    buildLevel2(name, json, cat);
  });

  // Level 2 (subs) — immediate apply
  level2?.addEventListener('click', e => {
    const btn = e.target.closest('.row');
    if (!btn) return;
    e.preventDefault(); e.stopPropagation();

    const cat  = btn.dataset.category;
    const name = btn.dataset.categoryName || btn.querySelector('.label')?.textContent?.trim() || 'Category';

    selected = { slug: cat, label: name };
    setToolbarLabel(name);
    syncFooterButton();
    closeSheet(e);

    if (typeof window.filterProducts === 'function') window.filterProducts(cat);
  });

  // Back to main
  backBtn?.addEventListener('click', e => {
    e.preventDefault(); e.stopPropagation();
    level2.hidden  = true;
    backBtn.hidden = true;
    hideSubHeader();
    $('.sheet-title', sheet).textContent = 'Choose Category';
    scrollCurrentIntoView(level1);
    syncFooterButton();
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
      // "Close"
      closeSheet(e);
    }
  });

  // Initial toolbar label + footer state
  setToolbarLabel(selected.label || 'All Products');
  syncFooterButton();
})();
