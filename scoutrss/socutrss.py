import logging
from datetime import datetime
from time import mktime
from typing import Callable, List
from zoneinfo import ZoneInfo

import pickledb
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from feedparser import FeedParserDict, parse

LOGGER = logging.getLogger(__name__)


class ScoutRSS:
    def __init__(
        self,
        url: str,
        callback: Callable[[List[FeedParserDict]], bool],
        id: str = None,
        last_saved_on: datetime = None,
        check_confirmation: bool = True,
        scheduler_timezone: ZoneInfo = ZoneInfo("UTC"),
        database_path: str = "scoutrss.data.json",
    ):
        """
        :param url: RSS feed url
        :param callback: callback function to call when new entries are found (entries are passed as a list)
        :param id: id to use to save the last saved on timestamp (defaults to url)
        :param last_saved_on: last saved on timestamp (defaults to now if not provided and not saved in db)
        :param check_confirmation: whether to check for confirmation from the callback function (defaults to False)
        """
        self.url = url
        self.id = id or url
        self.callback = callback
        self.check_confirmation = check_confirmation
        self.db = pickledb.load(database_path, True)
        if last_saved_on:
            self.update_last_saved_on(last_saved_on)
        elif not self.db.get(self.id):
            self.update_last_saved_on(datetime.now())
        else:
            self.update_last_saved_on()
        self.scheduler_timezone = scheduler_timezone

    def update_last_saved_on(self, new_last_saved_on: datetime = None):
        """
        Updates the last saved on timestamp

        :param new_last_saved_on: new last saved on timestamp to use
        """
        if new_last_saved_on:
            self.db.set(self.id, new_last_saved_on.isoformat())
            self.last_saved_on = new_last_saved_on
        else:
            last_saved_on_isoformat = self.db.get(self.id)
            self.last_saved_on = (
                datetime.fromisoformat(last_saved_on_isoformat)
                if last_saved_on_isoformat
                else datetime.now()
            )

    def check(self):
        """
        Checks for new entries in the RSS feed
        """

        self.update_last_saved_on()

        parsed = parse(self.url)
        entries = [
            entry
            for entry in parsed.entries
            if datetime.fromtimestamp(mktime(entry.published_parsed))
            > self.last_saved_on
        ]

        LOGGER.debug("There are {} new entries".format(len(entries)))
        last_saved_on = datetime.fromtimestamp(
            mktime(parsed.entries[0].published_parsed)
        )

        if entries:
            try:
                confirm = self.callback(entries)
                if self.check_confirmation:
                    if confirm:
                        self.update_last_saved_on(last_saved_on)
                    else:
                        LOGGER.warning(
                            "Callback returned False, not updating last_saved_on timestamp"
                        )
                else:
                    self.update_last_saved_on(last_saved_on)
            except Exception:
                LOGGER.exception(
                    "Error while calling callback, not updating last_saved_on timestamp"
                )

    def listen(
        self, interval: int = 60, blocking=False, apscheduler: BaseScheduler = None
    ):
        """
        Starts the scheduler

        :param interval: Interval in seconds (default: 60)
        :param blocking: If True, the scheduler will block the current thread (default: False)

        """
        self.should_shutdown_scheduler = False
        if not apscheduler:
            self.should_shutdown_scheduler = True
            self.scheduler = (BlockingScheduler if blocking else BackgroundScheduler)(
                timezone=self.scheduler_timezone
            )
        else:
            self.scheduler = apscheduler
        self.scheduler.add_job(
            self.check,
            "interval",
            seconds=interval,
            id=self.id,
            max_instances=1,  # Only one instance of the job can run at a time to avoid fetching the same entries multiple times
            next_run_time=datetime.now(tz=self.scheduler_timezone),
        )
        LOGGER.info("Watching RSS feed {} every {} seconds".format(self.url, interval))
        self.scheduler.start()

    def stop_listener(self):
        """
        Stops the scheduler
        """
        self.scheduler.remove_job(self.id)
        if self.should_shutdown_scheduler:
            self.scheduler.shutdown()
        LOGGER.info("ScoutRSS Stopped listening to {}".format(self.url))
