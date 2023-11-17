#!/usr/bin/env python3
import argparse
import asyncio
from collections import OrderedDict
from contextlib import aclosing
import datetime
import json
import os
import sys
from time import sleep
from twscrape import API, AccountsPool, gather
from twscrape.logger import set_log_level

OPERATIONS = ["save", "sort", "dedupe"]
KEY_ORDER_TWEET = ["_type", "url", "date", "rawContent", "renderedContent", "id", "user", "replyCount", "retweetCount", "likeCount", "quoteCount", "conversationId", "lang", "source", "sourceUrl", "sourceLabel", "links", "media", "retweetedTweet", "quotedTweet", "inReplyToTweetId", "inReplyToUser", "mentionedUsers", "coordinates", "place", "hashtags", "cashtags", "card", "viewCount", "vibe", "content", "outlinks", "outlinksss", "tcooutlinks", "tcooutlinksss", "username"]
KEY_ORDER_USER = ["_type", "username", "id", "displayname", "rawDescription", "renderedDescription", "descriptionLinks", "verified", "created", "followersCount", "friendsCount", "statusesCount", "favouritesCount", "listedCount", "mediaCount", "location", "protected", "link", "profileImageUrl", "profileBannerUrl", "label", "description", "descriptionUrls", "linkTcourl", "linkUrl", "url"]

def datetime_handler(x):
    if isinstance(x, datetime.datetime):
        return x.isoformat()
    raise TypeError("Unknown type")

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

def get_last_tweet(tweets):
    last_tweet_date = -1
    last_tweet_id = None
    for tweet in tweets:
        current_tweet_date = datetime.datetime.fromisoformat(tweet["date"]).timestamp()
        if current_tweet_date > last_tweet_date:
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
    last_datetime = datetime.datetime.fromtimestamp(last_timestamp) - datetime.timedelta(days=1)
    last_datetime_string = last_datetime.isoformat().replace("T", "_") + "_UTC"
    query_string = f"from:{account_handle} since:{last_datetime_string}"
    print(f"query: '{query_string}'")
    user_tweets = await gather(api.search(query_string))
    for tweet in user_tweets:
        if tweet.user.username == account_handle:
            tweets.append(json.loads(json.dumps(tweet.dict(), default=datetime_handler)))
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

async def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("mode", choices=OPERATIONS, help="operation to perform. 'save' downloads tweets to a file, 'sort' re-orders tweets in a file, 'dedupe' removes entries with duplicate ids.")
    parser.add_argument("filename", help="file prefix to write tweets to (will be appended with .tweets.json)")
    parser.add_argument("handle", nargs="?", help="handle of the account to download from")
    parser.add_argument("-n", action="store_false", help="prompt for overwriting the existing tweet file")
    args = parser.parse_args()
    base_filepath = args.filename.replace(".tweets.json", "")
    tmp_filepath = base_filepath + ".tmp.tweets.json"
    filepath = base_filepath + ".tweets.json"
    if not os.path.isfile(filepath):
        filepath = os.path.join(os.getcwd(), filepath)
    if args.mode == OPERATIONS[0]:
        script_path = os.path.dirname(os.path.realpath(__file__))
        api = API(AccountsPool(script_path + "/accounts.db"))
        account_handle = args.handle if args.handle else get_account_from_file(filepath)
        if not account_handle:
            print("could not get find handle in the provided file")
            sys.exit(1)
        print(f"getting tweets from account {account_handle}")
        saved_tweets = get_saved_tweets(filepath)
        last_saved_tweet_date, last_saved_tweet_id = get_last_tweet(saved_tweets)
        last_saved_datetime = datetime.datetime.fromtimestamp(last_saved_tweet_date)
        tweets_gathered = []
        if last_saved_tweet_date < 0:
            print("no previous tweets, creating new file")
            tweets_gathered = await gather_initial_tweets(api, account_handle)
        else:
            print(f"retrieving tweets since {last_saved_datetime.isoformat()}")
            tweets_gathered = await gather_tweets(api, account_handle, last_saved_tweet_date)
            tweets_gathered = list(filter(lambda t: datetime.datetime.fromisoformat(t["date"]).timestamp() != last_saved_tweet_date, tweets_gathered))
        if len(tweets_gathered) > 0:
            sorted_tweets_gathered = sort_tweets(tweets_gathered)
            last_retrieved_tweet_date = datetime.datetime.fromisoformat(sorted_tweets_gathered[-1]["date"]).timestamp()
            if last_saved_tweet_date > 0 and last_retrieved_tweet_date > last_saved_tweet_date:
                last_retrieved_datetime = datetime.datetime.fromtimestamp(last_retrieved_tweet_date)
                tweets_difference = last_retrieved_datetime - last_saved_datetime
                print(f"warning: oldest tweet retrieved is from {last_retrieved_datetime.isoformat()}, {tweets_difference.days} days difference")
            sorted_tweets_gathered.extend(saved_tweets)
            tweets_filtered = dedupe_tweets(sorted_tweets_gathered)
            tweets_sorted = sort_tweets(tweets_filtered)
            print(f"scraped {len(tweets_sorted) - len(saved_tweets)} new tweets")
            write_tweets(tweets_sorted, tmp_filepath, filepath, args.n)
        else:
            print("no new tweets found")
    elif args.mode == OPERATIONS[1]:
        saved_tweets = get_saved_tweets(filepath)
        if len(saved_tweets) > 0:
            tweets_sorted = sort_tweets(saved_tweets)
            print(f"sorted tweets in {filepath}")
            write_tweets(tweets_sorted, tmp_filepath, filepath, args.n)
    elif args.mode == OPERATIONS[2]:
        saved_tweets = get_saved_tweets(filepath)
        if len(saved_tweets) > 0:
            tweets_filtered = dedupe_tweets(saved_tweets)
            print(f"removed {len(saved_tweets) - len(tweets_filtered)} duplicates")
            write_tweets(tweets_filtered, tmp_filepath, filepath, args.n)

if __name__ == "__main__":
    asyncio.run(main())
