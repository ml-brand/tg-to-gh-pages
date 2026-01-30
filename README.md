# Telegram → GitHub Pages Mirror

Fully automated Telegram channel mirror that syncs posts (plus media) into `docs/` and serves them on GitHub Pages — no servers, just Actions.

## Highlights
- Hourly GitHub Actions sync with editable cron (`.github/workflows/sync.yml`).
- Dynamic UI (`docs/index.html`) with search, hashtag filters, lightbox gallery, and load-more pagination.
- Static snapshot (`docs/static/`) rendered ahead of time for fast, JS-free browsing.
- RSS/Atom feeds, sitemap, robots.txt, channel avatar download, and favicon generation from the avatar.
- Optional media download with size/scope limits to keep the repo lean.

## Quick start (local setup)
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
PYTHONPATH=. python scripts/create_session.py   # produce TG_SESSION (StringSession)
```
What you need from https://my.telegram.org (API Development Tools):
- `TG_API_ID` (GitHub **Secrets**)
- `TG_API_HASH` (GitHub **Secrets**)
- `TG_SESSION` (output of the script, GitHub **Secrets**)
- `TG_CHANNEL` (e.g. `mychannel` or `https://t.me/mychannel`, GitHub **Variables**)

## Deploy on GitHub
1) Push the repo.  
2) Repo → Settings → Secrets and variables → Actions:  
   - **Secrets**: add `TG_API_ID`, `TG_API_HASH`, `TG_SESSION`.  
   - **Variables**: add `TG_CHANNEL`.  
3) Repo → Settings → Actions → General → Workflow permissions → **Read and write permissions**.  
4) Repo → Settings → Pages: Source **Deploy from a branch**, branch `main`, folder `/docs`.  
5) Run the workflow “Sync Telegram channel to GitHub Pages” manually once; only after that open the site.  
   RSS/Atom feeds and `docs/static/` are generated only if the repo variables `FEED` and `GENERATE_STATIC` are enabled.  
   Make sure required Secrets/Variables are set; otherwise CI will fail.

## Run locally (sync + serve)
```bash
export TG_API_ID=...
export TG_API_HASH=...
export TG_SESSION=...
export TG_CHANNEL=mychannel

PYTHONPATH=. python scripts/fetch_telegram.py         # fetch posts/media, write docs/data + assets
PYTHONPATH=. python scripts/build_feeds.py            # regenerate feed/sitemap/robots from saved data
PYTHONPATH=. python scripts/build_static.py           # optional: pre-render static HTML into docs/static/
python -m http.server --directory docs 8000
# open http://localhost:8000
```
CLI overrides (examples):
```bash
PYTHONPATH=. python scripts/fetch_telegram.py --dry-run --refresh-last-n 200 --initial-limit 2000
```

## Config knobs (env or workflow vars)
Required:
- `TG_API_ID` (Secrets): Telegram API ID.
- `TG_API_HASH` (Secrets): Telegram API hash.
- `TG_SESSION` (Secrets): Telethon `StringSession`.
- `TG_CHANNEL` (Variables): channel username or `https://t.me/<channel>`.

UI / frontend:
- `TG_CHANNEL_SPECIFIC_LINK`: override the Subscribe button URL.
- `PROMO_TEXT`: promo banner HTML/text (shown on index and post pages).
- `METRIKA_ID`: Yandex Metrika counter id.

Sync tuning:
- `DOWNLOAD_MEDIA` (`true`/`false`): store media in `docs/assets/media/`.
- `MEDIA_MAX_MB`: max file size to download (default 200).
- `MEDIA_DOWNLOAD_SCOPE`: max media download attempts per run (default 1000).
- `INITIAL_FETCH_LIMIT`: `0` = full history; set >0 to cap initial import (default 1000).
- `REFRESH_LAST_N`: re-fetch recent messages to catch edits (default 200).
- `MAX_RETRIES`: RPC/timeout retry attempts (default 5).
- `BACKOFF_SECONDS`: initial retry backoff with exponential growth (default 2.0).
- `LOG_LEVEL`: logging verbosity (default `INFO`).

Workflow toggles (repo variables):
- `GENERATE_STATIC`: pre-rendered static snapshot (default off).
- `SEO`: toggles sitemap/robots; maps to `GENERATE_SITE_FILES` env.
- `FEED`: toggles RSS/Atom; maps to `GENERATE_FEEDS` env.
- `GENERATE_SITE_FILES`: sitemap/robots generation (default off; when off, `robots.txt` has `Disallow: /`).
- `GENERATE_FEEDS`: RSS/Atom generation (default off).

## What lives where
- `docs/data/posts.json` — posts (newest-first in UI; stored oldest→newest on disk).
- `docs/data/meta.json` — channel info, stats, last seen ID, avatar path.
- `docs/assets/media/` — downloaded media; thumbnails under `thumbs/`.
- `docs/assets/channel_avatar.jpg` — channel avatar; also drives favicons (`docs/favicon.ico`, `favicon-32.png`, `apple-touch-icon.png`).
- `docs/feed.xml`, `docs/atom.xml`, `docs/sitemap.xml`, `docs/robots.txt` — generated site files.
- `docs/static/` — pre-rendered index + paginated pages + per-post pages.

## How it works
- `scripts/fetch_telegram.py`: pulls messages, merges albums, downloads media (if enabled), writes `posts.json`/`meta.json`, generates feeds/sitemap/robots (unless disabled).
- `scripts/build_static.py`: renders static HTML snapshot from stored data.
- GitHub Actions (`.github/workflows/sync.yml`): installs deps, fetches posts, detects data/media changes, builds static snapshot when needed, commits, and pushes.

## Tips & caveats
- “Hourly” schedule is approximate; GitHub may drift by a few minutes.
- Large media can bloat the repo. For heavy channels set `DOWNLOAD_MEDIA=false` or lower `MEDIA_MAX_MB` / `MEDIA_DOWNLOAD_SCOPE`.
- Private channels: ensure the account behind `TG_SESSION` has access (subscriber/member); remember GitHub Pages is public if the repo is public.

## License
CPAL-1.0 — see `LICENSE` for full terms (attribution required).
