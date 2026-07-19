# HANDOFF.md — 詳細引き継ぎ書

どのモデル・どのセッションで作業しても同じ品質・同じ判断になるように、暗黙知を全部書き出したもの。
`CLAUDE.md` は要点（英語）、本書は詳細（日本語）。**分析の実行・findings の更新・レポート作成の前に、該当セクションを必ず読むこと。**
（最終更新: 2026-07-19。スナップショット数値は更新時点のもの）

---

## 1. プロジェクトの定義と現在地

**何か**: 2つのデータ領域を並行して調べる**リサーチプロジェクト**（2026-06-27 開始）。

1. **Hyperliquid (HyperCore perp DEX)**: 「本当に上手いトレーダー」を口座規模に関係なく発見し、
   **その手法（HOW）を分析する**。明示的に**コピートレードではない**（手法研究）。
2. **Bitcoin ベースチェーン**: 取引所など既知エンティティの大口オンチェーン資金移動の監視
   （2026-07-01 追加の第2ドメイン）。

**方向転換（2026-07-02、ユーザー決定）**: 当初の「whale（大口）ウォッチ」から
「**スキルで定義**したトレーダーの手法分析」へピボット。同日に **BTC 限定**に絞った
（`skilled.py` の `COINS = {"BTC"}`）。根拠となった発見の連鎖:
- ポジションサイズは勝敗と無相関（大玉ほど含み損ナンピンに偏る）
- fills 由来のスキル指標は持続する（split-half Spearman +0.54..0.62）が、
  リーダーボード損益はプロキシとして弱い（+0.22）
- 集団の売買方向には 1〜24h 先の予測力なし（`notes/track_findings.md`）

**現在地（2026-07-07 時点）**:
- 主要な分析は一巡し**結論が出ている**（§8）。直近成果物は
  `調査まとめ_2026-07-05.docx`（日本語 Word レポート、`make_report.py` で生成。
  **git 未追跡**・v3 相当が snitker NAS にコピー済み・v4 が未作成 → §11）。
- 2本の毎時 cron が時系列を蓄積中（§9）。30日分たまった時点の再検証が予定されている。
- 出力形式（CLI / アラート / ダッシュボード）は**意図的に未決**。30日再検証後に決める方針。
- ローカル main は **origin より 12 コミット先行（未 push）**（2026-07-07 時点、§10）。

**実行環境**: このマシン（elwhite = localhost, 192.168.101.201）が本番。cron もここで動く。
ドキュメントの「ssh elwhite」はここではローカル実行の意味。

---

## 2. ユーザー方針（全作業の前提。違反すると信頼を失う）

1. **無料サービスのみ**（「有料は使わないよ」2026-07-01）。$0 の無料ティアは signup 必要でも可
   （例: Arkham free tier）。課金が発生するものは一切不可。有料でしかできないことは
   「無料ではここまで」と明言し、無料キーが入れば即動く形で実装まで用意して止める。
2. **サンプルサイズ最大化**（2026-07-05「母集団は増やせるだけ増やした方が良い」）。
   統計的主張をする前に、無料 API の許す上限までデータを広げる: ファンネルを広げ
   （trips.py の `FUNNEL` が skilled.py の knob を上書き）、全約定履歴をページング取得
   （`deep_fills`、`userFillsByTime` を t=0 から 2000件/回）。速度よりデータ量。
   統計的検出力はどちらにせよ正直に報告する。
3. **結論先行・前置きなし**（2026-07-06）。事実質問には第一文で答えを言う。多くの場合それが
   回答の全部。「整理すると」「〜ですね」・質問の言い換え・頼まれていない表は不要。
   注意書きは省くと誤解を招く場合のみ1行。依頼された成果物（レポート・分析）は構造化してよい。
