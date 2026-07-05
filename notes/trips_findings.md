# Per-trip setup analysis of skilled BTC traders — first reading (2026-07-05)

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
