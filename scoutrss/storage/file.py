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
                seen_ids=list(entry.get("seen_ids", [])),
                etag=entry.get("etag"),
                modified=entry.get("modified"),
            )

    def set_state(self, id: str, state: FeedState) -> None:
        with self._lock:
            data = self._read()
            data[id] = {
                "last_seen_at": state.last_seen.isoformat()
                if state.last_seen
                else None,
                "seen_ids": list(state.seen_ids),
                "etag": state.etag,
                "modified": state.modified,
            }
            self._write(data)
