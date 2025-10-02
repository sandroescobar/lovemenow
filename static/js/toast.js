
(function(){
  function normalizeFlashStack(){
    const stack = document.getElementById('flashStack');
    if (!stack) return;

    // If server rendered any toast, discard stored auth toast to avoid double-pop
    if (stack.querySelector('.toast')) {
      sessionStorage.removeItem('authMessage');
      sessionStorage.removeItem('authMessageType');
    }

    const seen = new Set();
    [...stack.querySelectorAll('.toast')].forEach((el, i) => {
      const txt = (el.textContent||'').replace(/\s+/g,' ').trim().toLowerCase();

      // Force Flask 'message' → green success
      if (el.classList.contains('toast-message')) {
        el.classList.remove('toast-info','info','toast-error','error','toast-warning','warning','toast-danger','danger');
        el.classList.add('toast-success','success');
      }

      // Heuristic: if content obviously indicates login success, force green
      if (/(logged in|welcome back|signed in|login successful)/i.test(txt)) {
        el.classList.remove('toast-info','info','toast-error','error','toast-warning','warning','toast-danger','danger');
        el.classList.add('toast-success','success');
      }

      // De-dupe by text
      const key = txt;
      if (seen.has(key)) { el.remove(); return; }
      seen.add(key);

      // Smooth exit
      requestAnimationFrame(()=> {
        setTimeout(()=> {
          el.style.animation = 'toastSlideOutRight .35s forwards';
          el.addEventListener('animationend', ()=>el.remove(), { once:true });
        }, 3000 + i*120);
      });
    });
  }

  // Global hook for programmatic toasts (used by your index.js etc.)
  window.showFlash = function(msg, type='info', opts={}){
    const map = { message:'success', success:'success', info:'info', warning:'warning', error:'error', danger:'error' };
    const t = map[type] || 'info';

    let stack = document.getElementById('flashStack');
    if (!stack) {
      stack = document.createElement('div');
      stack.id = 'flashStack';
      stack.className = 'toast-stack';
      document.body.appendChild(stack);
    }

    const text = String(msg ?? '').replace(/\s+/g,' ').trim();
    const dupe = [...stack.children].some(n => (n.textContent||'').replace(/\s+/g,' ').trim().toLowerCase() === text.toLowerCase());
    if (dupe) return null;

    const el = document.createElement('div');
    el.className = `toast toast-${t} ${t}`;
    el.setAttribute('role','status'); el.setAttribute('aria-live','polite');
    el.innerHTML = `<button class="flash_message_close" aria-label="Close" onclick="this.parentElement.remove()"><i class="fas fa-times" aria-hidden="true"></i></button>${text}`;
    stack.appendChild(el);

    const ttl = Number(opts.ttl ?? 3000);
    if (ttl>0){
      setTimeout(()=>{ el.style.animation='toastSlideOutRight .35s forwards'; el.addEventListener('animationend', ()=>el.remove(), { once:true }); }, ttl);
    }
    return el;
  };

  document.addEventListener('DOMContentLoaded', normalizeFlashStack);
})();
