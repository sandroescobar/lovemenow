# Performance Optimization Guide

## 🎯 Goal
Reduce LCP (Largest Contentful Paint) from 3,971ms to below 1,200ms
Reduce SI (Speed Index) from 4,628ms to below 1,200ms

## 📊 Current Issues
1. **Large CSS file (315KB)** blocking initial render
2. **Google Tag Manager in head** blocking render
3. **Multiple JavaScript files** causing many network requests  
4. **Unoptimized images** slowing down LCP
5. **Synchronous font loading** blocking text rendering

## ✅ Implemented Solutions

### 1. Critical CSS Inlining
- Created `critical.css` with only above-the-fold styles
- Inline critical CSS in `<head>` for instant rendering
- Load main CSS asynchronously using `rel="preload"`

### 2. JavaScript Optimization
- Combined critical JS into `bundle.min.js`
- Deferred non-critical scripts
- Moved GTM to load after page content
- Implemented lazy loading for modals

### 3. Image Optimization
- Added `loading="lazy"` for below-the-fold images
- Set `fetchpriority="high"` for hero images
- Added `decoding="async"` to prevent render blocking
- Created image optimization script for WebP generation

### 4. Resource Hints
- Added DNS prefetch for external domains
- Preloaded critical fonts
- Preconnected to frequently used origins

### 5. Template Optimization
- Created `index_performance.html` with all optimizations
- Lazy load iframe content
- Defer modal rendering until needed

## 🚀 How to Use

### 1. Test Performance Template
```bash
# Visit your site with performance template
http://localhost:5000/?perf=1
```

### 2. Optimize CSS
```bash
python optimize_css.py
```

### 3. Optimize Images
```bash
python optimize_images.py static/IMG
```

### 4. Deploy Changes
1. Test the performance template thoroughly
2. Run Lighthouse test to verify improvements
3. If successful, make performance template the default:

```python
# In routes/main.py, change:
template = "index_performance.html" if request.args.get('perf') else "index.html"
# To:
template = "index_performance.html"
```

## 📈 Expected Improvements

### LCP (Largest Contentful Paint)
- **Before:** 3,971ms
- **After:** ~800-1,000ms
- **Improvement:** ~75% reduction

### SI (Speed Index)  
- **Before:** 4,628ms
- **After:** ~1,000-1,200ms
- **Improvement:** ~75% reduction

### How It Works:
1. **Critical CSS inline** = No render blocking
2. **Lazy loaded images** = Faster initial paint
3. **Deferred JavaScript** = Non-blocking execution
4. **Bundled resources** = Fewer network requests
5. **Async GTM** = No analytics blocking

## 🔧 Additional Optimizations

### Server-Side
```python
# Enable compression in Flask
from flask_compress import Compress
compress = Compress(app)

# Add caching headers
@app.after_request
def add_cache_headers(response):
    if 'static' in request.path:
        response.cache_control.max_age = 31536000  # 1 year
        response.cache_control.public = True
    return response
```

### CDN Setup
Consider using a CDN like Cloudflare for:
- Automatic image optimization
- Edge caching
- HTTP/3 support
- Brotli compression

### Database Optimization
```python
# Optimize product queries
featured_products = (
    Product.query
    .filter(Product.in_stock.is_(True))
    .options(
        joinedload(Product.variants),
        defer(Product.description),  # Don't load heavy fields
        defer(Product.specifications),
    )
    .limit(3)
    .all()
)
```

## 🧪 Testing

### Run Lighthouse Test
1. Open Chrome DevTools (F12)
2. Go to Lighthouse tab
3. Run Performance audit
4. Compare results

### Expected Scores After Optimization:
- **Performance:** 85-95 (from 68)
- **FCP:** < 1.0s (from 1.1s)
- **SI:** < 1.2s (from 4.6s)
- **LCP:** < 1.2s (from 4.0s)
- **TBT:** 0ms (already optimal)
- **CLS:** 0.04 (already optimal)

## ⚠️ Important Notes

1. **Test thoroughly** before making performance template default
2. **Monitor analytics** to ensure GTM events still fire correctly
3. **Check cart/wishlist functionality** with bundled JS
4. **Verify modals** load correctly when lazy loaded
5. **Test on mobile** devices for responsive behavior

## 🔄 Rollback Plan

If issues occur:
1. Remove `?perf=1` parameter to use original template
2. Original files remain untouched
3. Can revert route change in `main.py`

## 📚 Resources

- [Web.dev Performance Guide](https://web.dev/performance/)
- [Core Web Vitals](https://web.dev/vitals/)
- [Lighthouse Documentation](https://developers.google.com/web/tools/lighthouse)

## 🎉 Success Metrics

After implementing these optimizations:
- ✅ LCP < 1,200ms target
- ✅ SI < 1,200ms target  
- ✅ Better user experience
- ✅ Higher Google PageSpeed score
- ✅ Improved SEO rankings
- ✅ Lower bounce rate