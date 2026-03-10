from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from .adapter import FeedState, StorageAdapter


class FileStorage(StorageAdapter):
    def __init__(self, path: str = "scoutrss.data.json"):
        self._path = Path(path)
        self._lock = threading.Lock()
        if not self._path.exists():
            self._path.write_text("{}")

    def _read(self) -> dict:
        return json.loads(self._path.read_text())

    def _write(self, data: dict) -> None:
        self._path.write_text(json.dumps(data))

    def get_state(self, id: str) -> FeedState:
        with self._lock:
            entry = self._read().get(id, {})
            val = entry.get("last_seen_at")
            return FeedState(
                last_seen=datetime.fromisoformat(val) if val else None,
                seen_ids=set(entry.get("seen_ids", [])),
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
        with self._lock:
            data = self._read()
            entry = data.setdefault(id, {})
            if last_seen is not None:
                entry["last_seen_at"] = last_seen.isoformat()
            if seen_ids is not None:
                entry["seen_ids"] = list(seen_ids)
            if etag is not None:
                entry["etag"] = etag
            if modified is not None:
                entry["modified"] = modified
            self._write(data)
