# ScoutRSS

ScoutRSS is a Python library for monitoring RSS feeds and triggering callbacks when new entries are found. It uses [feedparser](https://pypi.org/project/feedparser/) for parsing and supports pluggable storage backends.

## Installation

```bash
pip install scoutrss
```

With built-in scheduler support:

```bash
pip install scoutrss[scheduler]
```

With MongoDB storage support:

```bash
pip install scoutrss[mongo]
```

## Usage

### Basic

```python
from scoutrss import ScoutRSS

def callback(entries):
    for entry in entries:
        print("New entry:", entry.title)

watcher = ScoutRSS("https://example.com/feed.xml", callback)
watcher.check()  # one-off check
```

### With scheduler

```python
watcher = ScoutRSS("https://example.com/feed.xml", callback)
watcher.listen(interval=60)   # background, non-blocking
watcher.listen(interval=60, blocking=True)  # blocks current thread
watcher.stop()
```

### Storage backends

By default, state is persisted to `scoutrss.data.json` in the current directory. You can switch backends or use in-memory storage:

```python
from scoutrss import ScoutRSS, FileStorage, MemoryStorage, MongoStorage

# Custom file path
watcher = ScoutRSS(url, callback, storage=FileStorage("data/feeds.json"))

# In-memory (no persistence, useful for testing)
watcher = ScoutRSS(url, callback, storage=MemoryStorage())

# MongoDB
from pymongo import MongoClient
collection = MongoClient()["mydb"]["rss"]
watcher = ScoutRSS(url, callback, storage=MongoStorage(collection))
```

### Custom ID

By default the URL is used as the storage key. Override with `id`:

```python
watcher = ScoutRSS(url, callback, id="my-feed")
```

### Require confirmation

Set `require_confirmation=True` to only advance the timestamp if the callback returns `True`:

```python
def callback(entries):
    success = process(entries)
    return success  # only update last_seen if True

watcher = ScoutRSS(url, callback, require_confirmation=True)
```

### Custom scheduler

Pass an existing APScheduler instance to share it across multiple watchers:

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.start()

watcher1 = ScoutRSS(url1, callback1)
watcher2 = ScoutRSS(url2, callback2)

watcher1.listen(interval=60, scheduler=scheduler)
watcher2.listen(interval=120, scheduler=scheduler)
```

### Custom retry logic

Pass a custom `check_fn` to `listen()` to wrap `check()` with retry logic:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def check_with_retry():
    watcher.check()

watcher.listen(interval=60, check_fn=check_with_retry)
```

### Custom storage adapter

Implement `StorageAdapter` to use any storage backend:

```python
from scoutrss import StorageAdapter
from datetime import datetime

class RedisStorage(StorageAdapter):
    def __init__(self, client):
        self._client = client

    def get_last_seen(self, id: str) -> datetime | None:
        val = self._client.get(id)
        return datetime.fromisoformat(val) if val else None

    def set_last_seen(self, id: str, last_seen: datetime) -> None:
        self._client.set(id, last_seen.isoformat())
```

## License

ScoutRSS is licensed under the [GNU GPLv3 license](LICENSE).

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.
