from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymongo.collection import Collection

from .adapter import FeedState, StorageAdapter


class MongoStorage(StorageAdapter):
    def __init__(self, collection: Collection):
        self._collection = collection

    def get_state(self, id: str) -> FeedState:
        result = self._collection.find_one({"_id": id})
        if not result:
            return FeedState()
        return FeedState(
            last_seen=result.get("last_seen_at"),
            seen_ids=set(result.get("seen_ids", [])),
            etag=result.get("etag"),
            modified=result.get("modified"),
        )

    def set_state(
        self,
        id: str,
        last_seen: datetime | None = None,
        seen_ids: set[str] | None = None,
        etag: str | None = None,
        modified: str | None = None,
    ) -> None:
        update: dict = {}
        if last_seen is not None:
            update["last_seen_at"] = last_seen
        if seen_ids is not None:
            update["seen_ids"] = list(seen_ids)
        if etag is not None:
            update["etag"] = etag
        if modified is not None:
            update["modified"] = modified
        if update:
            self._collection.update_one(
                {"_id": id},
                {"$set": update},
                upsert=True,
            )
