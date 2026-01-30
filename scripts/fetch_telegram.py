#!/usr/bin/env python3
"""Fetch Telegram channel posts and store them into docs/data/posts.json."""

import argparse
import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, cast

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Message

from scripts import models, paths, site_files, storage, utils  # noqa: E402
from scripts.config_loader import (  # noqa: E402
    SyncConfig,
    TelegramConfig,
    apply_cli_overrides,
    load_env_config,
)
from scripts.media_utils import (  # noqa: E402
    download_avatar,
    download_message_media,
    message_to_post_dict,
    run_with_retries,
)
from scripts.post_diff import post_changed  # noqa: E402
from scripts.post_merge import merge_albums  # noqa: E402

LOGGER = logging.getLogger("telegram_mirror")


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Telegram channel posts into static site data."
    )
    parser.add_argument(
        "--generate-site-files",
        dest="generate_site_files",
        action=argparse.BooleanOptionalAction,
        help="Generate sitemap/robots (default: GENERATE_SITE_FILES env, fallback: false).",
    )
    parser.add_argument(
        "--download-media",
        dest="download_media",
        action=argparse.BooleanOptionalAction,
        help="Download media files (default: DOWNLOAD_MEDIA env, fallback: true).",
    )
    parser.add_argument(
        "--media-max-mb",
        type=int,
        dest="media_max_mb",
        help="Max media file size in MB (default: MEDIA_MAX_MB env, fallback: 200).",
    )
    parser.add_argument(
        "--initial-limit",
        type=int,
        dest="initial_limit",
        help="Initial import limit, 0=all (default: INITIAL_FETCH_LIMIT env, fallback: 1000).",
    )
    parser.add_argument(
        "--refresh-last-n",
        type=int,
        dest="refresh_last_n",
        help="Refresh last N messages on each run (default: REFRESH_LAST_N env, fallback: 200).",
    )
    parser.add_argument(
        "--media-download-scope",
        type=int,
        dest="media_download_scope",
        help="Max number of media download attempts per run (default: MEDIA_DOWNLOAD_SCOPE env, fallback: 1000).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        dest="max_retries",
        help="Max retries for Telegram API calls (default: MAX_RETRIES env, fallback: 5).",
    )
    parser.add_argument(
        "--backoff-seconds",
        type=float,
        dest="backoff_seconds",
        help="Base backoff seconds for retries (default: BACKOFF_SECONDS env, fallback: 2.0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write any files; fetch and report only.",
    )
    return parser.parse_args()


def ensure_output_dirs() -> None:
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    paths.ASSETS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class LocalState:
    posts_by_id: Dict[int, models.PostDict]
    meta: models.MetaDict
    is_initial_sync: bool
    last_post_id: int
    fetch_start_id: int
    max_seen_message_id: int


def load_local_state() -> LocalState:
    posts_by_id: Dict[int, models.PostDict] = storage.load_posts()
    existing_meta = storage.load_meta()

    is_initial_sync = (not paths.POSTS_PATH.exists()) or (not posts_by_id)
    last_post_id = max(posts_by_id.keys()) if posts_by_id else 0

    last_seen_message_id = int(existing_meta.get("last_seen_message_id") or 0)
    fetch_start_id = last_seen_message_id if last_seen_message_id > 0 else last_post_id
    max_seen_message_id = last_seen_message_id

    return LocalState(
        posts_by_id=posts_by_id,
        meta=existing_meta,
        is_initial_sync=is_initial_sync,
        last_post_id=last_post_id,
        fetch_start_id=fetch_start_id,
        max_seen_message_id=max_seen_message_id,
    )


async def fetch_initial_posts(
    client: TelegramClient,
    entity: Any,
    channel_username: str | None,
    posts_by_id: Dict[int, models.PostDict],
    initial_limit: int,
    max_seen_id: int,
) -> tuple[int, int]:
    new_count = 0
    if initial_limit and initial_limit > 0:
        message_buffer: list[Message] = []
        async for message in client.iter_messages(entity, limit=initial_limit):
            if isinstance(message, Message) and getattr(message, "id", None):
                message_buffer.append(message)
                max_seen_id = max(max_seen_id, int(message.id))
        for message in reversed(message_buffer):
            post_dict = message_to_post_dict(message, channel_username)
            posts_by_id[int(post_dict["id"])] = post_dict
        new_count = len(message_buffer)
    else:
        async for message in client.iter_messages(entity, reverse=True):
            if isinstance(message, Message) and getattr(message, "id", None):
                post_dict = message_to_post_dict(message, channel_username)
                posts_by_id[int(post_dict["id"])] = post_dict
                new_count += 1
                max_seen_id = max(max_seen_id, int(message.id))
    return new_count, max_seen_id


