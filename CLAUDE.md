# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**詳細な引き継ぎは `HANDOFF.md` を読むこと**（ユーザー方針・依頼パターン・APIクックブック・確定した知見・落とし穴・申し送り。日本語）。

## What this is

A research project on **Hyperliquid (HYPE) — the HyperCore perpetuals exchange**.
**Focus (pivoted 2026-07-02): find *skilled* traders regardless of size, and analyze HOW they
trade** — style/method fingerprinting, explicitly *not* simple copy-trading. The whale-cohort
scripts predate the pivot and still run (hourly cron), but `skilled.py` is the current surface.
Output format (CLI / alerts / dashboard) is intentionally undecided — expect experiment
scripts, not a finished product.

## Commands

```bash
python3 explore.py     # sample every data source: market OI, leaderboard shape, one whale's state
python3 whales.py      # select whales by total account value, print their live positions
python3 whales_coin.py # rank whales by per-coin exposure (default BTC+ETH) -- the current focus
python3 whales_skill.py # real skill metrics from fills; --persistence tests if skill persists
python3 skilled.py     # THE CURRENT FOCUS: size-agnostic skilled-BTC-trader finder + style fingerprints
python3 skilled.py --addr 0x…  # deep style report for one address
python3 trips.py       # per-trip setup analysis of the directional skilled cluster
python3 trips.py --addr 0x…    # per-trip listing for one address
```

No dependencies to install — scripts use only the Python 3 stdlib (`urllib`, `json`).
`requirements.txt` lists optional libs (pandas, httpx) to uncomment when analysis grows.

The Hyperliquid Info API needs **no authentication**; everything runs against the public mainnet.

## Architecture

- **`hl/client.py` — `HyperliquidInfo`**: the only place that talks to Hyperliquid. All market
  and per-account *reads* go through one POST endpoint (`https://api.hyperliquid.xyz/info`) with a
  `{"type": ...}` body. The **leaderboard** is the one exception — it lives on a separate static host
  (`stats-data.hyperliquid.xyz/Mainnet/leaderboard`). Add new endpoints as methods here, not inline.
- **`explore.py`**: read-only sampler. Edit freely to eyeball a new endpoint's shape.
- **`whales.py`**: the experiment surface for the open question *"what is a whale?"* by total account
  value. The knobs (`MIN_ACCOUNT_VALUE`, `WINDOW`, `INCLUDE_LOSERS`, `TOP_N`) are module-level
  constants meant to be tweaked and rerun. Whale *definition* and *performance filtering* live here.
- **`whales_coin.py`**: the **current focus** — whales by *per-coin* exposure (default `COINS={"BTC","ETH"}`),
  since the leaderboard ranks by account value, not per-coin notional. It scans the top
  `SCAN_TOP_N` accounts with a thread pool (`WORKERS`), keeps those whose summed target-coin notional
  exceeds `MIN_COIN_NOTIONAL`, and ranks by that. ~21s for 1500 accounts. Caveat: scanning by
  account-value rank can miss a high-leverage account with a huge coin position but modest equity —
  raise `SCAN_TOP_N` to widen the net.
- **`data/`**: gitignored cache. The leaderboard is ~32MB; `client.leaderboard()` caches it to
  `data/leaderboard.json` and refetches only when older than `max_age_sec` (default 1h). Pass
  `max_age_sec=0` to force a refresh. Writes are validated + atomic (tmp file + rename), and a
  failed refresh falls back to the stale cache instead of raising — the hourly cron must not die
  on one bad download.
- **`skilled.py`** — **the current focus**: size-agnostic skilled-trader finder + style analysis,
  **restricted to BTC** (`COINS = {"BTC"}`; set to `None` for all coins). Funnels the full
  leaderboard via three routes (top month-pnl / week-pnl / month-roi with a volume floor — the roi
  route admits small accounts), verifies skill from the COINS-restricted fills (closes/span/net/PF
  knobs), then fingerprints each survivor's *method*: flat-to-flat round-trip hold time,
  maker/taker share, BTC-share-of-book (`BTC-only`/`-main`/`-side`), long/short lean, clip size →
  archetype tag (`swing/maker/BTC-main/short`). Findings so far (`notes/skilled_findings.md`):
  all-coin top PF is mostly *thin-market makers* (unfollowable by design); in deep-book BTC the
  biggest verified cluster is intraday takers. Lean labels are only meaningful when maker% is low.
- **`trips.py`**: the step after `skilled.py` — per-trip records for the *directional* skilled
  cluster (>= `MIN_TRIPS` flat-to-flat round trips): entry/exit px, hold, adds, per-trip maker
  share, pnl → `data/trips_btc.jsonl`, plus setup analysis against 1h candles
  (`HyperliquidInfo.candles`): time-of-day, momentum-vs-fade (prior 4h move), pyramiding,
  loss-cut speed. First reading (`notes/trips_findings.md`): the near-universal signature of
  verified skill is *cut losses fast, let wins run* (16/16, median loss/win hold ratio 0.30);
  entries are fades (~⅓ momentum-aligned), triggered by volatility, clustered at NY open.
