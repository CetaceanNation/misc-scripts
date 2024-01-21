#!/usr/bin/env python3
import argparse
import base64
from enum import Enum
import hashlib
import json
import os
import re
import requests
from requests_toolbelt import sessions
import shutil
import sys
from tqdm.auto import tqdm
import urllib.parse as urlparse

# api.vrchat.cloud domain does not always return full json details
API_URL = "https://vrchat.com/api/1/"
HEADERS = {"Host": "vrchat.com", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0"}
GUID_REGEX = r"_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
ASSET_REGEX = r"^(?P<asset_type>wrld)" + GUID_REGEX + r"$"
FILE_REGEX = r"^https?:\/\/api\.vrchat\.cloud\/api\/1\/file\/(?P<file_id>file" + GUID_REGEX + r")\/[0-9]+\/file$"
CLEAN_FILENAME_KINDA=r"[^\w\-_\. \[\]\(\)]"
BLOCK_SIZE = 1024
REMOVE_FROM_JSON = ["favorites", "visits", "popularity", "heat", "publicOccupants", "privateOccupants", "occupants", "instances"]
ASSET_TYPES = {"wrld": "world", "avtr": "avatar"}

class LogLevel(Enum):
    BASIC=1
    VERBOSE=2

def clean_filename(path):
    return re.sub(CLEAN_FILENAME_KINDA, "_", path)

def get_auth(s):
    config_r = s.get(f"config")
    if not config_r.ok:
        print_log("config", "failed to retrieve API key")
        print_log("config", f"config endpoint returned status '{config_r.status_code}'", level=LogLevel.VERBOSE)
        sys.exit(1)
    config_j = config_r.json()
    if "clientApiKey" not in config_j or not config_j["clientApiKey"]:
        print_log("config", "failed to retrieve API key")
        print_log("config", f"config response lacks clientApiKey value", level=LogLevel.VERBOSE)
        sys.exit(1)
    clientKey = config_j["clientApiKey"]
    token_path = os.path.join(os.getcwd(), "vrchat-token")
    auth_cookie = None
    if os.path.isfile(token_path):
        print_log("auth", "reading saved token")
        with open(token_path, "r") as token_file:
            auth_cookie = token_file.read()
    if not auth_cookie or len(auth_cookie) == 0:
        print_log("auth", f"while logged in to vrchat.com, visit '{API_URL}auth?apiKey={clientKey}' in your browser")
        auth_cookie = input("copy your token value here: ")
    s.headers["Cookie"] = f"apiKey={clientKey}; auth={auth_cookie};"
    auth_r = s.get(f"auth?apiKey={clientKey}")
    if not auth_r.ok:
        print_log("auth", "error: the token you provided does not appear to be valid")
        sys.exit(1)
    with open(token_path, "w") as token_file:
        token_file.write(auth_cookie)
    return clientKey

def download_asset(a_type, a_id, s, api_key):
    url = f"{a_type}s/{a_id}?{urlparse.urlencode(api_key)}"
    r = s.get(url)
    if not r.ok:
        print_log(f"{a_type}", f"failed to retrieve API response for {a_id}")
        print_log(f"{a_type}", f"asset endpoint returned status '{r.status_code}'", level=LogLevel.VERBOSE)
        return
    asset_j = r.json()

    file_j = None
    if "assetUrl" in asset_j and asset_j["assetUrl"]:
        # this URL no longer returned, may not ever exist again
        asset_m = re.search(FILE_REGEX, asset_j["assetUrl"])
        if asset_m:
            file_id = asset_m.group("file_id")
            print_log(f"{a_type}", f"found asset for '{asset_j['name']}' ({a_id})")
            file_j = get_file_json(file_id, s)
            asset_j["_assetFile"] = file_j
        else:
            print_log(f"{a_type}", f"could not find the asset url for '{asset_j['name']}' ({a_id})")
            print_log(f"{a_type}", f"assetUrl did not match expected pattern ('asset_j['assetUrl']')", level=LogLevel.VERBOSE)
    elif "unityPackages" in asset_j and len(asset_j["unityPackages"]) > 0:
        # new way to get asset file ids
        for unityPackage in asset_j["unityPackages"]:
            asset_m = re.search(FILE_REGEX, unityPackage["assetUrl"])
            if asset_m:
                file_id = asset_m.group("file_id")
                print_log(f"{a_type}", f"found asset for '{asset_j['name']}' ({a_id})")
                file_j = get_file_json(file_id, s)
                asset_j["_assetFile"] = file_j
            else:
                print_log(f"{a_type}", f"could not find the asset url for '{asset_j['name']}' ({a_id})")
                print_log(f"{a_type}", f"assetUrl did not match expected pattern ('asset_j['assetUrl']')", level=LogLevel.VERBOSE)
    else:
        print_log(f"{a_type}", f"could not find the asset url for '{asset_j['name']}' ({a_id})")
        print_log(f"{a_type}", f"asset response lacks assetUrl value", level=LogLevel.VERBOSE)

    image_j = None
    if "imageUrl" in asset_j and asset_j["imageUrl"]:
        image_m = re.search(FILE_REGEX, asset_j["imageUrl"])
        if image_m:
            image_id = image_m.group("file_id")
            print_log(f"{a_type}", f"found image for '{asset_j['name']}' ({a_id})")
            image_j = get_file_json(image_id, s)
            asset_j["_imageFile"] = image_j
        else:
            print_log(f"{a_type}", f"could not find the image url for '{asset_j['name']}' ({a_id})")
            print_log(f"{a_type}", f"imageUrl did not match expected pattern ('{asset_j['imageUrl']}')", level=LogLevel.VERBOSE)
    else:
        print_log(f"{a_type}", f"could not find the image url for '{asset_j['name']}' ({a_id})")
        print_log(f"{a_type}", f"asset response lacks imageUrl value", level=LogLevel.VERBOSE)

    if args.dont_clean_json:
        for key in REMOVE_FROM_JSON:
            if key in asset_j:
                asset_j.pop(key)

    if args.list_revisions:
        list_file_versions(file_j)
        return
    else:
        save_dir = os.path.join(args.directory, asset_j["name"])
        if not os.path.isdir(save_dir):
            os.makedirs(save_dir)
        if args.write_json:
            json_filename = f"{a_id}.json"
            json_filepath = os.path.join(save_dir, json_filename)
            if os.path.isfile(f"{json_filepath}.tmp"):
                os.remove(f"{json_filepath}.tmp")
            print_log(f"{a_type}", f"writing asset information to '{json_filename}'")
            with open(f"{json_filepath}.tmp", "w") as json_file:
                json_file.write(json.dumps(asset_j))
            if os.path.isfile(json_filepath):
                os.remove(json_filepath)
            os.rename(f"{json_filepath}.tmp", json_filepath)
        if image_j and args.write_thumbnail:
            download_file_from_json(image_j, save_dir, s)
        if asset_j and not args.skip_download:
            download_file_from_json(file_j, save_dir, s)
    print_log(f"{a_type}", f"finished '{asset_j['name']}' ({a_id})")

def get_file_json(f_id, s):
    url = f"file/{f_id}"
    r = s.get(url)
    if not r.ok:
        print_log("file", f"failed to retrieve API response for {f_id}")
        print_log("file", f"file endpoint returned status '{r.status_code}'", level=LogLevel.VERBOSE)
        return None
    file_j = r.json()
    return file_j

def list_file_versions(file_j):
    print(f"{'VERSION':<7} {'CREATED AT':<24} {'SIZE (BYTES)':<12} {'MD5':<32}")
    print(f"{'-' * 7} {'-' * 24} {'-' * 12} {'-' * 32}")
    for revision in file_j["versions"][1:]:
        md5sum = base64.b64decode(revision["file"]["md5"])
        file_size = revision['file']['sizeInBytes']
        print(f" {revision['version']:<6} " +
        f"{revision['created_at']:<24} " +
        f"{str(file_size):>12} " +
        f"{md5sum.hex():<32}")

def download_file_from_json(file_j, save_dir, s):
    get_versions = []
    latest_rev = len(file_j["versions"]) - 1
    term_width = shutil.get_terminal_size((80, 20))[0]
    if args.revisions == "all":
        get_versions = [*range(1, latest_rev + 1)]
    elif args.revisions == "latest":
        get_versions.append(latest_rev)
    elif int(args.revisions) < 1 or int(args.revisions) > latest_rev:
        print_log("file", f"error: revision specified out of range, try --list-revisions")
        return
    else:
        get_versions.append(int(args.revisions))
    print_log("file", f"Downloading {file_j['name']}")
    for dl_num, dl_ver in enumerate(get_versions):
        cur_j = file_j["versions"][dl_ver]["file"]
        file_path = os.path.join(save_dir, cur_j["fileName"])
        if os.path.isfile(file_path):
            print_log("file", f"'{cur_j['fileName']}' already exists")
        else:
            s.headers["Host"] = "api.vrchat.cloud"
            redirect_r = s.get(cur_j["url"], stream=True, allow_redirects=False)
            if not redirect_r.ok:
                print_log(f"file", f"could not retrieve file for '{file_j['id']}'")
                print_log(f"file", f"file url '{cur_j['url']}' returned status '{redirect_r.status_code}'", level=LogLevel.VERBOSE)
                break
            file_r = requests.get(redirect_r.headers["Location"], stream=True)
            if not file_r.ok:
                print_log(f"file", f"could not retrieve file for '{file_j['id']}'")
                print_log(f"file", f"file url '{cur_j['url']}' returned status '{file_r.status_code}'", level=LogLevel.VERBOSE)
                break
            total_size = int(cur_j["sizeInBytes"])
            with tqdm.wrapattr(open(file_path, "wb"), "write",
                desc=f"[file] Rev {dl_ver} ({dl_num + 1}/{len(get_versions)})", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}{postfix}]",
                ncols=int(term_width * 0.8), total=total_size,
                unit="B", unit_scale=True, unit_divisor=BLOCK_SIZE
            ) as file_h:
                for chunk in file_r.iter_content(BLOCK_SIZE):
                    file_h.write(chunk)
                file_h.flush()
        if args.verify and os.path.isfile(file_path):
            verify_file(cur_j["fileName"], file_path, cur_j["md5"])
    return

