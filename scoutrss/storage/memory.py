from __future__ import annotations

from datetime import datetime

from .adapter import FeedState, StorageAdapter


class MemoryStorage(StorageAdapter):
    def __init__(self):
        self._data: dict[str, dict] = {}

    def get_state(self, id: str) -> FeedState:
        entry = self._data.get(id, {})
        return FeedState(
            last_seen=entry.get("last_seen"),
            seen_ids=set(entry.get("seen_ids", ())),
            etag=entry.get("etag"),
            modified=entry.get("modified"),
        )

    def set_state(
        self,
        id: str,
        last_seen: datetime | None = None,
        seen_ids: set[str] | None = None,
        etag: str | None = None,
        modified: str | None = None,
    ) -> None:
        entry = self._data.setdefault(id, {})
        if last_seen is not None:
            entry["last_seen"] = last_seen
        if seen_ids is not None:
            entry["seen_ids"] = seen_ids
        if etag is not None:
            entry["etag"] = etag
        if modified is not None:
            entry["modified"] = modified
