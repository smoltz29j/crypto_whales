# Forward validation of the 2026-07-02 verified-skilled BTC cohort — first reading (2026-07-19)

The survivorship-free retest the HANDOFF scheduled for 07-19..08-02: take the
traders `skilled.py` verified on 2026-07-02 (on data available *then*), and
measure what they did *after* that moment. `forward.py` is the harness;
`data/forward_2026-07.json` the raw output.

## Method

- **Seed cohort**: the 07-02 run verified **43** traders; the printed
  top-40-by-PF table was recovered from the session transcript (the run
  itself printed only 10-char address prefixes; each prefix resolved uniquely
  against the 2,125 cached fill files — one 2-way collision disambiguated by
  fill content). The 3 lowest-PF rows were never printed and are lost →
  **cohort = 40 of 43**. Full list in the appendix; also
  `data/seed_2026-07-02.json`.
- **Cutoff** = 1782948004000 (2026-07-01T23:20:04Z), the exact run moment from
  the transcript timestamp. Everything after it is out-of-sample (OOS).
- **OOS window at this reading: 16.4 days.** All fills since cutoff fetched via
  `userFillsByTime` paged forward (cached `data/fills_fwd/`), metrics
  recomputed on the BTC subset with the same knobs skilled.py used
  (>=50 closes, >=7d span, net>0, PF>=1.5).
- Context: BTC moved **+2.0%** over the window ($62.7K → $64.0K) — flat enough
  that beta explains little of what follows.

## Finding 1 — the in-sample persistence result does NOT carry forward

| measure | in-sample expectation | OOS observed |
|---|---|---|
| stay-positive share | ~85% (skill_findings split-half) | **9/24 = 38%** |
| summed net (active traders) | — | **−$552.6K** |
| median net | — | **−$2.4K** |
| re-verify on OOS window alone | — | 3/24 |

- 38% positive is indistinguishable from a coin flip (two-sided binomial
  p≈0.31, n=24) and **decisively rejects the 85% in-sample rate**
  (P(X≤9 | p=0.85) ≈ 1.5e-7).
- **In-sample PF has zero forward predictive power**: Spearman(in-sample PF,
  OOS net) = **−0.20** (t=−0.95, n.s.); vs OOS PF = −0.03. The +0.54..0.62
  split-half persistence in `skill_findings.md` was within-window — its
  own caveat ("both halves share a regime; survivorship") is now confirmed
  as the load-bearing objection.
- The biggest OOS losers are the former stars: `0xfce053a5..` (the PF-211
  swing-maker showcase) **−$367K**, `0xec2aa004..` −$178K, `0x418aa6bf..`
  −$160K, `0xeff7fe67..` −$146K. Winners exist (`0xaf0fdd39..` +$158K,
  `0xd0580894..` +$112K, `0x05936f6a..` +$78K) but are the minority and not
  concentrated in any archetype — makers and takers appear on both sides.

## Finding 2 — attrition is huge

**15/40 traded zero BTC in the 16 days** (one more traded BTC but closed
nothing). Several were already quiet long before the cutoff (the first,
buggy 381-day run showed their activity as year-old bursts). The verified
population is transient: burst-trade, then vanish or rotate markets.
Half-life of "currently verified skilled" appears to be weeks, not months.

## Finding 3 — funnel-overlap overstates persistence

Fresh funnel today: 310 candidates → 32 verified. Of the 40 seeds, **8 are
still candidates, 6 verify again** — but skilled.py verifies on the last-2000-
fills window, which for quiet accounts reaches back *before* the cutoff:
4 of the 6 "survivors" have essentially no OOS BTC closes (`0xc7290b4b..`
verified today on fills that end in Feb 2026; leaderboard month-pnl keeps
ranking it via mark-to-market on open positions). Only **2/40**
(`0xaf0fdd39..`, `0x45354959..`) both re-verify *and* made OOS money.
Survivor overlap as a headline number is confounded — use OOS PnL.

## Caveats (honest ones, per house rules)

- 16 days is short; the 30-day reading (~2026-08-02, rerun `forward.py` —
  fills_fwd caches make it cheap) is the scheduled full test. The re-verify
  bar (>=50 closes over >=7d) is harsh at 16 days.
