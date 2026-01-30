#!/usr/bin/env python3
"""Generate a pre-rendered static HTML version of the Telegram mirror.

Reads `docs/data/posts.json` and `docs/data/meta.json` and outputs a fully
rendered site into `docs/static/` (index + per-post pages) that mirrors the
existing dynamic UI but without client-side fetching.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple
from urllib.parse import quote, urljoin

from scripts import models, paths, utils
from scripts.storage import load_meta, load_posts


DATE_FMT = "%Y-%m-%d %H:%M UTC"


def safe_json_dumps(data: Any) -> str:
    """Dump JSON that is safe to embed inside HTML."""
    raw = json.dumps(data, ensure_ascii=False)
    return (
        raw.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("</", "<\\/")
    )


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "")


def escape_attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


def escape_html(value: Any) -> str:
    return html.escape(str(value), quote=False)


def dedupe_media(media: Iterable[Mapping[str, Any]] | None) -> List[dict[str, Any]]:
    seen: set[Tuple[Any, Any, Any]] = set()
    out: List[dict[str, Any]] = []
    for item in media or []:
        key = (item.get("path"), item.get("kind"), item.get("mime"))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(item))
    return out


def format_date(iso: str | None, fmt: str = DATE_FMT) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime(fmt)
    except Exception:
        return iso


def load_config() -> Dict[str, Any]:
    if not paths.CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(paths.CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def search_text(post: models.PostDict) -> str:
    text = (post.get("text") or "") + " " + strip_tags(post.get("html") or "")
    return " ".join(text.split()).lower()


def adjust_media_paths(
    media_list: List[Dict[str, Any]], base: str
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in media_list or []:
        item = dict(m)
        path = item.get("path") or ""
        item["path"] = f"{base}{path}"
        if item.get("thumb"):
            item["thumb"] = f"{base}{item['thumb']}"
        out.append(item)
    return out


def render_media_item(
    media: Dict[str, Any], post_id: Any, image_index: int | None, base: str
) -> str:
    path = media.get("path")
    if not path:
        return ""
    kind = media.get("kind") or ""
    mime = (media.get("mime") or "").lower()
    name = media.get("name") or ""
    thumb = media.get("thumb") or ""

    src = f"{base}{escape_attr(path)}"
    idx_attr = f' data-image-index="{image_index}"' if image_index is not None else ""
    post_attr = f' data-post-id="{post_id}"'

    def looks_like_image() -> bool:
        p = str(path).lower()
        return (
            kind in {"photo", "image"}
            or mime.startswith("image/")
            or p.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
        )

    if looks_like_image():
        srcset = f"{base}{escape_attr(thumb)} 480w, {src} 1200w" if thumb else ""
        sizes = 'sizes="(max-width: 768px) 100vw, 800px"'
        main_src = f"{base}{escape_attr(thumb)}" if thumb else src
        srcset_attr = f' srcset="{srcset}"' if srcset else ""
        sizes_attr = f" {sizes}" if srcset else ""
        return f'<img class="media-img" loading="lazy" src="{main_src}"{srcset_attr}{sizes_attr} alt=""{post_attr}{idx_attr} />'
    if kind == "video":
        return f'<video controls preload="metadata" src="{src}"></video>'
    if kind == "audio":
        return f'<audio controls preload="metadata" src="{src}"></audio>'
    if kind == "document":
        if looks_like_image():
            return f'<img loading="lazy" src="{src}" alt="" />'
        label = name or "файл"
        return f'<a class="badge" href="{src}" target="_blank" rel="noopener">Скачать: {escape_html(label)}</a>'
    return f'<img class="media-img" loading="lazy" src="{src}" alt=""{post_attr}{idx_attr} />'


def render_post_card(
    post: models.PostDict, meta: models.MetaDict, media_base: str
) -> Tuple[str, Dict[str, Any]]:
    pid = post.get("id")
    permalink = f"./posts/{pid}.html"
    tg_link = post.get("link") or ""
    media_list = dedupe_media(post.get("media") or [])

    date_iso = post.get("date") or ""
    date_label = escape_html(format_date(date_iso))
    views = post.get("views")
    reactions = (post.get("reactions") or {}).get("total")
    views_label = (
        f"{views:,} просмотров".replace(",", " ") if isinstance(views, int) else ""
    )
    reactions_label = (
        f"{reactions:,} реакций".replace(",", " ") if isinstance(reactions, int) else ""
    )
    stat_label = " · ".join([v for v in (views_label, reactions_label) if v])

    if post.get("html"):
        body_html = post["html"]
    elif post.get("text"):
        safe_text = escape_html(post["text"]).replace("\n", "<br>")
        body_html = f"<p>{safe_text}</p>"
    else:
        body_html = '<p class="muted">[без текста]</p>'

    media_html_parts: List[str] = []
    image_idx = 0
    for m in media_list:
        idx = (
            image_idx
            if (
                m.get("kind") in {"photo", "image"}
                or (m.get("mime") or "").startswith("image/")
            )
            else None
        )
        media_html_parts.append(render_media_item(m, pid, idx, media_base))
        if idx is not None:
            image_idx += 1
    media_html = (
        f'<div class="media">{"".join(media_html_parts)}</div>'
        if media_html_parts
        else ""
    )

    action_links = []
    if tg_link:
        action_links.append(
            f'<a href="{escape_attr(tg_link)}" target="_blank" rel="noopener">Открыть в Telegram</a>'
        )
    action_links.append(f'<a href="{escape_attr(permalink)}">Открыть пост на сайте</a>')
    actions = " · ".join(action_links)

    card_html = f"""
    <article class=\"post\" data-post-id=\"{escape_attr(pid)}\" data-search=\"{escape_attr(search_text(post))}\">
      <div class=\"post-header\">
        <div class=\"left\"></div>
        <div class=\"right\"><a class=\"post-date\" data-iso-date=\"{escape_attr(date_iso)}\" href=\"{escape_attr(permalink)}\">{date_label}</a></div>
      </div>
      <div class=\"post-body\">{body_html}{media_html}</div>
      <div class=\"actions\">
        <span>{escape_html(stat_label)}</span>
        <span class=\"action-links\">{actions}</span>
      </div>
    </article>
    """
    light_post = {
        "id": pid,
        "media": adjust_media_paths(media_list, media_base),
    }
    return card_html, light_post


def page_filename(page: int) -> str:
    return "index.html" if page == 1 else f"page-{page}.html"


def pagination_links(current: int, total: int) -> str:
    parts: List[str] = []

    def add_page(p: int) -> None:
        cls = "page-link current" if p == current else "page-link"
        parts.append(
            f'<a class="{cls}" href="{escape_attr(page_filename(p))}">{escape_html(p)}</a>'
        )

    def add_ellipsis() -> None:
        parts.append('<span class="page-ellipsis">…</span>')

    if total <= 7:
        for p in range(1, total + 1):
            add_page(p)
    else:
        add_page(1)
        if current > 3:
            add_ellipsis()
        start = max(2, current - 1)
        end = min(total - 1, current + 1)
        for p in range(start, end + 1):
            add_page(p)
        if current < total - 2:
            add_ellipsis()
        add_page(total)

    return " ".join(parts)


def pager_html(current: int, total: int) -> str:
    prev_page = current - 1 if current > 1 else None
    next_page = current + 1 if current < total else None
    return f"""
    <div class=\"pager static-pager\" style=\"justify-content:center\">
      <div class=\"page-links\">
        <a class=\"nav-link{' disabled' if not prev_page else ''}\" href=\"{escape_attr(page_filename(prev_page) if prev_page else '#')}\">←</a>
        {pagination_links(current, total)}
        <a class=\"nav-link{' disabled' if not next_page else ''}\" href=\"{escape_attr(page_filename(next_page) if next_page else '#')}\">→</a>
      </div>
    </div>
    """


def favicon_links(base: str, version: str | None = None) -> str:
    suffix = f"?v={quote(version)}" if version else ""
    return (
        f'  <link rel="icon" href="{escape_attr(base + "favicon.ico" + suffix)}" sizes="any" />\n'
        f'  <link rel="icon" type="image/png" sizes="32x32" href="{escape_attr(base + "favicon-32.png" + suffix)}" />\n'
        f'  <link rel="apple-touch-icon" href="{escape_attr(base + "apple-touch-icon.png" + suffix)}" />\n'
    )


def telegram_url(meta: Dict[str, Any] | models.MetaDict) -> str:
    username = meta.get("username") or meta.get("channel") or ""
    if not username:
        return "#"
    username = str(username).lstrip("@")
    return f"https://t.me/{username}"


def metrika_script(base: str) -> str:
    return f'<script src="{escape_attr(base + "metrika.js")}"></script>'


def render_index_page(
    posts: List[models.PostDict],
    meta: models.MetaDict,
    page: int,
    total_pages: int,
    cfg: Dict[str, Any],
) -> str:
    cards: List[str] = []
    light_posts: List[Dict[str, Any]] = []
    for p in posts:
        card, lp = render_post_card(p, meta, "../")
        cards.append(card)
        light_posts.append(lp)

    title = meta.get("title") or "Telegram Mirror"
    avatar = meta.get("avatar")
    subscribe_url = (cfg.get("channel_specific_link") or "").strip() or telegram_url(
        meta
    )
    promo_text = (cfg.get("promo_text") or "").strip()
    pager = pager_html(page, total_pages)

    vtoken = (
        str(meta.get("last_sync_utc") or meta.get("last_seen_message_id") or "")
        .replace(" ", "")
        .strip()
    )

    html_out = f"""<!doctype html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>{escape_html(title)} — статическая версия (стр. {page}/{total_pages})</title>
  <meta name=\"description\" content=\"Статическая версия зеркала Telegram-канала\" />
{favicon_links('../', vtoken)}
  <link rel=\"stylesheet\" href=\"../style.css\" />
  {metrika_script('../')}
