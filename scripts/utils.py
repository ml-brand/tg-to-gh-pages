import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

from . import models


def setup_logging() -> None:
    level_str = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def normalize_site_url(raw: str) -> str:
    if not raw:
        return ""
    return raw if raw.endswith("/") else raw + "/"


def infer_github_pages_url() -> str:
    owner = (os.getenv("GITHUB_REPOSITORY_OWNER") or "").strip()
    repo = (os.getenv("GITHUB_REPOSITORY") or "").strip()
    repo_name = ""
    if repo:
        if "/" in repo:
            repo_owner, repo_name = repo.split("/", 1)
            if not owner:
                owner = repo_owner
        else:
            repo_name = repo
    if not owner or not repo_name:
        return ""
    owner_lower = owner.lower()
    repo_lower = repo_name.lower()
    if repo_lower == f"{owner_lower}.github.io":
        return normalize_site_url(f"https://{owner}.github.io/")
    return normalize_site_url(f"https://{owner}.github.io/{repo_name}/")


def clean_channel(s: str) -> str:
    s = s.strip()
    if s.startswith("https://t.me/"):
        s = s.replace("https://t.me/", "")
    if s.startswith("@"):
        s = s[1:]
    return s


def safe_filename(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]", "_", s)
    return s[:120] if len(s) > 120 else s


def iso_to_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        v = value.replace("Z", "+00:00") if isinstance(value, str) else value
        return datetime.fromisoformat(v)
    except Exception:
        return None


def fmt_lastmod(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def site_base_url(meta: models.MetaDict, channel: str, site_url: str = "") -> str:
    if site_url:
        return normalize_site_url(site_url)
    inferred = infer_github_pages_url()
    if inferred:
        return inferred
    username = meta.get("username") or channel
    return f"https://t.me/{username}/"
