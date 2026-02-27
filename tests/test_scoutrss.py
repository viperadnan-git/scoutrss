from datetime import datetime, timezone
from time import strptime
from unittest.mock import MagicMock, call, patch

import pytest

from scoutrss import ScoutRSS
from scoutrss.storage import MemoryStorage

URL = "https://example.com/feed.rss"
NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
OLD = datetime(2024, 1, 10, 0, 0, 0, tzinfo=timezone.utc)
NEW1 = datetime(2024, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
NEW2 = datetime(2024, 1, 21, 0, 0, 0, tzinfo=timezone.utc)
NEW3 = datetime(2024, 1, 22, 0, 0, 0, tzinfo=timezone.utc)


def make_entry(published: datetime) -> MagicMock:
    entry = MagicMock()
    entry.published_parsed = strptime(
        published.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S"
    )
    return entry


def make_parsed(*entries):
    parsed = MagicMock()
    parsed.entries = list(entries)
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
        assert storage.get_last_seen(URL) is not None

    def test_last_seen_loaded_from_storage(self):
        storage = MemoryStorage()
        storage.set_last_seen(URL, OLD)
        scout = ScoutRSS(URL, lambda e: None, storage=storage)
        assert scout.last_seen == OLD

    def test_last_seen_override(self):
        storage = MemoryStorage()
        storage.set_last_seen(URL, OLD)
        scout = ScoutRSS(URL, lambda e: None, storage=storage, last_seen=NEW1)
        assert scout.last_seen == NEW1
        assert storage.get_last_seen(URL) == NEW1


class TestStructToDatetime:
    def test_converts_struct_time(self):
        struct = strptime("2024-01-15 12:00:00", "%Y-%m-%d %H:%M:%S")
        result = ScoutRSS._struct_to_datetime(struct)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc


class TestCheck:
    def _make_scout(self, callback=None, require_confirmation=False):
        storage = MemoryStorage()
        storage.set_last_seen(URL, OLD)
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
        # feed returns newest-first (e3, e2, e1)
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
        # e1 confirmed, e2 rejected — last_seen should be e1's time
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
        e1 = make_entry(NEW1)
        e2 = make_entry(NEW2)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed(e2, e1)):
            scout.check()
        assert scout.last_seen == ScoutRSS._struct_to_datetime(e1.published_parsed)

    def test_reloads_last_seen_from_storage(self):
        storage = MemoryStorage()
        storage.set_last_seen(URL, OLD)
        scout = ScoutRSS(URL, MagicMock(return_value=True), storage=storage)
        storage.set_last_seen(URL, NEW1)
        with patch("scoutrss.socutrss.parse", return_value=make_parsed()):
            scout.check()
        assert scout.last_seen == NEW1


class TestListen:
    def _make_scout(self):
        storage = MemoryStorage()
        storage.set_last_seen(URL, OLD)
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
        storage.set_last_seen(URL, OLD)
        scout = ScoutRSS(URL, MagicMock(), storage=storage)
        mock_scheduler = MagicMock()
        scout._scheduler = mock_scheduler
        scout._should_shutdown_scheduler = True
        scout.stop()
        mock_scheduler.remove_job.assert_called_once_with(f"scoutrss:{URL}")
        mock_scheduler.shutdown.assert_called_once()

    def test_does_not_shutdown_external_scheduler(self):
        storage = MemoryStorage()
        storage.set_last_seen(URL, OLD)
        scout = ScoutRSS(URL, MagicMock(), storage=storage)
        mock_scheduler = MagicMock()
        scout._scheduler = mock_scheduler
        scout._should_shutdown_scheduler = False
        scout.stop()
        mock_scheduler.remove_job.assert_called_once_with(f"scoutrss:{URL}")
        mock_scheduler.shutdown.assert_not_called()
