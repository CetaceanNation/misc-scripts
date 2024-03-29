## caa-downloader
Download art for a [MusicBrainz](https://musicbrainz.org/) release from the [Cover Art Archive](https://coverartarchive.org/)
<details>
<summary>Show Usage</summary>

```sh
usage: caa-downloader.py [-h] [-d DIRECTORY] [-s SIZE] [RELEASES ...]

positional arguments:
  RELEASES              releases to download i.e.
                        3791c620-7ba4-3db0-bda8-2b060f31a7b8
                        https://musicbrainz.org/release/3791c620-7ba4-3db0-bda8-2b060f31a7b8
                        beta.musicbrainz.org/release/3791c620-7ba4-3db0-bda8-2b060f31a7b8/discids

options:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        save directory (defaults to current)
  -s SIZE, --size SIZE  image download size (250, 500, 1200, original)
```
</details>

## porn3dx-downloader
Downloads videos and images from posts on [Porn3dx](https://porn3dx.com). Video formats available are better than those you can download with an account, expects and decrypts any encrypted video playlists. Very basic error handling/reporting.
<details>
<summary>Show Usage</summary>

```sh
usage: porn3dx-downloader.py [-h] [-V] [-d DIRECTORY] [--write-sidecars] [-f FORMAT] [-F] [POSTS ...]

positional arguments:
  POSTS                 post url

options:
  -h, --help            show this help message and exit
  -V, --verbose         print debugging information
  -d DIRECTORY, --directory DIRECTORY
                        save directory (defaults to current)
  --write-sidecars      write sidecars for urls, timestamps, tags and description notes
  -f FORMAT, --format FORMAT
                        video format, specified by NAME or the keyword 'best'
  -F, --list-formats    list available formats
```
</details>

## twscraper-wrapper
Scrapes tweets into jsonl format. This script makes use of [twscrape](https://github.com/vladkens/twscrape) to replicate the functional output of
```sh
snscrape --jsonl twitter-user <handle> >> file_name.tweets.json
```
Before using, you must follow the instructions in the readme for twscrape to add at least one account to an `accounts.db` file in the same directory as the script. Additional functionality such as sorting saved files and automatically identifying the last tweet saved to limit search queries were added for convenience.

*Unfortunately, retweets are only able to be retrieved from an initial profile scrape. [Advanced search](https://github.com/igorbrigadir/twitter-advanced-search) queries (used with the `save-past` operation) are unable to retrieve retweets properly with modern twitter beyond ~10 days from the present for undocumented reasons. See [#2](https://github.com/CetaceanNation/misc-scripts/issues/2).*
<details>
<summary>Show Usage</summary>

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

</details>

## vrchat-asset-downloader
Use the [VRChat](https://vrchat.com/home) API to download assets. Only works with maps.
<details>
<summary>Show Usage</summary>

```sh
usage: vrchat-asset-downloader.py [-h] [-V] [-d DIRECTORY] [--write-thumbnail] [--write-json] [--dont-clean-json] [--verify] [--skip-download]
                                  [--revisions REVISIONS] [--list-revisions]
                                  [ASSET IDS ...]

positional arguments:
  ASSET IDS             world/avatar id(s) i.e. wrld_12345678-90ab-cdef-1234-567890abcdef

options:
  -h, --help            show this help message and exit
  -V, --verbose         print debugging information
  -d DIRECTORY, --directory DIRECTORY
                        save directory (defaults to current)
  --write-thumbnail     save thumbnail for the asset (if used with '--revision all', all thumbnail revisions will be retrieved)
  --write-json          write metadata to .json file(s)
  --dont-clean-json     retain all json values when writing .json file(s)
  --verify              whether or not to verify downloaded files against remote hashes
  --skip-download       skip downloading the actual asset(s)
  --revisions REVISIONS
                        valid values are the keywords 'all' and 'latest', or the revision integer itself
  --list-revisions      list available revisions for the specified asset
```
</details>

## vroid-hub-downloader
Downloads preview models from [VRoid Hub](https://hub.vroid.com/). Handles decryption and decompression (assist from bin).
<details>
<summary>Show Usage</summary>

```sh
usage: vroid-hub-downloader.py [-h] [-d DIRECTORY] [--write-info-json] [vroid links/vrm files ...]

positional arguments:
  vroid links/vrm files
                        vroid hub links or encrypted vrm files i.e.
                        https://hub.vroid.com/en/users/49620
                        https://hub.vroid.com/en/characters/6819070713126783571/models/9038381612772945358
                        2520951134072570694.vrm

options:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        save directory (defaults to current)
  --write-info-json     write user/model json information for urls
```
</details>
