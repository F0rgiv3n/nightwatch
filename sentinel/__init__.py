"""Sentinel — a legal-first, source-agnostic change-monitoring framework.

Sentinel watches a configurable set of *sources* (official APIs, RSS/Atom feeds,
or — only where permitted — polite HTML scraping), detects *changes* against a
local history, and dispatches *notifications*. Every layer is pluggable.

The design deliberately puts legality first: API access before scraping,
conditional GETs to avoid wasted bandwidth, per-host rate limiting with
``Crawl-delay`` support, robots.txt enforcement for crawl-style sources, and an
honest, identifying ``User-Agent``.
"""

__version__ = "0.1.0"
