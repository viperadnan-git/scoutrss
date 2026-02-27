from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class StorageAdapter(ABC):
    @abstractmethod
    def get_last_seen(self, id: str) -> datetime | None: ...

    @abstractmethod
    def set_last_seen(self, id: str, last_seen: datetime) -> None: ...
