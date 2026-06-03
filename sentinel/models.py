"""Core data structures shared across the framework.

Everything a source produces is normalized into :class:`Item` objects collected
in a :class:`Snapshot`. Keeping a single, source-agnostic representation is what
lets the diff engine, storage, and notifiers stay completely decoupled from any
particular source (GitHub, RSS, Hacker News, ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Item:
    """A single normalized unit of content from a source.

    Examples: one GitHub release, one Hacker News story, one RSS entry, or — for
    "single state" watches — one blob whose content hash changes over time.
    """

    id: str
    """Stable identifier, unique *within* a source. Used to tell new from seen."""

    title: str
    url: str | None = None
    summary: str | None = None
    timestamp: datetime | None = None
    extra: dict = field(default_factory=dict)
    """Source-specific fields that don't fit the common shape."""


@dataclass(slots=True)
class Snapshot:
    """The full normalized state of a source at one point in time."""

    source: str
    items: list[Item]
    etag: str | None = None
    last_modified: str | None = None
    """HTTP validators echoed back so the next poll can do a conditional GET."""


@dataclass(slots=True)
class SourceState:
    """Persisted, per-source cursor used to drive conditional requests."""

    name: str
    etag: str | None = None
    last_modified: str | None = None
