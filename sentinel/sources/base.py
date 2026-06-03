"""The :class:`Source` interface and a tiny type registry.

A source knows how to fetch its corner of the world and normalize it into a
:class:`~sentinel.models.Snapshot`. Everything else (diffing, storage, notifying)
is handled generically, so adding a source is just: subclass, set ``type``,
decorate with :func:`register`, implement :meth:`fetch`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from ..http import PoliteClient
from ..models import Snapshot, SourceState

SOURCE_REGISTRY: dict[str, type[Source]] = {}


def register(cls: type[Source]) -> type[Source]:
    """Class decorator that registers a source under its ``type`` string."""
    if not getattr(cls, "type", None):
        raise ValueError(f"{cls.__name__} must define a 'type'")
    SOURCE_REGISTRY[cls.type] = cls
    return cls


class Source(ABC):
    type: ClassVar[str] = ""

    #: Whether to consult robots.txt. Documented public APIs override to False.
    default_respect_robots: ClassVar[bool] = True

    def __init__(
        self,
        name: str,
        *,
        interval: int = 300,
        respect_robots: bool | None = None,
    ) -> None:
        self.name = name
        self.interval = interval
        self.respect_robots = (
            self.default_respect_robots if respect_robots is None else respect_robots
        )

    @abstractmethod
    async def fetch(self, client: PoliteClient, state: SourceState) -> Snapshot | None:
        """Fetch and normalize current state.

        Return ``None`` to signal "nothing changed" (e.g. an HTTP 304), which
        lets the scheduler skip diffing entirely.
        """

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} interval={self.interval}>"