def verify_file(file_name, file_path, md5b64):
    print_log("hash", f"verifying {file_name}...", overwrite = True)
    remote_md5 = base64.b64decode(md5b64)
    with open(file_path, "rb") as file_h:
        local_md5 = hashlib.md5()
        while chunk := file_h.read(BLOCK_SIZE):
            local_md5.update(chunk)
    if remote_md5 == local_md5.digest():
        print_log("hash", f"'{file_name}' verified successfully")
    else:
        print_log("hash", f"'{file_name}' failed to verify")

def print_log(component, message, level=LogLevel.BASIC, overwrite=False):
    if level == LogLevel.VERBOSE and not args.verbose:
        return
    if overwrite:
        print(f"[{component}] {message}", end="\r")
    else:
        print(f"[{component}] {message}")

def get_arguments():
    parser.add_argument("-V", "--verbose", action="store_true", help="print debugging information")
    parser.add_argument("-d", "--directory", type=str, help="save directory (defaults to current)", default=os.getcwd())
    parser.add_argument("--write-thumbnail", action="store_true", help="save thumbnail for the asset (if used with '--revision all', all thumbnail revisions will be retrieved)")
    parser.add_argument("--write-json", action="store_true", help="write metadata to .json file(s)")
    parser.add_argument("--dont-clean-json", action="store_false", help="retain all json values when writing .json file(s)")
    parser.add_argument("--verify", action="store_true", help="whether or not to verify downloaded files against remote hashes", default=False)
    parser.add_argument("--skip-download", action="store_true", help="skip downloading the actual asset(s)")
    parser.add_argument("--revisions", type=str, help="valid values are the keywords 'all' and 'latest', or the revision integer itself", default="latest")
    parser.add_argument("--list-revisions", action="store_true", help="list available revisions for the specified asset")
    parser.add_argument("asset_id_list", metavar="ASSET IDS", nargs="*", help="world/avatar id(s) i.e. wrld_12345678-90ab-cdef-1234-567890abcdef")
    return parser.parse_args()

def main():
    if len(args.asset_id_list) == 0:
        parser.print_usage()
        return
    elif not os.path.isdir(args.directory):
        os.makedirs(args.directory)
    api_session = sessions.BaseUrlSession(base_url=API_URL)
    api_session.headers = HEADERS
    api_key = get_auth(api_session)
    api_key_t = {"apiKey": api_key}
    for asset_id in args.asset_id_list:
        asset_type_m = re.search(ASSET_REGEX, asset_id)
        if asset_type_m:
            asset_type = asset_type_m.group("asset_type")
            download_asset(ASSET_TYPES[asset_type], asset_id, api_session, api_key_t)
        else:
            print_log("vrchat-asset-downloader", f"id {asset_id} does not appear to be valid")

parser = argparse.ArgumentParser()
args = get_arguments()

if __name__ == "__main__":
    main()
