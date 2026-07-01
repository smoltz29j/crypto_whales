# Fills-based skill metrics + persistence test — first reading (2026-07-02)

`whales_skill.py` computes *real* per-whale performance from `user_fills`
(win rate / profit factor / realized PnL net of fees / equity curve / max
drawdown) instead of trusting the leaderboard's windowed pnl. `--persistence`
runs the test everything else depends on: split each account's realized fills
in half by time — does first-half skill predict second-half net PnL across
accounts?

## Result: skill persists, and fills-metrics beat the leaderboard proxy

133 whales (of 152 in the BTC/ETH cohort) had >= 40 realized fills:

```
first-half metric        spearman vs 2nd-half net
win_rate                                    +0.54
net_pnl                                     +0.62
profit_factor                               +0.55
leaderboard pnl (proxy)                     +0.22

by first-half win_rate:  median 2nd-half net   P(net2 > 0)
  top half   (66)                  $59.3K          85%
  bottom half(67)                  -$3.6K          40%
  (const-guess base rate: 62%)
```

Two claims, different confidence:

1. **[solid] Fills-based metrics rank future performance far better than the
   leaderboard pnl we currently use as the skill weight** (+0.54..0.62 vs
   +0.22, same sample). Whatever the caveats below do to the absolute numbers,
   they apply to both sides of this comparison.
2. **[weaker] Skill persists** (top-half win_rate → 85% positive next-half vs
   40% for bottom half). Inflated by the caveats below; treat as encouraging,
   not proven.

## Caveats (read before believing)

- **Adjacent halves share a regime.** The 2000-fill window is days-to-weeks;
  first/second half often contain the *same* trend, sometimes the same
  position closed in partials across the split. Some "persistence" is just
  one good trade straddling the boundary.
- **Survivorship.** The cohort = accounts holding >= $1M BTC/ETH *today*.
  Whales who blew up last month aren't in the sample; that mechanically
  raises persistence.
- **"Close winners, ride losers" inflates win rate.** Win rate counts only
  *realized* fills — an account sitting on a huge unrealized loss can show
  100% win rate (several top-table whales do show 100%/inf PF; a couple look
  like maker/grid styles). Win rate alone is not a skill metric here; net PnL
  and PF suffer this less but not zero. A stricter version would mark open
  positions to market (add uPnL from clearinghouse_state at both split points
  — only possible forward, not retrospectively).
- 2000-fill cap → per-account windows differ wildly (0.2 to 574 days in the
  table). Split-half is within-account so comparisons are fair, but "skill"
  measured over 12 hours vs 6 months are different animals.

## Implications / next steps

- **Switch the skill weight**: `whales_coin.skill_weighted_sentiment` weights
  by leaderboard `windowPerformances` pnl. Replace/augment with fills-based
  net PnL (or PF) — the +0.22 vs +0.62 gap says the current weight is mostly
  noise. Costs one `user_fills` call per whale in the hourly cron (~150 calls;
  fine with the 429 backoff + fills cache).
- **Forward version of the persistence test**: snapshot each whale's fills
  metrics now, re-measure in N weeks against *out-of-window* PnL (kills the
  shared-regime and survivorship problems at once). The fills cache in
  `data/fills_cache/` is the seed for this.
- Ops note: the 1500-account scan drains the API rate budget, so the fills
  fetches right after it 429 for a while — `hl/client.py` now backs off
  exponentially on 429 (2/4/8/16s), `whales_skill.py` uses retries=4 and
  WORKERS=4, and fills are disk-cached 1h per address.