async def fetch_new_posts_since(
    client: TelegramClient,
    entity: Any,
    channel_username: str | None,
    posts_by_id: Dict[int, models.PostDict],
    fetch_start_id: int,
    max_seen_id: int,
) -> tuple[int, int]:
    new_count = 0
    if fetch_start_id <= 0:
        return new_count, max_seen_id
    try:
        async for message in client.iter_messages(
            entity, min_id=fetch_start_id, reverse=True
        ):
            if not isinstance(message, Message) or not getattr(message, "id", None):
                continue
            post_dict = message_to_post_dict(message, channel_username)
            message_id = int(post_dict["id"])
            max_seen_id = max(max_seen_id, message_id)
            if message_id not in posts_by_id:
                new_count += 1
            posts_by_id[message_id] = post_dict
    except Exception as e:
        LOGGER.error("Fetch new messages failed: %s", e)
        raise
    return new_count, max_seen_id


async def refresh_last_n_posts(
    client: TelegramClient,
    entity: Any,
    channel_username: str | None,
    posts_by_id: Dict[int, models.PostDict],
    refresh_last_n: int,
    max_seen_id: int,
) -> tuple[int, int, int]:
    updated_count = 0
    new_count = 0
    if refresh_last_n <= 0:
        return new_count, updated_count, max_seen_id
    try:
        async for message in client.iter_messages(entity, limit=refresh_last_n):
            if not isinstance(message, Message) or not getattr(message, "id", None):
                continue
            post_dict = message_to_post_dict(message, channel_username)
            message_id = int(post_dict["id"])
            max_seen_id = max(max_seen_id, message_id)
            if message_id in posts_by_id:
                if post_changed(posts_by_id[message_id], post_dict):
                    if posts_by_id[message_id].get("media") and not post_dict.get(
                        "media"
                    ):
                        post_dict["media"] = posts_by_id[message_id]["media"]
                    posts_by_id[message_id] = post_dict
                    updated_count += 1
            else:
                posts_by_id[message_id] = post_dict
                new_count += 1
    except Exception as e:
        LOGGER.warning("refresh_last_n failed: %s", e)
    return new_count, updated_count, max_seen_id


async def download_missing_media(
    client: TelegramClient,
    entity: Any,
    posts_by_id: Dict[int, models.PostDict],
    sync_cfg: SyncConfig,
    max_bytes: int,
) -> tuple[int, int]:
    downloaded = 0
    status_updates = 0
    scope = max(0, sync_cfg.media_download_scope)
    ids_sorted = sorted(posts_by_id.keys(), reverse=True)
    checked = 0
    for message_id in ids_sorted:
        if checked >= scope:
            break

        post = posts_by_id[message_id]
        if post.get("media"):
            continue
        if post.get("media_status") in {"skipped_too_large"}:
            continue
        if post.get("type") in {
            "photo",
            "video",
            "audio",
            "document",
            "image",
            "sticker",
        }:
            checked += 1
            try:
                message = await run_with_retries(
                    lambda: client.get_messages(entity, ids=message_id),
                    retries=sync_cfg.max_retries,
                    backoff_seconds=sync_cfg.backoff_seconds,
                )
                if not isinstance(message, Message):
                    continue
                items, status = await download_message_media(
                    client, message, max_bytes=max_bytes
                )
                if items:
                    post["media"] = [
                        cast(models.MediaDict, asdict(item)) for item in items
                    ]
                    post["media_status"] = "downloaded"
                    posts_by_id[message_id] = post
                    downloaded += len(items)
                elif status:
                    post["media_status"] = status
                    posts_by_id[message_id] = post
                    status_updates += 1
            except Exception as e:
                LOGGER.warning("Media download failed for %s: %s", message_id, e)
    return downloaded, status_updates


def build_meta_dict(
    channel_title: str,
    channel_username: str | None,
    telegram_cfg: TelegramConfig,
    posts_by_id: Dict[int, models.PostDict],
    max_seen_id: int,
    new_count: int,
    updated_count: int,
    downloaded: int,
    avatar_rel: str | None,
) -> models.MetaDict:
    meta: models.MetaDict = {
        "title": channel_title,
        "username": channel_username,
        "channel": telegram_cfg.channel,
        "last_sync_utc": (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        ),
        "posts_count": len(posts_by_id),
        "last_seen_message_id": max_seen_id,
        "stats": {
            "new": new_count,
            "updated": updated_count,
            "media_downloaded": downloaded,
        },
    }
    if avatar_rel:
        meta["avatar"] = avatar_rel
    return meta


def build_frontend_config(json_total_pages: int) -> Dict[str, Any]:
    metrika_id = (os.getenv("METRIKA_ID") or "").strip()
    channel_specific_link = (os.getenv("TG_CHANNEL_SPECIFIC_LINK") or "").strip()
    promo_text = (os.getenv("PROMO_TEXT") or "").strip()
    site_url = utils.infer_github_pages_url()
    config: Dict[str, Any] = {
        "page_size": paths.STATIC_PAGE_SIZE,
        "static_page_size": paths.STATIC_PAGE_SIZE,
        "site_url": site_url,
        "json_page_size": paths.JSON_PAGE_SIZE,
        "json_total_pages": json_total_pages,
        "metrika_id": metrika_id,
    }
    if channel_specific_link:
        config["channel_specific_link"] = channel_specific_link
    if promo_text:
        config["promo_text"] = promo_text
    return config


