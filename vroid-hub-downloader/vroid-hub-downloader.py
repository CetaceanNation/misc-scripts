#!/usr/bin/env python3
import argparse
from Crypto.Cipher import AES
import gzip
import io
import json
import os
import re
import requests
import sys
import zstandard

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/114.0"
HOST = "https://hub.vroid.com"
API_VERSION = "11"
MODEL_FILE_EXT = "glb"
VROID_BASE = r"(?:https?:\/\/)?hub\.vroid\.com\/(?P<lang>[a-z]{2}\/)?"
VROID_USER = VROID_BASE + r"users/(?P<user_id>\d+)"
VROID_MODEL = VROID_BASE + r"characters\/(?P<character_id>\d+)\/models\/(?P<model_id>\d+)"

def unpad(s):
    return s[:-ord(s[len(s)-1:])]

def get_user_model_ids(user_id):
    model_ids = []
    api_url = f"{HOST}/api/users/{user_id}/character_models?antisocial_or_hate_usage=&characterization_allowed_user=&corporate_commercial_use=&credit=&modification=&personal_commercial_use=&political_or_religious_usage=&redistribution=&sexual_expression=&violent_expression="
    page_num = 1
    while api_url:
        user_r = requests.get(api_url, headers={"User-Agent": USER_AGENT, "X-Api-Version": API_VERSION})
        if not user_r.ok:
            print(f"[user:{user_id}:page:{page_num}] got bad response from vroid hub, {user_r.status_code}")
            break
        user_j = user_r.json()
        if "next" in user_j["_links"]:
            api_url = HOST + user_j["_links"]["next"]["href"]
        else:
            api_url = None
        for model in user_j["data"]:
            model_ids.append(model["id"])
    print(f"[user:{user_id}] found {len(model_ids)} models")
    return model_ids

def download_preview_model(model_id):
    model_preview_url = f"{HOST}/api/character_models/{model_id}/optimized_preview"
    model_r = requests.get(model_preview_url, allow_redirects=True, headers={"User-Agent": USER_AGENT, "X-Api-Version": API_VERSION})
    if not model_r.ok:
        print(f"[model:{model_id}:preview] got bad response from vroid hub, {model_r.status_code}")
        print(model_r.content)
        return None
    return io.BytesIO(model_r.content)

def decrypt_decompress_model(model_id, model_bytes, model_filename):
    if not os.path.isfile(model_filename):
        with open(model_filename, "wb") as dec_vrm:
            iv_bytes = model_bytes.read(16)
            key_bytes = model_bytes.read(32)
            key_context = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            enc_data = model_bytes.read()
            dec_data = unpad(key_context.decrypt(enc_data))[4:]
            dctx = zstandard.ZstdDecompressor()
            with dctx.stream_writer(dec_vrm) as decompressor:
                decompressor.write(dec_data)
        print(f"[model:{model_id}] wrote decrypted and decompressed model '{os.path.basename(model_filename)}'")
    else:
        print(f"[model:{model_id}] '{os.path.basename(model_filename)}' already exists")

def download_model_from_vroid(model_id, subdir=None):
    model_path_base = os.path.join(subdir if subdir else args.directory, model_id)
    model_api_url = f"{HOST}/api/character_models/{model_id}"
    json_path = f"{model_path_base}.info.json"
    if args.write_info_json and not os.path.isfile(json_path):
        model_api_r = requests.get(model_api_url, headers={"User-Agent": USER_AGENT, "X-Api-Version": API_VERSION})
        if not model_api_r.ok:
            print(f"[model:{model_id}:api] got bad response from vroid hub, {model_r.status_code}")
        else:
            model_api_j = model_api_r.json()
            with open(json_path, "w") as json_file:
                json_file.write(json.dumps(model_api_j["data"]))
            print(f"[model:{model_id}:api] wrote '{os.path.basename(json_path)}'")
    else:
        print(f"[model:{model_id}:api] '{os.path.basename(json_path)}' already exists")
    enc_vrm = download_preview_model(model_id)
    if not enc_vrm:
        return
    decrypt_decompress_model(model_id, enc_vrm, f"{model_path_base}.{MODEL_FILE_EXT}")

def download_user_from_vroid(user_id):
    user_api_url = f"{HOST}/api/users/{user_id}"
    user_api_r = requests.get(user_api_url, headers={"User-Agent": USER_AGENT, "X-Api-Version": API_VERSION})
    if not user_api_r.ok:
        print(f"[user:{user_id}:api] got bad response from vroid hub, user might not exist, {user_api_r.status_code}")
        return
    user_api_j = user_api_r.json()
    username = user_api_j["data"]["user"]["name"]
    user_base_path = os.path.join(args.directory, f"{username} ({user_id})")
    if not os.path.isdir(user_base_path):
        os.makedirs(user_base_path)
    json_path = f"{user_base_path}.info.json"
    if args.write_info_json:
        with open(json_path, "w") as json_file:
            json_file.write(json.dumps(user_api_j["data"]))
        print(f"[user:{user_id}:api] wrote '{os.path.basename(json_path)}'")
    model_ids = get_user_model_ids(user_id)
    for model_id in model_ids:
        download_model_from_vroid(model_id, user_base_path)

parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("-d", "--directory", type=str, help="save directory (defaults to current)", default=os.getcwd())
parser.add_argument("--write-info-json", action="store_true", help="write user/model json information for urls")
parser.add_argument("vrms", metavar="vroid links/vrm files", nargs="*", help="vroid hub links or encrypted vrm files i.e.\nhttps://hub.vroid.com/en/users/49620\nhttps://hub.vroid.com/en/characters/6819070713126783571/models/9038381612772945358\n2520951134072570694.vrm")
args = parser.parse_args()

if not os.path.isdir(args.directory):
    os.makedirs(args.directory)

for vrm in args.vrms:
    vroid_usr_m = re.search(VROID_USER, vrm)
    model_m = re.search(VROID_MODEL, vrm)
    if vroid_usr_m:
        user_id = vroid_usr_m.group("user_id")
        download_user_from_vroid(user_id)
    elif model_m:
        model_id = model_m.group("model_id")
        download_model_from_vroid(model_id)
    else:
        if not os.path.isfile(vrm):
            print(f"could not find file at path '{vrm}'")
            continue
        with open(vrm, "rb") as vrm_file:
            enc_vrm = io.BytesIO(vrm_file.read())
        model_filename = os.path.join(args.directory, f"{vrm}.decrypted.{MODEL_FILE_EXT}")
        decrypt_decompress_model(enc_vrm, model_filename)