4. **ビット由来の量は 2^n を主表記**（鍵空間・ハッシュ・エントロピー等）。10進換算は補足のみ。
5. **レビュー依頼の定型**（「リビューして、改善できるところがあればなおして」）:
   実害のあるバグのみ最小差分で修正（リファクタ・スタイル変更・機能追加はしない）→
   py_compile + 安全なスモークテストで検証 → `notes/review_YYYY-MM-DD.md` に
   Before/Now/理由を記録 → コミット（開始時にツリーが clean だった場合のみ）。
   「問題ゼロ」も正当な結論。push はユーザーが言ったときだけ。作業前に `git fetch`。
6. **統計は誠実に**。プール集計の錯覚（Simpson のパラドックス）を避けトレーダー層別で検定する、
   ベースレートを並記する、生存バイアス・多重比較・非独立性の caveat を明記する — が
   このプロジェクトの確立された流儀（`trips_stats.py` / notes の Addendum が見本）。

---

## 3. 依頼のパターンと期待される動き

- **「◯◯を調べて/分析して」**: 実験スクリプトを書き足す文化。完成品ではなく
  knob（モジュール冒頭の定数）を編集して再実行するスタイルを踏襲する。新しい
  Hyperliquid エンドポイントは `hl/client.py` にメソッドとして追加（inline 禁止）。
  発見は `notes/*_findings.md` に日付つきで記録し、過去の読みは消さず Addendum を積む
  （`trips_findings.md` が見本: 初回の読み→統計処理→母集団拡張→対照群、と履歴が残る）。
- **「レポートにまとめて」**: `make_report.py`（python-docx）を編集して Word を再生成。
  python-docx は**システムに未導入** — venv を作って入れる（`.venv/` は gitignore 済み）。
  NAS へのコピーは snitker `document` 共有（gio mount → gio copy、~/.claude/CLAUDE.md 参照）。
  **旧版が Word で開かれたままロックされている可能性があるので、新ファイル名（v4 等）で置く。
  上書きしない。**
- **30日再検証（予定タスク）**: §11 の日付で `--analyze` を回して notes に追記。
- **コミットメッセージ**: 英語・内容要約型（`git log` の既存例に倣う。
  例: `trips.py: maximize the population — 3x funnel + full fill-history paging`）。
  Co-Authored-By trailer をつける。

---

## 4. ファイル別の役割

### Hyperliquid 系（第1ドメイン）

| ファイル | 役割 |
|---|---|
| `hl/client.py` | **HyperliquidInfo** — HL info API を叩く唯一の場所。429 指数バックオフ、leaderboard は検証つきアトミックキャッシュ（§6.1） |
| `explore.py` | 各データソースのサンプラー。自由に書き換えてよい scratch |
| `whales.py` | 旧・whale 定義実験（accountValue 基準）。ピボット前の遺物だが残置 |
| `whales_coin.py` | コイン別 notional で whale 抽出（BTC+ETH、top1500 スキャン ~21s）。`scan_whales`/`skill_weighted_sentiment` は whales_track が再利用 |
| `whales_skill.py` | fills からの実測スキル指標（WR/PF/net/maxDD）+ `--persistence` split-half 検定。`fetch_fills`（1h ディスクキャッシュ）と `collect` は skilled/trips が再利用 |
| `whales_track.py` | **毎時 cron（:05）** — skilled-whale の BTC/ETH ポジショニングスナップショット → `data/whale_track.jsonl`。`--analyze --horizon 1,4,24` で forward return 検定 |
| `skilled.py` | **ピボット後の中核** — サイズ非依存のスキルトレーダー発見（3ルートファンネル→fills検証→スタイル指紋→archetype）。`--addr 0x…` で個別深掘り。`COINS={"BTC"}` |
| `trips.py` | skilled の次段 — 方向性トレーダーの flat→flat トリップ抽出 + セットアップ分析（時間帯・順張り/逆張り・積み増し・損切り速度）→ `data/trips_btc.jsonl`。`--losers` で対照群（→ `trips_btc_losers.jsonl`）、`--addr` で個別一覧。`FUNNEL` で skilled の knob を 3x に上書き、`deep_fills` で全履歴ページング |
| `trips_stats.py` | トリップ主張の統計検定（Mann-Whitney U・符号検定・Stouffer・クラスタブートストラップ・**トレーダー層別 CMH**）。データパスがハードコードなので注意 |
| `trips_compare.py` | 勝ち組 vs 負け組の特徴量比較（トレーダー単位 MWU） |
| `forward.py` | **フォワード検証** — 07-02 検証済みコホート（transcript から復元した40人、`data/seed_2026-07-02.json`）の cutoff 以降 OOS 成績 + 今日のファンネルとの生存重複。OOS fills は `data/fills_fwd/` にキャッシュ（キャッシュはスーパーセット可・読み出し時に時刻フィルタ） |
| `make_report.py` | Word レポート生成（`調査まとめ_2026-07-05.docx`）。**要 python-docx（venv）** |

