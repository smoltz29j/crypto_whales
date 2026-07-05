#!/usr/bin/env python3
"""Generate the 2026-07-05 findings summary as a Word document (Japanese)."""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

OUT = "/home/smoltz/claude/crypto_whales/調査まとめ_2026-07-05.docx"

doc = Document()

# --- base styles -----------------------------------------------------------
style = doc.styles["Normal"]
style.font.name = "Noto Sans CJK JP"
style.font.size = Pt(10.5)
style.element.rPr.rFonts.set(
    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia",
    "Noto Sans CJK JP")

for lvl, sz in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)):
    h = doc.styles[lvl]
    h.font.name = "Noto Sans CJK JP"
    h.font.size = Pt(sz)
    h.font.color.rgb = RGBColor(0x1a, 0x1a, 0x2e)
    h.element.rPr.rFonts.set(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia",
        "Noto Sans CJK JP")


def p(text, bold=False, size=None, style_name=None):
    para = doc.add_paragraph(style=style_name)
    run = para.add_run(text)
    run.bold = bold
    if size:
        run.font.size = Pt(size)
    return para


def bullet(text, bold_prefix=None):
    para = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        r = para.add_run(bold_prefix)
        r.bold = True
        para.add_run(text)
    else:
        para.add_run(text)
    return para


def numbered(text, bold_prefix=None):
    para = doc.add_paragraph(style="List Number")
    if bold_prefix:
        r = para.add_run(bold_prefix)
        r.bold = True
        para.add_run(text)
    else:
        para.add_run(text)
    return para


def table(headers, rows, widths=None):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Light Grid Accent 1"
    for j, h in enumerate(headers):
        cell = t.rows[0].cells[j]
        cell.text = h
        for r in cell.paragraphs[0].runs:
            r.bold = True
    for i, row in enumerate(rows, 1):
        for j, v in enumerate(row):
            t.rows[i].cells[j].text = str(v)
    if widths:
        for j, w in enumerate(widths):
            for row in t.rows:
                row.cells[j].width = Cm(w)
    return t


# --- title -------------------------------------------------------------------
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run("Hyperliquid スキルトレーダー & BTC オンチェーン調査\nまとめと提言")
r.bold = True
r.font.size = Pt(18)
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sr = sub.add_run("2026年7月5日 / crypto_whales プロジェクト")
sr.font.size = Pt(10)
sr.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

# --- 1. overview ---------------------------------------------------------------
doc.add_heading("1. このプロジェクトは何か", level=1)
p("2つのデータ領域を並行して調べています。(1) Hyperliquid（無期限先物DEX）で"
  "「本当に上手いトレーダー」を口座規模に関係なく発見し、その手法を分析する"
  "（コピートレードではなく手法研究）。(2) Bitcoin ベースチェーン上で取引所など"
  "既知エンティティの大口資金移動を監視する。どちらも無料の公開APIのみで運用中です。")

# --- 2. findings ---------------------------------------------------------------
doc.add_heading("2. わかったこと", level=1)

doc.add_heading("2.1 スキルは実在し、持続する【確度: 高】", level=2)
p("リーダーボードの損益ランキングは当てにならない一方、約定履歴（fills）から計算した"
  "実測成績は将来の成績をよく予測します。133口座の分割検証では：")
bullet("fills 由来の指標（勝率・純損益・プロフィットファクター）と後半成績の相関は "
       "+0.54〜+0.62。リーダーボード損益は +0.22 しかない。")
bullet("前半勝率が上位半分の口座は 85% が後半もプラス（下位半分は 40%）。")
p("→「whale = 資金量」ではなく「whale = スキル」で定義すべき、という当初仮説を確認。", bold=True)

doc.add_heading("2.2 上手い人の実際の手法（BTC・574トリップ / 17人の分析）【確度: 中〜高】", level=2)
p("検証済みスキル保有者のうち、建玉をフラットに戻す「方向性トレーダー」全員の"
  "個別トレード（トリップ）を抽出し、セットアップを分析した結果：")

