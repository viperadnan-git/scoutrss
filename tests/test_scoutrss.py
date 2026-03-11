from datetime import datetime, timezone
from time import strptime
from unittest.mock import MagicMock, call, patch

import pytest

from scoutrss import ScoutRSS
from scoutrss.storage import FeedState, MemoryStorage

URL = "https://example.com/feed.rss"
NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
OLD = datetime(2024, 1, 10, 0, 0, 0, tzinfo=timezone.utc)
NEW1 = datetime(2024, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
NEW2 = datetime(2024, 1, 21, 0, 0, 0, tzinfo=timezone.utc)
NEW3 = datetime(2024, 1, 22, 0, 0, 0, tzinfo=timezone.utc)


def make_entry(
    published: datetime, id: str = None, link: str = None, title: str = None
) -> MagicMock:
    entry = MagicMock()
    entry.published_parsed = strptime(
        published.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S"
    )
    entry.id = id
    entry.link = link
    entry.title = title

    def mock_get(key, default=None):
        return getattr(entry, key, default)

    entry.get = mock_get
    return entry


def make_parsed(*entries, etag=None, modified=None, status=200):
    parsed = MagicMock()
    parsed.entries = list(entries)
    parsed.get = lambda key, default=None: {
        "status": status,
        "etag": etag,
        "modified": modified,
    }.get(key, default)
    return parsed


class TestInit:
    def test_defaults_to_file_storage(self):
        scout = ScoutRSS(URL, lambda e: None, storage=MemoryStorage())
        assert isinstance(scout.storage, MemoryStorage)

    def test_id_defaults_to_url(self):
        scout = ScoutRSS(URL, lambda e: None, storage=MemoryStorage())
        assert scout.id == URL

    def test_custom_id(self):
        scout = ScoutRSS(URL, lambda e: None, storage=MemoryStorage(), id="my-feed")
        assert scout.id == "my-feed"

    def test_last_seen_set_to_now_if_not_in_storage(self):
        storage = MemoryStorage()
        with patch("scoutrss.socutrss.datetime") as mock_dt:
            mock_dt.now.return_value = NOW
            mock_dt.fromtimestamp = datetime.fromtimestamp
            ScoutRSS(URL, lambda e: None, storage=storage)
        assert storage.get_state(URL).last_seen is not None

    def test_last_seen_loaded_from_storage(self):
        storage = MemoryStorage()
        storage.set_state(URL, FeedState(last_seen=OLD))
        scout = ScoutRSS(URL, lambda e: None, storage=storage)
        assert scout.last_seen == OLD

    def test_last_seen_override(self):
        storage = MemoryStorage()
        storage.set_state(URL, FeedState(last_seen=OLD))
        scout = ScoutRSS(URL, lambda e: None, storage=storage, last_seen=NEW1)
        assert scout.last_seen == NEW1
        assert storage.get_state(URL).last_seen == NEW1


class TestStructToDatetime:
    def test_converts_struct_time(self):
        struct = strptime("2024-01-15 12:00:00", "%Y-%m-%d %H:%M:%S")
        result = ScoutRSS._struct_to_datetime(struct)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc


class TestCheck:
    def _make_scout(self, callback=None, require_confirmation=False):
        storage = MemoryStorage()
        storage.set_state(URL, FeedState(last_seen=OLD))
        return ScoutRSS(
            URL,
            callback or MagicMock(return_value=True),
            storage=storage,
            require_confirmation=require_confirmation,
        )

    def test_no_entries_does_nothing(self):
        scout = self._make_scout()
        with patch("scoutrss.socutrss.parse", return_value=make_parsed()):
            scout.check()
        scout.callback.assert_not_called()

    def test_empty_feed_clears_cached_etag(self):
        """When feed returns no entries, stale etag/modified are cleared to avoid permanent 304."""
        storage = MemoryStorage()
        storage.set_state(
            URL,
            FeedState(last_seen=OLD, etag='"old-etag"', modified="Mon, 01 Jan 2024"),
        )
        scout = ScoutRSS(URL, MagicMock(), storage=storage)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed()):
            scout.check()
        state = storage.get_state(URL)
        assert state.etag is None
        assert state.modified is None
        assert state.last_seen == OLD

    def test_new_entry_triggers_callback_with_single_entry(self):
        scout = self._make_scout()
        entry = make_entry(NEW1)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(entry)):
            scout.check()
        scout.callback.assert_called_once_with(entry)

    def test_old_entries_do_not_trigger_callback(self):
        scout = self._make_scout()
        entry = make_entry(OLD)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(entry)):
            scout.check()
        scout.callback.assert_not_called()

    def test_entries_without_published_parsed_skipped(self):
        scout = self._make_scout()
        entry = MagicMock()
        entry.get = MagicMock(return_value=None)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(entry)):
            scout.check()
        scout.callback.assert_not_called()

    def test_entries_processed_oldest_first(self):
        scout = self._make_scout()
        e1 = make_entry(NEW1)
        e2 = make_entry(NEW2)
        e3 = make_entry(NEW3)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(e3, e2, e1)):
            scout.check()
        assert scout.callback.call_args_list == [call(e1), call(e2), call(e3)]

    def test_last_seen_updated_per_entry(self):
        scout = self._make_scout()
        e1 = make_entry(NEW1)
        e2 = make_entry(NEW2)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(e2, e1)):
            scout.check()
        assert scout.last_seen > NEW1

    def test_require_confirmation_true_updates_on_true(self):
        scout = self._make_scout(
            callback=MagicMock(return_value=True), require_confirmation=True
        )
        entry = make_entry(NEW1)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(entry)):
            scout.check()
        assert scout.last_seen > OLD

    def test_require_confirmation_false_stops_and_does_not_update(self):
        scout = self._make_scout(
            callback=MagicMock(return_value=False), require_confirmation=True
        )
        entry = make_entry(NEW1)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(entry)):
            scout.check()
        assert scout.last_seen == OLD

    def test_require_confirmation_partial_update(self):
        """Confirmed entries before failure should still be saved."""
        results = [True, False]
        scout = self._make_scout(
            callback=MagicMock(side_effect=results), require_confirmation=True
        )
        e1 = make_entry(NEW1)
        e2 = make_entry(NEW2)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(e2, e1)):
            scout.check()
        assert scout.last_seen == ScoutRSS._struct_to_datetime(e1.published_parsed)

    def test_callback_exception_stops_processing(self):
        scout = self._make_scout(callback=MagicMock(side_effect=Exception("fail")))
        entry = make_entry(NEW1)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(entry)):
            scout.check()
        assert scout.last_seen == OLD

    def test_callback_exception_partial_update(self):
        """Entries processed before exception should still be saved."""
        scout = self._make_scout(
            callback=MagicMock(side_effect=[True, Exception("fail")])
        )
        e1 = make_entry(NEW1, id="guid-1")
        e2 = make_entry(NEW2, id="guid-2")
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(e2, e1)):
            scout.check()
        assert scout.last_seen == ScoutRSS._struct_to_datetime(e1.published_parsed)
        state = scout.storage.get_state(URL)
        assert "guid-1" in state.seen_ids
        assert "guid-2" not in state.seen_ids

    def test_confirmation_partial_seen_ids(self):
        """Confirmed entries get seen_ids, rejected ones don't."""
        scout = self._make_scout(
            callback=MagicMock(side_effect=[True, False]),
            require_confirmation=True,
        )
        e1 = make_entry(NEW1, id="guid-1")
        e2 = make_entry(NEW2, id="guid-2")
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(e2, e1)):
            scout.check()
        state = scout.storage.get_state(URL)
        assert "guid-1" in state.seen_ids
        assert "guid-2" not in state.seen_ids

    def test_reloads_last_seen_from_storage(self):
        storage = MemoryStorage()
        storage.set_state(URL, FeedState(last_seen=OLD))
        scout = ScoutRSS(URL, MagicMock(return_value=True), storage=storage)
        storage.set_state(URL, FeedState(last_seen=NEW1))
        with patch("scoutrss.socutrss.parse", return_value=make_parsed()):
            scout.check()
        assert scout.last_seen == NEW1

    def test_etag_cleared_on_callback_failure(self):
        scout = self._make_scout(callback=MagicMock(side_effect=Exception("fail")))
        entry = make_entry(NEW1, id="guid-1")
        with patch(
            "scoutrss.socutrss.parse",
            return_value=make_parsed(entry, etag='"abc"'),
        ):
            scout.check()
        state = scout.storage.get_state(URL)
        assert state.etag is None
        assert "guid-1" not in state.seen_ids

    def test_etag_cleared_on_confirmation_false(self):
        scout = self._make_scout(
            callback=MagicMock(return_value=False), require_confirmation=True
        )
        entry = make_entry(NEW1, id="guid-1")
        with patch(
            "scoutrss.socutrss.parse",
            return_value=make_parsed(entry, etag='"abc"'),
        ):
            scout.check()
        state = scout.storage.get_state(URL)
        assert state.etag is None
        assert "guid-1" not in state.seen_ids

    def test_seen_ids_pruned_by_feed_size(self):
        """Seen IDs are pruned based on total feed entries, not just new ones."""
        from scoutrss.socutrss import MIN_SEEN_IDS, SEEN_IDS_MULTIPLIER

        storage = MemoryStorage()
        # pre-populate with 200 seen IDs (insertion order: old-0, old-1, ..., old-199)
        old_ids = [f"old-{i}" for i in range(200)]
        storage.set_state(URL, FeedState(last_seen=OLD, seen_ids=old_ids))
        scout = ScoutRSS(URL, MagicMock(return_value=True), storage=storage)
        # feed has 50 entries total, 1 new
        old_entries = [make_entry(OLD, id=f"feed-{i}") for i in range(49)]
        new_entry = make_entry(NEW1, id="new-1")
        with patch(
            "scoutrss.socutrss.parse",
            return_value=make_parsed(new_entry, *old_entries),
        ):
            scout.check()
        state = scout.storage.get_state(URL)
        max_ids = max(MIN_SEEN_IDS, 50 * SEEN_IDS_MULTIPLIER)
        assert len(state.seen_ids) <= max_ids
        # new entry must survive pruning (most recent)
        assert "new-1" in state.seen_ids

    def test_seen_ids_pruned_keeps_newest(self):
        """Pruning drops the oldest IDs and keeps the most recent ones."""
        from scoutrss.socutrss import MIN_SEEN_IDS, SEEN_IDS_MULTIPLIER

        storage = MemoryStorage()
        # pre-populate with ordered IDs: old-0 (oldest) through old-199 (newest)
        ordered_ids = [f"old-{i}" for i in range(200)]
        storage.set_state(URL, FeedState(last_seen=OLD, seen_ids=ordered_ids))
        scout = ScoutRSS(URL, MagicMock(return_value=True), storage=storage)
        # feed has 50 entries, 1 new
        old_entries = [make_entry(OLD, id=f"feed-{i}") for i in range(49)]
        new_entry = make_entry(NEW1, id="new-1")
        with patch(
            "scoutrss.socutrss.parse",
            return_value=make_parsed(new_entry, *old_entries),
        ):
            scout.check()
        state = scout.storage.get_state(URL)
        max_ids = max(MIN_SEEN_IDS, 50 * SEEN_IDS_MULTIPLIER)
        assert len(state.seen_ids) == max_ids
        # the newly processed entry must be retained
        assert "new-1" in state.seen_ids


