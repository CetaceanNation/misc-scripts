# caa-downloader
Download art for a [MusicBrainz](https://musicbrainz.org/) release from the [Cover Art Archive](https://coverartarchive.org/).

### Usage
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
