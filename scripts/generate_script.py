"""
台本生成スクリプト
1. config/sources.yaml のRSSからその日のローカルニュースを取得
2. Claude APIに投げて、群馬・埼玉のローカルラジオ台本を生成
3. out/script_YYYYMMDD.json に {"title":..., "lines":[{"speaker":..., "text":...}, ...]} を保存

必要な環境変数:
  ANTHROPIC_API_KEY

使い方:
  python scripts/generate_script.py
"""
import datetime
import json
import os
import sys
from pathlib import Path

import feedparser
import yaml
from anthropic import Anthropic

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
OUT_DIR = ROOT / "out"
MAX_ITEMS_PER_SOURCE = 5


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_news(sources):
    """各RSSソースから直近ニュースを取得。取得失敗しても処理は止めない。"""
    items = []
    for src in sources:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:
                items.append(
                    {
                        "prefecture": src["prefecture"],
                        "source": src["name"],
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", ""),
                        "link": entry.get("link", ""),
                    }
                )
        except Exception as e:  # フィード取得失敗はスキップしてログだけ残す
            print(f"[WARN] failed to fetch {src['url']}: {e}", file=sys.stderr)
    return items


def build_prompt(news_items, persona):
    today = datetime.date.today().strftime("%Y年%m月%d日")
    hosts = persona["hosts"]
    news_block = "\n".join(
        f"- [{i['prefecture']}] {i['title']} ({i['source']})" for i in news_items
    ) or "- (本日は目立ったニュースが取得できませんでした。フリートークで繋いでください)"

    return f"""あなたはローカルラジオ番組「{persona['station_name']}」の放送作家です。
{today}放送分の台本を作ってください。

# 出演者
{hosts[0]['name']}: {hosts[0]['role']}
{hosts[1]['name']}: {hosts[1]['role']}

# トーン
{persona['tone']}

# 本日のニュース候補
{news_block}

# 出力形式
以下のJSON配列「のみ」を出力してください（説明文や```は不要）。
[
  {{"speaker": "{hosts[0]['name']}", "text": "セリフ"}},
  {{"speaker": "{hosts[1]['name']}", "text": "セリフ"}}
]
オープニング挨拶→ニュース紹介・掛け合い→ローカルあるあるトーク→エンディングの流れで、
全体で40〜60セリフ程度、読み上げて3〜5分になる分量にしてください。
"""


def generate_script(news_items, persona):
    client = Anthropic()  # ANTHROPIC_API_KEY を環境変数から読む
    prompt = build_prompt(news_items, persona)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    # ```json ... ``` で囲まれて返ってきた場合の保険
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("json"):
            text = text[: -4]
    lines = json.loads(text)
    return lines


def main():
    config = load_config()
    news_items = fetch_news(config["sources"])
    lines = generate_script(news_items, config["persona"])

    OUT_DIR.mkdir(exist_ok=True)
    date_str = datetime.date.today().strftime("%Y%m%d")
    out_path = OUT_DIR / f"script_{date_str}.json"
    payload = {
        "date": date_str,
        "station_name": config["persona"]["station_name"],
        "lines": lines,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[OK] script saved: {out_path} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
