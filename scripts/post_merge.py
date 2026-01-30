from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from . import models


def merge_albums(posts_by_id: Dict[int, models.PostDict]) -> Dict[int, models.PostDict]:
    grouped_posts: Dict[int, List[models.PostDict]] = {}
    ungrouped_posts: Dict[int, models.PostDict] = {}

    for post_id, post in posts_by_id.items():
        group_id = post.get("grouped_id")
        if group_id:
            grouped_posts.setdefault(int(group_id), []).append(post)
        else:
            ungrouped_posts[post_id] = post

    merged_posts: Dict[int, models.PostDict] = {}
    merged_posts.update(ungrouped_posts)

    for group_id, group_posts in grouped_posts.items():
        if not group_posts:
            continue
        sorted_group_posts = sorted(group_posts, key=lambda p: int(p.get("id", 0)))
        base_post: Dict[str, Any] = dict(sorted_group_posts[0])

        merged_media: List[models.MediaDict] = []
        seen_media_keys: Set[Tuple[Any, Any, Any]] = set()

        def _media_dedupe_key(media_item: models.MediaDict) -> Tuple[Any, Any, Any]:
            return (
                media_item.get("path"),
                media_item.get("kind"),
                media_item.get("mime"),
            )

        for post_item in sorted_group_posts:
            for media_item in post_item.get("media") or []:
                if not isinstance(media_item, dict):
                    continue
                key = _media_dedupe_key(media_item)
                if key in seen_media_keys:
                    continue
                seen_media_keys.add(key)
                merged_media.append(media_item)

        text = base_post.get("text") or ""
        html = base_post.get("html") or ""
        if not text or not html:
            for post_item in sorted_group_posts:
                if not text and post_item.get("text"):
                    text = post_item["text"]
                if not html and post_item.get("html"):
                    html = post_item["html"]
                if text and html:
                    break

        base_post["media"] = merged_media
        base_post["text"] = text
        base_post["html"] = html
        base_post["grouped_id"] = group_id

        base_id = base_post.get("id")
        if not isinstance(base_id, (int, str)):
            continue
        try:
            base_post_id = int(base_id)
        except (TypeError, ValueError):
            continue

        base_post["id"] = base_post_id
        merged_posts[base_post_id] = base_post  # type: ignore[assignment]

    return merged_posts
