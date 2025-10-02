// static/js/home.js
(function () {
  'use strict';

  // --- Map helpers (for Folium iframe) ---
  function showMapFallback() {
    const mapIframe = document.querySelector('.folium-map');
    const fallback = document.getElementById('map-fallback');
    if (mapIframe && fallback) {
      mapIframe.style.display = 'none';
      fallback.style.display = 'flex';
    }
  }

  function initializeMap() {
    const mapIframe = document.querySelector('.folium-map');
    const fallback = document.getElementById('map-fallback');
    if (!mapIframe) return;

    // If Folium never loads, show fallback
    const timeout = setTimeout(() => {
      if (fallback) {
        mapIframe.style.display = 'none';
        fallback.style.display = 'flex';
      }
    }, 8000);

    mapIframe.onload = () => clearTimeout(timeout);
    mapIframe.onerror = () => {
      clearTimeout(timeout);
      if (fallback) {
        mapIframe.style.display = 'none';
        fallback.style.display = 'flex';
      }
    };
  }

  // Lazy-load the map when its container enters viewport
  document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('map-container');
    if (!container) return;

    const obs = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          setTimeout(initializeMap, 100);
          obs.unobserve(e.target);
        }
      });
    }, { rootMargin: '50px' });

    obs.observe(container);
  });

  // --- Product image fallback helper ---
  window.handleImageError = function (img) {
    const src = img?.src || '';
    if (!src) return;

    // Prefer JPG fallback when a “__alpha.webp” fails
    if (src.includes('__alpha.webp')) {
      img.src = src.replace('__alpha.webp', '.jpg');
      img.onerror = null; // stop infinite loops
      return;
    }

    // Generic fallback
    img.style.display = 'none';
    const p = document.createElement('p');
    p.textContent = 'Image not available';
    p.style.minHeight = '3rem';
    p.style.display = 'flex';
    p.style.alignItems = 'center';
    p.style.justifyContent = 'center';
    img.parentNode && img.parentNode.insertBefore(p, img);
  };
})();
