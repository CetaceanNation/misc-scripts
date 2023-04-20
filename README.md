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

## vrchat-asset-downloader
Use the VRChat API to download assets. Only works with maps.
<details>
<summary>Show Usage</summary>
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
</details>