### BTC オンチェーン系（第2ドメイン）

| ファイル | 役割 |
|---|---|
| `btc/client.py` | **Esplora** — mempool.space の公開 API（認証不要・**値は satoshi**）。`address_txs_paged` で履歴を遡る |
| `btc/watchlist.py` | 人手キュレーションのエンティティ→アドレス層。**11エンティティ / 30アドレス / 約759k BTC、全て残高実測検証済み**。追加時も必ず残高をライブ検証してから（seed policy がファイル冒頭に明文化） |
| `btc/labels_import.py` | GraphSense tagpacks（無料・キー不要）→ `data/btc_labels.json`（~336k BTC ラベル）。`python3 -m btc.labels_import` で更新 |
| `btc/expand.py` | ラベル済み未監視アドレスのプロファイル（1アドレス1コール、`data/btc_profile.json` にキャッシュ）→ watchlist 貼り付け用エントリを出力 |
| `btc/arkham.py` + `arkham_flows.py` | **ラベル付き API 経路**（`ARKHAM_API_KEY` 環境変数、無料ティア）。Coinbase/BlackRock/MSTR 等、無料データで帰属不能なエンティティ用。**キー未取得・ライブ未検証** |
| `btc_flows.py` | 監視エンティティの大口 IN/OUT 検出 + カウンターパーティのラベル付け。`--balances` / `--hours N` / `--min BTC` / `--netflow` |
| `btc_track.py` | **毎時 cron（:35）** — エンティティ別残高 + 前回スナップショット以降の IN/OUT/NET → `data/btc_track.jsonl`（BTC 価格同梱で自己完結）。`--analyze` でホットウォレット純流出 → forward BTC return 検定 |

### notes/（発見の記録。追記型・過去の読みは残す）

| ファイル | 内容 |
|---|---|
| `skill_findings.md` | スキル持続の split-half 検定結果 + caveats（勝率インフレ等） |
| `skilled_findings.md` | スキルトレーダーの類型（メーカー vs 方向性）+ BTC 限定の Addendum |
| `trips_findings.md` | **最重要** — トリップ分析。⚠️ 本文 Finding 1–4 は初回（17人/574）の古い数値のまま。**現在の真実は Addendum 2（50人/4,564）と Addendum 3（対照群）** |
| `track_findings.md` | 集団方向シグナルの検定履歴（追記型・no edge） |
| `btc_onchain.md` | BTC ドメインの全ノウハウ（芋づる式トレース法・帰属ソース調査・拡張記録） |
| `reference_repos.md` | 類似4リポジトリの調査（借りた手法と避けた欠陥 — 特に zero-lag 相関の罠） |
| `whales_watchlist.md` | 2026-06-27 の BTC/ETH whale アドレス集（ポジションは陳腐化、アドレスが恒久部分） |
| `review_2026-07-02.md` | コードレビュー記録（5修正の Before/Now） |
| `forward_findings.md` | **フォワード検証（07-19 初回読み）** — in-sample 持続性は前向きに再現せず（38% プラス vs 期待85%、p≈1.5e-7 で棄却、in-sample PF の予測力 ρ=−0.20）。40アドレスの恒久記録つき |