</head>
<body>
  <header class=\"header\">
    <div class=\"container\">
      <div class=\"title-grid\">
        <a class=\"grid-avatar\" href=\"#\" target=\"_blank\" rel=\"noopener\">
          <img id=\"channelAvatar\" class=\"channel-avatar\" src=\"{escape_attr('../' + avatar) if avatar else ''}\" alt=\"Аватар канала\" {'hidden' if not avatar else ''} />
        </a>
        <div class=\"grid-main\">
          <div class=\"title-head\">
            <div class=\"title-left\">
              <a class=\"badge-chip\" id=\"siteTitleWrap\" href=\"#\" target=\"_blank\" rel=\"noopener\"><h1 id=\"siteTitle\">{escape_html(title)}</h1></a>
            </div>
            <div class=\"hero-actions\">
              <a id=\"subscribeBtn\" class=\"subscribe-btn\" href=\"{escape_attr(subscribe_url)}\" target=\"_blank\" rel=\"noopener\" {'hidden' if subscribe_url == '#' or not subscribe_url else ''}>Подписаться</a>
              <a class=\"icon-btn\" href=\"../\" aria-label=\"Перейти к динамической версии\">↺</a>
              <button id=\"themeToggle\" class=\"icon-btn\" type=\"button\" aria-label=\"Переключить тему\"></button>
            </div>
          </div>
        </div>
        <div class=\"controls\"></div>
      </div>
    </div>
  </header>

  {f'''
  <div id="promoBanner" class="promo-banner" hidden>
    <div class="container promo-inner">
      <span class="promo-text">{promo_text}</span>
      <button id="promoClose" class="promo-close" type="button" aria-label="Скрыть плашку">×</button>
    </div>
  </div>
  ''' if promo_text else ''}

  <main class=\"container\">
    {pager}
    <div id=\"posts\" class=\"posts\">
      {"".join(cards) if cards else '<p class="muted">Постов пока нет.</p>'}
    </div>
    {pager}
  </main>

  <footer class=\"footer\">
    <div class=\"container\">
      <div class=\"footer-inner\">
        <span>based on <a href=\"https://github.com/ml-brand/tg-to-gh-pages\" target=\"_blank\" rel=\"noopener\">tg-to-gh-pages</a> (created by <a href=\"https://github.com/ml-brand\" target=\"_blank\" rel=\"noopener\">ML Brand</a>)</span>
        <a id=\"repoLink\" href=\"https://github.com/ml-brand/tg-to-gh-pages\" target=\"_blank\" rel=\"noopener\">Do the same with your channel.</a>
        <span class=\"footer-links\">
          static copy ·
          <a href=\"../feed.xml\" target=\"_blank\" rel=\"noopener\">RSS</a> ·
          <a href=\"../atom.xml\" target=\"_blank\" rel=\"noopener\">Atom</a>
        </span>
      </div>
    </div>
  </footer>

  <script>
    window.__STATIC_POSTS = {safe_json_dumps(light_posts)};
    window.__STATIC_META = {safe_json_dumps(meta)};
  </script>
  <script src=\"../common.js\"></script>
  <script src=\"../static.js\"></script>
