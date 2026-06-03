"""Declarative YAML configuration.

A config file describes global settings, one notifier, and a list of sources.
``${VAR}`` (and ``${VAR:-default}``) placeholders anywhere in the file are
expanded from the environment, so secrets like ntfy credentials never live in
the YAML itself.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .notify import Notifier, build_notifier
from .sources import Source, build_source

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        return os.environ.get(name, default if default is not None else "")

    return _ENV_PATTERN.sub(repl, value)


def _expand_tree(node: Any) -> Any:
    if isinstance(node, str):
        return _expand(node)
    if isinstance(node, dict):
        return {k: _expand_tree(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand_tree(v) for v in node]
    return node


@dataclass(slots=True)
class Config:
    user_agent: str
    database: str
    default_interval: int
    sources: list[Source]
    notifier: Notifier
    notify_on_first_run: bool = False
    heartbeat_file: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def load_config(path: str | Path) -> Config:
    text = Path(path).read_text(encoding="utf-8")
    data = _expand_tree(yaml.safe_load(text) or {})

    if "notify" not in data:
        raise ValueError("config must define a 'notify' block")
    if not data.get("sources"):
        raise ValueError("config must define at least one source")

    default_interval = int(data.get("default_interval", 300))

    sources: list[Source] = []
    for entry in data["sources"]:
        entry.setdefault("interval", default_interval)
        sources.append(build_source(entry))

    user_agent = data.get(
        "user_agent",
        "Sentinel/0.1 (+https://github.com/yourname/sentinel)",
    )

    return Config(
        user_agent=user_agent,
        database=data.get("database", "data/sentinel.db"),
        default_interval=default_interval,
        sources=sources,
        notifier=build_notifier(data["notify"]),
        notify_on_first_run=bool(data.get("notify_on_first_run", False)),
        heartbeat_file=data.get("heartbeat_file", "data/heartbeat"),
        raw=data,
    )
