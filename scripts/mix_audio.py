"""
音声ミックススクリプト
voice_YYYYMMDD.wav に イントロ/アウトロジングル・BGMを ffmpeg で合成し、
最終的な mp3 (episode_YYYYMMDD.mp3) を出力する。

assets/ 以下に以下のファイルを用意しておくこと（好きな音源に差し替え可）:
  assets/intro.mp3   オープニングジングル
  assets/outro.mp3   エンディングジングル
  assets/bgm.mp3      本編中に薄く流すBGM(ループ・音量小さめ推奨)

使い方:
  python scripts/mix_audio.py
"""
import datetime
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
ASSETS_DIR = ROOT / "assets"


def run(cmd):
    print("[cmd]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    date_str = datetime.date.today().strftime("%Y%m%d")
    voice_path = OUT_DIR / f"voice_{date_str}.wav"
    episode_path = OUT_DIR / f"episode_{date_str}.mp3"

    intro = ASSETS_DIR / "intro.mp3"
    outro = ASSETS_DIR / "outro.mp3"
    bgm = ASSETS_DIR / "bgm.mp3"

    # 1. 本編音声にBGMを薄く重ねる(BGMをloopしてvoiceの長さに合わせ、音量を下げてミックス)
    body_with_bgm = OUT_DIR / f"body_bgm_{date_str}.wav"
    run(
        [
            "ffmpeg", "-y",
            "-i", str(voice_path),
            "-stream_loop", "-1", "-i", str(bgm),
            "-filter_complex",
            "[1:a]volume=0.12[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[out]",
            "-map", "[out]",
            str(body_with_bgm),
        ]
    )

    # 2. イントロ + 本編(BGM入り) + アウトロ を結合してmp3化
    concat_list = OUT_DIR / f"concat_{date_str}.txt"
    with open(concat_list, "w") as f:
        f.write(f"file '{intro.resolve()}'\n")
        f.write(f"file '{body_with_bgm.resolve()}'\n")
        f.write(f"file '{outro.resolve()}'\n")

    run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(episode_path),
        ]
    )

    print(f"[OK] episode saved: {episode_path}")


if __name__ == "__main__":
    main()
