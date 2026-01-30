# AGENTS.md — Codex instructions

This repository is a **Telegram → GitHub Pages mirror**. GitHub Actions periodically fetches a Telegram channel (Telethon) and publishes a static site from the `docs/` folder.

The most common failure mode for automated edits is **accidentally regenerating huge outputs** under `docs/`. Follow the constraints below.

---

## 1) Prime directives (read first)

1. **Minimize churn in generated files.**
   - Do not rewrite JSON formatting, reorder lists, or rebuild `docs/static/` unless the task explicitly requires it.
2. **Do not touch the network unless asked.**
   - `scripts/fetch_telegram.py` requires Telegram credentials and performs network I/O.
3. **Never leak secrets.**
   - Do not print, log, or commit `TG_SESSION`, `TG_API_HASH`, `.env`, tokens, etc.
4. **Match CI exactly.**
   - If CI runs it (`.github/workflows/quality.yml`), your change must pass it.

---

## 2) Project map

### Source code

- `scripts/fetch_telegram.py` — main sync entrypoint
- `scripts/create_session.py` — interactive helper to generate `TG_SESSION` locally
- `scripts/build_feeds.py` — rebuild RSS/Atom/sitemap/robots from saved JSON
- `scripts/build_static.py` — pre-render static HTML into `docs/static/`
- `scripts/storage.py` — JSON read/write with “write only if changed”
- `scripts/media_utils.py` — media/avatar download, thumbnail + favicon generation, retry/backoff
- `scripts/html_sanitize.py` — link sanitization (safe schemes + hardened rel)
- `scripts/post_merge.py` — album merging (`grouped_id`)
- `scripts/post_diff.py` — detects meaningful post edits (`WATCHED_FIELDS`)
- `scripts/site_files.py` — RSS/Atom/sitemap/robots generation
- `scripts/models.py` — schema (dataclasses + `TypedDict`)
- `scripts/paths.py` — canonical paths + constants

### Frontend (zero-build)

- `docs/index.html` + `docs/app.js` — main feed UI (search, filters, load-more)
- `docs/post.html` + `docs/post.js` — single post view
- `docs/common.js` — shared rendering helpers (media rendering, hashtag linkification, etc.)
- `docs/static.js` — helpers used by pre-rendered pages
- `docs/style.css`

### Automation

- `.github/workflows/sync.yml` — scheduled sync (fetch → detect changes → build static → commit)
- `.github/workflows/quality.yml` — Ruff + MyPy (Python 3.12)

---

## 3) Generated artifacts (treat as outputs)

Avoid manual edits to these files; they are produced by scripts:

- `docs/data/posts.json`
- `docs/data/meta.json`
- `docs/data/config.json`
- `docs/data/pages/page-*.json`
- `docs/assets/media/**` and `docs/assets/media/thumbs/**`
- `docs/assets/channel_avatar.jpg`
- `docs/favicon.ico`, `docs/favicon-32.png`, `docs/apple-touch-icon.png`
- `docs/feed.xml`, `docs/atom.xml`, `docs/sitemap.xml`, `docs/robots.txt`
- `docs/static/**` (note: `build_static.py` deletes and recreates this directory)

**Default behavior for Codex:** if the task is “fix a bug / improve code quality”, do not regenerate outputs.

---

## 4) CI parity commands

CI uses **Python 3.12** and sets `PYTHONPATH=.`.

Local setup:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

Run the same checks as CI:

```bash
ruff check scripts
ruff format --check scripts
mypy scripts
```

Typical edit loop:

```bash
ruff format scripts
ruff check scripts
mypy scripts
```

---

## 5) Data contract invariants

### 5.1 `docs/data/posts.json`

- Must be a JSON **list** of posts.
- Written by `scripts/storage.py::write_posts()`.
- **On disk order is oldest → newest** (sorted by `id`) to keep diffs append-only.
- Posts follow `scripts/models.py::PostDict`.

Key fields used across code/UI:

- `id` (int or int-like string; must be convertible to `int`)
- `date` (ISO8601; typically UTC)
- `text` and/or `html`
- `link` (Telegram permalink when channel username is known)
- `type` (`text|photo|video|audio|document|image|sticker|poll|other`)
- `media` (optional list of media dicts)
- `reactions` (optional `{ total, details }`)
- `media_status` (optional; e.g. `skipped_too_large`, `download_failed`)

### 5.2 Media paths

- Media paths stored in JSON are **relative to `docs/`**.
- Thumbnails are generated as WebP under `docs/assets/media/thumbs/`.

If you change media structures, update both:

- dynamic UI (`docs/common.js` / `docs/app.js` / `docs/post.js`)
- static renderer (`scripts/build_static.py`)

### 5.3 `docs/data/meta.json`

Written by `storage.write_meta()` and must stay JSON-serializable.

Invariants:

- `last_seen_message_id` is an integer.
- `last_sync_utc` is ISO8601 (often with `Z`).
- `meta_schema_version` and `posts_schema_version` exist (default `1.0.0`).

