import logging
from datetime import datetime, timezone
from hashlib import blake2b
from time import mktime, struct_time
from typing import Any, Callable, Optional, cast

from feedparser import FeedParserDict, parse

from .storage.adapter import StorageAdapter
from .storage.file import FileStorage

logger = logging.getLogger(__name__)

MIN_SEEN_IDS = 100
SEEN_IDS_MULTIPLIER = 3
DEFAULT_USER_AGENT = "ScoutRSS (+https://github.com/viperadnan-git/scoutrss)"


class ScoutRSS:
    def __init__(
        self,
        url: str,
        callback: Callable[[FeedParserDict], Any],
        storage: Optional[StorageAdapter] = None,
        id: Optional[str] = None,
        last_seen: Optional[datetime] = None,
        require_confirmation: bool = False,
        user_agent: Optional[str] = None,
    ):
        """
        :param url: RSS feed url
        :param callback: function called once per new entry; return value is only used when require_confirmation=True
        :param storage: storage adapter (defaults to FileStorage)
        :param id: id for storing state (defaults to url)
        :param last_seen: override the last seen timestamp
        :param require_confirmation: update timestamp only if callback returns True
        :param user_agent: custom User-Agent header for HTTP requests
        """
        self.url = url
        self.id = id or url
        self.callback = callback
        self.require_confirmation = require_confirmation
        self.storage = storage or FileStorage()
        self.user_agent = user_agent or DEFAULT_USER_AGENT

        state = self.storage.get_state(self.id)
        if last_seen:
            self.last_seen = last_seen
            self.storage.set_state(self.id, last_seen=last_seen)
        elif state.last_seen is not None:
            self.last_seen = state.last_seen
        else:
            self.last_seen = datetime.now(tz=timezone.utc)
            self.storage.set_state(self.id, last_seen=self.last_seen)

    @staticmethod
    def _struct_to_datetime(struct: struct_time) -> datetime:
        return datetime.fromtimestamp(mktime(struct), tz=timezone.utc)

    @staticmethod
    def _entry_id(entry: FeedParserDict) -> str:
        """Resolve a unique ID for an entry: guid > hash(link) > hash(title)."""
        if entry.get("id"):
            return entry.id
        value = entry.get("link") or entry.get("title") or ""
        return blake2b(value.encode(), digest_size=16).hexdigest()

    def check(self) -> None:
        """Check for new entries in the RSS feed and invoke the callback per entry.

        Entries are filtered by both timestamp and seen ID to prevent duplicates.
        Processed oldest-first so last_seen advances progressively.
        On callback failure or False return (when require_confirmation=True),
        processing stops but previously confirmed entries remain saved.
        """
        state = self.storage.get_state(self.id)
        self.last_seen = state.last_seen or self.last_seen
        seen_ids = state.seen_ids

        parsed = parse(
            self.url,
            etag=state.etag,
            modified=state.modified,
            agent=self.user_agent,
        )

        # 304 Not Modified — feed unchanged, skip processing
        if parsed.get("status") == 304:
            return

        if not parsed.entries:
            return

        new_entries = (
            entry
            for entry in parsed.entries
            if entry.get("published_parsed")
            and self._struct_to_datetime(cast(struct_time, entry.published_parsed))
            > self.last_seen
            and self._entry_id(entry) not in seen_ids
        )

        # sort oldest-first so last_seen advances entry by entry
        new_entries = sorted(
            new_entries,
            key=lambda e: e.published_parsed,
        )

        logger.debug(f"Found {len(new_entries)} new entries for {self.url}")

        for entry in new_entries:
            entry_time = self._struct_to_datetime(
                cast(struct_time, entry.published_parsed)
            )
            try:
                confirm = self.callback(entry)
                seen_ids.add(self._entry_id(entry))
                if self.require_confirmation:
                    if confirm:
                        self.last_seen = entry_time
                    else:
                        logger.warning(
                            "Callback returned False, stopping at current entry"
                        )
                        break
                else:
                    self.last_seen = entry_time
            except Exception:
                logger.exception("Error in callback, stopping at current entry")
                break

        # prune to a cap based on feed size (minimum MIN_SEEN_IDS)
        max_ids = max(MIN_SEEN_IDS, len(new_entries) * SEEN_IDS_MULTIPLIER)
        if len(seen_ids) > max_ids:
            seen_ids = set(list(seen_ids)[-max_ids:])
        self.storage.set_state(
            self.id,
            last_seen=self.last_seen,
            seen_ids=seen_ids,
            etag=parsed.get("etag"),
            modified=parsed.get("modified"),
        )

    def listen(
        self,
        interval: int = 60,
        blocking: bool = False,
        scheduler=None,
        check_fn: Optional[Callable] = None,
    ) -> None:
        """
        Start watching the feed on a schedule.

        Requires APScheduler: pip install scoutrss[scheduler]

        :param interval: check interval in seconds (default: 60)
        :param blocking: block the current thread (default: False)
        :param scheduler: existing APScheduler instance to reuse; if not provided, a new one is created and started automatically
        :param check_fn: custom callable to use instead of self.check (e.g. wrapped with retry logic)
        """
        self._should_shutdown_scheduler = scheduler is None
        if scheduler is None:
            try:
                from apscheduler.schedulers.background import BackgroundScheduler
                from apscheduler.schedulers.blocking import BlockingScheduler
            except ImportError:
                raise ImportError(
                    "APScheduler is required for listen(). "
                    "Install it with: pip install scoutrss[scheduler]"
                )
            self._scheduler = (BlockingScheduler if blocking else BackgroundScheduler)(
                timezone="UTC"
            )
        else:
            self._scheduler = scheduler

        self._scheduler.add_job(
            check_fn or self.check,
            "interval",
            seconds=interval,
            id=f"scoutrss:{self.id}",
            max_instances=1,  # prevent overlapping runs
            next_run_time=datetime.now(tz=timezone.utc),
        )
        logger.info(f"Watching {self.url} every {interval}s")

        if self._should_shutdown_scheduler or blocking:
            self._scheduler.start()

    def stop(self) -> None:
        """Stop the scheduled feed watcher."""
        self._scheduler.remove_job(f"scoutrss:{self.id}")
        if self._should_shutdown_scheduler:
            self._scheduler.shutdown()
        logger.info(f"Stopped watching {self.url}")
