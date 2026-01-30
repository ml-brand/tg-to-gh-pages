import json
from pathlib import Path
from typing import Any, Dict, List, cast

from . import models, paths


def load_posts() -> Dict[int, models.PostDict]:
    if not paths.POSTS_PATH.exists():
        return {}
    try:
        data = json.loads(paths.POSTS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return {}
        out: Dict[int, models.PostDict] = {}
        for raw in data:
            if not isinstance(raw, dict):
                continue
            post_id = raw.get("id")
            if not isinstance(post_id, (int, str)):
                continue
            try:
                pid = int(post_id)
            except (TypeError, ValueError):
                continue
            out[pid] = cast(models.PostDict, raw)
        return out
    except Exception:
        return {}


def _write_if_changed(path: Path, data: str) -> bool:
    new_bytes = data.encode("utf-8")
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            current = path.read_bytes()
            if current == new_bytes:
                return False
    except Exception:
        # If we cannot read, fall back to writing.
        pass
    tmp_path.write_bytes(new_bytes)
    tmp_path.replace(path)
    return True


def write_posts(posts_by_id: Dict[int, models.PostDict]) -> bool:
    # Store oldest -> newest so new posts append to the end (git-friendly).
    posts = sorted(posts_by_id.values(), key=lambda p: int(p.get("id", 0)))
    payload = json.dumps(posts, ensure_ascii=False, indent=2) + "\n"
    return _write_if_changed(paths.POSTS_PATH, payload)


def load_meta() -> models.MetaDict:
    if not paths.META_PATH.exists():
        return {}
    try:
        return json.loads(paths.META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_meta(meta: models.MetaDict) -> bool:
    meta.setdefault("meta_schema_version", "1.0.0")
    meta.setdefault("posts_schema_version", "1.0.0")
    payload = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    return _write_if_changed(paths.META_PATH, payload)


def write_config(config: Dict[str, Any]) -> bool:
    payload = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    return _write_if_changed(paths.CONFIG_PATH, payload)


def write_post_pages(posts_desc: List[models.PostDict], page_size: int) -> bool:
    paths.PAGES_DIR.mkdir(parents=True, exist_ok=True)
    total_pages = (
        max(1, (len(posts_desc) + page_size - 1) // page_size) if posts_desc else 0
    )
    changed = False

    for page in range(1, total_pages + 1):
        start = (page - 1) * page_size
        end = start + page_size
        slice_posts = posts_desc[start:end]
        payload = json.dumps(slice_posts, ensure_ascii=False, indent=2) + "\n"
        page_path = paths.PAGES_DIR / f"page-{page}.json"
        if _write_if_changed(page_path, payload):
            changed = True

    # Remove stale pages beyond total_pages
    existing = list(paths.PAGES_DIR.glob("page-*.json"))
    for f in existing:
        try:
            name = f.stem.replace("page-", "")
            idx = int(name)
        except ValueError:
            continue
        if idx > total_pages:
            f.unlink(missing_ok=True)
            changed = True

    return changed