def write_mirror_files(
    posts_by_id: Dict[int, models.PostDict],
    meta: models.MetaDict,
    telegram_cfg: TelegramConfig,
    sync_cfg: SyncConfig,
) -> bool:
    posts_changed = storage.write_posts(posts_by_id)
    meta_changed = storage.write_meta(meta)
    generated = False
    if sync_cfg.generate_feeds:
        site_files.write_feeds(meta, posts_by_id, telegram_cfg.channel)
        generated = True
    if sync_cfg.generate_site_files:
        site_files.write_sitemap(meta, posts_by_id, telegram_cfg.channel)
        site_files.write_robots(meta, telegram_cfg.channel, allow_index=True)
        generated = True
    else:
        site_files.write_robots(meta, telegram_cfg.channel, allow_index=False)
        generated = True
    return posts_changed or meta_changed or generated


async def sync_channel(
    telegram_cfg: TelegramConfig, sync_cfg: SyncConfig, dry_run: bool = False
) -> None:
    max_bytes = max(1, sync_cfg.media_max_mb) * 1024 * 1024
    if not dry_run:
        ensure_output_dirs()

    local_state = load_local_state()
    posts_by_id = local_state.posts_by_id
    is_initial_sync = local_state.is_initial_sync
    last_post_id = local_state.last_post_id
    fetch_start_id = local_state.fetch_start_id
    max_seen_id = local_state.max_seen_message_id

    async with TelegramClient(
        StringSession(telegram_cfg.session), telegram_cfg.api_id, telegram_cfg.api_hash
    ) as client:
        entity = await client.get_entity(telegram_cfg.channel)
        channel_username = getattr(entity, "username", None)
        channel_title = (
            getattr(entity, "title", None)
            or getattr(entity, "first_name", None)
            or str(telegram_cfg.channel)
        )
        avatar_rel, avatar_changed = (
            (None, False) if dry_run else await download_avatar(client, entity)
        )

        new_count = 0
        updated_count = 0
        downloaded = 0

        if is_initial_sync:
            LOGGER.info("No existing posts. Running initial import…")
            new_count, max_seen_id = await fetch_initial_posts(
                client,
                entity,
                channel_username,
                posts_by_id,
                sync_cfg.initial_limit,
                max_seen_id,
            )
        else:
            new_posts_count, max_seen_id = await fetch_new_posts_since(
                client,
                entity,
                channel_username,
                posts_by_id,
                fetch_start_id,
                max_seen_id,
            )
            new_count += new_posts_count

            refresh_new, refresh_updated, max_seen_id = await refresh_last_n_posts(
                client,
                entity,
                channel_username,
                posts_by_id,
                sync_cfg.refresh_last_n,
                max_seen_id,
            )
            new_count += refresh_new
            updated_count += refresh_updated

        skipped_media_updates = 0
        if sync_cfg.download_media and not dry_run:
            downloaded, skipped_media_updates = await download_missing_media(
                client, entity, posts_by_id, sync_cfg, max_bytes
            )

    posts_by_id = merge_albums(posts_by_id)

    posts_desc = sorted(
        posts_by_id.values(), key=lambda p: int(p.get("id", 0)), reverse=True
    )
    json_total_pages = (
        (len(posts_desc) + paths.JSON_PAGE_SIZE - 1) // paths.JSON_PAGE_SIZE
        if posts_desc
        else 0
    )

    config = build_frontend_config(json_total_pages)
    config_changed = False if dry_run else storage.write_config(config)
    pages_changed = False
    if not dry_run:
        pages_changed = storage.write_post_pages(posts_desc, paths.JSON_PAGE_SIZE)

    content_changed = (
        (new_count > 0)
        or (updated_count > 0)
        or (downloaded > 0)
        or avatar_changed
        or config_changed
        or (skipped_media_updates > 0)
        or pages_changed
    )
    max_seen_id = max(max_seen_id, last_post_id, fetch_start_id)

    if dry_run:
        LOGGER.info(
            "DRY RUN — skipping writes. Posts: %s | new: %s | updated: %s | media downloaded: %s",
            len(posts_by_id),
            new_count,
            updated_count,
            downloaded,
        )
        return

    if not content_changed:
        LOGGER.info(
            "No changes. Posts: %s | new: %s | updated: %s | media downloaded: %s",
            len(posts_by_id),
            new_count,
            updated_count,
            downloaded,
        )
        return

    meta = build_meta_dict(
        channel_title,
        channel_username,
        telegram_cfg,
        posts_by_id,
        max_seen_id,
        new_count,
        updated_count,
        downloaded,
        avatar_rel,
    )
    write_mirror_files(posts_by_id, meta, telegram_cfg, sync_cfg)

    LOGGER.info(
        "Done. Posts: %s | new: %s | updated: %s | media downloaded: %s",
        len(posts_by_id),
        new_count,
        updated_count,
        downloaded,
    )


async def main() -> None:
    utils.setup_logging()
    load_dotenv()
    args = parse_cli_args()
    telegram_cfg, sync_cfg = load_env_config()
    sync_cfg = apply_cli_overrides(sync_cfg, args)
    await sync_channel(telegram_cfg, sync_cfg, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
