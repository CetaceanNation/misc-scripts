# vrchat-asset-downloader
Use the [VRChat](https://vrchat.com/home) API to download assets. **Only works with world maps**.

### Usage
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
