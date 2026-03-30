import argparse
import asyncio
import logging

from . import Holoplus

log = logging.getLogger("holoplus_lib")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true",
                        help="Print debug messages")
    parser.add_argument("--token", type=str,
                        help="File to read/save token information to/from", metavar="TOKEN_FILE")
    parser.add_argument("--cookies", type=str,
                        help="Browser cookies if you've already authenticated on account.hololive.net",
                        metavar="COOKIES_FILE")
    args = parser.parse_args()
    logging.basicConfig()
    log.setLevel(logging.DEBUG if args.debug else logging.INFO)
    async with Holoplus(args.token) as holoplus:
        signed_in = False
        if await holoplus.valid_auth():
            signed_in = True
        else:
            signed_in = await holoplus.do_login(args.cookies)
        if signed_in:
            while True:
                endpoint = input("Enter an endpoint to query: ")
                if endpoint == "exit":
                    break
                print(await holoplus.request(endpoint))

if __name__ == "__main__":
    asyncio.run(main())