</body>
</html>
"""
    return html_out


def render_post_page(
    post: models.PostDict,
    meta: models.MetaDict,
    prev_post: models.PostDict | None,
    next_post: models.PostDict | None,
    index_href: str,
    site_url: str,
    cfg: Dict[str, Any],
) -> str:
    pid = post.get("id")
    title = meta.get("title") or "Telegram Mirror"
    avatar = meta.get("avatar")
    subscribe_url = (cfg.get("channel_specific_link") or "").strip() or telegram_url(
        meta
    )
    back_href = index_href
    media_list = dedupe_media(post.get("media") or [])

    date_iso = post.get("date") or ""
    date_label = escape_html(format_date(date_iso))
    tg_link = post.get("link") or ""
    views = post.get("views")
    reactions = (post.get("reactions") or {}).get("total")
    views_label = (
        f"{views:,} просмотров".replace(",", " ") if isinstance(views, int) else ""
    )
    reactions_label = (
        f"{reactions:,} реакций".replace(",", " ") if isinstance(reactions, int) else ""
    )
    stat_label = " · ".join([v for v in (views_label, reactions_label) if v])

    description = strip_tags(post.get("html") or post.get("text") or "")[:200]

    if post.get("html"):
        body_html = post["html"]
    elif post.get("text"):
        safe_text = escape_html(post["text"]).replace("\n", "<br>")
        body_html = f"<p>{safe_text}</p>"
    else:
        body_html = '<p class="muted">[без текста]</p>'

    media_html_parts: List[str] = []
    image_idx = 0
    for m in media_list:
        idx = (
            image_idx
            if (
                m.get("kind") in {"photo", "image"}
                or (m.get("mime") or "").startswith("image/")
            )
            else None
        )
        media_html_parts.append(render_media_item(m, pid, idx, "../../"))
        if idx is not None:
            image_idx += 1
    media_html = (
        f'<div class="media">{"".join(media_html_parts)}</div>'
        if media_html_parts
        else ""
    )

    links = []
    if tg_link:
        links.append(
            f'<a href="{escape_attr(tg_link)}" target="_blank" rel="noopener">Открыть в Telegram</a>'
        )
    links.append(f'<a href="{escape_attr(back_href)}">К списку постов</a>')
    links.append(f'<a href="{escape_attr(f"./{pid}.html")}">Ссылка на этот пост</a>')

    prev_href = f"./{prev_post.get('id')}.html" if prev_post else "#"
    next_href = f"./{next_post.get('id')}.html" if next_post else "#"

    og_image = ""
    og_image_url = ""
    if media_list:
        first_media = media_list[0]
        og_src = first_media.get("thumb") or first_media.get("path") or ""
        if og_src:
            og_image_url = og_src
            og_image = (
                f'<meta property="og:image" content="{escape_attr(og_image_url)}" />'
            )
            og_image += (
                f'\n  <meta property="og:image:alt" content="{escape_attr(title)}" />'
            )

    canonical_href = tg_link or f"{index_href.rsplit('/',1)[0]}/posts/{pid}.html"
    if site_url:
        canonical_href = urljoin(site_url, f"static/posts/{pid}.html")
        if og_image_url:
            og_image_url = urljoin(site_url, og_image_url)
            og_image = (
                f'<meta property="og:image" content="{escape_attr(og_image_url)}" />'
            )
            og_image += (
                f'\n  <meta property="og:image:alt" content="{escape_attr(title)}" />'
            )

    twitter_card = (
        '<meta name="twitter:card" content="summary_large_image" />'
        if og_image_url
        else '<meta name="twitter:card" content="summary" />'
    )
    twitter_image = (
        f'<meta name="twitter:image" content="{escape_attr(og_image_url)}" />'
        if og_image_url
        else ""
    )

    promo_text = (cfg.get("promo_text") or "").strip()

    html_out = f"""<!doctype html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>{escape_html(title)} — пост #{escape_html(pid)}</title>
  <meta name=\"description\" content=\"{escape_html(description)}\" />
{favicon_links('../../')}
  <link rel=\"canonical\" href=\"{canonical_href}\" />
  <meta property=\"og:type\" content=\"article\" />
  <meta property=\"og:title\" content=\"{escape_html(title)} — пост #{escape_html(pid)}\" />
  <meta property=\"og:description\" content=\"{escape_html(description)}\" />
  {og_image}
  <meta property=\"article:published_time\" content=\"{escape_attr(date_iso)}\" />
  <meta property=\"article:author\" content=\"{escape_html(title)}\" />
  {twitter_card}
  {twitter_image}
  <link rel=\"stylesheet\" href=\"../../style.css\" />
  {metrika_script('../../')}
