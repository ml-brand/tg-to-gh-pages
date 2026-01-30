/* Single post view for Telegram mirror */

const POSTS_URL = './data/posts.json';
const META_URL = './data/meta.json';
const CONFIG_URL = './data/config.json';
const DATA_PAGES_BASE = './data/pages';

const Common = window.Common;
const {
  el: getById,
  normalizeHashtag,
  setStatus: setStatusText,
  formatLocalDate,
} = Common;

const uiState = {
  posts: [],
  postById: new Map(),
  currentPost: null,
};

let subscribeLinkOverride = '';
let promoBannerHtml = '';

function navigateToIndexWithTag(tag){
  const normalized = normalizeHashtag(tag);
  if(!normalized) return;
  try{
    const base = new URL(window.location.href);
    base.search = '';
    base.hash = '';
    const target = new URL('./', base);
    target.searchParams.set('q', normalized);
    window.location.href = target.toString();
  }catch(e){
    window.location.href = './?q=' + encodeURIComponent(normalized);
  }
}

function openLightboxForPostId(postId, imageIndex){
  const key = String(postId);
  const post = uiState.postById.get(key) || uiState.postById.get(Number(postId));
  if(!post) return;
  Common.openLightboxForPost(post, imageIndex);
}

function readPostIdFromUrl(){
  const params = new URLSearchParams(window.location.search);
  const id = params.get('id') || params.get('post');
  if(id && String(id).trim()) return String(id).trim();
  const hash = window.location.hash.replace('#', '').trim();
  return hash || null;
}

function buildPermalink(id){
  try{
    const url = new URL(window.location.href);
    url.search = '';
    url.hash = '';
    url.pathname = url.pathname.replace(/[^/]+$/, 'post.html');
    url.searchParams.set('id', id);
    return url.toString();
  }catch(e){
    return `./post.html?id=${encodeURIComponent(id)}`;
  }
}

function renderHeaderMeta(meta, post){
  const title = meta.title || 'Telegram Mirror';
  getById('siteTitle').textContent = title;
  document.title = post ? `${title} — пост #${post.id}` : `${title} — пост`;
  const channelUrl = meta.username
    ? `https://t.me/${meta.username}`
    : (meta.channel ? `https://t.me/${(meta.channel || '').replace(/^@/,'')}` : '#');

  const avatar = getById('channelAvatar');
  if(avatar && meta.avatar){
    avatar.src = `./${meta.avatar}`;
    avatar.hidden = false;
    avatar.alt = title;
  } else if(avatar){
    avatar.hidden = true;
  }

  Common.bumpFavicons(meta.last_sync_utc || meta.last_seen_message_id || '');

  const avatarLink = getById('channelAvatarLink');
  if(avatarLink){
    avatarLink.hidden = !meta.avatar;
  }

  const subscribeButton = getById('subscribeBtn');
  if(subscribeButton){
    const subscribeLink = (subscribeLinkOverride || channelUrl || '').trim();
    if(subscribeLink && subscribeLink !== '#'){
      subscribeButton.href = subscribeLink;
      subscribeButton.hidden = false;
    } else {
      subscribeButton.hidden = true;
    }
  }

  // `siteTitleWrap` href is set by Common.applyHomeLinks() so GitHub Pages
  // project sites (https://<user>.github.io/<repo>/) work correctly.

  // Keep the title visible on narrow screens by compacting the subscribe button when needed.
  Common.initResponsiveHeader();

  // Meta badges removed from header; keep date in body only.
}

function renderPost(post){
  const container = getById('postContainer');
  if(!container) return;

  if(!post){
    container.innerHTML = '<p class="muted">Пост не найден. Вернитесь к списку и попробуйте другой идентификатор.</p>';
    return;
  }

  const telegramLink = post.link
    ? `<a href="${Common.escapeHtml(post.link)}" target="_blank" rel="noopener">Открыть в Telegram</a>`
    : '';

  const views = (typeof post.views === 'number') ? `${post.views.toLocaleString('ru-RU')} просмотров` : '';
  const reactions = (post.reactions && post.reactions.total) ? `${post.reactions.total.toLocaleString('ru-RU')} реакций` : '';
  const permalink = buildPermalink(post.id);
  const dateLink = `<a class="post-date" href="${Common.escapeHtml(permalink)}">${Common.escapeHtml(formatLocalDate(post.date))}</a>`;

  const bodyHtml = (post.html && post.html.trim().length > 0)
    ? post.html
    : (post.text
      ? `<p>${Common.escapeHtml(post.text).replaceAll('\n','<br>')}</p>`
      : '<p class="muted">[без текста]</p>');

  let mediaHtml = '';
  const mediaList = Array.isArray(post.media) ? Common.dedupeMedia(post.media) : [];
  if(mediaList.length){
    let imageIndex = 0;
    const renderedMedia = mediaList.map((mediaItem) => {
      const isImage = Common.isImageMedia(mediaItem);
      const html = Common.renderMediaItem(mediaItem, post.id, isImage ? imageIndex : null);
      if(isImage){
        imageIndex += 1;
      }
      return html;
    }).filter(Boolean);

    if(renderedMedia.length){
      mediaHtml = `<div class="media">${renderedMedia.join('')}</div>`;
    }
  }

  const links = [telegramLink, `<a href="${Common.escapeHtml(permalink)}">Ссылка на этот пост</a>`]
    .filter(Boolean)
    .join(' · ');

  const actions = `
    <div class="actions">
      <span>${Common.escapeHtml([views, reactions].filter(Boolean).join(' · '))}</span>
      <span class="action-links">${links}</span>
    </div>
  `;

  container.innerHTML = `
    <div class="post-header">
      <div class="right">${dateLink}</div>
    </div>
    <div class="post-body">${bodyHtml}${mediaHtml}</div>
    ${actions}
  `;

  Common.linkifyHashtags(container);
  applySeoTags(post, permalink, bodyHtml);
}

