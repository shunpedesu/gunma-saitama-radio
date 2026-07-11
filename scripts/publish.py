"""
配信スクリプト
1. out/episode_YYYYMMDD.mp3 を Vercel Blob にアップロード(REST API, SDK不要)
2. feed/feed.xml (podcast RSS) に新しい<item>を追加して更新・アップロード

Spotifyへは一度だけ Spotify for Podcasters でこのRSSのURLを登録しておけば、
以降はこのスクリプトがfeed.xmlを更新するたびに自動で新エピソードが反映される。

必要な環境変数:
  BLOB_READ_WRITE_TOKEN   Vercelプロジェクトの Storage > Blob で発行するトークン
  PODCAST_TITLE, PODCAST_DESCRIPTION, PODCAST_AUTHOR (任意、未設定ならデフォルト値)

注意:
  Vercel BlobのアップロードURLは各blobごとに一意のURL(ランダムsuffix付き)が
  返ってくる仕様のため、feed.xmlの<enclosure>にはアップロードAPIのレスポンスに
  含まれる実際のurlをそのまま使う。
  (Vercel Blob REST APIの仕様は変更される可能性があるため、初回実行時にエラーが出たら
   https://vercel.com/docs/vercel-blob の最新のREST API仕様を確認して調整すること)

使い方:
  python scripts/publish.py
"""
import datetime
import json
import os
from pathlib import Path
from email.utils import format_datetime
from xml.etree import ElementTree as ET
from xml.dom import minidom

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
FEED_DIR = ROOT / "feed"
FEED_PATH = FEED_DIR / "feed.xml"

BLOB_API_BASE = "https://blob.vercel-storage.com"
BLOB_TOKEN = os.environ["BLOB_READ_WRITE_TOKEN"]

PODCAST_TITLE = os.environ.get("PODCAST_TITLE", "ラジオ・グンマサイタマ")
PODCAST_DESCRIPTION = os.environ.get(
    "PODCAST_DESCRIPTION", "群馬・埼玉のローカルネタを毎日お届けするAIラジオ番組"
)
PODCAST_AUTHOR = os.environ.get("PODCAST_AUTHOR", "チームグンマサイタマゲーム")


def upload_to_blob(pathname, file_path, content_type):
    """Vercel Blob REST APIでファイルをアップロードし、公開URLを返す"""
    with open(file_path, "rb") as f:
        data = f.read()
    resp = requests.put(
        f"{BLOB_API_BASE}/{pathname}",
        headers={
            "Authorization": f"Bearer {BLOB_TOKEN}",
            "x-api-version": "7",
            "x-content-type": content_type,
            # 同じファイル名で毎日上書きしたい場合はaddRandomSuffixをfalseにする
            "x-add-random-suffix": "0",
        },
        data=data,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["url"]


def upload_episode(date_str, episode_path):
    pathname = f"episodes/episode_{date_str}.mp3"
    return upload_to_blob(pathname, episode_path, "audio/mpeg")


def load_or_create_feed(channel_link):
    if FEED_PATH.exists():
        tree = ET.parse(FEED_PATH)
        return tree
    NSMAP = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
    ET.register_namespace("itunes", NSMAP["itunes"])
    rss = ET.Element("rss", {"version": "2.0", "xmlns:itunes": NSMAP["itunes"]})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = PODCAST_TITLE
    ET.SubElement(channel, "description").text = PODCAST_DESCRIPTION
    ET.SubElement(channel, "language").text = "ja"
    ET.SubElement(channel, "itunes:author").text = PODCAST_AUTHOR
    ET.SubElement(channel, "link").text = channel_link
    return ET.ElementTree(rss)


def add_episode_item(tree, date_str, title, audio_url, file_size, script_summary):
    channel = tree.getroot().find("channel")
    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "description").text = script_summary
    ET.SubElement(item, "pubDate").text = format_datetime(
        datetime.datetime.now(datetime.timezone.utc)
    )
    # guidはVercel Blobが返す実際のURL(内容が変わらない限り不変のキーとして使う)
    ET.SubElement(item, "guid").text = audio_url
    ET.SubElement(
        item,
        "enclosure",
        {"url": audio_url, "length": str(file_size), "type": "audio/mpeg"},
    )
    # 既存itemの先頭(直後)に挿入して新着順を維持
    channel.insert(list(channel).index(channel.find("link")) + 1, item)


def prettify(tree):
    rough = ET.tostring(tree.getroot(), encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ")


def main():
    date_str = datetime.date.today().strftime("%Y%m%d")
    episode_path = OUT_DIR / f"episode_{date_str}.mp3"
    script_path = OUT_DIR / f"script_{date_str}.json"

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    title = f"{script['station_name']} {date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
    summary = " / ".join(line["text"] for line in script["lines"][:2])

    audio_url = upload_episode(date_str, episode_path)
    file_size = episode_path.stat().st_size

    FEED_DIR.mkdir(exist_ok=True)
    # feed.xmlの<link>はブランドの入口として使うだけなので、audio_urlのドメインを仮利用
    tree = load_or_create_feed(channel_link=audio_url.rsplit("/", 1)[0])
    add_episode_item(tree, date_str, title, audio_url, file_size, summary)

    with open(FEED_PATH, "w", encoding="utf-8") as f:
        f.write(prettify(tree))

    # feed.xml自体もVercel Blobにアップロードして公開
    # x-add-random-suffix=0 により毎回同じURL(feed.xml)を上書きできる
    feed_url = upload_to_blob("feed.xml", FEED_PATH, "application/rss+xml")

    print(f"[OK] published: {audio_url}")
    print(f"[OK] feed updated: {feed_url}")
    print("[NOTE] 初回公開時はこのfeed_urlをSpotify for Podcastersに登録してください")


if __name__ == "__main__":
    main()
