"""The async scheduler that ties everything together.

For each source it runs an independent loop:

    fetch -> (304? stop) -> diff against history -> notify new/updated -> persist

Sources poll on their own intervals concurrently. The first time a source is
seen, its current items are recorded as a *baseline* without notifying (unless
``notify_on_first_run`` is set), so you don't get flooded on startup.

A heartbeat file is touched after every cycle; the Docker ``HEALTHCHECK`` reads
its age to detect a wedged process.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .config import Config
from .diffing import diff
from .http import PoliteClient, RobotsDisallowed
from .models import SourceState
from .sources import Source
from .storage import Storage

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, config: Config, storage: Storage, client: PoliteClient) -> None:
        self.config = config
        self.storage = storage
        self.client = client

    def _heartbeat(self) -> None:
        if not self.config.heartbeat_file:
            return
        path = Path(self.config.heartbeat_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    async def poll_once(self, source: Source) -> int:
        """Run one fetch/diff/notify cycle. Returns the number of changes sent."""
        state = self.storage.get_state(source.name)
        snapshot = await source.fetch(self.client, state)
        if snapshot is None:
            logger.debug("[%s] not modified", source.name)
            return 0

        first_run = not self.storage.has_history(source.name)
        changes = diff(self.storage.get_seen(source.name), snapshot)

        sent = 0
        if changes and (not first_run or self.config.notify_on_first_run):
            for change in changes:
                await self.config.notifier.send(source.name, change)
                sent += 1
            logger.info("[%s] %d change(s) notified", source.name, sent)
        elif first_run:
            logger.info(
                "[%s] baseline recorded (%d items, no alerts)",
                source.name,
                len(snapshot.items),
            )

        self.storage.record(source.name, snapshot.items)
        self.storage.save_state(
            SourceState(source.name, etag=snapshot.etag, last_modified=snapshot.last_modified)
        )
        return sent

    async def _loop(self, source: Source) -> None:
        while True:
            try:
                await self.poll_once(source)
            except RobotsDisallowed as exc:
                logger.error("[%s] robots.txt disallows %s — skipping", source.name, exc)
            except Exception:  # noqa: BLE001 - one bad poll must not kill the loop
                logger.exception("[%s] poll failed", source.name)
            self._heartbeat()
            await asyncio.sleep(source.interval)

    async def run(self) -> None:
        logger.info(
            "Starting Sentinel with %d source(s): %s",
            len(self.config.sources),
            ", ".join(s.name for s in self.config.sources),
        )
        self._heartbeat()
        await asyncio.gather(*(self._loop(s) for s in self.config.sources))

    async def run_once(self) -> int:
        """Poll every source a single time (used by the ``once`` command)."""
        total = 0
        for source in self.config.sources:
            try:
                total += await self.poll_once(source)
            except Exception:  # noqa: BLE001
                logger.exception("[%s] poll failed", source.name)
        self._heartbeat()
        return total