- **`whales_skill.py`**: *real* per-whale performance from `user_fills` (win rate, profit factor,
  net-of-fees PnL, equity curve, max drawdown) instead of the leaderboard pnl proxy; `--persistence`
  split-half-tests whether skill persists (first reading: yes, and fills metrics beat the proxy
  +0.54..0.62 vs +0.22 Spearman — see `notes/skill_findings.md` for caveats). Fills are disk-cached
  1h in `data/fills_cache/`; the client backs off on 429 (post-scan fills fetches drain rate budget).
- **`whales_track.py`**: hourly cron appends one snapshot (skill/notional bias per coin + mark
  prices + `n_failed` fetch errors) to `data/whale_track.jsonl`; `--analyze` tests whether the
  signal predicts **forward** returns (hit-rate vs a const-guess base rate, median-gap spacing
  guard against missed cron runs). See `notes/review_2026-07-02.md` for the schema/analysis details.
- **`btc/` + `btc_flows.py`**: a *second data domain* — on-chain Bitcoin base-chain flows, not
  Hyperliquid. `btc/client.py` (`Esplora`) reads the public mempool.space/blockstream Esplora API
  (no auth, values in **satoshis**; `address_txs_paged` walks history for 芋づる tracing);
  `btc/watchlist.py` is the curated entity→address layer (balance-verified Binance/Bitfinex
  cold+hot); `btc_flows.py` flags large IN/OUT balance moves per watched entity with counterparty
  labels. Attribution — not visibility — is the hard part. Two label sources feed it:
  `btc/labels_import.py` pulls **free, no-key** GraphSense tagpacks (~336k BTC address→entity
  labels: every major exchange's published wallets + one ETF) into `data/btc_labels.json`, overlaid
  under the curated watchlist for counterparty naming (cache keys are lowercased for lookups, but
  the `addr` field keeps original case — **base58 addresses are case-sensitive**, only `addr` can
  be used in API queries); `btc/expand.py` profiles labeled-but-unwatched wallets (one `/address`
  call each, cached in `data/btc_profile.json`) and prints watchlist-ready entries — the 2026-07-05
  pass grew the watchlist to ~759k BTC / 11 entities (Binance reserves, OKX, Crypto.com, Huobi,
  Bybit); `btc_track.py` (hourly cron at :35) appends per-entity balance + confirmed IN/OUT/NET
  since the previous snapshot to `data/btc_track.jsonl` with the BTC mark price, and `--analyze`
  tests hot-wallet net flow against **forward** BTC returns (series clean from 2026-07-05);
  `btc/arkham.py` + `arkham_flows.py` is the **labeled-API** path (needs `ARKHAM_API_KEY`, free
  tier) for custodial/omnibus/clustered entities the free data can't attribute (Coinbase,
  BlackRock/IBIT, MicroStrategy). See `notes/btc_onchain.md`.

## Data model (what HyperCore actually exposes)

The whale workflow is **discover addresses from the leaderboard → query each address**; there is no
public market-wide fill feed. Key shapes:

- **`leaderboard()`** → ~39.5k rows: `ethAddress`, `accountValue`, and `windowPerformances`
  (`day`/`week`/`month`/`allTime`, each with `pnl`/`roi`/`vlm`). This is the whale-discovery and
  performance-ranking source.
- **`clearinghouse_state(addr)`** → live perp state: `marginSummary` (accountValue, totalNtlPos) and
  `assetPositions[].position` (`coin`, `szi` signed size, `positionValue`, `unrealizedPnl`,
  `liquidationPx`, `leverage`).
- **`user_fills(addr)`** → up to 2000 recent fills: `coin`, `px`, `sz`, `dir` (Open/Close Long/Short),
  `closedPnl` (realized PnL per trade), `fee`, `time` (ms). Use `user_fills_by_time` for incremental polling.

## Gotchas (observed, not theoretical)

- **Leaderboard `accountValue` is a stale snapshot.** Top-by-`accountValue` rows often show $0 live
  notional and 0 positions in `clearinghouse_state` (vaults / inactive / settled accounts). Trust
  `clearinghouse_state` for current reality; treat leaderboard numbers as a ranking hint only.
- **`roi` can be wildly large** (e.g. +32955) for accounts seeded with tiny capital — don't rank on
  `roi` alone; combine with absolute `pnl` and live notional.
- All numeric fields come back as **strings**; coerce with a tolerant float helper (see `fnum`).
- `liquidationPx` is `null` for many cross-margin positions; don't assume it's always present.
