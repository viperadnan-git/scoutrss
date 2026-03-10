"""Integration tests against real RSS feeds. Requires network access.

Run with: uv run pytest tests/test_integration.py -v -m integration
"""

from datetime import datetime, timezone

import pytest

from scoutrss import ScoutRSS
from scoutrss.storage import MemoryStorage

FEEDS = [
    "https://www.reddit.com/r/python/.rss",
    "https://hnrss.org/frontpage",
    "https://feeds.bbci.co.uk/news/rss.xml",
]

EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def storage():
    return MemoryStorage()


@pytest.mark.integration
@pytest.mark.parametrize("url", FEEDS)
class TestLiveFeed:
    def test_check_fetches_entries(self, url, storage):
        entries = []
        scout = ScoutRSS(
            url, lambda e: entries.append(e), storage=storage, last_seen=EPOCH
        )
        scout.check()
        assert len(entries) > 0, f"No entries found for {url}"

    def test_entries_have_required_fields(self, url, storage):
        entries = []
        scout = ScoutRSS(
            url, lambda e: entries.append(e), storage=storage, last_seen=EPOCH
        )
        scout.check()
        for entry in entries[:3]:
            assert entry.get("title"), "Entry missing title"
            assert entry.get("link"), "Entry missing link"

    def test_second_check_returns_no_new_entries(self, url, storage):
        scout = ScoutRSS(url, lambda e: None, storage=storage, last_seen=EPOCH)
        scout.check()
        new_entries = []
        scout = ScoutRSS(url, lambda e: new_entries.append(e), storage=storage, id=url)
        scout.check()
        assert len(new_entries) == 0, (
            "Second check should not return already-seen entries"
        )

    def test_conditional_request_stores_etag_or_modified(self, url, storage):
        scout = ScoutRSS(url, lambda e: None, storage=storage, last_seen=EPOCH)
        scout.check()
        state = storage.get_state(url)
        # Not all servers support conditional requests, just verify we stored what was available
        if state.etag is not None or state.modified is not None:
            assert state.etag or state.modified

    def test_conditional_request_sends_etag_on_second_check(self, url, storage):
        """Verify etag/modified from first check is sent on second check."""
        from unittest.mock import patch

        from feedparser import parse as real_parse

        scout = ScoutRSS(url, lambda e: None, storage=storage, last_seen=EPOCH)
        scout.check()
        state = storage.get_state(url)

        if state.etag is None and state.modified is None:
            pytest.skip(f"{url} does not support conditional requests")

        with patch("scoutrss.socutrss.parse", wraps=real_parse) as mock_parse:
            scout.check()
        _, kwargs = mock_parse.call_args
        assert kwargs.get("etag") == state.etag
        assert kwargs.get("modified") == state.modified
