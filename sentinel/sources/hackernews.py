"""Hacker News source — via the official Algolia HN Search API.

``http://hn.algolia.com/api/v1/search_by_date`` returns recent stories matching a
query in a single request (far friendlier than walking the Firebase item API).
The API is public, keyless, and intended for exactly this use.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

from ..http import PoliteClient
from ..models import Item, Snapshot, SourceState
from .base import Source, register


@register
class HackerNewsSource(Source):
    type = "hackernews"
    default_respect_robots = False  # documented public API

    def __init__(
        self,
        name: str,
        query: str,
        *,
        limit: int = 30,
        **kwargs: object,
    ) -> None:
        super().__init__(name, **kwargs)  # type: ignore[arg-type]
        self.query = query
        self.limit = limit

    async def fetch(self, client: PoliteClient, state: SourceState) -> Snapshot | None:
        params = urlencode(
            {"query": self.query, "tags": "story", "hitsPerPage": self.limit}
        )
        url = f"https://hn.algolia.com/api/v1/search_by_date?{params}"
        resp = await client.get(url, respect_robots=self.respect_robots)
        resp.raise_for_status()

        items = []
        for hit in resp.json().get("hits", []):
            object_id = hit["objectID"]
            items.append(
                Item(
                    id=object_id,
                    title=hit.get("title") or hit.get("story_title") or "(untitled)",
                    url=hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                    summary=(
                        f"{hit.get('points', 0)} points · "
                        f"{hit.get('num_comments', 0)} comments"
                    ),
                    timestamp=_from_epoch(hit.get("created_at_i")),
                    extra={"author": hit.get("author")},
                )
            )
        return Snapshot(source=self.name, items=items)


def _from_epoch(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)
