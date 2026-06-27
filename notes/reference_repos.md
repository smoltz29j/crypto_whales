# Reference repos — distilled methods (2026-06-27)

Survey of four existing Hyperliquid whale/leaderboard projects, read to extract
reusable *methods, metrics, and framings* for `crypto_whales`. This is a notes
file, not a spec — it records what's worth borrowing and what to avoid.

## The four repos

| Repo | What it actually is | Usefulness |
|------|---------------------|-----------|
| **hyperliquid-smart-money** | Same approach as us: `sentiment` / `positions` / `winners_vs_losers` scripts. Real working implementation. | High — methods directly applicable |
| **hyperliquid-leaderboard-backtest** | Forward-collector testing "do top-100-PnL traders' positions predict BTC/ETH?". Python `backtest.py` + NestJS leaderboard cache + Next.js dashboard. | Medium — great idea, but conclusion never computed and methodology flawed |
| **hyperliquid_leaderboard_tracker** | React UI prototype ("HyperPulse"). **Never calls the Hyperliquid API — all data is `Math.random()` mock.** | Low — only the metric *formulas* are useful |
| **hyperliquid-whalealert-mcp** | 104-line MCP that just relays CoinGlass's `whale-alert` endpoint. Has an unimported-`datetime` bug; no HL calls. | Minimal — conceptual only |

## Where we already stand

Our data sourcing is **broader than all four**: we use `user_fills` and
`metaAndAssetCtxs`, and we cache the leaderboard. What we're missing is mostly:
(a) a **time-series / fixed-grid** view (we only take single snapshots),
(b) **skill-weighted** signal construction, and
(c) **real performance metrics from fills** (win rate, drawdown, equity curve).

---

## Methods worth borrowing (priority order)

### 1. `net_bias` — normalized conviction metric (from smart-money)
Per coin: `net_bias = (long_notional - short_notional) / gross`, range -1..+1.
Threshold at ±0.05 → LONG / SHORT / NEUTRAL. Side from sign of `szi`.
Keep **both notional and a wallet count** per side: a big net with `1L/4S` is one
whale, not a crowd — the dual signal surfaces concentration/crowdedness.
Source: `hyperliquid_sentiment.py:aggregate`.

### 2. Time-series positioning (from backtest) — our biggest gap
`whales_coin.py` is a single live snapshot. Instead, poll the skilled-whale
cohort's *signed* BTC/ETH exposure on a fixed grid (their default 5 min), track
the **change (`diff`)** over time. Refresh the cohort hourly; checkpoint to disk
incrementally for crash safety.
Source: `backtest.py` (cohort 21-81, signal 109-136, analysis 289-392).

> ⚠️ **Avoid their core flaw.** They correlate position change against the
> **contemporaneous, zero-lag** price change — that measures *herding/reaction*,
> not *prediction*. To test prediction, correlate position change at time `t`
> against **forward** returns `t→t+k`, and report a directional **hit-rate**
> (sign of net position vs sign of next-period return) — which their README
> claims but never computes. Also: raw aggregate net-USD is dominated by the
> few largest accounts, conflating skill with size (cf. MEMORY: whale = skill,
> not size) — weight/filter by skill rather than summing raw notional.

### 3. Notional-weighted "smart-money crowding" (from tracker)
Over the *skilled* whale set: `coin_notional[coin] += positionValue`, rank coins,
add a long/short % per coin → a direct signal like "skilled whales 72% long BTC
by notional." Operationalizes our core thesis; we already have `positionValue`
and signed `szi`. Source: `services/dataService.ts:calculateGlobalMetrics`.

### 4. "Whale event" schema + Open/Close verb (from whalealert)
Move from per-account ranking to an **event stream**. Event shape:
`{coin, address, signed_size, entry_px, liq_px, position_value_usd, action: Open|Close, time_ms}`.
Reconstruct faithfully from `user_fills` `dir` (Open/Close Long/Short) + `sz`*`px`
— more honest than diffing the stale leaderboard `accountValue`. The $1M notional
bar is crude but it's the *entire* definition of a commercial product; use it as a
noisy baseline for `MIN_COIN_NOTIONAL`, then layer a skill filter on top.

### 5. Implementation know-how
- **Retry/backoff**: on 429/500/502/503/504, exponential `wait = 2**attempt`
  (3 attempts) + fixed 0.5s inter-request delay + `User-Agent: Mozilla/5.0`
  header. All stdlib `urllib`. (smart-money `hyperliquid_positions.py:fetch_state`)
- **`-inf` sentinel** for missing leaderboard PnL so bad rows sink to the bottom
  and the loser cohort reflects real losses, not absent data.
- **Fields we may be dropping**: `leverageType` (cross/isolated) and `totalNtlPos`
  — useful margin/leverage denominators ("how levered is this book").
- **Composite risk score / archetype tags** (tracker `calculateRiskScore`):
  explainable buckets `Degen`/`Safe`/`Whale`/`Alpha` from avg leverage, equity,
  ROI, drawdown — fits "skill not size" framing.
- **Real win_rate / max_drawdown / equity curve**: tracker *stubs these as random*.
  That's exactly our legitimate differentiator — compute them for real from
  `user_fills` (`closedPnl > 0` fraction; drawdown/equity from the PnL+time series).
- **Server-side leaderboard cache** (backtest's NestJS service): fetch the ~32MB
  blob once / 5 min, GC batches >1h, sort/filter/paginate **in-memory** so clients
  get any metric/window without re-downloading. A richer version of our
  `data/leaderboard.json` 1h cache.

## Gaps none of them fill (our opportunity)
- Real performance metrics from fills (win rate, drawdown, equity curve).
- Skill-weighted (not size-weighted) directional signal.
- Lagged prediction test with an actual hit-rate, not zero-lag correlation.

## Cloned sources (gitignored / temp)
Clones lived under the prior session's scratchpad:
`…/58b8fdc0…/scratchpad/refs/{hyperliquid-smart-money,hyperliquid-leaderboard-backtest,hyperliquid_leaderboard_tracker,hyperliquid-whalealert-mcp}`
(temp dir — re-clone from GitHub if needed).