</head>
<body data-index-href=\"{escape_attr(back_href)}\">
  <header class=\"header\">
    <div class=\"container\">
      <div class=\"title-grid single-title\">
        <a class=\"grid-avatar\" href=\"#\" target=\"_blank\" rel=\"noopener\">
          <img id=\"channelAvatar\" class=\"channel-avatar\" src=\"{escape_attr('../../' + avatar) if avatar else ''}\" alt=\"Аватар канала\" {'hidden' if not avatar else ''} />
        </a>
        <div class=\"grid-main\">
          <div class=\"title-head\">
            <a class=\"back-link\" href=\"{back_href}\">← Ко всем постам</a>
            <a class=\"badge-chip\" id=\"siteTitleWrap\" href=\"#\" target=\"_blank\" rel=\"noopener\"><h1 id=\"siteTitle\">{escape_html(title)}</h1></a>
            <div class=\"hero-actions\">
              <a id=\"subscribeBtn\" class=\"subscribe-btn\" href=\"{escape_attr(subscribe_url)}\" target=\"_blank\" rel=\"noopener\" {'hidden' if subscribe_url == '#' or not subscribe_url else ''}>Подписаться</a>
              <a class=\"icon-btn\" href=\"../../post.html?id={escape_attr(pid)}\" aria-label=\"Открыть динамическую страницу поста\">↺</a>
              <button id=\"themeToggle\" class=\"icon-btn\" type=\"button\" aria-label=\"Переключить тему\"></button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </header>

  {f'''
  <div id="promoBanner" class="promo-banner" hidden>
    <div class="container promo-inner">
      <span class="promo-text">{promo_text}</span>
      <button id="promoClose" class="promo-close" type="button" aria-label="Скрыть плашку">×</button>
    </div>
  </div>
  ''' if promo_text else ''}

  <main class=\"container single-page\">
    <article id=\"postContainer\" class=\"post post-page\" data-post-id=\"{escape_attr(pid)}\">\n      <div class=\"post-header\">\n        <div class=\"right\"><span class=\"post-date\" data-iso-date=\"{escape_attr(date_iso)}\">{date_label}</span></div>\n      </div>\n      <div class=\"post-body\">{body_html}{media_html}</div>\n      <div class=\"actions\">\n        <span>{escape_html(stat_label)}</span>\n        <span class=\"action-links\">{' · '.join(links)}</span>\n      </div>\n    </article>

    <div class=\"pager single-nav\">
      <a id=\"prevPost\" class=\"nav-link{' disabled' if not prev_post else ''}\" href=\"{escape_attr(prev_href)}\" style=\"{'visibility:hidden' if not prev_post else 'visibility:visible'}\">← Более новый</a>
      <a id=\"nextPost\" class=\"nav-link{' disabled' if not next_post else ''}\" href=\"{escape_attr(next_href)}\" style=\"{'visibility:hidden' if not next_post else 'visibility:visible'}\">Более старый →</a>
    </div>
  </main>

  <footer class=\"footer\">
    <div class=\"container\">
      <div class=\"footer-inner\">
        <span>based on <a href=\"https://github.com/ml-brand/tg-to-gh-pages\" target=\"_blank\" rel=\"noopener\">tg-to-gh-pages</a> (created by <a href=\"https://github.com/ml-brand\" target=\"_blank\" rel=\"noopener\">ML Brand</a>)</span>
        <a id=\"repoLink\" href=\"https://github.com/ml-brand/tg-to-gh-pages\" target=\"_blank\" rel=\"noopener\">Do the same with your channel.</a>
        <span class=\"footer-links\">
          static copy ·
          <a href=\"../../feed.xml\" target=\"_blank\" rel=\"noopener\">RSS</a> ·
          <a href=\"../../atom.xml\" target=\"_blank\" rel=\"noopener\">Atom</a>
        </span>
      </div>
    </div>
  </footer>

  <script>
    window.__STATIC_POSTS = [{safe_json_dumps({'id': pid, 'media': adjust_media_paths(media_list, '../../')})}];
    window.__STATIC_META = {safe_json_dumps(meta)};
  </script>
  <script src=\"../../common.js\"></script>
  <script src=\"../../static.js\"></script>
