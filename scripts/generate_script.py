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

# 注意（内容の正確さ・読み上げの自然さ）
- 「からっ風(からっかぜ)」は【冬】に吹く冷たく乾いた強い季節風です。春・夏・秋など寒くない
  時期に「今まさにからっ風が吹いている」「今日もからっ風が」等、実際に吹いているかのような
  表現は絶対にしないでください（季節に合いません）。季節の話題では、その季節に合った風・気候
  （夏なら熱風・雷雨・猛暑など）を使ってください。
  ※パーソナリティ名「からっ風太郎」は季節に関係なくいつでも呼んでOKです。
- セリフは音声(VOICEVOX)で読み上げられます。イントネーションが自然になるよう、1文は短めにし、
  句読点(、。)を適切に打ってください。記号の乱用や英単語・アルファベットの多用は避けてください。
- 群馬・埼玉の地名など読み間違えられやすい固有名詞は、正しく読ませるためカタカナ表記にしても
  かまいません（セリフは音声のみで使われ、画面には表示されません）。
  例: 熊谷→クマガヤ、行田→ギョウダ、嵐山(埼玉)→ランザン。

# 本日のニュース候補
{news_block}

# 出力について
submit_script ツールを使って台本(セリフの配列)を提出してください。
オープニング挨拶→ニュース紹介・掛け合い→ローカルあるあるトーク→エンディングの流れで、
全体で40〜60セリフ程度、読み上げて3〜5分になる分量にしてください。
セリフ内で英数字の二重引用符(")は使わないでください。

episode_title には、今日扱うニュースや話題を踏まえた、Podcastアプリの一覧で
目を引くキャッチーなエピソードタイトルを1つ考えてください(12〜20文字程度)。
番組名(「{persona['station_name']}」)や日付は含めず、その日の内容が一目で
伝わる見出しにしてください。例:「からっ風とB級グルメ祭りの夜」

episode_summary には、その回の内容をリスナーに紹介する概要文を
約200字(180〜220字)で書いてください。番組名や日付は含めず、その日扱う
話題・ニュースの見どころと、2人の掛け合いの雰囲気が伝わるようにします。
番組全体の説明ではなく、フォロワーがこの1話を聴きたくなる「今日の回」の
紹介文です。セリフ内と同様、英数字の二重引用符(")は使わないでください。

readings には、台本(lines)に登場する語のうち、一般的な音声合成エンジンが読み間違え
そうなものを列挙してください。具体的には、地名・人名・企業名などの固有名詞、難読漢字、
複数の読み方がある語(例: 大人気=ダイニンキ、熊谷=クマガヤ)などです。各要素は
surface(台本に出てくる表記) と kana(正しい読み・全角カタカナ) のペアにします。
読み間違いの恐れがない平易な語は含めなくて構いません。台本に出てこない語も含めないこと。
"""


# Anthropicのtool useで構造化出力させることで、JSON解析エラーを避ける
SCRIPT_TOOL = {
    "name": "submit_script",
    "description": "ラジオ台本のセリフ配列とエピソードタイトルを提出する",
    "input_schema": {
        "type": "object",
        "properties": {
            "episode_title": {
                "type": "string",
                "description": "今日の放送内容を踏まえたキャッチーなエピソードタイトル(12〜20文字程度、番組名や日付は含めない)",
            },
            "episode_summary": {
                "type": "string",
                "description": "その回の内容を紹介する約200字(180〜220字)の概要文。番組名や日付は含めない。今日の話題の見どころと2人の掛け合いの雰囲気が伝わる、この1話を聴きたくなる紹介文にする。",
            },
            "readings": {
                "type": "array",
                "description": "台本に登場する読み間違えられやすい語(地名・人名・企業名などの固有名詞、難読漢字、多音語)の正しい読み一覧。平易な語は不要。",
                "items": {
                    "type": "object",
                    "properties": {
                        "surface": {"type": "string", "description": "台本に出てくる表記"},
                        "kana": {"type": "string", "description": "正しい読み(全角カタカナ)"},
                    },
                    "required": ["surface", "kana"],
                },
            },
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["speaker", "text"],
                },
            },
        },
        "required": ["episode_title", "episode_summary", "readings", "lines"],
    },
}

MAX_LINES = 120  # 暴走生成のセーフガード(想定は40〜60セリフ程度)


def _call_claude(prompt):
    client = Anthropic()  # ANTHROPIC_API_KEY を環境変数から読む
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        tools=[SCRIPT_TOOL],
        tool_choice={"type": "tool", "name": "submit_script"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "submit_script":
            return (
                block.input.get("episode_title", ""),
                block.input.get("episode_summary", ""),
                block.input.get("readings", []),
                block.input.get("lines", []),
            )
    raise RuntimeError("submit_script tool_use block not found in response")


def _valid_lines(lines):
    """{"speaker": str, "text": str} 形式以外の要素(モデルの暴走出力)を除外する"""
    valid = [
        line
        for line in lines
        if isinstance(line, dict)
        and isinstance(line.get("speaker"), str)
        and isinstance(line.get("text"), str)
        and line["speaker"]
        and line["text"]
    ]
    return valid[:MAX_LINES]


def generate_script(news_items, persona):
    prompt = build_prompt(news_items, persona)
    # モデルが極端に長い/壊れた出力を返すことが稀にあるため、
    # 有効なセリフ数が少なすぎる場合は1回だけ再試行する
    for attempt in range(2):
        episode_title, episode_summary, readings, lines = _call_claude(prompt)
        valid = _valid_lines(lines)
        if len(valid) >= 10:
            if not isinstance(episode_title, str) or not episode_title.strip():
                episode_title = ""  # publish.py側で日付ベースのタイトルにフォールバック
            if not isinstance(episode_summary, str):
                episode_summary = ""  # publish.py側でセリフ先頭のフォールバックに切替
            if not isinstance(readings, list):
                readings = []
            return episode_title.strip(), episode_summary.strip(), readings, valid
        print(
            f"[WARN] generated script looked malformed "
            f"(raw={len(lines)} valid={len(valid)}), retrying..."
        )
    raise RuntimeError("failed to generate a valid script after retry")


def main():
    config = load_config()
    news_items = fetch_news(config["sources"])
    episode_title, episode_summary, readings, lines = generate_script(news_items, config["persona"])

    OUT_DIR.mkdir(exist_ok=True)
    date_str = datetime.date.today().strftime("%Y%m%d")
    out_path = OUT_DIR / f"script_{date_str}.json"
    payload = {
        "date": date_str,
        "station_name": config["persona"]["station_name"],
        "episode_title": episode_title,
        "episode_summary": episode_summary,
        "readings": readings,
        "lines": lines,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[OK] script saved: {out_path} ({len(lines)} lines, title: {episode_title!r})")


if __name__ == "__main__":
    main()
