# Skilled traders (size-agnostic) + style fingerprints — first pass (2026-07-02)

Direction pivot: not whales, not copy-trading. `skilled.py` funnels the full
leaderboard (~39.7k rows) through three routes (top month-PnL 150 / top
week-PnL 100 / top month-ROI 150 with a $1M volume floor — the ROI route is
what admits small accounts), verifies skill from **fills** (>= 50 closes over
>= 7 days, net-of-fees > 0, PF >= 1.5), then fingerprints each survivor's
*method*: hold time from flat-to-flat round trips, maker/taker share, coin
concentration, long/short lean, clip size, activity.

First run: **378 candidates → 113 verified skilled** (3 fills fetches failed).

## Finding 1 — a large share of the consistently profitable are not directional traders

The top of the PF ranking is dominated by accounts with:
- very high maker share (70–100%),
- **zero complete round trips** in a 2000-fill window ("hodl?" tag = position
  never returns to flat — classic inventory-carrying market maker / grid),
- absurd PFs (inf, 4775, 110326) = almost no losing *closed* fill,
- niche-market specialization: xyz:SPCX, xyz:BRENTOIL, xyz:SILVER, xyz:MU
  (HL's equity/commodity perps), ZEC, XMR, HYPE — thin books where spread is wide.

Read: **their edge is liquidity provision / spread capture in thin markets,
not price prediction.** This is unfollowable by design — copying their fills
without being the maker just pays the spread they earn. Confirms the
"not simple copy-trading" framing: for this cluster the interesting question
is *which markets* they choose (where the spread is fat), not their direction.

## Finding 2 — the directional minority has recognizable shapes

Among verified accounts that *do* complete round trips:
- **scalp/intraday takers, multi-coin** (hold 0.2h–17h, maker% < 20%):
  momentum-style; several with 50–96% trip win rates.
- **swing makers** (hold 1–3 days, maker% 60–95%, trip WR ~100%): patient
  entries via resting orders, days-long holds — e.g. `0xfce053a5..` 43 days,
  PF 211, net $3.1M, median hold 33h, BTC-specialist.
- **position traders** (hold 10–26 *days*, PF 26–inf): low activity, very high
  trip WR; the closest thing to "smart money whose direction means something".

## Caveats

- `hodl?` + lean labels mislead for makers: "short 0% long" for a maker means
  their *opens* were sells (someone bought into them) — it is inventory, not a
  view. Treat lean as meaningful only when maker% is low.
- Leaderboard `accountValue` still stale ($0 rows appear); size column is a hint.
- PF from *closed* fills — an account riding a big unrealized loss still looks
  perfect (same caveat as notes/skill_findings.md; the persistence result there
  is what licenses using these metrics at all).
- 2000-fill window: for 200+ fills/day accounts this is ~1 week of behavior.

## Next steps (in value order)

1. **Split the analysis by cluster**: makers (unfollowable, but their *market
   choice* signals where retail flow is) vs directional (their round-trip
   entries/exits are study-able setups).
2. For the directional cluster: dump per-trip records (entry/exit px, hold,
   coin, pnl) and look for repeated *setups* — time-of-day, entry after N%
   moves, pyramiding patterns. This is the "how do they trade" deliverable.
3. Forward validation: snapshot today's verified-skilled list; re-run the
   funnel in 2–4 weeks and measure survivor overlap + out-of-window PnL
   (`data/fills_cache/` is the seed).
4. `--addr` deep report exists for manual study of any single account.
