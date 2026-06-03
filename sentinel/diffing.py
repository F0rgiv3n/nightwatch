"""The diff engine: turn "what we saw last time" + "what we see now" into changes.

Sentinel reduces every source to a list of :class:`~sentinel.models.Item`, so a
single, content-agnostic algorithm covers all of them:

* an item whose ``id`` we've never seen  -> ``new``
* an item we've seen but whose *content hash* differs -> ``updated``

The content hash is a stable SHA-256 over the meaningful fields, which is what
makes "single state" watches (one item that mutates) work the same as feeds.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from .models import Item, Snapshot

ChangeKind = Literal["new", "updated"]


@dataclass(slots=True)
class Change:
    kind: ChangeKind
    item: Item


def content_hash(item: Item) -> str:
    """A stable hash of an item's meaningful content (ignores ``id``)."""
    payload = json.dumps(
        {
            "title": item.title,
            "url": item.url,
            "summary": item.summary,
            "extra": item.extra,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def diff(previous: dict[str, str], snapshot: Snapshot) -> list[Change]:
    """Compare a snapshot against previously seen ``{item_id: content_hash}``.

    Returns changes in the order items appear in the snapshot. Disappearance of
    items is intentionally *not* reported — most feeds naturally roll old
    entries off the end, and treating that as a change would be noise.
    """
    changes: list[Change] = []
    for item in snapshot.items:
        current = content_hash(item)
        seen = previous.get(item.id)
        if seen is None:
            changes.append(Change("new", item))
        elif seen != current:
            changes.append(Change("updated", item))
    return changes
