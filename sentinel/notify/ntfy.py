"""ntfy.sh notification backend.

ntfy is a dead-simple pub/sub push service: POST a message body to
``{server}/{topic}`` and every subscribed device gets a notification. Optional
HTTP Basic auth supports private/self-hosted topics.
"""

from __future__ import annotations

import logging

import httpx

from .base import Change, Notifier

logger = logging.getLogger(__name__)


class NtfyNotifier(Notifier):
    def __init__(
        self,
        topic: str,
        *,
        server: str = "https://ntfy.sh",
        username: str | None = None,
        password: str | None = None,
        priority: str | None = None,
    ) -> None:
        if not topic:
            raise ValueError("ntfy notifier requires a 'topic'")
        self.url = f"{server.rstrip('/')}/{topic}"
        self.priority = priority
        auth = (username, password) if username and password else None
        self._client = httpx.AsyncClient(auth=auth, timeout=15.0)

    async def send(self, source: str, change: Change) -> None:
        item = change.item
        prefix = "🆕" if change.kind == "new" else "✏️"
        headers = {
            "Title": f"{prefix} [{source}] {item.title}".encode(),
            "Tags": "satellite",
        }
        if item.url:
            headers["Click"] = item.url
        if self.priority:
            headers["Priority"] = self.priority

        body = item.summary or item.url or item.title
        try:
            resp = await self._client.post(self.url, data=body.encode("utf-8"), headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("ntfy delivery failed for %s/%s: %s", source, item.id, exc)

    async def aclose(self) -> None:
        await self._client.aclose()
