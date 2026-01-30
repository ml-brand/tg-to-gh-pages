import asyncio
import logging
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
)
from PIL import Image

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.extensions import html as telethon_html
from telethon.tl.types import Message

from . import models, paths, utils
from .html_sanitize import sanitize_links

LOGGER = logging.getLogger("telegram_mirror")
T = TypeVar("T")


async def run_with_retries(
    operation: Callable[[], Awaitable[T]],
    *,
    retries: int,
    backoff_seconds: float,
    max_backoff_seconds: float = 30.0,
    jitter_ratio: float = 0.25,
) -> T:
    """Run an async operation with exponential backoff.

    `operation` must be a *factory* that returns a coroutine, so it can be
    re-invoked on retry.
    """

    attempt = 0
    delay_seconds = backoff_seconds
    while True:
        try:
            return await operation()
        except FloodWaitError as flood_wait:
            wait_seconds = (
                int(getattr(flood_wait, "seconds", 0))
                or int(getattr(flood_wait, "x", 0))
                or 0
            )
            wait_seconds = max(wait_seconds, 1)
            LOGGER.warning("FloodWaitError: sleeping %s seconds", wait_seconds)
            await asyncio.sleep(wait_seconds)
        except (RPCError, asyncio.TimeoutError, OSError) as err:
            attempt += 1
            if attempt > retries:
                LOGGER.error("Retries exhausted after %s attempts: %s", attempt, err)
                raise
            LOGGER.warning("Retrying after error (%s/%s): %s", attempt, retries, err)

            jitter_amount = delay_seconds * jitter_ratio
            sleep_for = delay_seconds + (
                random.uniform(-jitter_amount, jitter_amount) if jitter_amount else 0
            )
            await asyncio.sleep(max(sleep_for, 0))
            delay_seconds = min(delay_seconds * 2, max_backoff_seconds)


def get_message_type(message: Message) -> str:
    if getattr(message, "poll", None):
        return "poll"
    if getattr(message, "photo", None):
        return "photo"
    if getattr(message, "video", None):
        return "video"
    if getattr(message, "audio", None):
        return "audio"
    if getattr(message, "document", None):
        mime = getattr(getattr(message, "file", None), "mime_type", None) or ""
        if "image/" in mime:
            return "image"
        if "video/" in mime:
            return "video"
        if "audio/" in mime:
            return "audio"
        if "application/x-tgsticker" in mime:
            return "sticker"
        return "document"
    if message.message:
        return "text"
    return "other"


def extract_reactions_info(message: Message) -> Optional[models.ReactionInfo]:
    reactions = getattr(message, "reactions", None)
    if not reactions:
        return None
    total = 0
    details: List[Dict[str, Any]] = []
    try:
        for result in getattr(reactions, "results", []) or []:
            count = int(getattr(result, "count", 0) or 0)
            total += count
            reaction = getattr(result, "reaction", None)
            emoji = getattr(reaction, "emoticon", None)
            details.append({"count": count, "emoji": emoji})
    except Exception:
        return None
    return models.ReactionInfo(total=total, details=details)


async def download_message_media(
    client: TelegramClient, message: Message, *, max_bytes: int
) -> Tuple[List[models.MediaItem], Optional[str]]:
    if not message.media:
        return [], "no_media"

    telegram_file = getattr(message, "file", None)
    if not telegram_file:
        return [], "missing_file"

    file_size = getattr(telegram_file, "size", None)
    if file_size is not None and file_size > max_bytes:
        return [], "skipped_too_large"

    media_kind = get_message_type(message)
    mime_type = getattr(telegram_file, "mime_type", None) or ""
    mime_lower = mime_type.lower()
    paths.ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    file_ext = getattr(telegram_file, "ext", None) or ""
    if file_ext and not file_ext.startswith("."):
        file_ext = "." + file_ext

    file_name = getattr(telegram_file, "name", None)
    if file_name:
        file_name = utils.safe_filename(file_name)

    base_filename = f"{message.id}"
    if file_name and file_ext:
        output_filename = f"{base_filename}_{file_name}"
        if not output_filename.endswith(file_ext):
            output_filename += file_ext
    elif file_ext:
        output_filename = f"{base_filename}{file_ext}"
    else:
        output_filename = f"{base_filename}"

    output_path = paths.ASSETS_DIR / output_filename

    downloaded_file_path = output_path

    if not output_path.exists():
        try:
            downloaded = await run_with_retries(
                lambda: client.download_media(message, file=str(output_path)),
                retries=3,
                backoff_seconds=1.5,
            )
            if downloaded and isinstance(downloaded, (str, Path)):
                downloaded_file_path = Path(downloaded)
            if not downloaded_file_path.exists() and output_path.exists():
                downloaded_file_path = output_path
        except Exception as e:
            LOGGER.warning("Download media failed for %s: %s", message.id, e)
            return [], "download_failed"

    if not downloaded_file_path.exists():
        return [], "download_failed"

    relative_path = downloaded_file_path.relative_to(paths.DOCS).as_posix()
    thumbnail_relative_path: Optional[str] = None
    if (
        media_kind in {"photo", "image"}
        or mime_lower.startswith("image/")
        or downloaded_file_path.suffix.lower()
        in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    ):
        thumbnail_relative_path = generate_thumbnail(downloaded_file_path)

    return (
        [
            models.MediaItem(
                kind=media_kind
                if media_kind in {"photo", "video", "audio"}
                else "document",
                path=relative_path,
                thumb=thumbnail_relative_path,
                size=file_size,
                mime=mime_type or None,
                name=file_name,
            )
        ],
        "downloaded",
    )


