# twscraper-wrapper
Scrapes tweets into jsonl format. This script makes use of [twscrape](https://github.com/vladkens/twscrape) to replicate the functional output of
```sh
snscrape --jsonl twitter-user <handle> >> file_name.tweets.json
```
from before Twitter became worse for scraping (among other things).

Before using, you must follow the instructions in the [README for twscrape](https://github.com/vladkens/twscrape#add-accounts) to add at least one account to an `accounts.db` file in the same directory as the script. Additional functionality such as sorting saved files, deduplicating tweets in a file, and automatically identifying the last tweet saved as to limit search queries were added for convenience.

*Unfortunately, retweets are only able to be retrieved from an initial profile scrape. [Advanced search](https://github.com/igorbrigadir/twitter-advanced-search) queries (used with the `save-past` operation) are unable to retrieve retweets properly with modern twitter beyond ~10 days from the present for undocumented reasons. See [#2](https://github.com/CetaceanNation/misc-scripts/issues/2).*

### Usage
```sh
usage: twscrape-wrapper.py [-h] [-n] {save,save-past,sort,dedupe} filename [handle]

positional arguments:
  {save,save-past,sort,dedupe}
                        operation to perform. 'save' downloads tweets to a file ('save-past' works in reverse), 'sort' re-orders tweets in a file, 'dedupe' removes entries with duplicate ids.
  filename              file prefix to write tweets to (will be appended with .tweets.json)
  handle                handle of the account to download from

options:
  -h, --help            show this help message and exit
  -n                    prompt for overwriting the existing tweet file
  --download-media, -m  iterate through scraped/sorted tweets and download all media
```
