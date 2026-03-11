from __future__ import annotations

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
            seen_ids=list(result.get("seen_ids", [])),
            etag=result.get("etag"),
            modified=result.get("modified"),
        )

    def set_state(self, id: str, state: FeedState) -> None:
        self._collection.update_one(
            {"_id": id},
            {
                "$set": {
                    "last_seen_at": state.last_seen,
                    "seen_ids": list(state.seen_ids),
                    "etag": state.etag,
                    "modified": state.modified,
                }
            },
            upsert=True,
        )
