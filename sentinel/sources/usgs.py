"""USGS Earthquakes source — via the official public GeoJSON feeds.

The U.S. Geological Survey publishes real-time earthquake feeds as GeoJSON, free
and keyless, explicitly for public/programmatic use. We watch a feed (default:
all magnitude 4.5+ quakes in the past day) and can additionally filter by a
minimum magnitude locally.

Feed catalog: https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..http import PoliteClient
from ..models import Item, Snapshot, SourceState
from .base import Source, register

_FEED_BASE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"


@register
class USGSEarthquakeSource(Source):
    type = "usgs_earthquakes"
    default_respect_robots = False  # documented public data feed

    def __init__(
        self,
        name: str,
        *,
        feed: str = "4.5_day",
        min_magnitude: float = 0.0,
        **kwargs: object,
    ) -> None:
        super().__init__(name, **kwargs)  # type: ignore[arg-type]
        # e.g. "significant_week", "4.5_day", "2.5_hour", "all_day"
        self.feed = feed
        self.min_magnitude = min_magnitude

    async def fetch(self, client: PoliteClient, state: SourceState) -> Snapshot | None:
        url = f"{_FEED_BASE}/{self.feed}.geojson"
        resp = await client.get(
            url,
            etag=state.etag,
            last_modified=state.last_modified,
            respect_robots=self.respect_robots,
        )
        if resp.status_code == 304:
            return None
        resp.raise_for_status()

        items = []
        for feature in resp.json().get("features", []):
            props = feature.get("properties", {})
            mag = props.get("mag")
            if mag is None or mag < self.min_magnitude:
                continue
            items.append(
                Item(
                    id=feature["id"],
                    title=f"M{mag} — {props.get('place', 'unknown location')}",
                    url=props.get("url"),
                    summary=_describe(props),
                    timestamp=_from_ms(props.get("time")),
                    extra={"magnitude": mag, "tsunami": props.get("tsunami")},
                )
            )
        return Snapshot(
            source=self.name,
            items=items,
            etag=resp.headers.get("ETag"),
            last_modified=resp.headers.get("Last-Modified"),
        )


def _describe(props: dict) -> str:
    bits = [f"Magnitude {props.get('mag')}"]
    if props.get("place"):
        bits.append(str(props["place"]))
    if props.get("tsunami"):
        bits.append("⚠️ tsunami flag set")
    return " · ".join(bits)


def _from_ms(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
