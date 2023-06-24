#!/usr/bin/env python3
import argparse
from bs4 import BeautifulSoup as bs
from Crypto.Cipher import AES
from enum import Enum
import json
import js2py
import os
import re
import requests
from subprocess import Popen, PIPE, STDOUT
import tempfile
import urllib.parse as urlparse

HOST = "https://porn3dx.com/"
EMBED_HOST = "https://iframe.mediadelivery.net/"
DRM_ACTIVATION_HOST = "https://video-987.mediadelivery.net/"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/114.0"}
POST_REGEX = r".*(?P<url>porn3dx\.com\/post\/(?P<id>\d+)).*"
GUID_REGEX = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
PING_TOKEN_REGEX = r";setTimeout\(function\(\)\{var\ [a-z]=\"(?P<ping_token>" + GUID_REGEX + r")\";var\ [a-z]=(?P<secret_function>function\([a-z]+\)\{.*toLowerCase\(\)\});"
PLAYLIST_REGEX = r"https?:\/\/iframe\.mediadelivery\.net\/" + GUID_REGEX + r"\/playlist.drm\?contextId=(?P<context_id>" + GUID_REGEX + r")&secret=" + GUID_REGEX

class LogLevel(Enum):
    BASIC=1
    VERBOSE=2

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
    parser.add_argument("--skip-download", action="store_true", help="skip downloading the post")
    parser.add_argument("-f", "--format", type=str, help="video format, specified by NAME or the keyword \'best\'", default="best")
    parser.add_argument("-F", "--list-formats", action="store_true", help="list available formats")
    parser.add_argument("posts", metavar="POSTS", nargs="*", help="post url")
    return parser.parse_args()

# based on parts of https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/extractor/common.py
def get_m3u8_info(session, playlist_url, referer_url):
    m3u8_info = []
    print_log("get-m3u8-info", f"retrieving playlist from {playlist_url}", LogLevel.VERBOSE)
    m3u8_r = session.get(playlist_url, headers={"Referer": referer_url})
    if not m3u8_r.ok:
        print_log("get-m3u8-info", f"failed to retrieve playlist from {playlist_url}")
    m3u8_text = m3u8_r.text
    media_details = None
    format_details = None
    for line in m3u8_text.splitlines():
        if line.startswith("#EXT-X-STREAM-INF:"):
            # parse format details
            format_details = parse_m3u8_attributes(line)
        elif not line.startswith("#"):
            if format_details:
                if "RESOLUTION" in format_details:
                    media_name = format_details["RESOLUTION"].split("x")[1] + "p"
                else:
                    media_name = line.split("/")[0]
                m3u8_info += [{"location": line, "name": media_name, "bandwidth": format_details["BANDWIDTH"], "res": format_details["RESOLUTION"]}]
    return m3u8_info

# https://github.com/ytdl-org/youtube-dl/blob/master/youtube_dl/utils.py#L5495
def parse_m3u8_attributes(attrib):
    info = {}
    for (key, val) in re.findall(r'(?P<key>[A-Z0-9-]+)=(?P<val>"[^"]+"|[^",]+)(?:,|$)', attrib):
        if val.startswith("\""):
            val = val[1:-1]
        info[key] = val
    return info

def print_formats(formats_list):
    print(f"{'NAME':<10} {'BANDWIDTH':<10} {'RESOLUTION':<10}")
    print(f"{'-' * 10} {'-' * 10} {'-' * 10}")
    for format_settings in formats_list:
        print(f"{format_settings['name']:<10} " +
        f"{format_settings['bandwidth']:<10} " +
        f"{format_settings['res']:<10} ")

def get_post_data(post_id, soup):
    post_data = {}
    post_data["id"] = post_id
    post_data["urls"] = [soup.link["href"]]
    post_data["basefilename"] = soup.link["href"].split("/")[-1]
    post_data["description"] = soup.find("div", class_="desc-container").get_text().strip("\n ")
    tags = []
    post_title_block = soup.find("div", class_="title-wrapper")
    tags.append("title:" + post_title_block.find("h1").string)
    tags.append("creator:" + post_title_block.find("a").string)
    tag_block = soup.find("div", class_="tags-container")
    for tag_span in tag_block.find_all("span", recursive=False):
        tag_category = tag_span.span.text.lower()
        if tag_category == "copyright":
            tag_category = "series"
        elif tag_category == "artist":
            tag_category = "creator"
        tag_category = tag_category + ":" if tag_category != "general" else ""
        for tag_link in tag_span.find_all("a"):
            tags.append(tag_category + tag_link.text)
    post_data["tags"] = tags
    return post_data