table(
    ["発見", "内容", "統計検定の結果"],
    [
        ["① 損切りは速く、勝ちは伸ばす",
         "負けトレードの保有時間は勝ちの0.29倍（中央値）。負けの保有は全体中央値47分"
         "（高速勢は7〜11分、スウィング勢は数時間〜。普遍なのは分数ではなく比率）。"
         "勝率は45%しかないのに、非対称なペイオフで儲けている。トップ勢は勝率20〜40%"
         "でペイオフ比20倍超。",
         "確立。16/16人（符号検定 p=1.5×10⁻⁵、合成 p≈10⁻⁹、"
         "ブートストラップ95%CI [0.11, 0.51]、スクラッチ除外でも頑健）"],
        ["② 追いかけず、逆張りする",
         "直前4時間の値動きと同方向のエントリーは約3分の1のみ。ロングは中央値−0.66%"
         "の下落後に入る。これは「彼らがそう行動する」という事実。ただし『逆張りの方"
         "が順張りより勝ちやすい』というエッジの証拠は、トレーダー層別の検定では消えた。",
         "行動としては確か（15/17人）。エッジとしては不成立"
         "（CMH OR 1.18, p=0.40）"],
        ["③ ボラティリティが引き金",
         "エントリーの42%は4時間で1%以上動いた直後（勝率52% vs 静穏時43%）。",
         "示唆どまり（CMH OR 1.39, p=0.074）"],
        ["④ 積み増し（ピラミッディング）は常態",
         "半数のトリップでポジションに追加（中央値5回）。少額から100万ドル超の建玉を"
         "組み立てる例も。ただし『追加した方が勝ちやすい』は層別検定で消えた — "
         "よくある行動であって、優位性の証拠ではない。",
         "行動としては確か。エッジとしては不成立"
         "（CMH OR 1.02, p=0.91）"],
        ["⑤ 時間帯はNY朝と東京朝",
         "エントリーはUTC 13〜15時（日本時間22〜24時）と日本時間9〜11時に集中。",
         "記述統計のみ（口座集中に注意）"],
    ],
    widths=[4.0, 8.0, 5.0],
)
p("")
p("典型例：トップ収益者は数ヶ月間休眠し、急落日にだけ現れて下落を買い（4時間で"
  "−3.55%の暴落中にロング→18分で+$19.8K）、細かく積み増して大玉を作る"
  "「ボラティリティ・イベント逆張り型」でした。")
p("統計処理の要点：プールした集計は高頻度2口座（トリップの42%）に引きずられるため、"
  "勝率の比較はすべてトレーダー層別の Cochran-Mantel-Haenszel 検定で行いました。"
  "その結果、当初「発見」に見えた②のエッジと④の優位性は合成の錯覚（Simpson の"
  "パラドックス）と判明し、統計的に生き残ったのは①の撤退規律だけです。", bold=False)

doc.add_heading("2.3 「集団の方向」にはエッジがない【確度: 中】", level=2)
p("スキル加重した whale 集団の BTC/ETH ポジション方向は、1〜24時間先のリターンを"
  "予測しません（全ホライズンでベースレート以下、4.5日分）。上手い個人の手法を学ぶ"
  "のが正しく、集団の売買方向を真似るのは（現時点では）無意味 — プロジェクトの"
  "「コピートレードではない」方針を裏付ける結果です。30日分たまった時点で再検証します。")

doc.add_heading("2.4 BTC オンチェーン監視【確度: 高（インフラ）】", level=2)
bullet("チェーンの可視性は無料・完全。難しいのは「どのアドレスが誰か」（帰属）だけ。")
bullet("無料の GraphSense ラベルで大手取引所はカバー可能。本日の拡張で監視対象は "
       "11エンティティ / 約76万BTC（Binance・Bitfinex・OKX・Crypto.com・Huobi・Bybit "
       "のコールド/ホット、全て残高を実測検証済み）。")
bullet("教訓:「ラベルは腐る、残高が真実」。ラベル上は取引所ホットウォレットでも残高"
       "ゼロが多数（ローテーション済み）。残高検証なしにアドレスを信用しない。")
bullet("直近48時間は取引所へ +1,480 BTC の純流入（弱い売り圧サイン）。ただし単発の"
       "読みであり、時系列を貯めてから判断する（毎時cron稼働開始済み）。")
bullet("BlackRock / Coinbase / MicroStrategy の帰属だけは無料データでは不可能 — "
       "Arkham の無料APIキーが必要（コードは実装済み・キー待ち）。")

