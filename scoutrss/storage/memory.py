from __future__ import annotations

from datetime import datetime

from .adapter import StorageAdapter


class MemoryStorage(StorageAdapter):
    def __init__(self):
        self._data: dict[str, datetime] = {}

    def get_last_seen(self, id: str) -> datetime | None:
        return self._data.get(id)

    def set_last_seen(self, id: str, last_seen: datetime) -> None:
        self._data[id] = last_seen
