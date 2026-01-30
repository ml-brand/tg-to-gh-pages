from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict


@dataclass
class MediaItem:
    kind: str  # photo|video|audio|document
    path: str  # relative to docs/
    thumb: Optional[str] = None
    size: Optional[int] = None
    mime: Optional[str] = None
    name: Optional[str] = None


@dataclass
class ReactionInfo:
    total: int
    details: Optional[List[Dict[str, Any]]] = None


@dataclass
class Post:
    id: int
    date: str
    edited: Optional[str]
    text: str
    html: str
    link: Optional[str]
    type: str
    views: Optional[int]
    forwards: Optional[int]
    grouped_id: Optional[int]
    media: List[MediaItem]
    reactions: Optional[ReactionInfo]


class MediaDict(TypedDict, total=False):
    kind: str
    path: str
    thumb: Optional[str]
    size: Optional[int]
    mime: Optional[str]
    name: Optional[str]


class ReactionDict(TypedDict, total=False):
    total: int
    details: Optional[List[Dict[str, Any]]]


class PostDict(TypedDict, total=False):
    id: int
    date: str
    edited: Optional[str]
    text: str
    html: str
    link: Optional[str]
    type: str
    views: Optional[int]
    forwards: Optional[int]
    grouped_id: Optional[int]
    media: List[MediaDict]
    reactions: Optional[ReactionDict]
    media_status: Optional[str]


class StatsDict(TypedDict, total=False):
    new: int
    updated: int
    media_downloaded: int


class MetaDict(TypedDict, total=False):
    title: Optional[str]
    username: Optional[str]
    channel: str
    last_sync_utc: Optional[str]
    posts_count: int
    last_seen_message_id: int
    avatar: Optional[str]
    stats: StatsDict
    meta_schema_version: Optional[str]
    posts_schema_version: Optional[str]