### data/（**全て gitignore**。ローカル蓄積のみ）

| ファイル/dir | 形式・注意 |
|---|---|
| `leaderboard.json` | ~33MB キャッシュ（1h で再取得。`max_age_sec=0` で強制更新） |
| `whale_track.jsonl` | 1行=1スナップショット `{time_ms, n_whales, n_skilled, n_failed, prices, skill_bias, ntl_bias}`。**243行**（2026-06-27〜） |
| `btc_track.jsonl` | 1行=1スナップショット `{time_ms, since_ms, btc_px, n_failed, entities{...}}`。**48行**。⚠️ watchlist がスナップショット#2 で拡大したため**シリーズとして clean なのは 2026-07-05 23:23 JST 以降** |
| `trips_btc.jsonl` | 4,564行（勝ち組トリップ）。1行=1トリップ `{coin, side, open_ms, hold_h, entry_px, exit_px, max_ntl, n_adds, maker_share, pnl, addr, ret_prior, hour_utc, ret_trip}` |
| `trips_btc_losers.jsonl` | 34,606行（対照群） |
| `fills_cache/` | 直近2000 fills / アドレス（1h キャッシュ）。1,648件・**約959MB**。2026-07-02 分は forward validation の seed（消さない） |
| `fills_deep/` | 全履歴 fills / アドレス（日次キャッシュ）。243件・約700MB |
| `seed_2026-07-02.json` | フォワード検証のシード（07-02 検証済み40人。transcript から復元 — 消すと再復元が面倒） |
| `fills_fwd/` | cutoff 以降の全 fills / アドレス（1h キャッシュ。中身はスーパーセット可 — forward.py が読み出し時に時刻フィルタ） |
| `forward_2026-07.json` | forward.py の生出力（OOS 成績 + 生存重複） |
| `btc_labels.json` / `btc_profile.json` | GraphSense ラベル / プロファイルキャッシュ |
| `track_cron.log` / `btc_track_cron.log` | cron ログ |

依存: **標準ライブラリのみ**（urllib/json）。`requirements.txt` は「必要になったら uncomment」のコメントのみ。
唯一の例外は `make_report.py` の python-docx（venv で入れる）。

---

## 5. データモデル（HyperCore が実際に見せてくれるもの）

ワークフローは「leaderboard でアドレス発見 → 各アドレスに個別照会」。市場全体の fill フィードは存在しない。

- `leaderboard()` → 約39.5k行: `ethAddress`, `accountValue`, `windowPerformances`
  （day/week/month/allTime × {pnl, roi, vlm}。**[名前, dict] ペアのリスト**であって dict ではない）
- `clearinghouse_state(addr)` → ライブ perp 状態: `marginSummary`（accountValue, totalNtlPos）,
  `assetPositions[].position`（coin, szi 符号付き, positionValue, unrealizedPnl, liquidationPx, leverage）
- `user_fills(addr)` → 直近最大2000 fills: coin, px, sz, dir(Open/Close Long/Short),
  side(B/A), startPosition, crossed（false=メーカー）, closedPnl, fee, time(ms), tid
- `user_fills_by_time(addr, start_ms)` → 期間指定。**t=0 から前向きにページングすれば全履歴が取れる**
  （1回2000件、次ページはページ内最新 ms から inclusive 再開 + dedup。`trips.deep_fills` 参照）
- `candles(coin, "1h", start, end)` → OHLCV。**サーバ側に直近 ~5000本しかない**（1h なら ~200日）。
  それより古いリクエストは空が返る → 古いトリップは momentum 読み不能（除外扱い）

---

## 6. API クックブック（全部キー不要・読み取り専用、Arkham のみ無料キー必要）

