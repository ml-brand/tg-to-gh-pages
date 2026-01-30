from __future__ import annotations

from typing import List

from . import models


WATCHED_FIELDS: List[str] = [
    "date",
    "html",
    "text",
    "edited",
    "views",
    "reactions",
    "forwards",
    "type",
]


def post_changed(old: models.PostDict, new: models.PostDict) -> bool:
    for field in WATCHED_FIELDS:
        if old.get(field) != new.get(field):
            return True
    return False
