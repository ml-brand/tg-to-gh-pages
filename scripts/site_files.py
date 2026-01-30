import logging
import math
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

from . import models, paths, utils


def sanitize_feed_html(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"</?tg-emoji[^>]*>", "", value)


def post_title(post: models.PostDict) -> str:
    text = (post.get("text") or "").strip()
    if text:
        line = text.splitlines()[0].strip()
        return line[:120] if len(line) > 120 else line
    return f"Post #{post.get('id')}"


def post_link(post: models.PostDict, base_url: str) -> str:
    if post.get("link"):
        return str(post["link"])
    return urljoin(base_url, f"post.html?id={post.get('id')}")


def feed_items(posts_by_id: Dict[int, models.PostDict]) -> List[models.PostDict]:
    posts: List[models.PostDict] = list(posts_by_id.values())
    posts.sort(
        key=lambda p: utils.iso_to_dt(p.get("date"))
        or datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    return posts[: paths.FEED_ITEMS_LIMIT]


def write_rss(
    meta: models.MetaDict,
    posts_by_id: Dict[int, models.PostDict],
    channel: str,
    site_url: str = "",
) -> None:
    base_url = utils.site_base_url(meta, channel, site_url)
    items = feed_items(posts_by_id)
    if not items:
        return

    from xml.etree import ElementTree as ET

    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

    rss = ET.Element("rss", version="2.0")
    channel_el = ET.SubElement(rss, "channel")
    ET.SubElement(channel_el, "title").text = (
        meta.get("title") or f"Telegram — {channel}"
    )
    ET.SubElement(channel_el, "link").text = base_url
    ET.SubElement(channel_el, "description").text = f"Зеркало Telegram-канала {channel}"
    ET.SubElement(
        channel_el,
        "{http://www.w3.org/2005/Atom}link",
        attrib={
            "href": urljoin(base_url, "feed.xml"),
            "rel": "self",
            "type": "application/rss+xml",
        },
    )
    if meta.get("last_sync_utc"):
        dt = utils.iso_to_dt(meta["last_sync_utc"])
        if dt:
            ET.SubElement(channel_el, "lastBuildDate").text = format_datetime(dt)

    for p in items:
        item = ET.SubElement(channel_el, "item")
        ET.SubElement(item, "title").text = post_title(p)
        link = post_link(p, base_url)
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid").text = link
        pub_dt = utils.iso_to_dt(p.get("date")) or datetime.now(timezone.utc)
        ET.SubElement(item, "pubDate").text = format_datetime(pub_dt)
        desc = sanitize_feed_html(p.get("html") or p.get("text") or "")
        ET.SubElement(item, "description").text = desc

    paths.RSS_PATH.write_bytes(ET.tostring(rss, encoding="utf-8", xml_declaration=True))


def write_atom(
    meta: models.MetaDict,
    posts_by_id: Dict[int, models.PostDict],
    channel: str,
    site_url: str = "",
) -> None:
    base_url = utils.site_base_url(meta, channel, site_url)
    items = feed_items(posts_by_id)
    if not items:
        return

    from xml.etree import ElementTree as ET

    feed = ET.Element("feed", xmlns="http://www.w3.org/2005/Atom")
    ET.SubElement(feed, "title").text = meta.get("title") or f"Telegram — {channel}"
    ET.SubElement(feed, "link", href=base_url, rel="alternate")
    ET.SubElement(
        feed,
        "link",
        href=urljoin(base_url, "atom.xml"),
        rel="self",
        type="application/atom+xml",
    )
    ET.SubElement(feed, "id").text = base_url
    updated_dt = (
        utils.iso_to_dt(meta.get("last_sync_utc"))
        or utils.iso_to_dt(items[0].get("date"))
        or datetime.now(timezone.utc)
    )
    ET.SubElement(feed, "updated").text = updated_dt.isoformat()

    for p in items:
        entry = ET.SubElement(feed, "entry")
        ET.SubElement(entry, "title").text = post_title(p)
        link = post_link(p, base_url)
        ET.SubElement(entry, "link", href=link)
        ET.SubElement(entry, "id").text = link
        author = ET.SubElement(entry, "author")
        ET.SubElement(author, "name").text = (
            meta.get("title") or channel or "Telegram channel"
        )
        published = utils.iso_to_dt(p.get("date"))
        if published:
            ET.SubElement(entry, "updated").text = published.isoformat()
            ET.SubElement(entry, "published").text = published.isoformat()
        content = sanitize_feed_html(p.get("html") or p.get("text") or "")
        c_el = ET.SubElement(entry, "content", type="html")
        c_el.text = content

    paths.ATOM_PATH.write_bytes(
        ET.tostring(feed, encoding="utf-8", xml_declaration=True)
    )


def write_feeds(
    meta: models.MetaDict,
    posts_by_id: Dict[int, models.PostDict],
    channel: str,
    site_url: str = "",
) -> None:
    try:
        write_rss(meta, posts_by_id, channel, site_url)
        write_atom(meta, posts_by_id, channel, site_url)
    except Exception as e:
        logging.getLogger("telegram_mirror").warning("Failed to generate feeds: %s", e)


def write_sitemap(
    meta: models.MetaDict,
    posts_by_id: Dict[int, models.PostDict],
    channel: str,
    site_url: str = "",
) -> None:
    base_url = utils.site_base_url(meta, channel, site_url)
    items = list(posts_by_id.values())
    items.sort(
        key=lambda p: utils.iso_to_dt(p.get("date"))
        or datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    if paths.SITEMAP_ITEMS_LIMIT and len(items) > paths.SITEMAP_ITEMS_LIMIT:
        items = items[: paths.SITEMAP_ITEMS_LIMIT]

    from xml.etree import ElementTree as ET

    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    def add_url(loc: str, lastmod_value: Optional[str]) -> None:
        if not loc:
            return
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = loc
        if lastmod_value:
            ET.SubElement(url_el, "lastmod").text = lastmod_value

    last_sync_dt = utils.iso_to_dt(meta.get("last_sync_utc"))
    last_sync = utils.fmt_lastmod(last_sync_dt)
    add_url(base_url, last_sync)
    add_url(urljoin(base_url, "feed.xml"), last_sync)
    add_url(urljoin(base_url, "atom.xml"), last_sync)

    total_pages = max(1, math.ceil(len(items) / paths.STATIC_PAGE_SIZE)) if items else 1
    for page in range(1, total_pages + 1):
        path = "static/" if page == 1 else f"static/page-{page}.html"
        add_url(urljoin(base_url, path), last_sync)

    for p in items:
        loc = urljoin(base_url, f"post.html?id={p.get('id')}")
        lm = utils.fmt_lastmod(utils.iso_to_dt(p.get("edited") or p.get("date")))
        add_url(loc, lm)
        add_url(urljoin(base_url, f"static/posts/{p.get('id')}.html"), lm)

    paths.SITEMAP_PATH.write_bytes(
        ET.tostring(urlset, encoding="utf-8", xml_declaration=True)
    )


def write_robots(
    meta: models.MetaDict, channel: str, site_url: str = "", allow_index: bool = True
) -> None:
    base_url = utils.site_base_url(meta, channel, site_url)
    if allow_index:
        lines = [
            "# Robots file is auto-generated; base URL is inferred from GitHub Pages when available.",
            "User-agent: *",
            "Allow: /",
            "Allow: /static/",
            "",
            f"Sitemap: {urljoin(base_url, 'sitemap.xml')}",
            f"Sitemap: {urljoin(base_url, 'feed.xml')}",
            f"Sitemap: {urljoin(base_url, 'atom.xml')}",
            "",
        ]
    else:
        lines = [
            "# Robots file is auto-generated; set SEO=true to allow crawling.",
            "User-agent: *",
            "Disallow: /",
            "",
        ]
    paths.ROBOTS_PATH.write_text("\n".join(lines), encoding="utf-8")
