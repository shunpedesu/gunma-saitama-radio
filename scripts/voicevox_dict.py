"""
VOICEVOX ユーザー辞書登録

漢字の読み間違い(特に群馬・埼玉の地名や誤読されやすい語)を防ぐため、
音声合成の前に VOICEVOX engine のユーザー辞書へ「表記→読み(カタカナ)」を登録する。
GitHub Actions では毎回まっさらな VOICEVOX コンテナが起動するため、実行ごとに登録する。

辞書の追加・修正はこの WORDS リストを編集するだけでよい。
  (surface=表記, pronunciation=全角カタカナの読み, accent_type=アクセント核のモーラ位置)
  ※accent_type は 0(平板型) にしておけば読みは必ず正しくなる。イントネーションを
    さらに詰めたい語だけ、アクセント核の位置(1始まり)を設定する。
"""
import requests

# (表記, 読み[全角カタカナ], アクセント型)
# アクセント型は迷ったら 0(平板) にしておく。まず「正しい読み」を最優先にしている。
WORDS = [
    # --- 誤読しやすい一般語(ユーザー報告分) ---
    ("大人気", "ダイニンキ", 0),   # 「おとなげ」と誤読される
    # --- 埼玉の地名 ---
    ("熊谷", "クマガヤ", 0),       # 「くまがい」と誤読される
    ("行田", "ギョウダ", 0),
    ("加須", "カゾ", 0),
    ("幸手", "サッテ", 0),
    ("蕨", "ワラビ", 0),
    ("越谷", "コシガヤ", 0),
    ("鴻巣", "コウノス", 0),
    ("桶川", "オケガワ", 0),
    ("上尾", "アゲオ", 0),
    ("蓮田", "ハスダ", 0),
    ("久喜", "クキ", 0),
    ("長瀞", "ナガトロ", 0),
    ("寄居", "ヨリイ", 0),
    ("越生", "オゴセ", 0),
    ("毛呂山", "モロヤマ", 0),
    ("嵐山町", "ランザンマチ", 0),  # 埼玉のらんざん(京都の嵐山あらしやまと区別)
    ("八潮", "ヤシオ", 0),
    ("三郷市", "ミサトシ", 0),
    ("羽生市", "ハニュウシ", 0),    # 「はぶ」等との区別のため市までで登録
    # --- 群馬の地名 ---
    ("邑楽", "オウラ", 0),
    ("甘楽", "カンラ", 0),
    ("嬬恋", "ツマゴイ", 0),
    ("下仁田", "シモニタ", 0),
    ("吾妻", "アガツマ", 0),
    ("東吾妻", "ヒガシアガツマ", 0),  # しゅんぺの拠点
    ("安中", "アンナカ", 0),
    ("榛名", "ハルナ", 0),
    ("妙義", "ミョウギ", 0),
    ("伊勢崎", "イセサキ", 0),
    ("桐生", "キリュウ", 0),
    ("中之条", "ナカノジョウ", 0),
    ("片品", "カタシナ", 0),
    ("神流", "カンナ", 0),
    ("四万温泉", "シマオンセン", 0),  # 「四万」単体(よんまん)と区別するため複合で登録
    ("上州", "ジョウシュウ", 0),
]


def register_words(base_url, words=WORDS, timeout=10):
    """VOICEVOX engine のユーザー辞書へ WORDS を登録する。
    1語ずつ失敗しても止めず、合成処理は続行できるようにする(辞書は補助であり必須ではない)。
    """
    ok = 0
    ng = 0
    for surface, pronunciation, accent_type in words:
        try:
            resp = requests.post(
                f"{base_url}/user_dict_word",
                params={
                    "surface": surface,
                    "pronunciation": pronunciation,
                    "accent_type": accent_type,
                    "priority": 8,  # 既定(5)より優先させる
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            ok += 1
        except Exception as e:  # 1語の失敗で全体を止めない
            ng += 1
            print(f"[WARN] user dict register failed: {surface}({pronunciation}): {e}")
    print(f"[OK] VOICEVOX user dict: {ok} registered / {ng} failed (total {len(words)})")
    return ok, ng


if __name__ == "__main__":
    import os

    register_words(os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021"))
