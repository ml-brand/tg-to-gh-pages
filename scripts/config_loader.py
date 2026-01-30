import argparse
from dataclasses import dataclass
from typing import Tuple

from . import utils


@dataclass
class TelegramConfig:
    api_id: int
    api_hash: str
    session: str
    channel: str


@dataclass
class SyncConfig:
    download_media: bool
    media_max_mb: int
    initial_limit: int
    refresh_last_n: int
    media_download_scope: int
    max_retries: int = 3
    backoff_seconds: float = 2.0
    generate_site_files: bool = False
    generate_feeds: bool = False


def load_env_config() -> Tuple[TelegramConfig, SyncConfig]:
    telegram = TelegramConfig(
        api_id=int(utils.require("TG_API_ID")),
        api_hash=utils.require("TG_API_HASH"),
        session=utils.require("TG_SESSION"),
        channel=utils.clean_channel(utils.require("TG_CHANNEL")),
    )
    sync = SyncConfig(
        download_media=utils.env_bool("DOWNLOAD_MEDIA", True),
        media_max_mb=utils.env_int("MEDIA_MAX_MB", 200),
        initial_limit=utils.env_int("INITIAL_FETCH_LIMIT", 1000),
        refresh_last_n=utils.env_int("REFRESH_LAST_N", 200),
        media_download_scope=utils.env_int("MEDIA_DOWNLOAD_SCOPE", 1000),
        max_retries=utils.env_int("MAX_RETRIES", 5),
        backoff_seconds=utils.env_float("BACKOFF_SECONDS", 2.0),
        generate_site_files=utils.env_bool("GENERATE_SITE_FILES", False),
        generate_feeds=utils.env_bool("GENERATE_FEEDS", False),
    )
    return telegram, sync


def apply_cli_overrides(sync: SyncConfig, args: argparse.Namespace) -> SyncConfig:
    return SyncConfig(
        download_media=sync.download_media
        if args.download_media is None
        else args.download_media,
        media_max_mb=sync.media_max_mb
        if args.media_max_mb is None
        else args.media_max_mb,
        initial_limit=sync.initial_limit
        if args.initial_limit is None
        else args.initial_limit,
        refresh_last_n=sync.refresh_last_n
        if args.refresh_last_n is None
        else args.refresh_last_n,
        media_download_scope=sync.media_download_scope
        if getattr(args, "media_download_scope", None) is None
        else args.media_download_scope,
        max_retries=sync.max_retries
        if getattr(args, "max_retries", None) is None
        else args.max_retries,
        backoff_seconds=sync.backoff_seconds
        if getattr(args, "backoff_seconds", None) is None
        else args.backoff_seconds,
        generate_site_files=sync.generate_site_files
        if args.generate_site_files is None
        else args.generate_site_files,
        generate_feeds=sync.generate_feeds,
    )
