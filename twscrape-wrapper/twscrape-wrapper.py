#!/usr/bin/env python3
import argparse
import asyncio
from collections import OrderedDict
from contextlib import aclosing
import datetime
import json
import os
import requests
import sys
from time import sleep
from twscrape import API, AccountsPool, gather
from twscrape.logger import set_log_level

OPERATIONS = ["save", "save-past", "sort", "dedupe"]
KEY_ORDER_TWEET = ["_type", "url", "date", "rawContent", "renderedContent", "id", "user", "replyCount", "retweetCount", "likeCount", "quoteCount", "conversationId", "lang", "source", "sourceUrl", "sourceLabel", "links", "media", "retweetedTweet", "quotedTweet", "inReplyToTweetId", "inReplyToUser", "mentionedUsers", "coordinates", "place", "hashtags", "cashtags", "card", "viewCount", "vibe", "content", "outlinks", "outlinksss", "tcooutlinks", "tcooutlinksss", "username"]
KEY_ORDER_USER = ["_type", "username", "id", "displayname", "rawDescription", "renderedDescription", "descriptionLinks", "verified", "created", "followersCount", "friendsCount", "statusesCount", "favouritesCount", "listedCount", "mediaCount", "location", "protected", "link", "profileImageUrl", "profileBannerUrl", "label", "description", "descriptionUrls", "linkTcourl", "linkUrl", "url"]
BACKWARDS_INTERVAL = 120
MEDIA_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/114.0"}
MEDIA_IMAGE_NAMES = ["orig", "large", "medium", "900x900", "small", "thumb"]

def datetime_handler(x):
    if isinstance(x, datetime.datetime):
        return x.isoformat()
    raise TypeError("Unknown type")

def datetime_to_search_string(dt):
    return dt.isoformat().replace("T", "_") + "_UTC"

async def get_account_id(api, handle):
    try:
        twitter_user = await api.user_by_login(handle)
        return twitter_user.id
    except Exception:
        print("could not lookup user with that handle")
        sys.exit(1)

def get_account_from_file(filepath):
    if os.path.isfile(filepath):
        try:
            with open(filepath, "r") as tweetsfile:
                last_tweet_json = tweetsfile.readline()
            last_tweet = json.loads(last_tweet_json)
            return last_tweet["user"]["username"]
        except Exception:
            print(f"failed reading the existing tweets file '{filepath}'")
            sys.exit(1)
    print(f"could not find the specified file '{filepath}'")
    sys.exit(1)

def get_saved_tweets(filepath):
    saved_tweets = []
    saved_tweet_jsons = []
    print(f"looking for tweets in {filepath}")
    if os.path.isfile(filepath):
        try:
            with open(filepath, "r") as tweetsfile:
                saved_tweets = tweetsfile.readlines()
            if len(saved_tweets) > 0:
                for tweet_json in saved_tweets:
                    saved_tweet_jsons.append(json.loads(tweet_json))
        except Exception:
            print("failed reading the existing tweets file")
            sys.exit(1)
    print(f"found {len(saved_tweet_jsons)} saved tweets")
    return saved_tweet_jsons

def dedupe_tweets(tweets):
    stored_ids = []
    filtered_tweets = []
    for tweet in tweets:
        if not tweet["id"] in stored_ids:
            stored_ids.append(tweet["id"])
            filtered_tweets.append(tweet)
    return filtered_tweets

def get_last_tweet(tweets, since=True):
    last_tweet_date = datetime.datetime.fromisoformat(tweets[0]["date"]).timestamp()
    last_tweet_id = None
    for tweet in tweets:
        current_tweet_date = datetime.datetime.fromisoformat(tweet["date"]).timestamp()
        if (since and current_tweet_date > last_tweet_date) or (not since and current_tweet_date < last_tweet_date):
            last_tweet_date = current_tweet_date
            last_tweet_id = tweet["id"]
    return last_tweet_date, last_tweet_id

async def gather_initial_tweets(api, account_handle):
    tweets = []
    account_id = await get_account_id(api, account_handle)
    user_tweets = await gather(api.user_tweets(account_id))
    for tweet in user_tweets:
        if tweet.user.username == account_handle:
            tweets.append(json.loads(json.dumps(tweet.dict(), default=datetime_handler)))
    return tweets

async def gather_tweets(api, account_handle, last_timestamp):
    tweets = []
    # Subtract a day to try ensuring overlap, prevents <24 hour difference issues
    last_datetime = datetime.datetime.fromtimestamp(last_timestamp)
    last_datetime -= datetime.timedelta(days=1)
    last_datetime_string = datetime_to_search_string(last_datetime)
    query_string = f"from:{account_handle} since:{last_datetime_string}"
    print(f"query: '{query_string}'")
    user_tweets = await gather(api.search(query_string))
    for tweet in user_tweets:
        if tweet.user.username == account_handle:
            tweets.append(json.loads(json.dumps(tweet.dict(), default=datetime_handler)))
    return tweets

