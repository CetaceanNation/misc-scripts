# vroid-hub-downloader
Downloads preview models (viewable in the browser) from [VRoid Hub](https://hub.vroid.com/). Handles decryption and decompression (assist from bin).

### Usage
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
