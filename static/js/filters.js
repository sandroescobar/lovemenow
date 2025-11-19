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
  const mainHeader     = $('#mainHeader');
  const subHeader      = $('#subHeader');
  const subHeaderName  = $('#subHeaderName');
  const sectionDivider = $('#sectionDivider');

  // ---- id/slug maps (prefer global if present) ----
  const ID_BY_SLUG = (window.categoryMap && typeof window.categoryMap === 'object')
    ? window.categoryMap
    : {
        // Gender categories (these use slug directly, not numeric IDs)
        'men': 'men', 'women': 'women',
        // Main categories
        'bdsm': 1, 'toys': 2, 'kits': 3, 'lubricant': 4, 'lingerie': 5,
        'anal-toys': 58, 'sexual-enhancements': 59,
        // Subcategories
        'roleplay-kit': 6, 'masks': 7, 'bondage-kit': 9, 'restraints': 10,
        'butt-plug': 11, 'anal-numbing-gel': 22, 'dildos': 33, 'masturbators': 34,
        'cock-pumps': 35, 'vibrators': 36, 'penis-extensions': 37, 'anal-beads': 38,
        'wands': 39, 'collars-nipple-clamps': 40, 'nipple-clamps': 50,
        'douches-and-enemas': 51, 'strap-on-kits': 54, 'cock-rings': 60,
        'Water Based Lubricant': 55, 'oil based': 56, 'Massage Oil': 57
      };
  const SLUG_BY_ID = Object.fromEntries(Object.entries(ID_BY_SLUG).map(([slug, id]) => [String(id), slug]));

  function setToolbarLabel(txt) {
    const labelEl = $('#mobileCategoryLabel');
    if (labelEl) {
      // If "All Products" (no filter), show "Click to filter/sort"
      // Otherwise, just show the category name without prefix
      labelEl.textContent = (txt === 'All Products') ? '👆 Click to filter/sort' : txt;
    }
  }
  function resolveCategoryName(slug) {
    if (!slug || slug === 'all') return 'All Products';
    if (slug === 'men') return 'Men';
    if (slug === 'women') return 'Women';
    if (slug === 'gender') return 'Gender';
    const main = sheet.querySelector(`.level-1 .row[data-category="${CSS.escape(slug)}"] .label`);
    if (main) return main.textContent.trim();
    
    // Recursive function to search nested children (for Gender subcategories)
    function searchInChildren(children, targetSlug) {
      if (!Array.isArray(children)) return null;
      for (const ch of children) {
        if (ch.slug === targetSlug) return ch.name || null;
        // Recursively search nested children
        if (ch.children) {
          const result = searchInChildren(ch.children, targetSlug);
          if (result) return result;
        }
      }
      return null;
    }
    
    // Search in all level-1 rows including their nested children
    for (const p of $$('.level-1 .row', sheet)) {
      try {
        const children = JSON.parse(p.dataset.children || '[]');
        // First check direct children
        const hit = children.find(ch => ch.slug === slug);
        if (hit?.name) return hit.name;
        // Then check nested children (e.g., Gender > Men > Masturbators)
        const nestedHit = searchInChildren(children, slug);
        if (nestedHit) return nestedHit;
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
  let selectedGender = null; // Track selected gender for level 2
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

    level1.hidden = false; // SHOW main categories
    level2.hidden = true;  // HIDE subcategories
    if (mainHeader) mainHeader.hidden = false; // SHOW main header label
    hideSubHeader();
    backBtn.hidden = true; // HIDE back button initially
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
  function rowHTML(slug, name, childObj) {
    // Preserve nested children data for multi-level navigation
    const childrenAttr = (childObj && childObj.children) ? ` data-children='${JSON.stringify(childObj.children).replace(/'/g, "&apos;")}'` : '';
    // Escape HTML special characters in name
    const escapedName = (name || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    return `
      <li>
        <button type="button" class="row" data-category="${slug}" data-category-name="${escapedName}"${childrenAttr}>
          <span class="label">${escapedName}</span><span class="check" aria-hidden="true"></span>
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
    children.forEach(ch => level2.insertAdjacentHTML('beforeend', rowHTML(ch.slug || '', ch.name || '', ch)));
    showSubHeader(parentName);
    level1.hidden  = true;   // HIDE main categories when showing subcategories
    if (mainHeader) mainHeader.hidden = true; // HIDE main header label when viewing subcategories
    level2.hidden  = false;  // SHOW subcategories
    backBtn.hidden = false;  // SHOW back button
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
    const hasChildren = btn.dataset.hasChildren === 'true';

    // If it's the Gender button, show Men/Women options
    if (cat === 'gender') {
      selectedGender = null; // Reset gender when going back to Gender
      buildLevel2(name, json, cat);
      return;
    }

    // Regular categories with children - show subcategories
    if (hasChildren) {
      buildLevel2(name, json, cat);
      return;
    }
  });

  // Level 2 (subs) — handle men/women or final category
  level2?.addEventListener('click', e => {
    const btn = e.target.closest('.row');
    if (!btn) return;
    e.preventDefault(); e.stopPropagation();

    const cat  = btn.dataset.category;
    const name = btn.dataset.categoryName || btn.querySelector('.label')?.textContent?.trim() || 'Category';
    const json  = btn.dataset.children || '[]';

    // If clicking Men or Women (from Gender level), show subcategories
    if ((cat === 'men' || cat === 'women') && !selectedGender) {
      try {
        const parsed = JSON.parse(json);
        // parsed should be an array of subcategories [{"slug":"masturbators",...}, ...]
        if (Array.isArray(parsed) && parsed.length > 0) {
          selectedGender = cat; // Store gender
          buildLevel2(`${name}`, JSON.stringify(parsed), cat);
          return;
        }
      } catch (err) {
        // Continue to filter if parsing fails
      }
    }

    // Otherwise apply filter immediately
    selected = { slug: cat, label: name };
    setToolbarLabel(name);
    syncFooterButton();
    closeSheet(e);

    if (typeof window.filterProducts === 'function') window.filterProducts(cat);
  });

  // Back to main
  backBtn?.addEventListener('click', e => {
    e.preventDefault(); e.stopPropagation();
    level1.hidden  = false; // SHOW main categories again
    if (mainHeader) mainHeader.hidden = false; // SHOW main header label again
    level2.hidden  = true;  // HIDE subcategories
    backBtn.hidden = true;  // HIDE back button
    hideSubHeader();
    $('.sheet-title', sheet).textContent = 'Choose Category';
    selectedGender = null; // Reset gender when going back
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