def write_frag(session, frag_url, frag_name, key_context):
    try:
        with open(frag_name, "wb") as frag_file:
            video_frag_r = session.get(frag_url, headers={"Origin": EMBED_HOST, "Referer": EMBED_HOST})
            if not video_frag_r.ok:
                print_log(f"dl:{post_id}", f"failed to download video fragment '{frag_name}'")
                return False
            # Fragments are small, decrypt in memory then write to disk
            frag_bytes = key_context.decrypt(video_frag_r.content)
            frag_file.write(frag_bytes)
        return True
    except:
        print_log(f"dl:{post_id}", f"exception downloading video fragment '{frag_name}'")
        return False

def download_stream(session, index, post_data, downloading_format, drm_session, referer_url):
    post_id = post_data["id"]
    file_name = post_data["basefilename"]
    res_name = downloading_format["name"][:-1]
    context_id = drm_session["id"]
    refresh_token = drm_session["token"]
    refresh_function = drm_session["function"]
    playlist_r = session.get(downloading_format["location"], headers={"Referer": referer_url})
    if not playlist_r.ok:
        print_log(f"dl:{post_id}", "failed to retrieve post playlist")
        return
    playlist_text = playlist_r.text
    key_context = None
    key_count = 0
    frag_files = []
    for line in playlist_text.splitlines():
        if line.startswith("#EXT-X-KEY:"):
            # New key for decrypting fragments
            key_attr = parse_m3u8_attributes(line)
            key_r = session.get(key_attr["URI"], headers={"Origin": EMBED_HOST, "Referer": EMBED_HOST})
            if not key_r.ok:
                print_log(f"key-context:{post_id}", "failed to retrieve key for segments")
            key_bytes = key_r.content
            iv_bytes = bytearray.fromhex(key_attr["IV"][2:])
            print_log(f"key-context:{post_id}", f"new key context [IV: {iv_bytes.hex()}, K: {key_bytes.hex()}]", LogLevel.VERBOSE)
            key_context = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            key_count += 1
            # Refresh DRM context
            time_in_video = float(key_count)
            refresh_string = f"{refresh_token}_{context_id}_{time_in_video}_false_{res_name}"
            refresh_hash = refresh_function(refresh_string)
            refresh_url = DRM_ACTIVATION_HOST + f".drm/{context_id}/ping?hash={refresh_hash}&time={time_in_video}&paused=false&resolution={res_name}"
            print_log(f"drm:{post_id}", f"refreshing session; {refresh_url}", LogLevel.VERBOSE)
            refresh_r = session.get(refresh_url, headers={"Origin": EMBED_HOST, "Referer": EMBED_HOST})
            if not refresh_r.ok:
                print_log(f"drm:{post_id}", "failed to refresh the drm session, will continue but likely to fail if the video is long")
        elif not line.startswith("#"):
            # Write the fragment
            frag_file_name = os.path.abspath(os.path.join(args.directory, f"{file_name}.{len(frag_files)}.ts"))
            if write_frag(session, line, frag_file_name, key_context):
                frag_files.append(frag_file_name)
    output_file_name = f"{file_name}.{index}.mp4"
    output_file_path = os.path.abspath(os.path.join(args.directory, output_file_name))
    # Use ffmpeg to concatenate all the fragments into a single output file
    print_log("mpeg-convert", f"merging into {output_file_name}")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as frag_list:
        for frag_name in frag_files:
            frag_list.write(f"file '{frag_name}'\n")
        frag_list.flush()
        ffmpeg_list = ["ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", frag_list.name, "-c", "copy", output_file_path]
        print_log("ffmpeg", f"args: {ffmpeg_list}", LogLevel.VERBOSE)
        try:
            ffmpeg_process = Popen(ffmpeg_list, stdout=PIPE, stderr=PIPE)
            stdout, stderr = ffmpeg_process.communicate()
        except Exception:
            print_log("mpeg-convert", "failure in executing ffmpeg")
            print_log("ffmpeg", f"stdout: {str(stdout)}\n\nstderr: {str(stderr)}", LogLevel.VERBOSE)
            return
        frag_list.close()
    # Cleanup only if file is found
    if os.path.isfile(output_file_path):
        for frag_name in frag_files:
            os.remove(frag_name)
        return output_file_path, post_data
    print_log("mpeg-convert", "could not find output file")

