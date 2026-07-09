# Per-trip setup analysis of skilled BTC traders

**Current verdicts (2026-07-09 — Addendum 4 is authoritative; everything below
this box is chronological history, kept because each revision taught
something):**

- Population: **54 winners / 5,486 trips** vs **156 verified losers / 31,906**
  (continuity-guarded extraction after the 2026-07-09 corruption fix,
  `MAX_DEEP_FILLS` 30k — see `notes/review_2026-07-09.md`).
- **Exit discipline is real but universal.** Within winners it is enormous
  (Stouffer p = 7.3e-38, median hold ratio 0.35), but the control group cuts
  losses at the identical rate (82% both groups; degree n.s., p = 0.29).
  It is a market norm, not an edge marker.
- **What robustly separates winners from losers:** trade half as often
  (p = 0.001), pyramid more (p = 0.004), 2.3x the clip size (p = 0.006) —
  「少なく・大きく・積み増して張る」. "Let winners run" (2.8h vs 1.4h) survives
  only as a trend (p = 0.056).
- **Fade edge within winners: reopened on clean data** (CMH p = 0.023) — weak
  evidence, pending forward validation; do not quote as confirmed.
  Vol-trigger: dead. Pyramiding-within-winners: dead.
- History reading order: first reading (17/574) → statistical treatment →
  Addendum 2 (50/4,564) → Addendum 3 (control group) → **Addendum 4 (current)**.

---

## First reading (2026-07-05) — historical; population and numbers superseded

`trips.py` executes the next step recorded in notes/skilled_findings.md: for the
*directional* cluster of verified skilled BTC traders (>= 8 complete flat->flat
round trips), dump every trip (entry/exit px, hold, adds, pnl) to
`data/trips_btc.jsonl` and analyze the entries as **setups** against 1h BTC
candles (new `HyperliquidInfo.candles` endpoint).

Run: 314 candidates → 25 verified skilled in BTC → **17 directional traders,
574 complete trips**. (An earlier same-day run had 30/314 fills fetches fail on
rate limits and found only 20 verified — rerunning with the warm cache recovered
everything; heed the `warning: N fills fetches failed` line.)

## Finding 1 — the one near-universal signature: cut losses fast, let wins run

**16 of 16** traders (with >= 3 wins and >= 3 losses) hold losing trips shorter
than winning ones — median ratio **0.30** (pooled: losing hold 0.8h vs winning
2.8h). Pooled trip win rate is only 45%; the profitability comes from asymmetry,
not from being right. The top earners are the extreme version: WR 20–40% with
payoff ratios 20–27 (`0x8685a7e8..` net $47.5K at WR 40%, `0xfa07f252..` net
$25.3K at WR 20%).

This is the single most consistent behavioral marker of verified skill in the
sample — more consistent than any entry pattern.

## Finding 2 — they fade, they don't chase

Only **39%** of entries are aligned with the prior 4h move (536 readable);
per-trader median alignment is **31%**, and only 2 of 17 lean momentum. Longs
open after a median **−0.66%** 4h dip. And alignment *hurts*: winning trips were
35% aligned vs losing trips 43% — the chase entries are the losing ones.

Volatility is the trigger, though: 42% of entries come within 4h of a >= 1%
move, and those entries win more (WR 52% vs 43% quiet) — but per-trader this is
mixed (8/16 positive, median +9pp), so treat "vol-triggered entries do better"
as suggestive, not established.

Portrait: **skilled BTC traders in this cohort are dip-buyers / spike-faders who
show up when the market moves.** The `--addr` view of the top earner makes it
vivid — dormant for months, then bursts on crash days (2026-02-05: buys into a
−3.55% 4h move, +$19.8K in 0.3h, then flips short the bounce).

## Finding 3 — pyramiding is normal, not degen

49% of trips add to the position before closing (median 5 adds when they do);
WR with adds 49% vs 42% single-entry. Several accounts build large notional
from small clips this way (`0x8685a7e8..`: 42 adds to $1.4M notional). Adds are
part of the method, not a tilt marker, in this verified-skilled sample.

## Finding 4 — time-of-day clusters at NY open and Asia morning

Pooled entries peak at **13–15 UTC** (NY morning; 14U = 73 trips ≈ 3× the
average hour) with a secondary bump at **00–02 UTC** (09–11 JST, Asia morning),
and a trough 03–08 UTC. Caveat: the 13–14U spike is partly two hyperactive
accounts (62 of 112 entries); the per-trader `block` column is the honest view —
top blocks vary (12-16U, 16-20U, 00-04U all appear).

## Addendum — statistical treatment (2026-07-05, same day; `trips_stats.py`)

Proper tests change the picture: **one finding survives decisively, two die.**

