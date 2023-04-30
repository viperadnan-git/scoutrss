# ScoutRSS

ScoutRSS is a Python package for monitoring RSS feeds and triggering callbacks when new entries are found. It uses the [feedparser](https://pypi.org/project/feedparser/) package to parse RSS feeds and the [APScheduler](https://pypi.org/project/APScheduler/) package to schedule checks at regular intervals.

## Installation

To install ScoutRSS, use pip:

```bash
pip install ScoutRSS
```

## Usage

To use ScoutRSS, create an instance of the `ScoutRSS` class and pass in the RSS feed URL, a callback function to be called when new entries are found, and other optional parameters.

```python
from ScoutRSS import ScoutRSS

def callback(entries):
    print("Found {} new entries".format(len(entries)))

watcher = ScoutRSS("http://example.com/feed.xml", callback)
watcher.listen()
```

This will start monitoring the RSS feed and calling the `callback` function whenever new entries are found. The `listen` method starts the scheduler with a default interval of 60 seconds. You can customize the interval by passing a different value to the `interval` parameter:

```python
watcher.listen(interval=120)  # Check every 2 minutes
```

You can also use the `stop_listener` method to stop monitoring the RSS feed:

```python
watcher.stop_listener()
```

### Advanced usage

You can use the `check_confirmation` parameter to control whether to update the last saved on timestamp based on the return value of the callback function. If set to `True`, the `callback` function should return `True` to update the last saved on timestamp:

```python
def callback(entries):
    for entry in entries:
        print("Found new entry: {}".format(entry.title))
    return True

watcher = ScoutRSS("http://example.com/feed.xml", callback, check_confirmation=True)
watcher.listen()
```

You can also use the `id` parameter to specify a unique ID for the RSS feed. This can be useful if you want to monitor multiple RSS feeds with different callback functions:

```python
watcher1 = ScoutRSS("http://example1.com/feed.xml", callback1, id="feed1")
watcher2 = ScoutRSS("http://example2.com/feed.xml", callback2, id="feed2")
```

By default, the last saved on timestamp is stored in a pickledb database file named `scoutrss.data.json` in the current directory. You can customize the database file path by passing a different value to the `load` method of the `pickledb` package:

```python
import pickledb

db = pickledb.load("custom/path/to/database.json", True)
watcher = ScoutRSS("http://example.com/feed.xml", callback, db=db)
```

You can also pass in a custom scheduler instance if you want to use a different scheduler:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
watcher = ScoutRSS("http://example.com/feed.xml", callback, apscheduler=scheduler)
```

## License

ScoutRSS is licensed under the GNU v3 license. See the `LICENSE` file for more information.

## Contributing

Contributions are welcome! See the `CONTRIBUTING.md` file for more information.

## Credits

ScoutRSS was created by Adnan Ahmad and licensed under the [GNU GPLv3 license](LICENSE).