### 5.4 `docs/data/config.json`

Produced by `fetch_telegram.build_frontend_config()`.

Frontend relies on:

- `page_size` and `static_page_size`
- `json_page_size` and `json_total_pages` (paging through `docs/data/pages/page-*.json`)
- `site_url` (absolute base URL for feeds/sitemap/static)
- `metrika_id` (read by `docs/metrika.js`)

If you rename/remove any of these, update scripts + frontend.

### 5.5 Link sanitization

Telegram HTML is produced via `telethon.extensions.html.unparse()` and then sanitized by `scripts/html_sanitize.py`.

- Allowed schemes: `http`, `https`, `mailto`, `tg`, `tel`.
- Anchor tags must have hardened rel tokens: `noopener noreferrer nofollow`.

Do not relax this without a security review.

---

## 6) Networked sync (only when explicitly needed)

Main script:

```bash
PYTHONPATH=. python scripts/fetch_telegram.py
```

`fetch_telegram.py` loads `.env` automatically (`python-dotenv`).
**Never commit `.env`.**

### Required environment variables

- `TG_API_ID`
- `TG_API_HASH`
- `TG_SESSION` (Telethon `StringSession`)
- `TG_CHANNEL` (username or `https://t.me/<channel>`)

### Common knobs

- `DOWNLOAD_MEDIA` (`true/false`, default `true`)
- `MEDIA_MAX_MB` (default `200`)
- `MEDIA_DOWNLOAD_SCOPE` (default `1000`)
- `INITIAL_FETCH_LIMIT` (default `1000`; `0` = full history)
- `REFRESH_LAST_N` (default `200`)
- `METRIKA_ID` (optional)
- `GENERATE_SITE_FILES` (`true/false`, default `false`; set repo variable `SEO` for sitemap/robots; when false, robots.txt is written with `Disallow: /`)
- `GENERATE_FEEDS` (`true/false`, default `false`; set repo variable `FEED` for RSS/Atom)
- `MAX_RETRIES` (default `5`), `BACKOFF_SECONDS` (default `2.0`)
- `LOG_LEVEL` (`DEBUG`, `INFO`, ...)

Feeds/sitemaps/static links infer the base URL from GitHub Pages when available.

### Safe smoke run

```bash
PYTHONPATH=. python scripts/fetch_telegram.py --dry-run --refresh-last-n 50
```

### Generating `TG_SESSION` (interactive, local-only)

```bash
PYTHONPATH=. python scripts/create_session.py
```

---

## 7) Offline rebuilds (no Telegram I/O)

Rebuild feeds/sitemap/robots from existing JSON:

```bash
PYTHONPATH=. python scripts/build_feeds.py
```

Rebuild pre-rendered static HTML:

```bash
PYTHONPATH=. python scripts/build_static.py
# optional: --output /path/to/dir
```

Serve locally:

```bash
python -m http.server --directory docs 8000
# open http://localhost:8000
```

---

## 8) GitHub Actions workflow invariants

If you change output paths or add new generated files, you must update `.github/workflows/sync.yml`:

- The **Detect data/media changes** step checks a hard-coded path list.
- The **Commit & push** step runs a hard-coded `git add` list.

If these lists don’t include your new/renamed files, Actions will not rebuild/commit correctly.

Also:

- Sync job installs only `requirements.txt`.
  - Any runtime dependency used by the sync workflow must be added to `requirements.txt`.

`GENERATE_STATIC` is controlled in the workflow (it gates whether `build_static.py` runs). `fetch_telegram.py` does **not** read `GENERATE_STATIC`.
`GENERATE_SITE_FILES` is fed from the workflow (repo var `SEO`) and gates sitemap/robots generation.
`GENERATE_FEEDS` is fed from the workflow (repo var `FEED`) and gates RSS/Atom generation.

---

## 9) Change playbooks

### 9.1 Add/modify post fields

1) Update schema in `scripts/models.py`.
2) Update extraction in `scripts/media_utils.py::message_to_post_dict()`.
3) If the field should trigger updates on edit, add it to `scripts/post_diff.py::WATCHED_FIELDS`.
4) Update renderers:
   - dynamic UI: `docs/app.js`, `docs/post.js`, `docs/common.js`
   - static UI: `scripts/build_static.py`

### 9.2 Media behavior changes

- Keep paths relative to `docs/`.
- Keep thumbnail generation consistent with `docs/common.js` expectations.
- Avoid adding heavy processing in the sync path; it runs every hour.

### 9.3 Reduce repo bloat

Prefer config knobs over code changes:

- `DOWNLOAD_MEDIA=false`, or
- lower `MEDIA_MAX_MB`, or
- lower `MEDIA_DOWNLOAD_SCOPE`.

---

## 10) Definition of done

A change is “done” when:

- `ruff check` + `ruff format --check` pass
- `mypy scripts` passes
- Generated outputs were not regenerated unless required
- If schema/UI changed: dynamic pages and `build_static.py` are consistent
- If workflows or output paths changed: `sync.yml` path lists updated
