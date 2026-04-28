# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` is the long-form contributor guide — read it for change playbooks, data-contract invariants, and CI parity details. This file is the short orientation.

## What this repo is

A serverless **Telegram → GitHub Pages mirror**. A scheduled GitHub Action runs `scripts/fetch_telegram.py` (Telethon) hourly, writes posts/media into `docs/`, and GitHub Pages serves `docs/` directly. There is no backend, no build step for the frontend, and no test suite — CI only runs lint + type checks.

## Common commands

CI uses **Python 3.12** with `PYTHONPATH=.`. All scripts are run from the repo root.

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Match CI (this is exactly what .github/workflows/quality.yml runs)
ruff check scripts
ruff format --check scripts
mypy scripts

# Typical edit loop
ruff format scripts && ruff check scripts && mypy scripts
```

Offline rebuilds (no network, work from existing `docs/data/*.json`):
```bash
PYTHONPATH=. python scripts/build_feeds.py    # regenerate feed.xml/atom.xml/sitemap.xml/robots.txt
PYTHONPATH=. python scripts/build_static.py   # rebuild docs/static/ snapshot
python -m http.server --directory docs 8000   # preview locally
```

Networked sync (only when explicitly needed; requires `.env` with `TG_API_ID`/`TG_API_HASH`/`TG_SESSION`/`TG_CHANNEL`):
```bash
PYTHONPATH=. python scripts/fetch_telegram.py --dry-run --refresh-last-n 50
```

There are **no tests**; CI only enforces ruff + mypy. Don't invent a test runner.

## Architecture

### Two render paths share one data store
The same JSON files under `docs/data/` feed two renderers:
- **Dynamic UI** — `docs/index.html` + `docs/app.js` + `docs/post.html` + `docs/post.js` + shared `docs/common.js`. Loads paginated `docs/data/pages/page-*.json` client-side.
- **Static snapshot** — `scripts/build_static.py` pre-renders the same data into `docs/static/` (deletes and recreates the directory each run). Gated by repo variable `GENERATE_STATIC`.

Anything that changes post schema or media rendering must be updated in **both paths** or they will diverge.

### Sync pipeline (`scripts/fetch_telegram.py`)
Orchestrates:
1. `post_merge.py` — merges Telegram albums by `grouped_id` into single posts.
2. `media_utils.py` — downloads media (size/scope-limited), generates WebP thumbnails, builds favicons from the channel avatar.
3. `html_sanitize.py` — sanitizes Telethon-produced HTML (allowed schemes only: `http/https/mailto/tg/tel`; anchors get `rel="noopener noreferrer nofollow"`).
4. `post_diff.py` — detects meaningful edits via `WATCHED_FIELDS`; only those trigger updates on re-fetch.
5. `storage.py` — writes JSON only when content changes (keeps git diffs small).
6. `site_files.py` — generates RSS/Atom/sitemap/robots when gated on.

`models.py` defines the dataclasses + `TypedDict` schema; `paths.py` centralises canonical output paths; `config_loader.py` reads env knobs.

### Data contract (critical)
- `docs/data/posts.json` is sorted **oldest → newest by `id`** on disk so diffs stay append-only. The UI reverses for display.
- Media paths in JSON are **relative to `docs/`**.
- `docs/data/config.json` (built by `fetch_telegram.build_frontend_config()`) is the contract between Python and the frontend — keys like `page_size`, `static_page_size`, `json_page_size`, `json_total_pages`, `site_url`, `metrika_id` are read by `docs/app.js`. Renaming a key requires changing both sides.

### Workflow coupling
`.github/workflows/sync.yml` has **two hard-coded path lists** that must be kept in sync with what scripts produce:
- the `git status --porcelain ...` change-detection step, and
- the `add_paths=(...)` commit step.

If you add a new generated output path, both lists need updating or the workflow will silently miss it. Also: the sync job installs **only `requirements.txt`**, so any new runtime dep must land there (not just `requirements-dev.txt`).

Three independent toggles flow from repo Variables → workflow → env:
- `GENERATE_STATIC` (gates `build_static.py` in the workflow only — `fetch_telegram.py` does not read it)
- `SEO` → `GENERATE_SITE_FILES` (sitemap/robots; when false, `robots.txt` is written with `Disallow: /`)
- `FEED` → `GENERATE_FEEDS` (RSS/Atom)

## Important constraints

- **Don't regenerate outputs as a side effect of code changes.** `docs/data/**`, `docs/assets/media/**`, `docs/static/**`, `docs/feed.xml`, `docs/atom.xml`, `docs/sitemap.xml`, `docs/robots.txt`, `docs/favicon*`, `docs/apple-touch-icon.png`, and `docs/assets/channel_avatar.jpg` are all script outputs. If a bug fix doesn't require regenerating them, leave them alone — the diffs are huge and reviewer-hostile.
- **Don't relax `html_sanitize.py`** (URL schemes, `rel` tokens) without a security review.
- **Never commit `.env`** or print/log Telegram credentials.
- See `AGENTS.md` §9 for the step-by-step playbooks when adding post fields, changing media behaviour, or renaming output paths.
