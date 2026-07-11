"""
パイプライン一括実行スクリプト。
GitHub Actionsからはこれ1本を呼ぶだけでよい。
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
STEPS = [
    "generate_script.py",
    "synthesize_audio.py",
    "mix_audio.py",
    "publish.py",
]


def main():
    for step in STEPS:
        print(f"\n===== RUN {step} =====")
        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / step)])
        if result.returncode != 0:
            print(f"[FAIL] {step} exited with {result.returncode}")
            sys.exit(result.returncode)
    print("\n===== ALL DONE =====")


if __name__ == "__main__":
    main()
