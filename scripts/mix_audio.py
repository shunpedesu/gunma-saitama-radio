"""
音声ミックススクリプト
voice_YYYYMMDD.wav に イントロ/アウトロジングルを ffmpeg で結合し、
最終的な mp3 (episode_YYYYMMDD.mp3) を出力する。

assets/ 以下に以下のファイルを用意しておくこと（好きな音源に差し替え可）:
  assets/intro.mp3   オープニングジングル
  assets/outro.mp3   エンディングジングル
  ※本編BGM(bgm.mp3)は「ツー」という一定の背景音(耳鳴りのよう)になり不評だったため
    2026-07-30に廃止。復活させる場合は本編にごく小さい音量でamixすること。

使い方:
  python scripts/mix_audio.py
"""
import datetime
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
ASSETS_DIR = ROOT / "assets"


def run(cmd):
    print("[cmd]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    # ファイル名キーは他スクリプトと揃える(EPISODE_ID優先、無ければ当日日付)
    key = os.environ.get("EPISODE_ID", "").strip() or datetime.date.today().strftime("%Y%m%d")
    voice_path = OUT_DIR / f"voice_{key}.wav"
    episode_path = OUT_DIR / f"episode_{key}.mp3"

    intro = ASSETS_DIR / "intro.mp3"
    outro = ASSETS_DIR / "outro.mp3"

    # 1. 本編音声を、intro/outro(44100Hz)と揃えて連結できるように44100Hz/モノへリサンプルする。
    #    ※BGMは入れない。常時流すと「ツー」という一定の背景音(耳鳴りのよう)になり不評だったため
    #      2026-07-30に廃止。BGMを復活させたい場合は volume を十分小さくして amix で重ねること。
    body = OUT_DIR / f"body_{key}.wav"
    run(
        [
            "ffmpeg", "-y",
            "-i", str(voice_path),
            "-ar", "44100", "-ac", "1",
            str(body),
        ]
    )

    # 2. イントロ + 本編 + アウトロ を結合してmp3化
    # 注意: concat demuxer(-f concat)はmp3とwavなど形式の異なるファイルを混在させると
    # デコードエラーで音声が欠落することがあるため、filter_complexのconcatフィルタで
    # 各入力を正しくデコードしてから結合する
    run(
        [
            "ffmpeg", "-y",
            "-i", str(intro),
            "-i", str(body),
            "-i", str(outro),
            "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
            "-map", "[out]",
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(episode_path),
        ]
    )

    print(f"[OK] episode saved: {episode_path}")


if __name__ == "__main__":
    main()
