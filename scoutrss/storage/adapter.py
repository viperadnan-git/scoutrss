from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FeedState:
    last_seen: datetime | None = None
    seen_ids: set[str] = field(default_factory=set)
    etag: str | None = None
    modified: str | None = None


class StorageAdapter(ABC):
    @abstractmethod
    def get_state(self, id: str) -> FeedState:
        """Return the stored state for the given feed id."""
        ...

    @abstractmethod
    def set_state(
        self,
        id: str,
        last_seen: datetime | None = None,
        seen_ids: set[str] | None = None,
        etag: str | None = None,
        modified: str | None = None,
    ) -> None:
        """Persist state for the given feed id.

        Only provided (non-None) fields are updated.
        """
        ...