function updatePrevNextNavigation(post){
  if(!post) return;
  const idx = uiState.posts.findIndex((p) => String(p.id) === String(post.id));
  const newer = idx > 0 ? uiState.posts[idx - 1] : null;
  const older = idx >= 0 && idx < uiState.posts.length - 1 ? uiState.posts[idx + 1] : null;
  setPrevNextLink(getById('prevPost'), newer, '← Более новый');
  setPrevNextLink(getById('nextPost'), older, 'Более старый →');
}

function setPrevNextLink(node, post, label){
  if(!node) return;
  if(post){
    node.href = `./post.html?id=${encodeURIComponent(post.id)}`;
    node.textContent = label;
    node.classList.remove('disabled');
    node.style.visibility = 'visible';
  } else {
    node.href = '#';
    node.textContent = label;
    node.classList.add('disabled');
    node.style.visibility = 'hidden';
  }
}

async function loadSinglePostPage(){
  setStatusText('Загрузка…');
  const targetId = readPostIdFromUrl();
  if(!targetId){
    setStatusText('Не указан идентификатор поста.', 'notice-bad');
    return;
  }

  try{
    const configRequest = fetch(CONFIG_URL, { cache: 'no-store' }).catch(() => null);
    const metaRequest = fetch(META_URL, { cache: 'no-store' }).catch(() => null);

    const configResponse = await configRequest;
    const config = configResponse && configResponse.ok ? await configResponse.json() : {};

    const customSubscribe = (config.channel_specific_link || '').trim();
    if(customSubscribe){
      subscribeLinkOverride = customSubscribe;
    }

    const promoText = (config.promo_text || '').trim();
    if(promoText){
      promoBannerHtml = promoText;
    }

    Common.initPromoBanner(promoBannerHtml);
    const metaResponse = await metaRequest;
    const meta = metaResponse && metaResponse.ok ? await metaResponse.json() : {};

    const totalPages = Number(config.json_total_pages);
    const pageSize = Number(config.json_page_size);

    let post = null;
    let pageData = [];
    let currentPage = null;

    const fetchPage = async (pageNum) => {
      const res = await fetch(`${DATA_PAGES_BASE}/page-${pageNum}.json`, { cache: 'no-store' });
      if(!res.ok) throw new Error(`page ${pageNum} load failed`);
      const data = await res.json();
      if(!Array.isArray(data) || data.length === 0) throw new Error('page empty');
      return data;
    };

    if(Number.isFinite(totalPages) && totalPages > 0 && Number.isFinite(pageSize) && pageSize > 0){
      let low = 1;
      let high = totalPages;
      const targetNum = Number(targetId);

      while(low <= high){
        const mid = Math.floor((low + high) / 2);
        let data;
        try{
          data = await fetchPage(mid);
        }catch(err){
          console.warn('Paging failed, fallback to posts.json', err);
          low = high + 1;
          break;
        }

        const firstId = Number(data[0]?.id ?? 0);
        const lastId = Number(data[data.length - 1]?.id ?? 0);
        if(firstId === 0 && lastId === 0){
          break;
        }

        if(targetNum <= firstId && targetNum >= lastId){
          pageData = data;
          currentPage = mid;
          break;
        }

        if(targetNum > firstId){
          high = mid - 1;
        } else {
          low = mid + 1;
        }
      }

      if(pageData.length){
        uiState.posts = pageData;
        uiState.postById = new Map(pageData.map((p) => [String(p.id), p]));
        post = uiState.postById.get(String(targetId)) || null;

        const idx = post ? pageData.findIndex((p) => String(p.id) === String(targetId)) : -1;

        const loadNeighborPage = async (pageNum, pickFirst) => {
          if(pageNum < 1 || pageNum > totalPages) return null;
          const data = await fetchPage(pageNum);
          return pickFirst ? data[0] : data[data.length - 1];
        };

        // Preload nav neighbors across pages.
        if(idx === 0 && currentPage && currentPage > 1){
          const newer = await loadNeighborPage(currentPage - 1, true);
          if(newer) uiState.posts.unshift(newer);
        }

        if(idx === pageData.length - 1 && currentPage && currentPage < totalPages){
          const older = await loadNeighborPage(currentPage + 1, false);
          if(older) uiState.posts.push(older);
        }
      }
    }

    if(!post){
      const postsResponse = await fetch(POSTS_URL, { cache: 'no-store' });
      const posts = postsResponse.ok ? await postsResponse.json() : [];
      const rawPosts = Array.isArray(posts) ? posts : [];
      uiState.posts = rawPosts.slice().sort((a, b) => Number(b.id) - Number(a.id));
      uiState.postById = new Map(uiState.posts.map((p) => [String(p.id), p]));
      post = uiState.postById.get(String(targetId)) || uiState.postById.get(Number(targetId)) || null;
    }

    uiState.currentPost = post || null;
    renderHeaderMeta(meta, post);
    renderPost(post);
    updatePrevNextNavigation(post);
    setStatusText(post ? '' : 'Пост не найден.', post ? 'notice-ok' : 'notice-bad');
  }catch(err){
    console.error(err);
    setStatusText('Ошибка загрузки данных. Проверьте, что docs/data/posts.json доступен и валиден.', 'notice-bad');
  }
}