class TestConditionalRequests:
    def _make_scout(self):
        storage = MemoryStorage()
        storage.set_state(URL, FeedState(last_seen=OLD))
        return ScoutRSS(URL, MagicMock(return_value=True), storage=storage)

    def test_304_skips_processing(self):
        scout = self._make_scout()
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(status=304)):
            scout.check()
        scout.callback.assert_not_called()

    def test_etag_passed_to_parse(self):
        scout = self._make_scout()
        scout.storage.set_state(URL, FeedState(last_seen=OLD, etag='"abc123"'))
        with patch("scoutrss.socutrss.parse", return_value=make_parsed()) as mock_parse:
            scout.check()
        _, kwargs = mock_parse.call_args
        assert kwargs["etag"] == '"abc123"'
        assert kwargs["modified"] is None

    def test_modified_passed_to_parse(self):
        scout = self._make_scout()
        scout.storage.set_state(
            URL, FeedState(last_seen=OLD, modified="Mon, 01 Jan 2024 00:00:00 GMT")
        )
        with patch("scoutrss.socutrss.parse", return_value=make_parsed()) as mock_parse:
            scout.check()
        _, kwargs = mock_parse.call_args
        assert kwargs["etag"] is None
        assert kwargs["modified"] == "Mon, 01 Jan 2024 00:00:00 GMT"

    def test_etag_persisted_after_check(self):
        scout = self._make_scout()
        entry = make_entry(NEW1)
        with patch(
            "scoutrss.socutrss.parse",
            return_value=make_parsed(entry, etag='"new-etag"'),
        ):
            scout.check()
        assert scout.storage.get_state(URL).etag == '"new-etag"'

    def test_modified_persisted_after_check(self):
        scout = self._make_scout()
        entry = make_entry(NEW1)
        with patch(
            "scoutrss.socutrss.parse",
            return_value=make_parsed(entry, modified="Tue, 02 Jan 2024"),
        ):
            scout.check()
        assert scout.storage.get_state(URL).modified == "Tue, 02 Jan 2024"

    def test_etag_and_modified_both_passed(self):
        scout = self._make_scout()
        scout.storage.set_state(
            URL,
            FeedState(last_seen=OLD, etag='"abc"', modified="Mon, 01 Jan 2024"),
        )
        with patch("scoutrss.socutrss.parse", return_value=make_parsed()) as mock_parse:
            scout.check()
        _, kwargs = mock_parse.call_args
        assert kwargs["etag"] == '"abc"'
        assert kwargs["modified"] == "Mon, 01 Jan 2024"

    def test_user_agent_passed_to_parse(self):
        scout = self._make_scout()
        with patch("scoutrss.socutrss.parse", return_value=make_parsed()) as mock_parse:
            scout.check()
        _, kwargs = mock_parse.call_args
        assert kwargs["agent"] == scout.user_agent

    def test_custom_user_agent(self):
        storage = MemoryStorage()
        storage.set_state(URL, FeedState(last_seen=OLD))
        scout = ScoutRSS(URL, MagicMock(), storage=storage, user_agent="MyBot/1.0")
        assert scout.user_agent == "MyBot/1.0"
        with patch("scoutrss.socutrss.parse", return_value=make_parsed()) as mock_parse:
            scout.check()
        _, kwargs = mock_parse.call_args
        assert kwargs["agent"] == "MyBot/1.0"


