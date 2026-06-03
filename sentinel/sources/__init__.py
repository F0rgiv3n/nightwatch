"""Source implementations and the type registry.

Importing this package registers every built-in source (each module calls
``@register`` at import time), populating :data:`SOURCE_REGISTRY` and powering
:func:`build_source`.
"""

from __future__ import annotations

from typing import Any

# Import for side effects: each module registers its source type.
from . import github_releases, hackernews, rss, usgs  # noqa: E402,F401
from .base import SOURCE_REGISTRY, Source


def build_source(config: dict[str, Any]) -> Source:
    """Instantiate a source from its YAML config block (``type:`` selects it)."""
    cfg = dict(config)
    kind = cfg.pop("type", None)
    if kind not in SOURCE_REGISTRY:
        raise ValueError(
            f"Unknown source type {kind!r}; available: {sorted(SOURCE_REGISTRY)}"
        )
    return SOURCE_REGISTRY[kind](**cfg)


__all__ = ["SOURCE_REGISTRY", "Source", "build_source"]