def download_video(session, index, post_data, content_soup):
    post_id = post_data["id"]
    iframe_url = content_soup.find("div", class_="video-block").iframe["src"]
    if not iframe_url:
        print_log(f"info:{post_id}", "could not find embed url in post page")
        return
    # Download embed to get formats playlist url
    iframe_r = session.get(iframe_url, headers={"Referer": HOST})
    if not iframe_r.ok:
        print_log(f"info:{post_id}", "failed to retrieve video embed")
        return
    iframe_soup = bs(iframe_r.content, "html.parser")
    iframe_script = iframe_soup.find_all("script")[-1].string
    # Extract formats playlist url from embed script
    playlist_m = re.search(PLAYLIST_REGEX, iframe_script)
    if not playlist_m:
        print_log(f"info:{post_id}", "could not find format playlist url in embed")
        return
    playlist_url = playlist_m.group(0)
    context_id = playlist_m.group("context_id")
    # Get available formats
    formats_list = get_m3u8_info(session, playlist_url, iframe_url)
    if args.list_formats:
        print_log(f"info:{post_id}", "available formats:")
        print_formats(formats_list)
        return
    # Activate DRM session
    drm_session = {}
    activation_url = urlparse.urljoin(DRM_ACTIVATION_HOST, f".drm/{context_id}/activate")
    if not session.get(activation_url, headers={"Origin": EMBED_HOST, "Referer": EMBED_HOST}).ok:
        print_log(f"drm:{post_id}", "failed to activate drm context, download will not proceed")
        return
    print_log(f"drm:{post_id}", f"activated drm context {context_id}", LogLevel.VERBOSE)
    drm_session["id"] = context_id
    # Extract refresh token from embed script
    # TODO: reverse hashing function to make drm session pings possible
    token_m = re.search(PING_TOKEN_REGEX, iframe_script)
    if not token_m:
        print_log(f"info:{post_id}", "could not find ping refresh token in embed")
        return
    drm_session["token"] = token_m.group("ping_token")
    secret_script = token_m.group("secret_function")
    drm_session["function"] = js2py.eval_js(secret_script)
    # Select preferred format
    downloading_format = None
    best_bitrate = 0
    for format_settings in formats_list:
        if args.format == "best":
            if int(format_settings["bandwidth"]) > best_bitrate:
                downloading_format = format_settings
                best_bitrate = int(format_settings["bandwidth"])
        elif args.format == format_settings["name"]:
            downloading_format = format_settings
            break
    if not downloading_format:
        print_log(f"info:{post_id}", f"the specified format could not be found: {args.format}")
        return
    downloading_format["location"] = urlparse.urljoin(playlist_url, format_settings["location"])
    format_name = downloading_format["name"]
    print_log(f"info:{post_id}", f"downloading format {format_name}")
    return download_stream(session, index, post_data, downloading_format, drm_session, iframe_url)

def download_image(session, index, post_data, content_soup):
    post_id = post_data["id"]
    file_name = post_data["basefilename"]
    image_url = content_soup.img["data-full-url"] if content_soup.img["data-full-url"] else content_soup["href"]
    image_ext = os.path.splitext(urlparse.urlparse(image_url).path)[1]
    output_file_name = f"{file_name}.{index}{image_ext}"
    output_file_path = os.path.join(args.directory, output_file_name)
    with open(output_file_path, "wb") as image_file:
        image_r = session.get(image_url)
        if not image_r.ok:
            print_log(f"info:{post_id}", "failed to retrieve image content")
            return
        image_file.write(image_r.content)
    post_data["urls"].append(image_url)
    return output_file_path, post_data

def write_sidecar(path, data):
    if path and data:
        data["filename"] = os.path.basename(path)
        with open(f"{path}.json", "w") as sidecar_file:
            json.dump(data, sidecar_file, ensure_ascii=False, indent=4)

def download_post(session, post_id, post_url):
    # Download page to extract iframe embed url
    print_log(f"info:{post_id}", "retrieving post page")
    post_page_r = session.get(post_url)
    if not post_page_r.ok:
        print_log(f"info:{post_id}", "failed to retrieve post page")
        return
    page_soup = bs(post_page_r.content, "html.parser")
    post_data = get_post_data(post_id, page_soup)
    post_contents = page_soup.find("div", class_="content-wrapper")
    potential_content = post_contents.find_all("div", recursive=False) + post_contents.find_all("a", recursive=False)
    other_media = post_contents.find("div", class_="other-media")
    if other_media:
        potential_content += other_media.find_all("div", recursive=False) + other_media.find_all("a", recursive=False)
    content_index = 0
    for wrapper in potential_content:
        match wrapper["class"][0]:
            case "videobox":
                print_log(f"info:{post_id}", "getting video")
                video_result = download_video(session, content_index, post_data, wrapper)
                if video_result:
                    video_path, post_data = video_result
                    write_sidecar(video_path, post_data)
                content_index += 1
            case "example-image-link":
                print_log(f"info:{post_id}", "getting image")
                image_result = download_image(session, content_index, post_data, wrapper)
                if image_result:
                    image_path, post_data = image_result
                    write_sidecar(image_path, post_data)
                content_index += 1

def main():
    if len(args.posts) == 0:
        parser.print_usage()
        return
    elif not os.path.isdir(args.directory):
        os.makedirs(args.directory)
    s = requests.Session()
    s.headers = HEADERS
    for post in args.posts:
        url_m = re.search(POST_REGEX, post)
        if url_m:
            post_url = "https://" + url_m.group("url")
            download_post(s, url_m.group("id"), post_url)

parser = argparse.ArgumentParser()
args = get_arguments()

if __name__ == "__main__":
    main()