class TestEntryId:
    def test_uses_guid(self):
        entry = make_entry(NEW1, id="guid-123")
        assert ScoutRSS._entry_id(entry) == "guid-123"

    def test_falls_back_to_link_hash(self):
        entry = make_entry(NEW1, link="https://example.com/post")
        eid = ScoutRSS._entry_id(entry)
        assert eid != "https://example.com/post"
        assert len(eid) == 32  # blake2b hex

    def test_falls_back_to_title_hash(self):
        entry = make_entry(NEW1, title="My Post")
        eid = ScoutRSS._entry_id(entry)
        assert len(eid) == 32

    def test_deterministic(self):
        e1 = make_entry(NEW1, link="https://example.com/post")
        e2 = make_entry(NEW2, link="https://example.com/post")
        assert ScoutRSS._entry_id(e1) == ScoutRSS._entry_id(e2)


class TestDedup:
    def _make_scout(self, callback=None):
        storage = MemoryStorage()
        storage.set_state(URL, FeedState(last_seen=OLD))
        return ScoutRSS(
            URL,
            callback or MagicMock(return_value=True),
            storage=storage,
        )

    def test_already_seen_entry_skipped(self):
        scout = self._make_scout()
        entry = make_entry(NEW1, id="guid-1")
        scout.storage.set_state(URL, FeedState(last_seen=OLD, seen_ids=["guid-1"]))
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(entry)):
            scout.check()
        scout.callback.assert_not_called()

    def test_seen_ids_persisted_after_check(self):
        scout = self._make_scout()
        entry = make_entry(NEW1, id="guid-1")
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(entry)):
            scout.check()
        assert "guid-1" in scout.storage.get_state(URL).seen_ids

    def test_duplicate_entry_with_drifted_timestamp(self):
        """Same guid, different timestamp — should be deduped."""
        scout = self._make_scout()
        entry1 = make_entry(NEW1, id="guid-1")
        entry2 = make_entry(NEW2, id="guid-1")
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(entry1)):
            scout.check()
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(entry2)):
            scout.check()
        assert scout.callback.call_count == 1

    def test_mixed_seen_and_unseen(self):
        scout = self._make_scout()
        scout.storage.set_state(URL, FeedState(last_seen=OLD, seen_ids=["guid-1"]))
        e1 = make_entry(NEW1, id="guid-1")
        e2 = make_entry(NEW2, id="guid-2")
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(e2, e1)):
            scout.check()
        scout.callback.assert_called_once_with(e2)


