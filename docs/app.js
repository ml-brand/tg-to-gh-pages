/* Minimal client-side renderer for docs/data/posts.json */

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
  filteredPosts: [],
  pageSize: 30,
  renderedCount: 0,
  jsonPages: {
    total: 0,
    size: 0,
  },
  searchQuery: '',
  postById: new Map(),
};

let subscribeLinkOverride = '';
let promoBannerHtml = '';

function escapeRegExp(str){
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function clearSearchHighlights(rootNode){
  if(!rootNode) return;
  const marks = rootNode.querySelectorAll('mark.search-hit');
  marks.forEach((mark) => {
    const parent = mark.parentNode;
    if(!parent) return;
    parent.replaceChild(document.createTextNode(mark.textContent || ''), mark);
    parent.normalize();
  });
}

function highlightSearchMatchesInCard(cardNode, query){
  if(!cardNode) return;
  const body = cardNode.querySelector('.post-body');
  if(!body) return;

  clearSearchHighlights(body);

  const queryText = (query || '').trim();
  if(!queryText) return;

  const lowerQuery = queryText.toLowerCase();
  if(!body.textContent || !body.textContent.toLowerCase().includes(lowerQuery)) return;

  const queryRe = new RegExp(escapeRegExp(queryText), 'gi');
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
    acceptNode(node){
      if(!node || !node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      const parent = node.parentElement;
      if(!parent) return NodeFilter.FILTER_REJECT;
      if(parent.closest('mark.search-hit')) return NodeFilter.FILTER_REJECT;
      if(parent.closest('script') || parent.closest('style')) return NodeFilter.FILTER_REJECT;
      return node.nodeValue.toLowerCase().includes(lowerQuery)
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_REJECT;
    }
  });

  const targetTextNodes = [];
  let currentNode;
  while((currentNode = walker.nextNode())){
    targetTextNodes.push(currentNode);
  }

  for(const textNode of targetTextNodes){
    const originalText = textNode.nodeValue || '';
    queryRe.lastIndex = 0;
    const fragment = document.createDocumentFragment();
    let lastIndex = 0;
    let match;

    while((match = queryRe.exec(originalText))){
      const start = match.index;
      if(start > lastIndex){
        fragment.append(originalText.slice(lastIndex, start));
      }
      const mark = document.createElement('mark');
      mark.className = 'search-hit';
      mark.textContent = match[0];
      fragment.append(mark);
      lastIndex = start + match[0].length;
    }

    if(lastIndex < originalText.length){
      fragment.append(originalText.slice(lastIndex));
    }

    if(textNode.parentNode){
      textNode.parentNode.replaceChild(fragment, textNode);
    }
  }
}

function applySearchFilter(){
  const normalizedQuery = uiState.searchQuery.trim().toLowerCase();
  let filteredPosts = uiState.posts;

  if(normalizedQuery){
    filteredPosts = filteredPosts.filter((post) => (post.text || '').toLowerCase().includes(normalizedQuery));
  }

  uiState.filteredPosts = filteredPosts;
  uiState.renderedCount = 0;
  getById('posts').innerHTML = '';
}

function onHashtagClick(tag){
  const searchInput = getById('searchInput');
  const normalized = normalizeHashtag(tag);
  if(!searchInput || !normalized) return;

  searchInput.value = normalized;
  uiState.searchQuery = normalized;
  applySearchFilter();
  renderNextPostsPage();
  searchInput.focus();
}

function readInitialQueryFromUrl(){
  try{
    const params = new URLSearchParams(window.location.search);
    const rawQuery = params.get('q') || params.get('search') || params.get('tag');
    return rawQuery ? rawQuery.trim() : '';
  }catch(e){
    return '';
  }
}


function renderNextPostsPage(){
  const container = getById('posts');
  const postsSlice = uiState.filteredPosts.slice(
    uiState.renderedCount,
    uiState.renderedCount + uiState.pageSize,
  );

  for(const post of postsSlice){
    const card = document.createElement('article');
    card.className = 'post';

    const telegramLink = post.link
      ? `<a href="${Common.escapeHtml(post.link)}" target="_blank" rel="noopener">Открыть в Telegram</a>`
      : '';
    const permalink = `./post.html?id=${encodeURIComponent(post.id)}`;
    const dateLabel = Common.escapeHtml(formatLocalDate(post.date));
    const actionLinks = [telegramLink, `<a href="${permalink}">Открыть пост на сайте</a>`]
      .filter(Boolean)
      .join(' · ');
    const views = (typeof post.views === 'number') ? `${post.views.toLocaleString('ru-RU')} просмотров` : '';
    const reactions = (post.reactions && post.reactions.total) ? `${post.reactions.total.toLocaleString('ru-RU')} реакций` : '';

    const header = `
      <div class="post-header">
        <div class="left"></div>
        <div class="right"><a class="post-date" href="${permalink}">${dateLabel}</a></div>
      </div>
    `;

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

    const actions = `
      <div class="actions">
        <span>${Common.escapeHtml([views, reactions].filter(Boolean).join(' · '))}</span>
        <span class="action-links">${actionLinks}</span>
      </div>
    `;

    card.innerHTML = header + `<div class="post-body">${bodyHtml}${mediaHtml}</div>` + actions;
    Common.linkifyHashtags(card);
    highlightSearchMatchesInCard(card, uiState.searchQuery);
    container.appendChild(card);
  }

  uiState.renderedCount += postsSlice.length;

  const remaining = uiState.filteredPosts.length - uiState.renderedCount;
  const loadMoreButton = getById('loadMoreBtn');
  loadMoreButton.disabled = remaining <= 0;
  loadMoreButton.textContent = remaining > 0 ? `Показать ещё (${remaining})` : 'Больше нет постов';
}

