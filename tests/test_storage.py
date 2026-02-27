import json
from datetime import datetime, timezone

from scoutrss.storage import FileStorage, MemoryStorage

DT = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
DT2 = datetime(2024, 2, 20, 8, 30, 0, tzinfo=timezone.utc)


class TestMemoryStorage:
    def test_get_returns_none_for_unknown_id(self):
        storage = MemoryStorage()
        assert storage.get_last_seen("unknown") is None

    def test_set_and_get(self):
        storage = MemoryStorage()
        storage.set_last_seen("feed1", DT)
        assert storage.get_last_seen("feed1") == DT

    def test_overwrite(self):
        storage = MemoryStorage()
        storage.set_last_seen("feed1", DT)
        storage.set_last_seen("feed1", DT2)
        assert storage.get_last_seen("feed1") == DT2

    def test_multiple_ids(self):
        storage = MemoryStorage()
        storage.set_last_seen("feed1", DT)
        storage.set_last_seen("feed2", DT2)
        assert storage.get_last_seen("feed1") == DT
        assert storage.get_last_seen("feed2") == DT2


class TestFileStorage:
    def test_get_returns_none_for_unknown_id(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        assert storage.get_last_seen("unknown") is None

    def test_set_and_get(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_last_seen("feed1", DT)
        assert storage.get_last_seen("feed1") == DT

    def test_overwrite(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_last_seen("feed1", DT)
        storage.set_last_seen("feed1", DT2)
        assert storage.get_last_seen("feed1") == DT2

    def test_persists_to_disk(self, tmp_path):
        path = tmp_path / "data.json"
        storage = FileStorage(path)
        storage.set_last_seen("feed1", DT)

        storage2 = FileStorage(path)
        assert storage2.get_last_seen("feed1") == DT

    def test_creates_file_if_missing(self, tmp_path):
        path = tmp_path / "data.json"
        assert not path.exists()
        FileStorage(path)
        assert path.exists()

    def test_uses_last_seen_at_key(self, tmp_path):
        path = tmp_path / "data.json"
        storage = FileStorage(path)
        storage.set_last_seen("feed1", DT)
        data = json.loads(path.read_text())
        assert "last_seen_at" in data["feed1"]

    def test_multiple_ids(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_last_seen("feed1", DT)
        storage.set_last_seen("feed2", DT2)
        assert storage.get_last_seen("feed1") == DT
        assert storage.get_last_seen("feed2") == DT2
