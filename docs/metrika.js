(function () {
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  if (window.__ymInjected) return;
  window.__ymInjected = true;

  const configUrl = (function () {
    const scriptEl = document.currentScript;
    const base = scriptEl && scriptEl.src ? scriptEl.src : window.location.href;
    try {
      const url = new URL(base);
      const segments = url.pathname.split('/').filter(Boolean);
      const prefix = segments.length ? `/${segments[0]}` : '';
      return `${url.origin}${prefix}/data/config.json`;
    } catch (e) {
      return './data/config.json';
    }
  })();

  function inject(counterId) {
    const cid = Number(counterId || 0) || String(counterId || '').trim();
    if (!cid) return;
    if (typeof window.ym === 'undefined') {
      window.ym = function () {
        (window.ym.a = window.ym.a || []).push(arguments);
      };
      window.ym.l = 1 * new Date();
    }
    const existing = Array.from(document.scripts || []).some((s) => (s.src || '').includes('mc.yandex.ru/metrika'));
    if (!existing) {
      const script = document.createElement('script');
      script.async = true;
      script.src = `https://mc.yandex.ru/metrika/tag.js?id=${encodeURIComponent(cid)}`;
      document.head.appendChild(script);
    }
    try {
      // eslint-disable-next-line no-undef
      ym(cid, 'init', {
        ssr: true,
        webvisor: true,
        clickmap: true,
        ecommerce: 'dataLayer',
        referrer: document.referrer,
        url: location.href,
        accurateTrackBounce: true,
        trackLinks: true,
      });
    } catch (e) {}
  }

  fetch(configUrl, { cache: 'no-store' })
    .then((res) => (res.ok ? res.json() : {}))
    .then((cfg) => inject((cfg && cfg.metrika_id) || ''))
    .catch(() => {});
})();