**Finding 1 (cut losses fast) — SOLID.** Per-trader one-sided Mann-Whitney U
(losing holds < winning holds), then combined across traders:
- direction: 16/16 traders, exact sign test p = 1.5e-5;
- Stouffer-combined z = −5.99, p ≈ 1e-9;
- median hold ratio 0.29, cluster-bootstrap (resampling traders) 95% CI
  [0.11, 0.51];
- robust to excluding scratch trips (|price move| < 0.05%): 15/16,
  sign p = 2.6e-4, CI [0.09, 0.45]. The one ratio≈1 trader (`0xdd17b90b..`)
  is also the biggest net loser in the table — consistent, though anecdotal.

**Finding 2 (fading wins, chasing loses) — DOES NOT survive.** The pooled
wins-35%-aligned vs losses-43%-aligned gap was a composition artifact
(Simpson's paradox from the two hyperactive accounts). Cochran-Mantel-Haenszel
stratified *by trader*: OR_MH = 1.18, p = 0.40. What remains true is purely
descriptive: these traders *choose* to fade (~61% of entries) — but there is
no within-trader evidence that their fade entries win more than their chase
entries.

**Finding 3 addendum (vol-triggered entries win more) — marginal.** CMH
OR_MH = 1.39, p = 0.074. Suggestive, not established; consistent with the
per-trader median +9pp noted above.

**Finding 3 (pyramiding wins more) — DEAD.** Pooled 49% vs 42% collapses to
OR_MH = 1.02, p = 0.91 under trader stratification: entirely between-trader
composition. Pyramiding remains a common *behavior* (49% of trips) but there
is no evidence adds improve a given trader's odds.

Test caveats: trips within a trader are not independent (time clustering,
shared regime), so p-values are somewhat optimistic; 3 win-rate contrasts
were run (multiple comparisons); n = 16-17 traders is the effective sample
for all cross-trader claims.

## Addendum 2 — maximized population (2026-07-06, run just before session end)

User direction: maximize n. Funnel widened 3x (833 candidates; 93 fills
fetches failed on rate limits — worth a warm-cache rerun) + full-history
`deep_fills` paging → **64 verified, 50 directional traders, 4,564 trips**
(8x the first pass). `trips_stats.py` on the new population:

- **① cut-losses-fast: confirmed decisively.** 41/46 traders (sign
  p = 2.2e-8), Stouffer p ≈ 3e-35, median hold ratio 0.39, CI [0.29, 0.48]
  (was [0.11, 0.51] — tighter, slightly higher). Robust to scratch exclusion.
- **② fade edge: stays dead** (OR 1.05, p = 0.56) — now with ~3,400 readable
  trips, convincingly zero.
- **③ vol-trigger: RESOLVED — dead.** OR 1.02, p = 0.78. The first-pass
  marginal p = 0.074 was noise; 4x the data killed it.
- **④ pyramiding: flipped from dead to marginal** (OR 1.14, p = 0.076,
  was 1.02/0.91). Unstable across populations → treat as no effect until it
  survives a fresh sample.

Bottom line unchanged and now much stronger: **exit discipline is the only
statistically real edge marker in this cohort.** Still pending: control group
(do losing traders also cut fast?), notes update of the main findings above,
Word report v3 to the NAS.

## Addendum 3 — control group: verified losers (2026-07-06, trips.py --losers)

Same activity bar, opposite outcome (net < 0, PF <= 0.9, worst-pnl/roi funnel):
**182 loser traders / 34,606 trips** vs the 50 winners / 4,564. Per-trader
features, two-sided MWU across traders (`trips_compare.py`):

```
feature            winners  losers   p        note
cut_ratio            0.39    0.53   0.021    losers cut fast TOO (134/177 < 1)
payoff ratio         1.38    0.81   4.5e-5   (partly selection-implied)
trip win rate        50%     37%    9.6e-9   (partly selection-implied)
median hold          2.6h    1.4h   0.006
fade share           63%     54%    0.014
pyramid rate         85%     77%    0.002
median clip         $77K    $36K    0.002
trips (activity)     43     100     9.1e-5   losers overtrade 2.3x
```

**The revision to Finding 1:** cut-losses-fast is NOT a winner-only trait —
76% of verified losers also hold losses shorter than wins (stop-losses are
just how active HL traders operate). Winners are more *extreme* about it
(0.39 vs 0.53, p=0.021), but the discipline alone doesn't separate the groups.

**What actually separates them (beyond the selection-implied WR/payoff):**
losers cut losses fast *and cut winners fast too* (hold 1.4h vs 2.6h overall)
— they have the loss-cutting half of the asymmetry without the let-winners-run
half. Plus: losers overtrade (100 vs 43 trips), trade smaller ($36K vs $77K),
chase more (fade 54% vs 63%), pyramid less. The one-line story becomes:
**「負けを切る」は全員やっている。勝者を分けるのは「勝ちを切らない」方.**

Caveats: WR and payoff differences are partly tautological (groups were
*selected* on net pnl, and net pnl is a function of WR × payoff) — the
behavioral rows (holds, fade, pyramid, clip, activity) are the meaningful
discriminators. Cohort sizes are asymmetric (182 vs 50). Same
non-independence caveats as Addendum 2.

## Addendum 4 — data regenerated after the continuity-bug fix (2026-07-09)

**Why everything above was re-derived:** the 2026-07-09 review
(`notes/review_2026-07-09.md` #1) found that trip extraction trusted the fill
stream to be gapless. `deep_fills`' 12k pagination cap left an unfetched hole
before the spliced recent window, and some position changes have no fill at
all; 87/243 cached accounts had position-chain breaks (worst: one "trip"
spanning a 97-day gap). A continuity guard now drops any trip straddling a
gap, and `MAX_DEEP_FILLS` was raised 12k → 30k to recover the region the guard
would otherwise discard. **All Addendum 2/3 numbers are superseded by the
following** (winners 54 traders / 5,486 trips; losers 156 / 31,906;
101/836 fills fetches failed on rate limits — a warm-cache rerun could grow
this slightly).

**Setup verdicts on clean data (`trips_stats.py`):**

1. **Exit discipline (hold ratio): confirmed, stronger.** 42/51 traders with
   ratio < 1; Stouffer z = −12.81, p = 7.3e-38; median ratio 0.35, cluster
   bootstrap 95% CI [0.22, 0.54]. Scratch-excluded: p = 2.1e-24, median 0.47.
2. **Fade edge: REOPENED (was "dead" on corrupt data).** CMH stratified,
   44 strata: OR_MH = 1.19, z = +2.28, p = 0.023 two-sided. Nominally
   significant, but (a) three comparisons in this family (Bonferroni ≈ 0.07),
   (b) the verdict flipped between datasets, which is itself evidence of
   fragility. Status: *weak evidence, pending forward validation* — do not
   quote as a confirmed edge.
3. **Vol-trigger: still dead** (OR 1.05, p = 0.53). Verdict unchanged.
4. **Pyramiding within winners: dead** (OR 0.97, p = 0.71) — settles
   Addendum 2's "unstable marginal" as no effect.

**Control-group revision (this changes Addendum 3's story):**

```
feature            winners  losers   p(two-sided)   verdict on clean data
cut_ratio            0.35    0.47      0.29         NOT a discriminator anymore
cut_ratio < 1        42/51  121/148     —           82% vs 82% — identical share
median hold          2.8h    1.4h      0.056        trend only, no longer clean
fade share           56%     53%       0.060        trend only (was 63% vs 54%)
trip count           48.5    99        0.001        ROBUST: losers overtrade 2x
pyramid rate         89%     81%       0.004        ROBUST
median clip         $115K   $49K       0.006        ROBUST
trip win rate        49%     36%       3e-6         partly selection-implied
payoff               1.13    0.91      0.018        partly selection-implied
```

Loss-cutting is now *fully* universal: the share of cutters is identical
(82% both groups) and even the degree (0.35 vs 0.47) is not significant.
The Addendum 3 one-liner — 「勝者を分けるのは『勝ちを切らない』方」 — must be
downgraded to a trend (p = 0.056). What robustly separates winners on clean
data is **selectivity and size: they trade half as often, with 2.3x the clip,
and pyramid more**. 規律の物語はどちらの向きでも死に、残ったのは
「少なく・大きく・積み増して張る」.

(The corrupt data had *inflated* the discipline contrasts: gap-spanning
phantom trips created artificially long "winning holds" for winners with long
histories — exactly the accounts the 12k cap hit hardest.)

**Persistence test** (fee bug fixed the same day, see
`notes/skill_findings.md` addendum): Spearman +0.59..+0.64, conclusions
unchanged.

## Caveats

- **Survivorship by construction**: every trader here passed the skill filter,
  so these are "habits of the profitable", not "habits that cause profit".
  Losing traders may also cut losses fast; we haven't run the contrast group.
- **Alignment has no natural 50% base rate** in a trending regime; the
  wins-vs-losses alignment gap (35% vs 43%) is the more meaningful comparison.
- Pooled stats lean on two accounts with 135 and 106 trips (42% of the sample);
  per-trader medians quoted above are the robust versions.
- 1h candles only reach back ~5000 hours (~200 days); older trips get no
  momentum read (`prior4h = -` in `--addr`).
- Same 2000-fill window as skilled.py; window-straddling trips are dropped.

## Next steps

1. **Contrast group**: run the same trip extraction on verified *losers*
   (net < 0, PF < 1) — does the cut-fast/fade profile actually separate winners
   from losers, or is it just how everyone on HL trades?
2. **Forward validation** (unchanged from skilled_findings.md): re-run the
   funnel in 2–4 weeks, measure survivor overlap and whether the trip signature
   (cut ratio, fade share) is stable per address.
3. Trip-level MFE/MAE from candles (how much heat do they take before winning?)
   if the setup work needs a risk dimension.
