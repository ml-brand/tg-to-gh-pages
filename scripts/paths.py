from pathlib import Path

# Shared filesystem locations for the Telegram mirror.
ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA_DIR = DOCS / "data"
ASSETS_DIR = DOCS / "assets" / "media"
STATIC_DIR = DOCS / "static"
STATIC_POSTS_DIR = STATIC_DIR / "posts"

POSTS_PATH = DATA_DIR / "posts.json"
META_PATH = DATA_DIR / "meta.json"
CONFIG_PATH = DATA_DIR / "config.json"
PAGES_DIR = DATA_DIR / "pages"

RSS_PATH = DOCS / "feed.xml"
ATOM_PATH = DOCS / "atom.xml"
SITEMAP_PATH = DOCS / "sitemap.xml"
ROBOTS_PATH = DOCS / "robots.txt"
AVATAR_PATH = DOCS / "assets" / "channel_avatar.jpg"

STATIC_PAGE_SIZE = 30
JSON_PAGE_SIZE = 500
FEED_ITEMS_LIMIT = 50
SITEMAP_ITEMS_LIMIT = 1000
