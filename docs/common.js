(() => {
  const THEME_STORAGE_KEY = 'tg-theme';
  const HASHTAG_RE = /#([\p{L}\p{N}_]+)/gu;
  const lightboxState = { index: 0, items: [] };
  let headerResponsiveInited = false;
  const PROMO_COOKIE = 'tg_promo_hidden';

  function el(id){ return document.getElementById(id); }
  function setCookie(name, value, days){
    const maxAge = Math.max(1, days || 365) * 24 * 60 * 60;
    const secure = window.location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `${name}=${encodeURIComponent(value)}; max-age=${maxAge}; path=/; SameSite=Lax${secure}`;
  }
  function hasCookie(name, expectedValue){
    return document.cookie.split(';').some((part) => {
      const [k, v] = part.split('=').map((s) => (s || '').trim());
      if(k !== name) return false;
      if(typeof expectedValue === 'undefined') return true;
      return decodeURIComponent(v || '') === expectedValue;
    });
  }

  function setStatus(text, kind, nodeId = 'status'){
    const box = el(nodeId);
    if(!box) return;
    if(!text){
      box.textContent = '';
      box.className = 'status';
      box.style.display = 'none';
      return;
    }
    box.textContent = text;
    box.className = 'status' + (kind ? ' ' + kind : '');
    box.style.display = '';
  }

  function formatLocalDate(iso){
    if(!iso) return '—';
    try{
      const date = new Date(iso);
      return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
    }catch(e){
      return iso;
    }
  }

  function getPreferredTheme(){
    let stored = '';
    try{
      stored = (localStorage.getItem(THEME_STORAGE_KEY) || '').toLowerCase();
    }catch(e){
      stored = '';
    }
    if(stored === 'light' || stored === 'dark') return stored;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme){
    const t = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', t);
    if(document.body){
      document.body.setAttribute('data-theme', t);
    }
    const btn = el('themeToggle');
    if(btn){
      const label = t === 'dark' ? 'Светлая тема' : 'Тёмная тема';
      btn.textContent = t === 'dark' ? '☾' : '☀';
      btn.setAttribute('aria-label', label);
      btn.title = label;
    }
  }

  function initTheme(){
    applyTheme(getPreferredTheme());

    if(window.matchMedia){
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      const handler = (e) => {
        try{
          if(localStorage.getItem(THEME_STORAGE_KEY)) return;
        }catch(err){}
        applyTheme(e.matches ? 'dark' : 'light');
      };
      if(typeof mq.addEventListener === 'function'){
        mq.addEventListener('change', handler);
      } else if(typeof mq.addListener === 'function'){
        mq.addListener(handler);
      }
    }
  }

  function initPromoBanner(text){
    const banner = el('promoBanner');
    if(!banner) return;
    const promoText = (text || '').trim();
    if(!promoText || hasCookie(PROMO_COOKIE, '1')){
      banner.remove();
      return;
    }
    const textNode = banner.querySelector('.promo-text');
    if(textNode){
      textNode.innerHTML = promoText;
    }
    const closeBtn = document.getElementById('promoClose') || banner.querySelector('.promo-close');
    banner.hidden = false;
    if(closeBtn){
      closeBtn.addEventListener('click', () => {
        setCookie(PROMO_COOKIE, '1', 365 * 5);
        banner.remove();
      });
    }
  }

  function toggleTheme(){
    const current = document.documentElement.getAttribute('data-theme') || getPreferredTheme();
    const next = current === 'dark' ? 'light' : 'dark';
    try{
      localStorage.setItem(THEME_STORAGE_KEY, next);
    }catch(e){}
    applyTheme(next);
  }

  function computeHomeHref(){
    const loc = window.location || {};
    const hostname = (loc.hostname || '').toLowerCase();
    const parts = (loc.pathname || '/').split('/').filter(Boolean);
    if(hostname.endsWith('github.io') && parts.length){
      return `/${parts[0]}/`;
    }
    if(parts.length){
      return `/${parts[0]}/`;
    }
    return '/';
  }

  function applyHomeLinks(){
    const home = computeHomeHref();
    const title = el('siteTitleWrap');
    if(title) title.href = home;

    // Dynamic pages use an explicit id, static pages use an <a class="grid-avatar">.
    const avatar = el('channelAvatarLink');
    if(avatar) avatar.href = home;

    const staticAvatars = document.querySelectorAll('a.grid-avatar');
    staticAvatars.forEach((node) => {
      try{ node.href = home; }catch(e){}
    });
  }

  function bumpFavicons(version){
    const v = (version || '').toString().trim();
    if(!v) return;
    const links = document.querySelectorAll('link[rel="icon"], link[rel="apple-touch-icon"]');
    links.forEach((link) => {
      try{
        const url = new URL(link.href, window.location.href);
        url.searchParams.set('v', v);
        link.href = url.toString();
      }catch(e){}
    });
  }

  function initResponsiveHeader(){
    if(headerResponsiveInited) return;
    headerResponsiveInited = true;

    const titleHead = document.querySelector('.title-head');
    const subscribe = el('subscribeBtn');
    if(!titleHead || !subscribe) return;

    const backLink = titleHead.querySelector('.back-link');
    const BACK_SECOND_ROW_CLASS = 'title-head--back-row2';
    const heroActions = titleHead.querySelector('.hero-actions');

    // Keep the header readable on narrow screens.
    //
    // Priority (degradation order):
    //   1) Do NOT show a truncated "Подпи…". If the subscribe button cannot fit, collapse it to an icon.
    //   2) Only allow truncation of the title as a last resort (i.e. when actions are already compact).
    //
    // Implementation: instead of using a fixed pixel threshold, we detect real truncation in the
    // full (non-compact) state. If either the title or the subscribe label would be truncated,
    // we keep the button in compact mode.
    const TRUNCATION_EPS_PX = 1;

    if(!subscribe.getAttribute('aria-label')){
      subscribe.setAttribute('aria-label', 'Подписаться на Telegram');
    }
    if(!subscribe.getAttribute('title')){
      subscribe.setAttribute('title', 'Подписаться');
    }

    // Static pages may ship a simplified "Подписаться" link without the icon markup.
    // Normalize it here so the same responsive logic/CSS works everywhere.
    const ensureSubscribeMarkup = () => {
      const hasText = subscribe.querySelector('.subscribe-text');
      const hasIcon = subscribe.querySelector('.subscribe-icon');
      if(hasText && hasIcon) return;

      const label = (hasText ? (hasText.textContent || '') : (subscribe.textContent || '')).trim() || 'Подписаться';
      while(subscribe.firstChild){
        subscribe.removeChild(subscribe.firstChild);
      }

      const textSpan = document.createElement('span');
      textSpan.className = 'subscribe-text';
      textSpan.textContent = label;

      const iconSpan = document.createElement('span');
      iconSpan.className = 'subscribe-icon';
      iconSpan.setAttribute('aria-hidden', 'true');
      iconSpan.innerHTML = `
        <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
          <path d="M21.9 2.3c-.2-.2-.5-.3-.8-.2L2.4 9.3c-.4.1-.7.5-.7.9 0 .4.2.8.6 1l7.3 3.3 3.3 7.3c.2.4.6.6 1 .6.4 0 .8-.3.9-.7L22.1 3.1c.1-.3 0-.6-.2-.8ZM9.7 13.3l-4.6-2L18.5 6 9.7 13.3Zm3.6 5.6-2-4.6L18.5 6l-5.2 13.4Z" />
        </svg>
      `;
      subscribe.append(textSpan, iconSpan);
    };

    ensureSubscribeMarkup();

    const titleTextNode = () => document.getElementById('siteTitle') || document.getElementById('siteTitleWrap') || document.querySelector('.title-left');
    const subscribeTextNode = () => subscribe.querySelector('.subscribe-text') || subscribe;

    const isTruncated = (node) => {
      if(!node) return false;
      const cw = node.clientWidth || 0;
      const sw = node.scrollWidth || 0;
      return sw > cw + TRUNCATION_EPS_PX;
    };

    const applySubscribeState = () => {
      if(subscribe.hidden){
        subscribe.classList.remove('subscribe-btn--compact');
        return;
      }

      // Decide based on whether the FULL state would cause any truncation.
      if(subscribe.classList.contains('subscribe-btn--compact')){
        subscribe.classList.remove('subscribe-btn--compact');
      }

      const titleEl = titleTextNode();
      const subTextEl = subscribeTextNode();
      const titleWouldTruncate = isTruncated(titleEl);
      const subscribeWouldTruncate = isTruncated(subTextEl);

      // Post pages (with a back-link) may allow wrapping when the back-link is moved to row 2.
      // In that mode, the actions block can drop to the next line *before* any text truncation happens.
      // We still want the subscribe button to become an icon first.
      const titleWrapEl = document.getElementById('siteTitleWrap') || titleHead.querySelector('.badge-chip') || titleEl;
      const actionsWrapped = !!(
        backLink &&
        titleHead.classList.contains(BACK_SECOND_ROW_CLASS) &&
        heroActions &&
        titleWrapEl &&
        heroActions.getBoundingClientRect().top >= titleWrapEl.getBoundingClientRect().bottom - 1
      );

      const shouldCompact = titleWouldTruncate || subscribeWouldTruncate || actionsWrapped;

      if(shouldCompact){
        subscribe.classList.add('subscribe-btn--compact');
      } else {
        subscribe.classList.remove('subscribe-btn--compact');
      }
    };

    const shouldMoveBackLinkToSecondRow = () => {
      if(!backLink) return false;
      // Conditions from UX spec:
      //  - if "Ко всем постам" doesn't fit on one line
      //  - or if the title starts truncating
      const titleEl = titleTextNode();
      return isTruncated(backLink) || isTruncated(titleEl);
    };

    const update = () => {
      // Always start from the single-row layout to measure consistently.
      if(backLink){
        titleHead.classList.remove(BACK_SECOND_ROW_CLASS);
      }

      // 1) Apply subscribe compacting rules first (keeps title readable).
      applySubscribeState();

      // 2) On post pages: move the back link to the second row when it can't fit.
      if(backLink){
        titleHead.classList.toggle(BACK_SECOND_ROW_CLASS, shouldMoveBackLinkToSecondRow());
      }

      // 3) Re-evaluate subscribe after layout change (extra width may allow full label).
      applySubscribeState();
    };

    const rafUpdate = () => window.requestAnimationFrame(update);

    // Initial measurement after first paint.
    rafUpdate();

    if('ResizeObserver' in window){
      const ro = new ResizeObserver(rafUpdate);
      ro.observe(titleHead);
    } else {
      window.addEventListener('resize', rafUpdate, { passive: true });
    }
  }

  function escapeHtml(s){
    return (s ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function normalizeHashtag(tag){
    const t = (tag || '').trim();
    if(!t) return '';
    return t.startsWith('#') ? t : '#' + t;
  }

  function linkifyHashtags(root){
    if(!root || typeof document === 'undefined') return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    const targets = [];
    let node;
    while((node = walker.nextNode())){
      if(!node.nodeValue || !node.nodeValue.includes('#')) continue;
      if(node.parentElement && node.parentElement.closest('a')) continue;
      targets.push(node);
    }

    for(const textNode of targets){
      const text = textNode.nodeValue;
      HASHTAG_RE.lastIndex = 0;
      let match;
      let lastIndex = 0;
      let replaced = false;
      const frag = document.createDocumentFragment();

      while((match = HASHTAG_RE.exec(text))){
        const start = match.index;
        if(start > lastIndex){
          frag.append(text.slice(lastIndex, start));
        }
        const tag = match[0];
        const clean = match[1];
        const a = document.createElement('a');
        a.className = 'hashtag';
        a.textContent = tag;
        a.href = '#';
        a.setAttribute('data-tag', clean);
        frag.append(a);
        lastIndex = start + tag.length;
        replaced = true;
      }

      if(!replaced) continue;
      if(lastIndex < text.length){
        frag.append(text.slice(lastIndex));
      }

      if(textNode.parentNode){
        textNode.parentNode.replaceChild(frag, textNode);
      }
    }
  }

  function looksLikeImage(path, mime){
    const p = (path || '').toLowerCase();
    if(mime && mime.startsWith('image/')) return true;
    return p.endsWith('.jpg') || p.endsWith('.jpeg') || p.endsWith('.png') || p.endsWith('.gif') || p.endsWith('.webp');
  }

  function isImageMedia(m){
    if(!m) return false;
    if(m.kind === 'photo' || m.kind === 'image') return true;
    return looksLikeImage(m.path, m.mime);
  }

  function dedupeMedia(media){
    const out = [];
    const seen = new Set();
    for(const m of media || []){
      const key = `${m.path}|${m.kind}|${m.mime}`;
      if(seen.has(key)) continue;
      seen.add(key);
      out.push(m);
    }
    return out;
  }

  function renderMediaItem(m, postId, imageIndex){
    if(!m || !m.path) return '';
    const path = escapeHtml(m.path);
    const thumb = m.thumb ? escapeHtml(m.thumb) : '';
    const mime = m.mime || '';
    const name = m.name || path.split('/').pop();

    if(isImageMedia(m)){
      const idxAttr = (imageIndex ?? '') !== '' ? ` data-image-index="${imageIndex}"` : '';
      const srcset = thumb ? ` srcset="./${thumb} 480w, ./${path} 1200w"` : '';
      const sizes = 'sizes="(max-width: 768px) 100vw, 800px"';
      const src = thumb || path;
      return `<img class="media-img" loading="lazy" src="./${src}"${srcset ? ' ' + srcset : ''} ${srcset ? sizes : ''} alt="" data-post-id="${postId}"${idxAttr} />`;
    }

    if(m.kind === 'video'){
      return `<video controls preload="metadata" src="./${path}"></video>`;
    }
    if(m.kind === 'audio'){
      return `<audio controls preload="metadata" src="./${path}"></audio>`;
    }

    if(m.kind === 'document'){
      if(looksLikeImage(path, mime)){
        return `<img loading="lazy" src="./${path}" alt="" />`;
      }
      return `<a class="badge" href="./${path}" target="_blank" rel="noopener">Скачать: ${escapeHtml(name || 'файл')}</a>`;
    }

    return `<img class="media-img" loading="lazy" src="./${path}" alt="" data-post-id="${postId}"${(imageIndex ?? '') !== '' ? ` data-image-index="${imageIndex}"` : ''} />`;
  }

  function ensureLightbox(){
    let lb = document.getElementById('lightbox');
    if(lb) return lb;
    lb = document.createElement('div');
    lb.id = 'lightbox';
    lb.className = 'lightbox';
    lb.innerHTML = `
      <div class="lightbox-inner">
        <button class="lightbox-btn lightbox-close" type="button" aria-label="Закрыть">✕</button>
        <div class="lightbox-nav">
          <button class="lightbox-btn lightbox-prev" type="button" aria-label="Предыдущее">‹</button>
          <button class="lightbox-btn lightbox-next" type="button" aria-label="Следующее">›</button>
        </div>
        <img id="lightboxImage" alt="" />
        <div class="lightbox-counter" id="lightboxCounter"></div>
      </div>
    `;
    document.body.appendChild(lb);

    lb.addEventListener('click', (e) => {
      if(e.target === lb) closeLightbox();
    });
    lb.querySelector('.lightbox-close')?.addEventListener('click', () => closeLightbox());
    lb.querySelector('.lightbox-prev')?.addEventListener('click', () => stepLightbox(-1));
    lb.querySelector('.lightbox-next')?.addEventListener('click', () => stepLightbox(1));
    document.addEventListener('keydown', onLightboxKey);
    return lb;
  }

  function onLightboxKey(e){
    const lb = document.getElementById('lightbox');
    if(!lb || !lb.classList.contains('visible')) return;
    if(e.key === 'Escape'){ closeLightbox(); }
    else if(e.key === 'ArrowLeft'){ stepLightbox(-1); }
    else if(e.key === 'ArrowRight'){ stepLightbox(1); }
  }

  function showLightbox(){
    const lb = ensureLightbox();
    const img = document.getElementById('lightboxImage');
    const counter = document.getElementById('lightboxCounter');
    const item = lightboxState.items[lightboxState.index];
    if(!item){
      closeLightbox();
      return;
    }
    img.src = item.src;
    img.alt = item.alt || '';
    if(counter){
      counter.textContent = `${lightboxState.index + 1} / ${lightboxState.items.length}`;
    }
    lb.classList.add('visible');
  }

  function closeLightbox(){
    const lb = document.getElementById('lightbox');
    if(lb){
      lb.classList.remove('visible');
    }
    lightboxState.index = 0;
    lightboxState.items = [];
  }

  function stepLightbox(delta){
    if(!lightboxState.items.length) return;
    lightboxState.index = (lightboxState.index + delta + lightboxState.items.length) % lightboxState.items.length;
    showLightbox();
  }

  function openLightboxForPost(post, imageIndex){
    if(!post || !Array.isArray(post.media)) return;
    const items = dedupeMedia(post.media).filter(isImageMedia).map((m) => ({
      src: `./${m.path}`,
      alt: m.name || '',
    }));
    if(!items.length) return;
    const idx = Math.max(0, Math.min(imageIndex || 0, items.length - 1));
    lightboxState.index = idx;
    lightboxState.items = items;
    showLightbox();
  }

  window.Common = {
    el,
    setStatus,
    formatLocalDate,
    initTheme,
    initPromoBanner,
    applyHomeLinks,
    initResponsiveHeader,
    toggleTheme,
    bumpFavicons,
    escapeHtml,
    normalizeHashtag,
    linkifyHashtags,
    isImageMedia,
    dedupeMedia,
    renderMediaItem,
    openLightboxForPost,
  };
})();