- n=24 active: the 38% could drift either way; what is *not* fragile is the
  rejection of 85% and the sign of the aggregate.
- Cohort is top-40-by-PF, i.e. tilted toward the maker/inf-PF cluster whose
  edge was never directional; but the directional takers did no better
  (two of the four biggest losers are intraday takers).
- 3 of 43 seeds are lost to history (unprinted table tail) — direction of
  that bias unknown, magnitude small.
- The cohort leaned short at verification time; BTC +2.0% costs a pure
  passive short ~2% of notional, which does not cover the observed losses.
- Single 16-day regime, one cohort, one venue — this is one draw, not a law.

## Where this leaves the project

The core premise "verified skill persists → study the persistent skilled"
now has an asterisk: **selection-by-recent-PF finds last month's winners,
not next month's**. What survived every test so far is behavioral
(*how* the winners traded: few, large, pyramided trips — trips_findings
Addendum 3), not predictive (who wins next). The 30-day reading decides
whether to kill the "follow the currently-skilled" thread entirely or
whether a slower-selection variant (require persistence across two disjoint
windows) is worth building.

## Appendix — the 40 seed addresses (durable record; data/ is gitignored)

```
0x05936f6a5ea9abfbfcc690f1a6140d97e80640f9  0x0f626f3ecffcf9cc97c0f2f8307d4501f15908a9
0x103e9d15f8a102ef9333ad8b66ffe25b0db448a4  0x13533eef19262af120d5c0427229a3cb6a1509d7
0x192dfd9c08cd9e17cc695913bca39b36ec425324  0x218a65e21eddeece7a9df38c6bbdd89f692b7da2
0x25dacd8a27eac9ad6eba5eb88e3b68f707eb1397  0x27d06c2cba7e16673b4b9f5387b06af8c6b1d7b7
0x30bcd26adb8dc080065a4ceb8294abf43d086a8e  0x3e74607ac4d7c30a6a276bfba6465b6074488f0b
0x418aa6bf98a2b2bc93779f810330d88cde488888  0x4535495989f30de9044bdf7409c0e104e1422131
0x4aada58e425bb36c8cb39cd4e3ebf8571b76b2b5  0x4e14fc11f58b64740e66e4b1aa188a4b007c0eab
0x4f12b217aa59e6d3e1f91ca2dc96f9543576618b  0x50a4d39bc020be2c86954eec2670541d300f8168
0x5559da6ec434c5723d0ce9c4da7f29e3f8a3d43b  0x5a62d437575bd175495926de799050b34b4dba44
0x697bb69144e716c019734d2db46f437220a889ba  0x6daec5ff434924e0839358e710e6ae5f158590de
0x6df99d59cdada18ade521e05edd5e6a2ec91b734  0x732f7178048a7329cb37e251845d4d39d62ab4ae
0x7839e2f2c375dd2935193f2736167514efff9916  0x906d31b2ee92c4bc720232112274a0e1ffb0ad6e
0x91487668dc7f16e26b8ce5feb39cef66163f1b74  0x9c68cd0568eb47bad36ecd8090e6c1d1396a7783
0xaec601c7312d63610c6ce0facfd3b1498fd4fe9f  0xaf0fdd39e5d92499b0ed9f68693da99c0ec1e92e
0xb2be5cb4e3bc5992531cd7e09ec59a4aadd71cf1  0xb6c0e4296ffcf7ffb1ba4245f8b0b16c54724a96
0xc7290b4b308431a985fa9e3e8a335c2f7650517c  0xc882fb57b1ff5ce0ffb737e6c9cdfeeaa6912d6f
0xd05808946809c180d190608e13f473db30aa8524  0xe392e9008c49e7f82e7927a741fcb12799ebdb2b
0xe8adbfeb2112b81f640df743b7919c3d68afc078  0xec2aa004732b35d4f763e7e73e7918da37274c96
0xec9045405a878d01cdb836f82a6dd2abd49a169c  0xeff7fe671d9a7acf86f48994bc5d5161042415b6
0xfa07f2520b0d99f04d0a25df169407909a41c40c  0xfce053a5e461683454bf37ad66d20344c0e3f4c0
```