function bindPostPageUi(){
  const themeBtn = getById('themeToggle');
  if(themeBtn){
    themeBtn.addEventListener('click', () => Common.toggleTheme());
  }

  const container = getById('postContainer');
  if(container){
    container.addEventListener('click', (e) => {
      const clickedElement = e.target;
      const hashtagLink = clickedElement && typeof clickedElement.closest === 'function'
        ? clickedElement.closest('.hashtag')
        : null;

      if(hashtagLink){
        e.preventDefault();
        navigateToIndexWithTag(hashtagLink.getAttribute('data-tag') || hashtagLink.textContent);
        return;
      }

      if(clickedElement && clickedElement.classList && clickedElement.classList.contains('media-img')){
        const postId = clickedElement.getAttribute('data-post-id');
        const imageIndex = Number(clickedElement.getAttribute('data-image-index') || 0);
        openLightboxForPostId(postId, Number.isNaN(imageIndex) ? 0 : imageIndex);
      }
    });
  }
}

function applySeoTags(post, canonicalHref, bodyHtml){
  const head = document.head;
  if(!head || !post) return;

  const ensureTag = (selector, create) => {
    let node = head.querySelector(selector);
    if(!node && create){
      node = create();
      head.appendChild(node);
    }
    return node;
  };

  const plainText = (bodyHtml || post.text || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  const description = (plainText || '').slice(0, 200);

  const titleBase = Common.escapeHtml(getById('siteTitle')?.textContent || 'Telegram Mirror');
  const pageTitle = `${titleBase} — пост #${post.id}`;

  const canonical = post.link || canonicalHref || window.location.href;
  const canonicalTag = ensureTag('link[rel="canonical"]', () => document.createElement('link'));
  if(canonicalTag){
    canonicalTag.setAttribute('rel', 'canonical');
    canonicalTag.setAttribute('href', canonical);
  }

  document.title = pageTitle;

  const setMeta = (name, content, attr = 'name') => {
    if(!content) return;
    const selector = `meta[${attr}="${name}"]`;
    const node = ensureTag(selector, () => document.createElement('meta'));
    if(node){
      node.setAttribute(attr, name);
      node.setAttribute('content', content);
    }
  };

  setMeta('description', description);
  setMeta('robots', 'index,follow');
  setMeta('og:title', pageTitle, 'property');
  setMeta('og:description', description, 'property');
  setMeta('og:type', 'article', 'property');
  setMeta('og:url', canonical, 'property');
  setMeta('twitter:card', 'summary_large_image');
  setMeta('twitter:title', pageTitle);
  setMeta('twitter:description', description);

  const firstImage = (post.media || []).find(Common.isImageMedia);
  if(firstImage){
    const imgPath = firstImage.thumb || firstImage.path;
    if(imgPath){
      const url = new URL(`./${imgPath}`, window.location.href).toString();
      setMeta('og:image', url, 'property');
      setMeta('twitter:image', url);
    }
  }

  const ld = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: pageTitle,
    description,
    datePublished: post.date || '',
    dateModified: post.edited || post.date || '',
    mainEntityOfPage: canonical,
  };

  const ldNode = ensureTag('script[type="application/ld+json"]', () => {
    const script = document.createElement('script');
    script.setAttribute('type', 'application/ld+json');
    return script;
  });

  if(ldNode){
    ldNode.textContent = JSON.stringify(ld);
  }
}

Common.initTheme();
Common.applyHomeLinks();
bindPostPageUi();
loadSinglePostPage();