async def gather_tweets_backwards(api, account_handle, latest_timestamp):
    tweets = []
    # Add a day to try ensuring overlap, prevents <24 hour difference issues
    latest_datetime = datetime.datetime.fromtimestamp(latest_timestamp)
    latest_datetime += datetime.timedelta(days=1)
    while True:
        latest_datetime_string = datetime_to_search_string(latest_datetime)
        back_one_month = latest_datetime - datetime.timedelta(days=BACKWARDS_INTERVAL)
        back_one_month_string = datetime_to_search_string(back_one_month)
        query_string = f"from:{account_handle} since:{back_one_month_string} until:{latest_datetime_string}"
        print(f"query: '{query_string}'")
        user_tweets = await gather(api.search(query_string))
        if len(user_tweets) == 0:
            break
        for tweet in user_tweets:
            if tweet.user.username == account_handle:
                tweets.append(json.loads(json.dumps(tweet.dict(), default=datetime_handler)))
        latest_datetime = back_one_month + datetime.timedelta(days=1)
    return tweets

def sort_tweets(tweets):
    return list(reversed(sorted(tweets, key=lambda t: datetime.datetime.fromisoformat(t["date"]).timestamp())))

def order_tweet_dict(tweet):
    ordered_tweet = OrderedDict((key, tweet.get(key)) for key in KEY_ORDER_TWEET)
    ordered_tweet["user"] = OrderedDict((key, ordered_tweet["user"].get(key)) for key in KEY_ORDER_USER)
    return ordered_tweet

def write_tweets(tweets, tmp_filepath, filepath, overwrite):
    with open(tmp_filepath, "w") as tmp_tweetsfile:
        for tweet in tweets:
            tweet_json = json.dumps(order_tweet_dict(tweet), default=datetime_handler)
            tmp_tweetsfile.write(f"{tweet_json}\n")
    overwrite = overwrite or input("overwrite existing file? (y/N): ") == "y"
    if overwrite:
        os.replace(tmp_filepath, filepath)

def get_tweet_media(base_filepath, tweets):
    media_directory = base_filepath + ".media"
    if not os.path.isdir(media_directory):
        try:
            os.makedirs(media_directory)
        except:
            try:
                media_directory = os.path.join(os.getcwd(), media_directory)
                os.makedirs(media_directory)
            except:
                print("could not find or make the media directory, skipping media downloads")
                return
    print(f"downloading media for {len(tweets)} tweets")
    media_count = 0
    for tweet in tweets:
        if "media" in tweet and tweet["media"]:
            tweet_url = tweet["url"]
            tweet_media = tweet["media"]
            media_index = 0
            tweet_id = tweet["id"]
            if "photos" in tweet_media and tweet_media["photos"]:
                images = tweet_media["photos"]
                for image in images:
                    image_url = image["url"]
                    image_url_path, image_ext = os.path.splitext(image_url.split("?")[0])
                    image_filename = f"{tweet_id}_{media_index}{image_ext}"
                    image_fmt = image_ext[1:]
                    for img_name in MEDIA_IMAGE_NAMES:
                        image_url = f"{image_url_path}?format={image_fmt}&name={img_name}"
                        image_res = download_media_file(tweet_url, image_url, os.path.join(media_directory, image_filename))
                        if image_res > 1:
                            media_count += 1
                        if image_res > 0:
                            media_index += 1
                            break
            if "videos" in tweet_media and tweet_media["videos"]:
                videos = tweet_media["videos"]
                for video in videos:
                    video_variants_sorted = sorted(video["variants"], key=lambda v: v["bitrate"], reverse=True)
                    for variant in video_variants_sorted:
                        video_url = variant["url"]
                        _, video_ext = os.path.splitext(video_url.split("?")[0])
                        video_filename = f"{tweet_id}_{media_index}{video_ext}"
                        video_res = download_media_file(tweet_url, video_url, os.path.join(media_directory, video_filename))
                        if video_res > 1:
                            media_count += 1
                        if video_res > 0:
                            media_index += 1
                            break
            if "animated" in tweet_media and tweet_media["animated"]:
                animations = tweet_media["animated"]
                for animation in animations:
                    animation_url = animation["videoUrl"]
                    _, animation_ext = os.path.splitext(animation_url.split("?")[0])
                    animation_filename = f"{tweet_id}_{media_index}{animation_ext}"
                    animation_res = download_media_file(tweet_url, animation_url, os.path.join(media_directory, animation_filename))
                    if animation_res > 1:
                        media_count += 1
                    if animation_res > 0:
                        media_index += 1
                        break
    print(f"downloaded {media_count} new media files")

