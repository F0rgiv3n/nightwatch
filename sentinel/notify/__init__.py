"""Notification backends.

A notifier turns a detected :class:`~sentinel.diffing.Change` into an outbound
alert. The abstraction is deliberately tiny so adding Telegram, Discord, email,
or a webhook later is a single small class.
"""

from __future__ import annotations

from typing import Any

from .base import Notifier
from .ntfy import NtfyNotifier

_BACKENDS: dict[str, type[Notifier]] = {
    "ntfy": NtfyNotifier,
}


def build_notifier(config: dict[str, Any]) -> Notifier:
    """Instantiate a notifier from its YAML config block (``type:`` selects it)."""
    cfg = dict(config)
    kind = cfg.pop("type", None)
    if kind not in _BACKENDS:
        raise ValueError(
            f"Unknown notifier type {kind!r}; available: {sorted(_BACKENDS)}"
        )
    return _BACKENDS[kind](**cfg)


__all__ = ["Notifier", "NtfyNotifier", "build_notifier"]