### 6.1 Hyperliquid
- info API: `POST https://api.hyperliquid.xyz/info`、body `{"type": ...}`。認証不要。
- leaderboard だけ別ホスト: `https://stats-data.hyperliquid.xyz/Mainnet/leaderboard`（静的 ~32MB）。
- **429 対策が最大の運用課題**: 1500口座スキャン（whales_coin）は毎時のレート予算をほぼ使い切る。
  直後の fills 取得は 429 が出る → `hl/client.py` が 2/4/8/16s 指数バックオフ、
  大量取得スクリプトは `HyperliquidInfo(retries=4)` + `WORKERS=4` で運用。
  それでも失敗は起きる — **stderr の `warning: N fills fetches failed` を必ず見る**。
  失敗が多かった run は**ウォームキャッシュで再実行**すると取り零しが回収できる
  （初回 trips run では 30/314 失敗 → 再実行で verified が 20→25 に増えた実績）。
- leaderboard キャッシュは JSON 検証 → .tmp → アトミック rename。取得失敗時は stale キャッシュに
  フォールバック（cron を殺さないため）。

### 6.2 Bitcoin (Esplora)
- `https://mempool.space/api`（blockstream.info も同一 API）。認証不要・値は **satoshi**。
- `/address/{a}` = 残高 + tx_count（1コールで両方）/ `/address/{a}/txs` = 直近~50 tx（vin/vout 完備）/
  `/address/{a}/txs/chain/{last_txid}` = 25件ずつ過去へページング。
- **⚠️ ヘビーセッションはスロットルされる**: 数百コール後、1コールが <1s → ~24s に劣化した実績。
  大規模ループは間隔を空け（`btc/expand.py` は +0.5s/コール）、必ずディスクキャッシュする。
  tx 履歴ページングを profiling ループに足さない。

### 6.3 ラベル（帰属）ソース
- **GraphSense tagpacks**（GitHub raw、無料・キー不要）— 取引所ラベルの主源。stdlib の
  簡易 YAML サブセットパーサで読む（`btc/labels_import.py`）。
- **Arkham**（無料ティア、`ARKHAM_API_KEY`）— custodial/omnibus（Coinbase, BlackRock/IBIT, MSTR）用。
  `/transfers` は 1 req/s 制限。**キー未取得のためライブ未検証** — レスポンスのキー名が
  ドキュメントと違ったら `arkham_flows.py` 側の extractor を直す（client は触らない）。
- キー無しで試して**ダメだった**もの（再挑戦しない）: api.arkm.com 直（403）、Blockchair（430）、
  WalletExplorer（クラスタリングのみ・命名は2016年で凍結）。

---

## 7. 分析の作法（このプロジェクト固有の判断基準）

1. **スキルは fills から定義する**。leaderboard の pnl/roi は候補出し（ファンネル）にだけ使う。
   `roi` 単独ランキングは厳禁（少額口座で +32955 のような値が出る）— 必ず volume floor か絶対 pnl と併用。
2. **リーダーボードの accountValue は stale スナップショット**。上位に $0 notional・0ポジションの
   口座（vault/休眠/精算済み）が普通に混ざる。現在の実態は `clearinghouse_state` が正。
3. **数値フィールドは全部 string で返る** → 寛容な float ヘルパ（`wc.fnum`）で変換。
   `liquidationPx` は cross margin で null が多い。
4. **メーカーの lean はインベントリであって view ではない**。maker% が高い口座の long/short タグや
   「方向」を意味づけしない。lean が意味を持つのは maker% が低い方向性トレーダーのみ。
5. **勝率は単独ではスキル指標にならない**（実現 fills だけ数えるので「勝ちは確定・負けは塩漬け」で
   100% になり得る）。PF と net PnL を優先。
6. **勝率コントラストは必ずトレーダー層別（CMH）で検定**。プール集計は高頻度口座2つに引きずられて
   Simpson のパラドックスを起こした実績あり（fade edge / pyramiding が初回「発見」に見えた原因）。
