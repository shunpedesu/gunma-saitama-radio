# ラジオ・グンマサイタマ 自動配信パイプライン

群馬・埼玉のローカルニュースを台本化 → VOICEVOXで音声合成 → ffmpegでミックス →
Vercel Blobにアップロード → podcast RSSを更新、までを毎日自動実行し、
Spotify for Podcastersに登録したRSS経由で自動的に新エピソードを配信する。

## 全体フロー

```
GitHub Actions (毎日 JST 7:00, cron)
  1. generate_script.py  … 県庁RSSを取得しClaude APIで台本生成
  2. synthesize_audio.py … VOICEVOX(Actions内でDocker起動)でセリフを音声化
  3. mix_audio.py         … ffmpegでイントロ/アウトロ/BGMを合成
  4. publish.py           … Vercel Blobへmp3アップロード + feed.xmlを更新してBlobへ反映
  → Spotifyが数十分〜数時間以内にfeed.xmlの更新を検知し自動配信
```

## 手動 / 自動の切り分け

### 手動(最初に1回だけ)
- Anthropic APIキー取得
- Vercelプロジェクト作成 → Storage タブから Blob store を作成し、
  `BLOB_READ_WRITE_TOKEN` を発行
- `config/sources.yaml` の話者ID・番組トーンを調整
- `assets/intro.mp3` `assets/outro.mp3` `assets/bgm.mp3` を用意して配置
- このリポジトリをGitHubへpushし、Secretsを登録
  (`ANTHROPIC_API_KEY`, `BLOB_READ_WRITE_TOKEN`)
- 初回パイプライン実行後にログへ出力される `feed_url` を確認し、
  Spotify for Podcastersでアカウント作成 →「すでに配信先がある」を選んでそのURLを登録

ここまでで数時間程度(Vercel/Spotifyの審査待ちを除く実作業は1〜2時間目安)。

### 自動(毎日・GitHub Actionsが実行)
- ニュース取得、台本生成、音声合成、ミックス、アップロード、RSS更新の全工程
- 何もしなくても毎朝新しいエピソードが公開される

## 一日あたりの運用時間

- 通常運転時: **0分**。Actionsが自動で回る
- 品質チェックしたい場合: 配信後に音声を1回聞く運用にするなら、週1〜2回・数分のスポットチェックで十分
  (毎日チェックする場合でも1本3〜5分の尺なので確認は3〜5分程度)
- 台本のネタや口調を変えたくなった時だけ `config/sources.yaml` を編集(数分)

つまり「セットアップに数時間、以降は運用ゼロ〜週数分」が目安。

## セットアップ手順

1. `git clone` してこのフォルダをpush
2. `pip install -r requirements.txt` でローカル動作確認も可能(VOICEVOXはDocker起動が必要)
   ```
   docker run -d -p 50021:50021 voicevox/voicevox_engine:cpu-latest
   python scripts/run_pipeline.py
   ```
3. GitHub Secretsを設定(`ANTHROPIC_API_KEY`, `BLOB_READ_WRITE_TOKEN`)
4. `assets/` にジングル・BGM音源を配置
5. 初回は `workflow_dispatch` で手動実行して動作確認し、ログの `feed_url` を確認
6. Spotify for PodcastersにそのRSS URLを登録
7. 以降は毎日 JST 7:00 に自動公開

## ディレクトリ構成

```
config/sources.yaml       ニュースソース・番組設定
scripts/generate_script.py
scripts/synthesize_audio.py
scripts/mix_audio.py
scripts/publish.py
scripts/run_pipeline.py   上記4本をまとめて実行
assets/                   ジングル・BGM (要用意)
feed/feed.xml             生成される podcast RSS (自動更新)
.github/workflows/daily_radio.yml
```

## 既知の注意点

- `config/sources.yaml` のRSS URLはプレースホルダ。各県サイトの実際のRSS配信ページで
  最新のURLを確認して差し替えること
- VOICEVOXの話者IDはキャラごとに異なるため、`/speakers` APIで確認して
  `config/sources.yaml` の `voicevox_speaker_id` を設定すること
- VOICEVOX音声を使う場合、配信のクレジット表記(例: 「VOICEVOX:ずんだもん」)を
  番組概要やSNS投稿に入れること(キャラ別ライセンス)
- Vercel Blobの無料枠(Hobbyプラン)はストレージ1GB・転送10GB/月。3〜5分のmp3は
  1本あたり3〜5MB程度のため、毎日蓄積すると半年〜1年ほどでストレージ上限に近づく。
  古いエピソードの削除、またはPro/従量課金プランへの切り替えを検討すること
- Vercel Blobは各アップロードごとにURLが決まる仕様(feed.xmlのみ`x-add-random-suffix: 0`で
  固定URLに上書き)。REST APIの仕様が変わっていた場合は
  https://vercel.com/docs/vercel-blob を確認して `scripts/publish.py` を調整すること
