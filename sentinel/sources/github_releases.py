"""GitHub Releases source — via the official, documented REST API.

Watches ``https://api.github.com/repos/{owner}/{repo}/releases``. The GitHub API
is designed for programmatic use and supports ETag-based conditional requests
that do **not** count against your rate limit when they return 304 — exactly the
kind of well-behaved access Sentinel is built around. No token is required for
public repos (optionally set ``GITHUB_TOKEN`` for a higher rate limit).
"""

from __future__ import annotations

import os
from datetime import datetime

from ..http import PoliteClient
from ..models import Item, Snapshot, SourceState
from .base import Source, register


@register
class GitHubReleasesSource(Source):
    type = "github_releases"
    # robots.txt on api.github.com disallows crawlers; the documented API is the
    # sanctioned access path, so we rate-limit but skip robots here.
    default_respect_robots = False

    def __init__(self, name: str, repo: str, **kwargs: object) -> None:
        super().__init__(name, **kwargs)  # type: ignore[arg-type]
        self.repo = repo  # "owner/name"

    async def fetch(self, client: PoliteClient, state: SourceState) -> Snapshot | None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = await client.get(
            f"https://api.github.com/repos/{self.repo}/releases",
            etag=state.etag,
            respect_robots=self.respect_robots,
            headers=headers,
        )
        if resp.status_code == 304:
            return None
        resp.raise_for_status()

        items = [
            Item(
                id=str(release["id"]),
                title=release.get("name") or release["tag_name"],
                url=release.get("html_url"),
                summary=(release.get("body") or "").strip()[:500] or None,
                timestamp=_parse(release.get("published_at")),
                extra={"tag": release.get("tag_name"), "prerelease": release.get("prerelease")},
            )
            for release in resp.json()
        ]
        return Snapshot(source=self.name, items=items, etag=resp.headers.get("ETag"))


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