</body>
</html>
"""
    return html_out


def build_static(output_dir: Path | None = None) -> None:
    posts_by_id: Dict[int, models.PostDict] = load_posts()
    meta: models.MetaDict = load_meta()
    cfg = load_config()
    page_size = int(
        cfg.get("static_page_size") or cfg.get("page_size") or paths.STATIC_PAGE_SIZE
    )
    site_url = (cfg.get("site_url") or "").strip()
    if not site_url:
        site_url = utils.infer_github_pages_url()
    if page_size <= 0:
        page_size = paths.STATIC_PAGE_SIZE

    posts_sorted = sorted(
        posts_by_id.values(), key=lambda p: int(p.get("id", 0)), reverse=True
    )

    out_dir = output_dir or paths.STATIC_DIR
    posts_dir = paths.STATIC_POSTS_DIR if output_dir is None else out_dir / "posts"

    if out_dir.exists():
        shutil.rmtree(out_dir)
    posts_dir.mkdir(parents=True, exist_ok=True)

    total_pages = max(1, ceil(len(posts_sorted) / page_size)) if posts_sorted else 1
    post_to_page: Dict[int, int] = {}
    for idx, post in enumerate(posts_sorted):
        pid = int(post.get("id", 0))
        post_to_page[pid] = (idx // page_size) + 1

    for page in range(1, total_pages + 1):
        start = (page - 1) * page_size
        end = start + page_size
        slice_posts = posts_sorted[start:end]
        index_html = render_index_page(slice_posts, meta, page, total_pages, cfg)
        (out_dir / page_filename(page)).write_text(index_html, encoding="utf-8")

    for idx, post in enumerate(posts_sorted):
        prev_post = posts_sorted[idx - 1] if idx > 0 else None
        next_post = posts_sorted[idx + 1] if idx + 1 < len(posts_sorted) else None
        page_num = post_to_page.get(int(post.get("id", 0)), 1)
        index_href = f"../{page_filename(page_num)}"
        page_html = render_post_page(
            post, meta, prev_post, next_post, index_href, site_url, cfg
        )
        (posts_dir / f"{post.get('id')}.html").write_text(page_html, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build static HTML version of the Telegram mirror."
    )
    parser.add_argument(
        "--output", type=Path, help="Custom output directory (default: docs/static)."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_static(args.output)


if __name__ == "__main__":
    main()
