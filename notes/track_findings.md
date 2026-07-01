# whale_track prediction-test readings (dated, append-only)

Each entry: `whales_track.py --analyze --horizon 1,4,8,12,24` on the series to
date. Keep past readings — the point is to see whether conclusions survive as
data accumulates.

## 2026-07-02 — 109 snapshots (~4.5 days hourly)

```
h=1 :  BTC 53% (base 54%)   ETH 47% (base 53%)   spread 47% (base 53%)
h=4 :  BTC 43% (base 57%)   ETH 57% (base 57%)   spread 47% (base 53%)
h=8 :  BTC 47% (base 53%)   ETH 49% (base 51%)   spread 43% (base 57%)
h=12:  BTC 39% (base 61%)   ETH 50% (base 50%)   spread 36% (base 64%)
h=24:  BTC 28% (base 72%)   ETH 52% (base 52%)   spread  7% (base 93%)
```

**Read: no positive edge at any horizon.** Every hit-rate is at or below the
const-guess base rate.

The eye-catching part — BTC corr going *negative* with horizon (−0.05 at h=1 →
−0.27 at h=24) and the h=24 spread hitting 7% vs base 93% — is **not** evidence
of a contrarian signal yet, for two reasons:

1. **The windows overlap massively.** 85 pairs at h=24 are 24h windows shifted
   1h apart; the effective number of independent observations in 4.5 days is
   ~4–5. Any single multi-day trend dominates.
2. **The base rates say this was one trend.** base=72% (BTC h=24) and 93%
   (ratio h=24) mean price/ratio moved the same direction nearly the whole
   period. Skilled whales leaned against that one trend and were wrong (or
   early) — that's one anecdote, not a pattern.

**Decision: keep the cron running, re-test at ~30 days (~720 snapshots), when
h=24 has ~30 non-overlapping windows.** If the negative correlation *persists*
across regimes, the actionable version is a fade signal — but don't flip the
sign on 4.5 days of data.
