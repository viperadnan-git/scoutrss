from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymongo.collection import Collection

from .adapter import StorageAdapter


class MongoStorage(StorageAdapter):
    def __init__(self, collection: Collection):
        self._collection = collection

    def get_last_seen(self, id: str) -> datetime | None:
        result = self._collection.find_one({"_id": id})
        return result["last_seen_at"] if result else None

    def set_last_seen(self, id: str, last_seen: datetime) -> None:
        self._collection.update_one(
            {"_id": id},
            {"$set": {"last_seen_at": last_seen}},
            upsert=True,
        )