def download_media_file(tweet_url, media_url, filename):
    if os.path.isfile(filename):
        return 1
    media_r = requests.get(media_url, headers=MEDIA_HEADERS)
    if not media_r.ok:
        print(f"got bad response for media '{media_url}' from '{tweet_url}'")
        return 0
    with open(filename, "wb") as media_file:
        media_file.write(media_r.content)
        media_file.flush()
    return 2 if os.path.isfile(filename) else 0

async def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("mode", choices=OPERATIONS, help="operation to perform. 'save' downloads tweets to a file ('save-past' works in reverse), 'sort' re-orders tweets in a file, 'dedupe' removes entries with duplicate ids.")
    parser.add_argument("filename", help="file prefix to write tweets to (will be appended with .tweets.json)")
    parser.add_argument("handle", nargs="?", help="handle of the account to download from")
    parser.add_argument("-n", action="store_false", help="prompt for overwriting the existing tweet file")
    parser.add_argument("--download-media", "-m", action="store_true", help="iterate through scraped/sorted tweets and download all media")
    args = parser.parse_args()
    base_filepath = args.filename.replace(".tweets.json", "")
    tmp_filepath = base_filepath + ".tmp.tweets.json"
    filepath = base_filepath + ".tweets.json"
    if not os.path.isfile(filepath):
        filepath = os.path.join(os.getcwd(), filepath)
    if args.mode == OPERATIONS[0] or args.mode == OPERATIONS[1]:
        since = args.mode == OPERATIONS[0]
        script_path = os.path.dirname(os.path.realpath(__file__))
        api = API(AccountsPool(script_path + "/accounts.db"))
        account_handle = args.handle if args.handle else get_account_from_file(filepath)
        if not account_handle:
            print("could not get find handle in the provided file")
            sys.exit(1)
        print(f"getting tweets from account {account_handle}")
        saved_tweets = get_saved_tweets(filepath)
        last_saved_tweet_date, last_saved_tweet_id = get_last_tweet(saved_tweets, since)
        tweets_gathered = []
        if last_saved_tweet_date < 0:
            print("no previous tweets, creating new file")
            tweets_gathered = await gather_initial_tweets(api, account_handle)
        else:
            last_saved_datetime = datetime.datetime.fromtimestamp(last_saved_tweet_date)
            print(f"retrieving tweets {'since' if since else 'until'} {last_saved_datetime.isoformat()}")
            if since:
                tweets_gathered = await gather_tweets(api, account_handle, last_saved_tweet_date)
            else:
                tweets_gathered = await gather_tweets_backwards(api, account_handle, last_saved_tweet_date)
            tweets_gathered = list(filter(lambda t: datetime.datetime.fromisoformat(t["date"]).timestamp() != last_saved_tweet_date, tweets_gathered))
        if len(tweets_gathered) > 0:
            sorted_tweets_gathered = sort_tweets(tweets_gathered)
            last_retrieved_tweet_date = datetime.datetime.fromisoformat(sorted_tweets_gathered[-1]["date"]).timestamp()
            if last_saved_tweet_date > 0 and last_retrieved_tweet_date > last_saved_tweet_date:
                last_retrieved_datetime = datetime.datetime.fromtimestamp(last_retrieved_tweet_date)
                tweets_difference = last_retrieved_datetime - last_saved_datetime
                print(f"warning: oldest tweet retrieved is from {last_retrieved_datetime.isoformat()}, {tweets_difference.days} days difference")
            if args.download_media:
                get_tweet_media(base_filepath, sorted_tweets_gathered)
            sorted_tweets_gathered.extend(saved_tweets)
            tweets_filtered = dedupe_tweets(sorted_tweets_gathered)
            tweets_sorted = sort_tweets(tweets_filtered)
            print(f"scraped {len(tweets_sorted) - len(saved_tweets)} new tweets")
            write_tweets(tweets_sorted, tmp_filepath, filepath, args.n)
        else:
            print(f"no {'new' if since else 'prior'} tweets found")
    elif args.mode == OPERATIONS[2]:
        saved_tweets = get_saved_tweets(filepath)
        if len(saved_tweets) > 0:
            tweets_sorted = sort_tweets(saved_tweets)
            print(f"sorted tweets in {filepath}")
            write_tweets(tweets_sorted, tmp_filepath, filepath, args.n)
        if args.download_media:
            get_tweet_media(base_filepath, tweets_sorted)
    elif args.mode == OPERATIONS[3]:
        saved_tweets = get_saved_tweets(filepath)
        if len(saved_tweets) > 0:
            tweets_filtered = dedupe_tweets(saved_tweets)
            print(f"removed {len(saved_tweets) - len(tweets_filtered)} duplicates")
            write_tweets(tweets_filtered, tmp_filepath, filepath, args.n)
        if args.download_media:
            get_tweet_media(base_filepath, tweets_filtered)

if __name__ == "__main__":
    asyncio.run(main())
