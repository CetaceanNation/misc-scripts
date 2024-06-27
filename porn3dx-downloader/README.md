# porn3dx-downloader
Downloads videos and images from posts on [Porn3dx](https://porn3dx.com). Video formats available are better than those you can download with an account, expects and decrypts any encrypted video playlists.

The `--write-sidecars` option can be used in conjunction with `hydrus_sidecar_routers.png` to import the downloaded files along with tags and other metadata into [hydrus](https://github.com/hydrusnetwork/hydrus).

### Usage
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
