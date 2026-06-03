"""The notifier interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..diffing import Change


class Notifier(ABC):
    @abstractmethod
    async def send(self, source: str, change: Change) -> None:
        """Deliver a single change. Implementations should not raise on
        transient delivery errors — log and move on so one failed push never
        stops the monitor."""

    async def aclose(self) -> None:  # noqa: B027 - optional hook, not all notifiers hold resources
        """Release any held resources (HTTP clients, etc.)."""
