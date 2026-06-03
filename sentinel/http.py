"""A "polite" async HTTP client — the heart of Sentinel's legal-first stance.

Responsibilities layered on top of :class:`httpx.AsyncClient`:

* **Honest identity** — every request carries an identifying ``User-Agent``.
* **robots.txt** — for crawl-style sources, fetch and honor the site's rules
  (and any ``Crawl-delay``). Disallowed URLs raise :class:`RobotsDisallowed`.
* **Rate limiting** — never hammer a host: enforce a minimum delay between
  requests *per host*, taking the larger of our configured interval and the
  site's advertised ``Crawl-delay``.
* **Conditional GET** — send ``If-None-Match`` / ``If-Modified-Since`` so the
  server can answer ``304 Not Modified`` and save everyone bandwidth.

Note on robots.txt and APIs: robots.txt governs *crawlers*. Documented public
APIs (GitHub, Hacker News, USGS) are meant to be called programmatically, so
their source classes opt out of robots checks while still rate-limiting.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)


class RobotsDisallowed(Exception):
    """Raised when robots.txt forbids fetching a URL for our User-Agent."""


class PoliteClient:
    """An async HTTP client that plays by the rules."""

    def __init__(
        self,
        user_agent: str,
        *,
        min_interval: float = 1.0,
        timeout: float = 20.0,
    ) -> None:
        self.user_agent = user_agent
        self.min_interval = min_interval
        self._client = httpx.AsyncClient(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> PoliteClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        respect_robots: bool = True,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Perform a rate-limited, optionally conditional GET.

        Returns the raw :class:`httpx.Response`; callers should treat a 304 as
        "no change". Raises :class:`RobotsDisallowed` if disallowed.
        """
        parsed = urlparse(url)
        host = parsed.netloc
        crawl_delay: float | None = None

        if respect_robots:
            rfp = await self._robots_for(f"{parsed.scheme}://{host}")
            if not rfp.can_fetch(self.user_agent, url):
                raise RobotsDisallowed(url)
            crawl_delay = rfp.crawl_delay(self.user_agent)

        await self._throttle(host, crawl_delay)

        request_headers = dict(headers or {})
        if etag:
            request_headers["If-None-Match"] = etag
        if last_modified:
            request_headers["If-Modified-Since"] = last_modified

        logger.debug("GET %s (conditional=%s)", url, bool(etag or last_modified))
        return await self._client.get(url, headers=request_headers)

    async def _throttle(self, host: str, crawl_delay: float | None) -> None:
        """Block until enough time has elapsed since the last request to ``host``."""
        delay = max(self.min_interval, crawl_delay or 0.0)
        loop = asyncio.get_running_loop()
        async with self._lock:
            last = self._last_request.get(host)
            now = loop.time()
            if last is not None:
                wait = delay - (now - last)
                if wait > 0:
                    logger.debug("Rate limiting %s for %.2fs", host, wait)
                    await asyncio.sleep(wait)
            self._last_request[host] = loop.time()

    async def _robots_for(self, base: str) -> RobotFileParser:
        """Fetch and cache the parsed robots.txt for an origin.

        We fetch via our own client (so the request carries our User-Agent);
        on any error we fail *open* — a missing/unreachable robots.txt is, by
        convention, treated as "no restrictions".
        """
        if base in self._robots:
            return self._robots[base]

        rfp = RobotFileParser()
        try:
            resp = await self._client.get(f"{base}/robots.txt")
            if resp.status_code == 200:
                rfp.parse(resp.text.splitlines())
            else:
                rfp.allow_all = True
        except httpx.HTTPError:
            logger.warning("Could not fetch robots.txt for %s; assuming allowed", base)
            rfp.allow_all = True

        self._robots[base] = rfp
        return rfp
