#!/usr/bin/env python3
import argparse
import json
import os
import re
import requests
from requests_toolbelt import sessions
import shutil
from tqdm.auto import tqdm
import urllib.parse as urlparse

VALID_THUMBS = [250, 500, 1200]
API = "http://coverartarchive.org/release/"
RELEASE_REGEX = r"^(?:(?:https?:\/\/)?(?:.*?\.)?musicbrainz\.org\/release\/)?(?P<release_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:\/.+)?$"
BLOCK_SIZE = 1024


def download_image(i_url, filename):
    file_path = os.path.join(args.directory, filename)
    file_r = requests.get(i_url, stream=True, allow_redirects=True)
    if not file_r.ok:
        print(f"could not get art for {filename}")
    total_size = int(file_r.headers['content-length'])
    term_width = shutil.get_terminal_size((80, 20))[0]
    with tqdm.wrapattr(open(file_path, "wb"), "write",
                       desc=f"{filename}", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}{postfix}]",
                       ncols=int(term_width * 0.8), total=total_size,
                       unit="B", unit_scale=True, unit_divisor=BLOCK_SIZE
                       ) as file_h:
        for chunk in file_r.iter_content(BLOCK_SIZE):
            file_h.write(chunk)
    return


def download_covers(s, r_id):
    print(f"requesting art for {r_id}")
    covers_r = s.get(f"{r_id}")
    if not covers_r.ok:
        print(f"error: could not find art for release {r_id}")
        return
    covers_j = covers_r.json()
    print(f"found {len(covers_j['images'])} images")
    for image_i in range(0, len(covers_j["images"])):
        image_j = covers_j["images"][image_i]
        image_url = None
        if args.size == "original":
            image_url = image_j["image"]
        else:
            image_url = image_j["thumbnails"][args.size]
        filename = f"{str(image_i)}_" + "+".join(image_j["types"])
        if len(image_j["comment"]) > 0:
            comment = image_j["comment"]
            filename += f" ({comment})"
        filename_clean = re.sub(r"[^\w\-_\. \[\]\(\)\+]", "_", filename)
        filename_clean += "." + image_url.split(".")[-1]
        download_image(image_url, filename_clean)
    print(f"finished retrieving art for {r_id}")


def main():
    if len(args.release_list) == 0:
        parser.print_usage()
        return
    elif args.size != "original" and args.size not in VALID_THUMBS:
        print(f"invalid size specified ({args.size})")
        return
    elif not os.path.isdir(args.directory):
        os.makedirs(args.directory)
    api_session = sessions.BaseUrlSession(base_url=API)
    for release in args.release_list:
        release_id_m = re.search(RELEASE_REGEX, release)
        if release_id_m:
            release_id = release_id_m.group("release_id")
            download_covers(api_session, release_id)
        else:
            print(f"could not parse release id from '{release}'")


parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("-d", "--directory", type=str,
                    help="save directory (defaults to current)", default=os.getcwd())
parser.add_argument("-s", "--size", type=str, default="original",
                    help="image download size (250, 500, 1200, original)")
parser.add_argument("release_list", metavar="RELEASES", nargs="*",
                    help="releases to download i.e.\n3791c620-7ba4-3db0-bda8-2b060f31a7b8\nhttps://musicbrainz.org/release/3791c620-7ba4-3db0-bda8-2b060f31a7b8\nbeta.musicbrainz.org/release/3791c620-7ba4-3db0-bda8-2b060f31a7b8/discids")
args = parser.parse_args()

if __name__ == "__main__":
    main()
