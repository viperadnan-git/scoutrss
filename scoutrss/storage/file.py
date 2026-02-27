from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from .adapter import StorageAdapter


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

    def get_last_seen(self, id: str) -> datetime | None:
        with self._lock:
            entry = self._read().get(id)
            if not entry:
                return None
            return datetime.fromisoformat(entry["last_seen_at"])

    def set_last_seen(self, id: str, last_seen: datetime) -> None:
        with self._lock:
            data = self._read()
            data[id] = {"last_seen_at": last_seen.isoformat()}
            self._write(data)