# --- 3. useful ---------------------------------------------------------------
doc.add_heading("3. 有益なこと（実用的な示唆）", level=1)
numbered("統計的に確立した発見は一つだけで、それは「エントリーの上手さ」ではなく"
         "「エグジット規律」です。勝率45%でも、負けに与える時間を勝ちの3分の1以下に"
         "絞れば勝てる — 検証した全員に共通し（p≈10⁻⁹）、タイムフレームを問わず比率"
         "ルールとして個人のトレードに移植できる唯一の再現性ある要素です。",
         bold_prefix="エグジット規律がすべて。")
numbered("上手い人が追いかけないのは事実ですが、「逆張りの方が勝てる」という統計的"
         "裏付けは層別検定で消えました。エントリー手法の真似より、出口の規律の移植に"
         "集中するのが正しい読み方です。",
         bold_prefix="エントリーの型は真似る根拠が弱い。")
numbered("集団の売買方向をシグナルとして使うのは現時点で根拠なし。使うなら「特定の検証済み"
         "個人が何をしたか」で、それも方向ではなく手法の学習対象として。",
         bold_prefix="群衆シグナルは使わない。")
numbered("オンチェーンではホットウォレットのネットフローだけが売買圧のシグナル。コールド"
         "ウォレットの動きは大半が内部移動（保管の付け替え）でノイズ。",
         bold_prefix="見るべきはホットウォレットのみ。")

# --- 4. actions ---------------------------------------------------------------
doc.add_heading("4. あなたが行うべきこと", level=1)

doc.add_heading("4.1 すぐできる（所要10分・無料）", level=2)
numbered("intel.arkm.com/api で無料アカウントを作り、API キーを取得して環境変数 "
         "ARKHAM_API_KEY に設定する。これだけで BlackRock→Coinbase 級の資金フロー追跡"
         "（arkham_flows.py）が即座に動きます。現在唯一、人手が必要な項目です。",
         bold_prefix="Arkham 無料キーの取得。")

doc.add_heading("4.2 待つだけ（cron が自動で蓄積中）", level=2)
table(
    ["いつ", "何を", "目的"],
    [
        ["2026-07-27 頃", "whales_track.py --analyze --horizon 1,4,8,12,24",
         "集団方向シグナルの30日再検証（現状エッジなしの確認）"],
        ["2026-08-05 頃", "btc_track.py --analyze --horizon 1,4,24",
         "取引所ネットフロー→BTCリターン予測の初検証"],
        ["2026-07-19〜08-02", "skilled.py 再実行（フォワード検証）",
         "検証済みトレーダーが期間外でも勝ち続けるかの確認"],
    ],
    widths=[3.5, 7.5, 6.0],
)

doc.add_heading("4.3 判断してほしいこと（次の分析の優先順位）", level=2)
numbered("§2.2 の手法分析は「勝者の習性」であって因果ではありません。負けトレーダー群に"
         "同じトリップ分析をかけ、「速い損切り・逆張り」が本当に勝者と敗者を分けるのかを"
         "検証する — 現時点で最も価値ある次の一手です。指示があれば私が実装します。",
         bold_prefix="対照群分析を実施するか。")
numbered("CLI・アラート・ダッシュボードのどれにするかは未決のまま（意図的）。データの"
         "価値が確定する30日再検証後に決めるのが合理的です。",
         bold_prefix="出力形式はまだ決めなくてよい。")

# --- 5. caveats ---------------------------------------------------------------
doc.add_heading("5. 注意（読み違えないために）", level=1)
bullet("生存バイアス: §2.2 は「スキル検証を通過した人」だけの分析です。負けている人も"
       "同じ行動をしている可能性は未検証（→対照群分析）。")
bullet("トリップは同一トレーダー内で独立ではない（時間的クラスタ・同一相場）ため、"
       "p値はやや楽観的です。またクロストレーダーの主張の実効サンプルは16〜17人です。")
bullet("直近ウィンドウ: 約定履歴は直近2000件のみ。数ヶ月〜1年の行動であり、"
       "全キャリアではありません。")
bullet("勝率のインフレ: 含み損を抱えたまま実現益だけ計上する口座は勝率が過大に出ます。"
       "プロフィットファクターと純損益を優先して見ています。")
bullet("オンチェーンの純流入/流出は監視ウォレット間の内部移動を含みます。"
       "ホットウォレット行だけが実シグナルです。")

doc.save(OUT)
print(f"saved: {OUT}")