7. **予測力の検定は forward return + hit-rate + const-guess base rate**。zero-lag 相関は
   herding を測るだけ（参考リポジトリの中核的欠陥、`notes/reference_repos.md`）。
   スナップショット間隔の乱れは median gap の 0.5–1.5x でペアを落とす（spacing guard）。
   `n_failed` 入りの行は劣化スナップショットとして識別可能（2026-07-02 以前の行にはキー無し →
   `.get("n_failed", 0)`）。
8. **BTC watchlist 追加は残高ライブ検証が必須**。「ラベルは腐る、残高が真実」
   （ラベル上ホットウォレットでも残高0が多数 = ローテーション済み）。
9. **オンチェーンのシグナルはホットウォレット行のみ**。コールドの動きは保管の付け替え（ノイズ）。
   net INflow ≈ 売り圧、net OUTflow ≈ 蓄積、はあくまで prior（検証は 2026-08-05 の --analyze）。

---

## 8. 確定した主要知見（再調査しないための要約）

1. **スキルは実在し持続する**（133口座 split-half）: fills 指標 Spearman +0.54..0.62 ≫
   leaderboard 損益 +0.22。前半勝率上位半分は 85% が後半もプラス（下位半分 40%）。
   caveats: 同一レジーム共有・生存バイアス・勝率インフレ（`notes/skill_findings.md`）。
2. **集団の方向にはエッジがない**（1〜24h、全ホライズンでベースレート以下）。
   h=24 の「逆相関」は1トレンドのアーティファクト — 符号を反転させる根拠にはならない。
   30日分（~2026-07-27）で再検証。
3. **全コイン PF 上位は薄い板のメーカー**（追随不能・設計上コピー無意味）。BTC の深い板では
   最大クラスタは**イントラデイのテイカー**。
4. **トリップ分析（50人/4,564トリップ、勝ち組）**: 統計的に生き残ったエッジマーカーは
   **①損切りの速さ（撤退規律）だけ**（41/46人、Stouffer p≈3e-35、hold ratio 中央値 0.39、
   CI [0.29,0.48]）。②逆張り優位は死（p=0.56）、③ボラトリガー優位は死と決着
   （初回 p=0.074 は 8x の母集団で消滅 → p=0.78）、④積み増し優位は不安定（p=0.076、効果なし扱い）。
   逆張り 61%・NY オープン集中・積み増し常態は「行動としての事実」であってエッジの証拠ではない。
5. **対照群で①が改訂された（最重要の教訓）**: 検証済み負け組 182人/34,606トリップも
   76% が損切りは速い（中央値 0.53）— **「負けを切る」は全員やっている。勝者を分けるのは
   「勝ちを切らない」方**（勝ち保有 2.6h vs 負け組 1.4h）。加えて勝者は: トレード数が少ない
   （43 vs 100）、クリップが大きい（$77K vs $36K）、より逆張り（63% vs 54%）、より積み増す。
   ⚠️ WR・ペイオフの群間差は選択で部分的にトートロジー — findings として引用しない。
6. **スキルは前向きには持続しなかった（07-19 フォワード検証・初回読み、OOS 16日）**:
   07-02 検証済み40人のうち BTC で活動継続 24人 → プラスは 9/24（38%、コインフリップと
   区別不能、in-sample の「85% プラス維持」は p≈1.5e-7 で棄却）。合計 OOS net −$553K
   （BTC は +2.0% の横ばい）。in-sample PF と OOS net の Spearman は −0.20（予測力ゼロ）。
   離脱も大きい（15/40 が BTC 取引ゼロ）。skill_findings の split-half 持続は
   「同一レジーム共有」の caveat が本質だったと確定。詳細 `notes/forward_findings.md`。