async def download_avatar(
    client: TelegramClient, entity: Any
) -> Tuple[Optional[str], bool]:
    """Download avatar and favicons; return (relative_path, changed)."""
    paths.AVATAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_avatar_path = paths.AVATAR_PATH.with_suffix(".tmp")
    downloaded_avatar_path: Optional[Path] = None
    try:
        avatar_path = await run_with_retries(
            lambda: client.download_profile_photo(entity, file=str(temp_avatar_path)),
            retries=2,
            backoff_seconds=1.5,
        )
        if not avatar_path:
            return None, False
        downloaded_avatar_path = Path(avatar_path)
        if not downloaded_avatar_path.exists() and temp_avatar_path.exists():
            downloaded_avatar_path = temp_avatar_path
        if not downloaded_avatar_path.exists():
            return None, False

        changed = True
        if paths.AVATAR_PATH.exists():
            try:
                if (
                    paths.AVATAR_PATH.read_bytes()
                    == downloaded_avatar_path.read_bytes()
                ):
                    changed = False
            except Exception:
                changed = True

        if changed:
            downloaded_avatar_path.replace(paths.AVATAR_PATH)
            try:
                generate_favicons(paths.AVATAR_PATH)
            except Exception as e:  # pragma: no cover - best-effort only
                LOGGER.warning("Could not generate favicons: %s", e)
        else:
            downloaded_avatar_path.unlink(missing_ok=True)

        return paths.AVATAR_PATH.relative_to(paths.DOCS).as_posix(), changed
    except Exception as e:
        LOGGER.warning("Could not download avatar: %s", e)
    finally:
        if downloaded_avatar_path and downloaded_avatar_path != paths.AVATAR_PATH:
            downloaded_avatar_path.unlink(missing_ok=True)
        temp_avatar_path.unlink(missing_ok=True)
    return None, False


def message_to_post_dict(
    message: Message, channel_username: Optional[str]
) -> models.PostDict:
    text = message.message or ""
    entities = message.entities or []
    try:
        html_text = telethon_html.unparse(text, entities)
        html_text = html_text.replace("\n", "<br>")
        html_text = sanitize_links(html_text)
    except Exception:
        html_text = ""

    link = None
    if channel_username:
        link = f"https://t.me/{channel_username}/{message.id}"

    post = models.Post(
        id=int(message.id),
        date=message.date.astimezone(timezone.utc).isoformat()
        if message.date
        else datetime.now(timezone.utc).isoformat(),
        edited=message.edit_date.astimezone(timezone.utc).isoformat()
        if getattr(message, "edit_date", None)
        else None,
        text=text,
        html=html_text,
        link=link,
        type=get_message_type(message),
        views=getattr(message, "views", None),
        forwards=getattr(message, "forwards", None),
        grouped_id=int(getattr(message, "grouped_id", 0))
        if getattr(message, "grouped_id", None)
        else None,
        media=[],
        reactions=extract_reactions_info(message),
    )
    return asdict(post)  # type: ignore[return-value]


def generate_thumbnail(image_path: Path) -> Optional[str]:
    try:
        paths.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        thumb_dir = paths.ASSETS_DIR / "thumbs"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / (image_path.stem + "_480.webp")

        with Image.open(image_path) as img:
            img.thumbnail((480, 480), Image.Resampling.LANCZOS)
            img.save(thumb_path, format="WEBP", quality=80, optimize=True)

        return thumb_path.relative_to(paths.DOCS).as_posix()
    except Exception as e:
        LOGGER.warning("Thumbnail generation failed for %s: %s", image_path, e)
        return None


def _square_image(img: Image.Image) -> Image.Image:
    width, height = img.size
    if width == height:
        return img
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return img.crop((left, top, left + side, top + side))


def generate_favicons(image_path: Path) -> Dict[str, str]:
    """Create favicon assets from the downloaded avatar."""
    out: Dict[str, str] = {}
    try:
        paths.DOCS.mkdir(parents=True, exist_ok=True)
        favicon_ico = paths.DOCS / "favicon.ico"
        favicon_png = paths.DOCS / "favicon-32.png"
        apple_icon = paths.DOCS / "apple-touch-icon.png"

        with Image.open(image_path) as img:
            base = _square_image(img.convert("RGBA"))

            base.resize((64, 64), Image.Resampling.LANCZOS).save(
                favicon_ico,
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
            )
            base.resize((32, 32), Image.Resampling.LANCZOS).save(
                favicon_png, format="PNG"
            )
            base.resize((180, 180), Image.Resampling.LANCZOS).save(
                apple_icon, format="PNG"
            )

        out["favicon"] = favicon_ico.relative_to(paths.DOCS).as_posix()
        out["favicon_png"] = favicon_png.relative_to(paths.DOCS).as_posix()
        out["apple_touch"] = apple_icon.relative_to(paths.DOCS).as_posix()
    except Exception as e:
        LOGGER.warning("Failed to generate favicons: %s", e)
    return out
