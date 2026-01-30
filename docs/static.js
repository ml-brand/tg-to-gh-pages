(() => {
  const Common = window.Common;

  function updateDates(rootNode){
    if(!rootNode) return;
    const dateNodes = rootNode.querySelectorAll('[data-iso-date]');
    dateNodes.forEach((node) => {
      const iso = node.getAttribute('data-iso-date') || '';
      node.textContent = Common.formatLocalDate(iso);
    });
  }

  function buildPostIndex(){
    const postById = new Map();
    const posts = Array.isArray(window.__STATIC_POSTS) ? window.__STATIC_POSTS : [];
    for(const post of posts){
      if(post && typeof post.id !== 'undefined'){
        postById.set(String(post.id), post);
      }
    }
    return postById;
  }

  function initThemeToggle(){
    Common.initTheme();
    const themeButton = Common.el('themeToggle');
    if(themeButton){
      themeButton.addEventListener('click', () => Common.toggleTheme());
    }
  }

  function initIndexPageInteractions(){
    const postsContainer = Common.el('posts');
    if(!postsContainer) return;

    const postById = buildPostIndex();
    Common.linkifyHashtags(postsContainer);
    updateDates(postsContainer);

    postsContainer.addEventListener('click', (e) => {
      const clickedElement = e.target;
      const hashtagLink = clickedElement && typeof clickedElement.closest === 'function'
        ? clickedElement.closest('.hashtag')
        : null;

      if(hashtagLink){
        e.preventDefault();
        return;
      }

      if(clickedElement && clickedElement.classList && clickedElement.classList.contains('media-img')){
        const postId = clickedElement.getAttribute('data-post-id');
        const imageIndex = Number(clickedElement.getAttribute('data-image-index') || 0);
        const postData = postById.get(String(postId));
        if(postData){
          Common.openLightboxForPost(postData, Number.isNaN(imageIndex) ? 0 : imageIndex);
        }
      }
    });

    Common.setStatus('');
  }

  function initPostPageInteractions(){
    const container = Common.el('postContainer');
    if(!container) return;

    const postById = buildPostIndex();
    const indexHref = document.body?.getAttribute('data-index-href') || '../';

    Common.linkifyHashtags(container);
    updateDates(container);

    container.addEventListener('click', (e) => {
      const clickedElement = e.target;
      const hashtagLink = clickedElement && typeof clickedElement.closest === 'function'
        ? clickedElement.closest('.hashtag')
        : null;

      if(hashtagLink){
        e.preventDefault();
        const normalized = Common.normalizeHashtag(hashtagLink.getAttribute('data-tag') || hashtagLink.textContent);
        if(!normalized) return;
        try{
          const url = new URL(indexHref, window.location.href);
          url.searchParams.set('q', normalized);
          window.location.href = url.toString();
        }catch(err){
          window.location.href = `${indexHref}?q=${encodeURIComponent(normalized)}`;
        }
        return;
      }

      if(clickedElement && clickedElement.classList && clickedElement.classList.contains('media-img')){
        const imageIndex = Number(clickedElement.getAttribute('data-image-index') || 0);
        const postId = clickedElement.getAttribute('data-post-id');
        const postData = postById.get(String(postId));
        if(postData){
          Common.openLightboxForPost(postData, Number.isNaN(imageIndex) ? 0 : imageIndex);
        }
      }
    });

    Common.setStatus('');
  }

  function init(){
    if(!Common) return;

    initThemeToggle();

    const banner = Common.el('promoBanner');
    const promoText = banner ? (banner.querySelector('.promo-text')?.innerHTML || '') : '';
    Common.initPromoBanner(promoText);

    Common.applyHomeLinks();
    // Use the same responsive header behavior as the dynamic pages.
    // (Collapse the subscribe button to an icon before any truncation happens.)
    Common.initResponsiveHeader();

    if(Common.el('posts')){
      initIndexPageInteractions();
    } else if(Common.el('postContainer')){
      initPostPageInteractions();
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