7. **BTC オンチェーン**: 可視性は無料・完全、**帰属だけが問題**。単一アドレスの取引所
   コールド/ホットは watchlist で追える。BlackRock/Coinbase/MSTR は構造的に無料不可
   （ローテーションする custodial クラスタ）→ Arkham 待ち。
   Binance はコールド（休眠 vault、トレース起点として死に筋）とホット（実流動ハブ）が分離、
   Bitfinex はコールドがホットに補給する。芋づるトレースは**監視アドレスの net delta を集計**
   （生の tx in/out 合計はマーカー出力で大幅過大計上 — 一度踏んだ）。

---

## 9. cron 運用（本番。壊さない）

```
5 * * * *  cd ~/claude/crypto_whales && python3 whales_track.py >> data/track_cron.log 2>&1
35 * * * * cd ~/claude/crypto_whales && python3 btc_track.py    >> data/btc_track_cron.log 2>&1
```
- TZ=Asia/Tokyo。マシンが落ちている/スリープ中の時間は欠測（--analyze の spacing guard が吸収）。
- whales_track は毎時 ~1500 clearinghouse コール + leaderboard。**たまの 429 で1点落ちるのは想定内**
  （破損はしない）。頻発したら WORKERS を下げるか backoff を強める。
- btc_track は cron 停止後の初回、フローウィンドウを 6h でキャップ（mempool.space への politeness）。
- 手動での再実行は安全（追記のみ）。ただし同じ時間帯に2回実行すると間隔が乱れた点が増えるだけ。

---

## 10. git 運用

- remote: `origin = https://github.com/smoltz29j/crypto_whales.git`（**private 前提**）。
- **push はユーザーが言ったときだけ**。コミットは作業ごとに作る（英語・内容要約型メッセージ）。
  ⚠️ 2026-07-07 時点でローカル main は origin より **12コミット先行（6d92706 以降未 push）**。
- `data/` `__pycache__` `.venv/` は gitignore。`調査まとめ_2026-07-05.docx` は**未追跡のまま**
  （追跡するかはユーザーに確認していない — 未確認）。
- 作業前に `git fetch`（他マシンから push されるリポジトリがユーザー環境に存在するため、習慣として）。

---

## 11. 申し送り（未完了・時限タスク）

| 期日/状態 | タスク |
|---|---|
| 未完了 | `notes/trips_findings.md` の**本文 Finding 1–4 が初回（17人/574）の古い数値のまま**。Addendum 2/3 が現在の真実。本文の書き直しが宙に浮いている |
| 未完了 | **Word レポート v4**（対照群の改訂を反映。「撤退規律が THE マーカー」→「負けを切るのは全員、勝者は勝ちを切らない」への reframe）を `make_report.py` で生成し、snitker NAS `document` 共有へ**新ファイル名**でコピー。v3 は反映前の内容のまま NAS にある |
| ユーザー作業 | **Arkham 無料 API キーの取得**（intel.arkm.com/api → 環境変数 `ARKHAM_API_KEY`）。コードは実装済み・キーが入れば `arkham_flows.py` が即動く（ただし初回はレスポンス形状の確認が要る） |
| ~2026-07-27 | `python3 whales_track.py --analyze --horizon 1,4,8,12,24`（30日 ≒ 720スナップショット時点）→ 結果を `notes/track_findings.md` に追記 |
| ~2026-08-05 | `python3 btc_track.py --analyze --horizon 1,4,24`（clean series 30日時点）→ `notes/btc_onchain.md` に追記 |
| ~2026-08-02 | **フォワード検証の30日読み**: `python3 forward.py` を再実行（fills_fwd キャッシュで安価）→ `notes/forward_findings.md` に Addendum。初回読み（07-19、OOS 16日）は完了 — 持続性は再現せず。30日読みで「現在スキル選抜」路線の存廃を決める |
| 任意 | trips.py のウォームキャッシュ再実行（拡張 run で 93/833 fills 取得失敗 + deep 3件 — 回収するとトレーダーが増えるかもしれない） |
| メモ | 出力形式（CLI/アラート/ダッシュボード）は 30日再検証の結果を見てから決める（意図的な未決） |