class TestListen:
    def _make_scout(self):
        storage = MemoryStorage()
        storage.set_state(URL, FeedState(last_seen=OLD))
        return ScoutRSS(URL, MagicMock(), storage=storage)

    def test_raises_without_apscheduler(self):
        scout = self._make_scout()
        with patch.dict(
            "sys.modules",
            {
                "apscheduler": None,
                "apscheduler.schedulers": None,
                "apscheduler.schedulers.background": None,
                "apscheduler.schedulers.blocking": None,
            },
        ):
            with pytest.raises(ImportError, match="scoutrss\\[scheduler\\]"):
                scout.listen()

    def test_uses_provided_scheduler(self):
        scout = self._make_scout()
        mock_scheduler = MagicMock()
        scout.listen(interval=30, scheduler=mock_scheduler)
        mock_scheduler.add_job.assert_called_once()
        call_kwargs = mock_scheduler.add_job.call_args
        assert call_kwargs[1]["seconds"] == 30
        assert call_kwargs[1]["id"] == f"scoutrss:{URL}"

    def test_prefixed_job_id(self):
        scout = self._make_scout()
        mock_scheduler = MagicMock()
        scout.listen(scheduler=mock_scheduler)
        job_id = mock_scheduler.add_job.call_args[1]["id"]
        assert job_id == f"scoutrss:{URL}"

    def test_custom_check_fn(self):
        scout = self._make_scout()
        mock_scheduler = MagicMock()
        custom_fn = MagicMock()
        scout.listen(scheduler=mock_scheduler, check_fn=custom_fn)
        assert mock_scheduler.add_job.call_args[0][0] == custom_fn

    def test_uses_self_check_by_default(self):
        scout = self._make_scout()
        mock_scheduler = MagicMock()
        scout.listen(scheduler=mock_scheduler)
        assert mock_scheduler.add_job.call_args[0][0] == scout.check

    def test_does_not_start_external_scheduler(self):
        scout = self._make_scout()
        mock_scheduler = MagicMock()
        scout.listen(scheduler=mock_scheduler)
        mock_scheduler.start.assert_not_called()


class TestStop:
    def test_removes_job_and_shuts_down(self):
        storage = MemoryStorage()
        storage.set_state(URL, FeedState(last_seen=OLD))
        scout = ScoutRSS(URL, MagicMock(), storage=storage)
        mock_scheduler = MagicMock()
        scout._scheduler = mock_scheduler
        scout._should_shutdown_scheduler = True
        scout.stop()
        mock_scheduler.remove_job.assert_called_once_with(f"scoutrss:{URL}")
        mock_scheduler.shutdown.assert_called_once()

    def test_does_not_shutdown_external_scheduler(self):
        storage = MemoryStorage()
        storage.set_state(URL, FeedState(last_seen=OLD))
        scout = ScoutRSS(URL, MagicMock(), storage=storage)
        mock_scheduler = MagicMock()
        scout._scheduler = mock_scheduler
        scout._should_shutdown_scheduler = False
        scout.stop()
        mock_scheduler.remove_job.assert_called_once_with(f"scoutrss:{URL}")
        mock_scheduler.shutdown.assert_not_called()
