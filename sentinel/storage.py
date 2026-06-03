"""SQLite-backed history.

Two small tables keep Sentinel stateless between runs:

* ``source_state`` — the conditional-GET cursor (ETag / Last-Modified) per source.
* ``seen_items``  — every item id we've encountered plus its content hash, so we
  can tell new/updated from already-known across restarts.

SQLite is intentional: zero-config, single file, trivially persisted via a Docker
volume. Calls are synchronous but local and sub-millisecond, so they run inline
within the async loop without meaningful blocking.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .diffing import content_hash
from .models import Item, SourceState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_state (
    name          TEXT PRIMARY KEY,
    etag          TEXT,
    last_modified TEXT
);

CREATE TABLE IF NOT EXISTS seen_items (
    source       TEXT NOT NULL,
    item_id      TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    title        TEXT,
    url          TEXT,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    PRIMARY KEY (source, item_id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.parent != Path(""):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- conditional-GET cursor -------------------------------------------------

    def get_state(self, source: str) -> SourceState:
        row = self._conn.execute(
            "SELECT etag, last_modified FROM source_state WHERE name = ?", (source,)
        ).fetchone()
        if row is None:
            return SourceState(name=source)
        return SourceState(name=source, etag=row["etag"], last_modified=row["last_modified"])

    def save_state(self, state: SourceState) -> None:
        self._conn.execute(
            """
            INSERT INTO source_state (name, etag, last_modified)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET etag=excluded.etag,
                                            last_modified=excluded.last_modified
            """,
            (state.name, state.etag, state.last_modified),
        )
        self._conn.commit()

    # -- seen items -------------------------------------------------------------

    def get_seen(self, source: str) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT item_id, content_hash FROM seen_items WHERE source = ?", (source,)
        ).fetchall()
        return {row["item_id"]: row["content_hash"] for row in rows}

    def has_history(self, source: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen_items WHERE source = ? LIMIT 1", (source,)
        ).fetchone()
        return row is not None

    def record(self, source: str, items: list[Item]) -> None:
        """Upsert items, refreshing their content hash and ``last_seen``."""
        now = _now()
        with self._conn:
            for item in items:
                self._conn.execute(
                    """
                    INSERT INTO seen_items
                        (source, item_id, content_hash, title, url, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, item_id) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        title        = excluded.title,
                        url          = excluded.url,
                        last_seen    = excluded.last_seen
                    """,
                    (source, item.id, content_hash(item), item.title, item.url, now, now),
                )
