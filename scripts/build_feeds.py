#!/usr/bin/env python3
"""Generate feeds, sitemap, and robots.txt from existing posts/meta data."""

import argparse

from scripts import site_files, storage  # noqa: E402


def build_feeds(channel: str | None = None) -> None:
    meta = storage.load_meta()
    posts = storage.load_posts()

    channel_val = channel or (str(meta["channel"]) if meta.get("channel") else "")
    if not channel_val:
        raise SystemExit(
            "Channel not specified; provide --channel or ensure meta.json contains 'channel'."
        )
    site_files.write_feeds(meta, posts, channel_val)
    site_files.write_sitemap(meta, posts, channel_val)
    site_files.write_robots(meta, channel_val, allow_index=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate feeds, sitemap, and robots.txt from existing data."
    )
    parser.add_argument(
        "--channel", help="Channel username/ID (defaults to meta.json channel)."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_feeds(channel=args.channel)


if __name__ == "__main__":
    main()
