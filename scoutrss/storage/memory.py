from __future__ import annotations

from .adapter import FeedState, StorageAdapter


class MemoryStorage(StorageAdapter):
    def __init__(self):
        self._data: dict[str, FeedState] = {}

    def get_state(self, id: str) -> FeedState:
        return self._data.get(id, FeedState())

    def set_state(self, id: str, state: FeedState) -> None:
        self._data[id] = state
