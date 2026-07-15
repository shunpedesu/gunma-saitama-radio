"""
TTS(VOICEVOX)音声合成スクリプト
out/script_YYYYMMDD.json を読み込み、話者ごとにVOICEVOX engineへ投げて
セリフごとのwavを生成し、1本のwavに連結する。

前提: VOICEVOX engineがHTTPで起動していること (デフォルト http://127.0.0.1:50021)
  docker run -p 50021:50021 voicevox/voicevox_engine:cpu-latest

使い方:
  python scripts/synthesize_audio.py
"""
import datetime
import json
import os
import wave
from pathlib import Path

import requests
import yaml

from voicevox_dict import register_words, register_pairs

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
OUT_DIR = ROOT / "out"
VOICEVOX_URL = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")


def load_speaker_map():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return {h["name"]: h["voicevox_speaker_id"] for h in config["persona"]["hosts"]}


def synth_line(text, speaker_id):
    query = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={"text": text, "speaker": speaker_id},
        timeout=30,
    )
    query.raise_for_status()
    synth = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={"speaker": speaker_id},
        json=query.json(),
        timeout=60,
    )
    synth.raise_for_status()
    return synth.content  # wav bytes


def concat_wavs(wav_bytes_list, out_path):
    """複数のwavバイト列を単純連結して1本のwavにする"""
    import io

    frames = []
    params = None
    for b in wav_bytes_list:
        with wave.open(io.BytesIO(b), "rb") as w:
            if params is None:
                params = w.getparams()
            frames.append(w.readframes(w.getnframes()))
    with wave.open(str(out_path), "wb") as out:
        out.setparams(params)
        for f in frames:
            out.writeframes(f)


def main():
    date_str = datetime.date.today().strftime("%Y%m%d")
    script_path = OUT_DIR / f"script_{date_str}.json"
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    speaker_map = load_speaker_map()

    # 漢字の読み間違い(地名など)を防ぐため、合成前にユーザー辞書を登録する。
    #  1. 固定辞書(voicevox_dict.WORDS): 群馬・埼玉の基礎地名など常に効かせたい語
    #  2. その回の readings: 台本生成AIが今日の台本から抽出した難読語(自動で増える)
    # 辞書登録に失敗しても合成自体は続行する。
    try:
        register_words(VOICEVOX_URL)
        register_pairs(VOICEVOX_URL, script.get("readings", []))
    except Exception as e:
        print(f"[WARN] user dict registration skipped: {e}")

    wav_chunks = []
    for i, line in enumerate(script["lines"]):
        if not isinstance(line, dict) or "speaker" not in line:
            print(f"[WARN] malformed line {i}, skipping: {line!r}")
            continue
        speaker_id = speaker_map.get(line["speaker"])
        if speaker_id is None:
            print(f"[WARN] unknown speaker '{line['speaker']}', skipping line {i}")
            continue
        wav_chunks.append(synth_line(line["text"], speaker_id))
        print(f"[OK] synthesized line {i+1}/{len(script['lines'])}")

    out_path = OUT_DIR / f"voice_{date_str}.wav"
    concat_wavs(wav_chunks, out_path)
    print(f"[OK] voice track saved: {out_path}")


if __name__ == "__main__":
    main()
