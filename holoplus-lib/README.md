# holoplus-lib
I know that [kunesj/holoplus-resources](https://github.com/kunesj/holoplus-resources) already exists but I wanted to make my own way to interact with the API. Bonus of being able to authenticate in a managed browser window if want a clean session.

### CLI Usage
```sh
usage: python -m holoplus_lib [-h] [--debug] [--token TOKEN_FILE] [--cookies COOKIES_FILE]

options:
  -h, --help            show this help message and exit
  --debug               Print debug messages
  --interactive         Start interactive prompt
  --token TOKEN_FILE    File to read/save token information to/from
  --cookies COOKIES_FILE
                        Browser cookies if you've already authenticated on account.hololive.net
```

### CLI Example
```sh
# Authenticate to create token (token doesn't exist, will start Chromium browser for login)
python -m holoplus_lib --token my-token.json
# Authenticate to create token (token doesn't exist, will use cookies for authentication with account.hololive.net)
python -m holoplus_lib --token my-token.json --cookies my-cookies.txt
```

### Library Example
```python
import asyncio
from holoplus_lib import Holoplus

async def list_channels():
    async with Holoplus("my-token.json") as holoplus:
        channel_list = await holoplus.request("v4/talent-channel/channels")
        for c in channel_list["items"]:
            print("Found talent channel {} ({})".format(c["name"], c["id"]))

asyncio.run(list_channels())
```
