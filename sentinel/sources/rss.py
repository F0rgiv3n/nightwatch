"""Generic RSS / Atom feed source.

Covers an enormous slice of the legal monitoring space for free: news sites,
blogs, PyPI release feeds, arXiv, GitHub's own ``.atom`` endpoints, subreddit
``.rss`` feeds, status pages, and more. Uses conditional GET so well-behaved
feeds answer 304 when nothing changed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from time import mktime

import feedparser

from ..http import PoliteClient
from ..models import Item, Snapshot, SourceState
from .base import Source, register


def _entry_time(entry: feedparser.FeedParserDict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)


@register
class RSSSource(Source):
    type = "rss"

    def __init__(self, name: str, url: str, **kwargs: object) -> None:
        super().__init__(name, **kwargs)  # type: ignore[arg-type]
        self.url = url

    async def fetch(self, client: PoliteClient, state: SourceState) -> Snapshot | None:
        resp = await client.get(
            self.url,
            etag=state.etag,
            last_modified=state.last_modified,
            respect_robots=self.respect_robots,
        )
        if resp.status_code == 304:
            return None
        resp.raise_for_status()

        feed = feedparser.parse(resp.content)
        items = [
            Item(
                id=entry.get("id") or entry.get("link") or entry.get("title", ""),
                title=entry.get("title", "(untitled)"),
                url=entry.get("link"),
                summary=entry.get("summary"),
                timestamp=_entry_time(entry),
            )
            for entry in feed.entries
        ]
        return Snapshot(
            source=self.name,
            items=items,
            etag=resp.headers.get("ETag"),
            last_modified=resp.headers.get("Last-Modified"),
        )
