import json
from datetime import datetime, timezone

from scoutrss.storage import FeedState, FileStorage, MemoryStorage

DT = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
DT2 = datetime(2024, 2, 20, 8, 30, 0, tzinfo=timezone.utc)


class TestFeedState:
    def test_defaults(self):
        state = FeedState()
        assert state.last_seen is None
        assert state.seen_ids == set()
        assert state.etag is None
        assert state.modified is None


class TestMemoryStorage:
    def test_get_returns_defaults_for_unknown_id(self):
        storage = MemoryStorage()
        state = storage.get_state("unknown")
        assert state.last_seen is None
        assert state.seen_ids == set()
        assert state.etag is None

    def test_set_and_get_last_seen(self):
        storage = MemoryStorage()
        storage.set_state("feed1", last_seen=DT)
        assert storage.get_state("feed1").last_seen == DT

    def test_overwrite_last_seen(self):
        storage = MemoryStorage()
        storage.set_state("feed1", last_seen=DT)
        storage.set_state("feed1", last_seen=DT2)
        assert storage.get_state("feed1").last_seen == DT2

    def test_multiple_ids(self):
        storage = MemoryStorage()
        storage.set_state("feed1", last_seen=DT)
        storage.set_state("feed2", last_seen=DT2)
        assert storage.get_state("feed1").last_seen == DT
        assert storage.get_state("feed2").last_seen == DT2

    def test_set_and_get_seen_ids(self):
        storage = MemoryStorage()
        storage.set_state("feed1", seen_ids={"a", "b", "c"})
        assert storage.get_state("feed1").seen_ids == {"a", "b", "c"}

    def test_seen_ids_returns_copy(self):
        storage = MemoryStorage()
        storage.set_state("feed1", seen_ids={"a"})
        ids = storage.get_state("feed1").seen_ids
        ids.add("b")
        assert storage.get_state("feed1").seen_ids == {"a"}

    def test_seen_ids_independent_per_feed(self):
        storage = MemoryStorage()
        storage.set_state("feed1", seen_ids={"a"})
        storage.set_state("feed2", seen_ids={"b"})
        assert storage.get_state("feed1").seen_ids == {"a"}
        assert storage.get_state("feed2").seen_ids == {"b"}

    def test_partial_update_preserves_other_field(self):
        storage = MemoryStorage()
        storage.set_state("feed1", last_seen=DT, seen_ids={"a"})
        storage.set_state("feed1", last_seen=DT2)
        state = storage.get_state("feed1")
        assert state.last_seen == DT2
        assert state.seen_ids == {"a"}

    def test_etag_and_modified(self):
        storage = MemoryStorage()
        storage.set_state(
            "feed1", etag='"abc"', modified="Mon, 01 Jan 2024 00:00:00 GMT"
        )
        state = storage.get_state("feed1")
        assert state.etag == '"abc"'
        assert state.modified == "Mon, 01 Jan 2024 00:00:00 GMT"

    def test_partial_update_preserves_etag(self):
        storage = MemoryStorage()
        storage.set_state("feed1", last_seen=DT, etag='"abc"')
        storage.set_state("feed1", last_seen=DT2)
        assert storage.get_state("feed1").etag == '"abc"'


class TestFileStorage:
    def test_get_returns_defaults_for_unknown_id(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        state = storage.get_state("unknown")
        assert state.last_seen is None
        assert state.seen_ids == set()
        assert state.etag is None

    def test_set_and_get_last_seen(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_state("feed1", last_seen=DT)
        assert storage.get_state("feed1").last_seen == DT

    def test_overwrite_last_seen(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_state("feed1", last_seen=DT)
        storage.set_state("feed1", last_seen=DT2)
        assert storage.get_state("feed1").last_seen == DT2

    def test_persists_to_disk(self, tmp_path):
        path = tmp_path / "data.json"
        storage = FileStorage(path)
        storage.set_state("feed1", last_seen=DT)

        storage2 = FileStorage(path)
        assert storage2.get_state("feed1").last_seen == DT

    def test_creates_file_if_missing(self, tmp_path):
        path = tmp_path / "data.json"
        assert not path.exists()
        FileStorage(path)
        assert path.exists()

    def test_uses_last_seen_at_key(self, tmp_path):
        path = tmp_path / "data.json"
        storage = FileStorage(path)
        storage.set_state("feed1", last_seen=DT)
        data = json.loads(path.read_text())
        assert "last_seen_at" in data["feed1"]

    def test_multiple_ids(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_state("feed1", last_seen=DT)
        storage.set_state("feed2", last_seen=DT2)
        assert storage.get_state("feed1").last_seen == DT
        assert storage.get_state("feed2").last_seen == DT2

    def test_set_and_get_seen_ids(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_state("feed1", seen_ids={"a", "b", "c"})
        assert storage.get_state("feed1").seen_ids == {"a", "b", "c"}

    def test_seen_ids_persists(self, tmp_path):
        path = tmp_path / "data.json"
        storage = FileStorage(path)
        storage.set_state("feed1", seen_ids={"a", "b"})

        storage2 = FileStorage(path)
        assert storage2.get_state("feed1").seen_ids == {"a", "b"}

    def test_partial_update_preserves_other_field(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_state("feed1", last_seen=DT, seen_ids={"a"})
        storage.set_state("feed1", seen_ids={"a", "b"})
        state = storage.get_state("feed1")
        assert state.last_seen == DT
        assert state.seen_ids == {"a", "b"}

    def test_etag_and_modified_persist(self, tmp_path):
        path = tmp_path / "data.json"
        storage = FileStorage(path)
        storage.set_state(
            "feed1", etag='"abc"', modified="Mon, 01 Jan 2024 00:00:00 GMT"
        )

        storage2 = FileStorage(path)
        state = storage2.get_state("feed1")
        assert state.etag == '"abc"'
        assert state.modified == "Mon, 01 Jan 2024 00:00:00 GMT"
