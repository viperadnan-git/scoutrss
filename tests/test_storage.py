import json
from datetime import datetime, timezone

from scoutrss.storage import FeedState, FileStorage, MemoryStorage

DT = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
DT2 = datetime(2024, 2, 20, 8, 30, 0, tzinfo=timezone.utc)


class TestFeedState:
    def test_defaults(self):
        state = FeedState()
        assert state.last_seen is None
        assert state.seen_ids == []
        assert state.etag is None
        assert state.modified is None


class TestMemoryStorage:
    def test_get_returns_defaults_for_unknown_id(self):
        storage = MemoryStorage()
        state = storage.get_state("unknown")
        assert state.last_seen is None
        assert state.seen_ids == []
        assert state.etag is None

    def test_set_and_get(self):
        storage = MemoryStorage()
        storage.set_state("feed1", FeedState(last_seen=DT))
        assert storage.get_state("feed1").last_seen == DT

    def test_overwrite(self):
        storage = MemoryStorage()
        storage.set_state("feed1", FeedState(last_seen=DT))
        storage.set_state("feed1", FeedState(last_seen=DT2))
        assert storage.get_state("feed1").last_seen == DT2

    def test_multiple_ids(self):
        storage = MemoryStorage()
        storage.set_state("feed1", FeedState(last_seen=DT))
        storage.set_state("feed2", FeedState(last_seen=DT2))
        assert storage.get_state("feed1").last_seen == DT
        assert storage.get_state("feed2").last_seen == DT2

    def test_seen_ids(self):
        storage = MemoryStorage()
        storage.set_state("feed1", FeedState(seen_ids=["a", "b", "c"]))
        assert storage.get_state("feed1").seen_ids == ["a", "b", "c"]

    def test_etag_and_modified(self):
        storage = MemoryStorage()
        storage.set_state(
            "feed1",
            FeedState(etag='"abc"', modified="Mon, 01 Jan 2024 00:00:00 GMT"),
        )
        state = storage.get_state("feed1")
        assert state.etag == '"abc"'
        assert state.modified == "Mon, 01 Jan 2024 00:00:00 GMT"

    def test_full_state_roundtrip(self):
        storage = MemoryStorage()
        original = FeedState(
            last_seen=DT,
            seen_ids=["a", "b"],
            etag='"abc"',
            modified="Mon, 01 Jan 2024",
        )
        storage.set_state("feed1", original)
        state = storage.get_state("feed1")
        assert state.last_seen == DT
        assert state.seen_ids == ["a", "b"]
        assert state.etag == '"abc"'
        assert state.modified == "Mon, 01 Jan 2024"


class TestFileStorage:
    def test_get_returns_defaults_for_unknown_id(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        state = storage.get_state("unknown")
        assert state.last_seen is None
        assert state.seen_ids == []
        assert state.etag is None

    def test_set_and_get(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_state("feed1", FeedState(last_seen=DT))
        assert storage.get_state("feed1").last_seen == DT

    def test_overwrite(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_state("feed1", FeedState(last_seen=DT))
        storage.set_state("feed1", FeedState(last_seen=DT2))
        assert storage.get_state("feed1").last_seen == DT2

    def test_persists_to_disk(self, tmp_path):
        path = tmp_path / "data.json"
        storage = FileStorage(path)
        storage.set_state("feed1", FeedState(last_seen=DT))

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
        storage.set_state("feed1", FeedState(last_seen=DT))
        data = json.loads(path.read_text())
        assert "last_seen_at" in data["feed1"]

    def test_multiple_ids(self, tmp_path):
        storage = FileStorage(tmp_path / "data.json")
        storage.set_state("feed1", FeedState(last_seen=DT))
        storage.set_state("feed2", FeedState(last_seen=DT2))
        assert storage.get_state("feed1").last_seen == DT
        assert storage.get_state("feed2").last_seen == DT2

    def test_seen_ids_persist(self, tmp_path):
        path = tmp_path / "data.json"
        storage = FileStorage(path)
        storage.set_state("feed1", FeedState(seen_ids=["a", "b"]))

        storage2 = FileStorage(path)
        assert storage2.get_state("feed1").seen_ids == ["a", "b"]

    def test_etag_and_modified_persist(self, tmp_path):
        path = tmp_path / "data.json"
        storage = FileStorage(path)
        storage.set_state(
            "feed1",
            FeedState(etag='"abc"', modified="Mon, 01 Jan 2024 00:00:00 GMT"),
        )

        storage2 = FileStorage(path)
        state = storage2.get_state("feed1")
        assert state.etag == '"abc"'
        assert state.modified == "Mon, 01 Jan 2024 00:00:00 GMT"

    def test_full_state_roundtrip(self, tmp_path):
        path = tmp_path / "data.json"
        storage = FileStorage(path)
        original = FeedState(
            last_seen=DT,
            seen_ids=["a", "b"],
            etag='"abc"',
            modified="Mon, 01 Jan 2024",
        )
        storage.set_state("feed1", original)

        storage2 = FileStorage(path)
        state = storage2.get_state("feed1")
        assert state.last_seen == DT
        assert state.seen_ids == ["a", "b"]
        assert state.etag == '"abc"'
        assert state.modified == "Mon, 01 Jan 2024"
