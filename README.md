# crypto_whales

Hyperliquid (HYPE / HyperCore) の大口トレーダー（whale）の動向を調べる調査プロジェクト。

現状は**探索フェーズ**：どんなデータが取れるかを確認し、「whale をどう定義するか」「成績の悪い
口座を含めるか」などを実験しながら決める段階。出力形式（CLI / アラート / ダッシュボード）は未確定。

## 使い方

```bash
python3 explore.py    # 各データソースのサンプルを表示（市場OI・リーダーボード・whale1件の状態）
python3 whales.py     # ファイル冒頭のフィルタで whale を抽出し、ライブ建玉を表示
```

依存ライブラリなし（Python 3 標準ライブラリのみ）。Hyperliquid Info API は認証不要。

## whale の定義を実験する

`whales.py` 冒頭の定数を編集して再実行する：

| 定数 | 意味 |
|---|---|
| `MIN_ACCOUNT_VALUE` | whale とみなす口座総額の下限（USD） |
| `WINDOW` | 成績の集計窓 `day`/`week`/`month`/`allTime` |
| `INCLUDE_LOSERS` | `False` で当該窓のPnLが負の口座を除外 |
| `TOP_N` | ライブ照会する上位件数 |

## データの流れ

リーダーボードでアドレスを発見 → 各アドレスを `clearinghouse_state` / `user_fills` で照会。
詳細・既知の落とし穴は `CLAUDE.md` を参照。