async function loadIndexData(){
  setStatusText('Загрузка…');

  try{
    const configRequest = fetch(CONFIG_URL, { cache: 'no-store' }).catch(() => null);
    const metaRequest = fetch(META_URL, { cache: 'no-store' }).catch(() => null);

    const configResponse = await configRequest;
    const config = configResponse && configResponse.ok ? await configResponse.json() : {};

    const configuredPageSize = Number(config.page_size || config.static_page_size);
    if(Number.isFinite(configuredPageSize) && configuredPageSize > 0){
      uiState.pageSize = configuredPageSize;
    }

    const customSubscribe = (config.channel_specific_link || '').trim();
    if(customSubscribe){
      subscribeLinkOverride = customSubscribe;
    }

    const promoText = (config.promo_text || '').trim();
    if(promoText){
      promoBannerHtml = promoText;
    }
    Common.initPromoBanner(promoBannerHtml);

    const jsonPageSize = Number(config.json_page_size);
    const jsonTotalPages = Number(config.json_total_pages);
    if(Number.isFinite(jsonPageSize) && jsonPageSize > 0 && Number.isFinite(jsonTotalPages) && jsonTotalPages > 0){
      uiState.jsonPages.size = jsonPageSize;
      uiState.jsonPages.total = jsonTotalPages;
    }

    const metaResponse = await metaRequest;
    const meta = metaResponse && metaResponse.ok ? await metaResponse.json() : {};
    Common.bumpFavicons(meta.last_sync_utc || meta.last_seen_message_id || '');

    let postsData = [];
    let loadedViaJsonPages = false;

    if(uiState.jsonPages.total > 0){
      const allPages = [];
      for(let pageNum = 1; pageNum <= uiState.jsonPages.total; pageNum++){
        setStatusText(`Загрузка страниц (${pageNum}/${uiState.jsonPages.total})…`);
        try{
          const res = await fetch(`${DATA_PAGES_BASE}/page-${pageNum}.json`, { cache: 'no-store' });
          if(!res.ok) throw new Error(`Page ${pageNum} not found`);
          const data = await res.json();
          if(Array.isArray(data)) allPages.push(...data);
        }catch(e){
          console.warn('Paging load failed, will fall back to posts.json', e);
          allPages.length = 0;
          break;
        }
      }

      if(allPages.length){
        postsData = allPages;
        loadedViaJsonPages = true;
      }
    }

    if(!loadedViaJsonPages){
      setStatusText('Загрузка всех постов…');
      const postsResponse = await fetch(POSTS_URL, { cache: 'no-store' });
      postsData = postsResponse.ok ? await postsResponse.json() : [];
    }

    const rawPosts = Array.isArray(postsData) ? postsData : [];
    // Ensure newest-first order for UI (storage keeps oldest->newest).
    uiState.posts = rawPosts.slice().sort((a, b) => Number(b.id) - Number(a.id));
    uiState.postById = new Map(uiState.posts.map((post) => [String(post.id), post]));

    applySearchFilter();
    renderNextPostsPage();

    // meta UI
    const title = meta.title || 'Telegram Mirror';
    getById('siteTitle').textContent = title;
    document.title = title;

    const avatar = getById('channelAvatar');
    const channelUrl = meta.username
      ? `https://t.me/${meta.username}`
      : (meta.channel ? `https://t.me/${(meta.channel || '').replace(/^@/,'')}` : '#');

    if(avatar && meta.avatar){
      avatar.src = `./${meta.avatar}`;
      avatar.hidden = false;
      avatar.alt = title;
    } else if(avatar){
      avatar.hidden = true;
    }

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

    setStatusText('', 'notice-ok');
  }catch(err){
    console.error(err);
    setStatusText('Ошибка загрузки данных. Проверьте, что docs/data/posts.json доступен и валиден.', 'notice-bad');
  }
}

function bindIndexUi(){
  const themeButton = getById('themeToggle');
  if(themeButton){
    themeButton.addEventListener('click', () => Common.toggleTheme());
  }

  getById('searchInput').addEventListener('input', (e) => {
    uiState.searchQuery = e.target.value || '';
    applySearchFilter();
    renderNextPostsPage();
  });

  getById('loadMoreBtn').addEventListener('click', () => renderNextPostsPage());

  getById('posts').addEventListener('click', (e) => {
    const clickedElement = e.target;
    const hashtagLink = clickedElement && typeof clickedElement.closest === 'function'
      ? clickedElement.closest('.hashtag')
      : null;

    if(hashtagLink){
      e.preventDefault();
      onHashtagClick(hashtagLink.getAttribute('data-tag') || hashtagLink.textContent);
      return;
    }

    if(clickedElement && clickedElement.classList && clickedElement.classList.contains('media-img')){
      const postId = clickedElement.getAttribute('data-post-id');
      const imageIndex = Number(clickedElement.getAttribute('data-image-index') || 0);
      const post = uiState.postById.get(String(postId)) || uiState.postById.get(Number(postId));
      Common.openLightboxForPost(post, Number.isNaN(imageIndex) ? 0 : imageIndex);
    }
  });
}

Common.initTheme();
Common.applyHomeLinks();
bindIndexUi();

const seededQuery = readInitialQueryFromUrl();
if(seededQuery){
  const input = getById('searchInput');
  if(input) input.value = seededQuery;
  uiState.searchQuery = seededQuery;
}

loadIndexData();
