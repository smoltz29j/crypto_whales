#!/usr/bin/env python3
"""Real skill metrics from fills — and a test of whether skill persists.

The leaderboard's windowed pnl is our current "skill" proxy, but it can't
distinguish a good trader from a levered lucky one. This computes *real*
performance per whale from `user_fills` (up to 2000 recent fills):

  win rate, profit factor, realized PnL net of fees, equity curve, max drawdown

and then runs the test everything else depends on (--persistence): split each
account's realized fills in half by time — does first-half skill predict
second-half PnL *cross-sectionally*? If it doesn't, following "skilled" whales
is following noise, whatever the metric.

Usage:
  python3 whales_skill.py                # metrics table for the whale cohort
  python3 whales_skill.py --persistence  # split-half skill persistence test

Caveats (by construction):
  - `user_fills` caps at the most recent 2000 fills, so the observed window
    differs per account (days for hyperactive ones, months for slow ones).
    The split-half test is within-account, which limits but doesn't remove this.
  - Win rate is per *fill*, not per round-trip trade: one position closed in
    ten partial fills votes ten times.
  - Only perp fills count (dir contains Long/Short); spot fills are dropped.
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from hl import HyperliquidInfo
import whales_coin as wc

# --- knobs (edit & rerun) ------------------------------------------------
MIN_REALIZED_FILLS = 40   # min closing fills to include in the persistence test
TOP_N = 25                # rows in the metrics table
WORKERS = 4               # concurrent user_fills fetches (429s above this after a scan)
FILLS_CACHE_AGE = 3600.0  # reuse cached fills younger than this (sec); 0 = refetch
# -------------------------------------------------------------------------

FILLS_CACHE_DIR = Path(__file__).resolve().parent / "data" / "fills_cache"


# --- fills fetch (cached) --------------------------------------------------

def fetch_fills(hl: HyperliquidInfo, addr: str) -> list[dict]:
    """user_fills with a per-address disk cache (experiments rerun often)."""
    FILLS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = FILLS_CACHE_DIR / f"{addr}.json"
    if FILLS_CACHE_AGE and cache.exists() \
            and (time.time() - cache.stat().st_mtime) < FILLS_CACHE_AGE:
        return json.loads(cache.read_text())
    fills = hl.user_fills(addr)
    tmp = cache.with_name(cache.name + ".tmp")
    tmp.write_text(json.dumps(fills))
    tmp.replace(cache)
    return fills


def perp_fills(fills: list[dict]) -> list[dict]:
    """Perp position fills only (spot dirs are Buy/Sell), oldest first."""
    keep = [f for f in fills if "Long" in f.get("dir", "") or "Short" in f.get("dir", "")]
    keep.sort(key=lambda f: f.get("time", 0))
    return keep


# --- metrics ----------------------------------------------------------------

def fill_metrics(fills: list[dict]) -> dict:
    """Performance metrics from one account's perp fills (oldest first).

    Realized fills = those with nonzero closedPnl (breakeven closes are rare
    and carry no directional information either way). Equity curve is the
    cumulative (closedPnl - fee) over *all* perp fills, so opening fees hit
    the curve too.
    """
    realized = [f for f in fills if wc.fnum(f.get("closedPnl")) != 0.0]
    wins = [f for f in realized if wc.fnum(f["closedPnl"]) > 0]
    gross_win = sum(wc.fnum(f["closedPnl"]) for f in wins)
    gross_loss = -sum(wc.fnum(f["closedPnl"]) for f in realized
                      if wc.fnum(f["closedPnl"]) < 0)
    fees = sum(wc.fnum(f.get("fee")) for f in fills)
    realized_pnl = gross_win - gross_loss

    equity = peak = max_dd = 0.0
    for f in fills:
        equity += wc.fnum(f.get("closedPnl")) - wc.fnum(f.get("fee"))
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    span_days = ((fills[-1]["time"] - fills[0]["time"]) / 86_400_000
                 if len(fills) >= 2 else 0.0)
    net = realized_pnl - fees
    return {
        "n_fills": len(fills),
        "n_realized": len(realized),
        "span_days": span_days,
        "win_rate": len(wins) / len(realized) if realized else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss else float("inf"),
        "realized_pnl": realized_pnl,
        "fees": fees,
        "net_pnl": net,
        "max_dd": max_dd,
        "pnl_per_day": net / span_days if span_days else 0.0,
    }


def collect(hl: HyperliquidInfo, whales: list[dict]) -> list[dict]:
    """whale dict + 'fills' (perp, oldest first) + 'metrics', fetched in parallel."""
    out: list[dict] = []
    n_failed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_fills, hl, w["addr"]): w for w in whales}
        for i, fut in enumerate(as_completed(futs), 1):
            if i % 25 == 0:
                print(f"  ...{i}/{len(whales)} fills fetched")
            w = futs[fut]
            try:
                fills = perp_fills(fut.result())
            except Exception:
                n_failed += 1
                continue
            out.append({**w, "fills": fills, "metrics": fill_metrics(fills)})
    if n_failed:
        print(f"warning: {n_failed}/{len(whales)} fills fetches failed",
              file=sys.stderr)
    return out


# --- rank stats (stdlib only) ----------------------------------------------

def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    for rank, i in enumerate(order):
        r[i] = float(rank)
    return r


def spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 3:
        return 0.0
    return _pearson(_ranks(xs), _ranks(ys))


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    return cov / (vx * vy) ** 0.5 if vx and vy else 0.0


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


# --- persistence test --------------------------------------------------------

def persistence(rows: list[dict]) -> None:
    """Split each account's realized fills in half by time; test whether
    first-half skill predicts second-half net PnL across accounts."""
    samples = []
    for r in rows:
        realized = [f for f in r["fills"] if wc.fnum(f.get("closedPnl")) != 0.0]
        if len(realized) < MIN_REALIZED_FILLS:
            continue
        half = len(realized) // 2
        m1, m2 = fill_metrics(realized[:half]), fill_metrics(realized[half:])
        samples.append({
            "addr": r["addr"],
            "skillPnl": r.get("skillPnl", 0.0),   # leaderboard proxy, for comparison
            "wr1": m1["win_rate"], "wr2": m2["win_rate"],
            "net1": m1["net_pnl"], "net2": m2["net_pnl"],
            "pf1": m1["profit_factor"],
        })
    n = len(samples)
    print(f"\nskill persistence (split-half, {n} accounts with >= "
          f"{MIN_REALIZED_FILLS} realized fills):\n")
    if n < 10:
        print("  too few accounts for a cross-sectional read; lower "
              "MIN_REALIZED_FILLS or widen the cohort.")
        return

    net2 = [s["net2"] for s in samples]
    base = max(sum(1 for v in net2 if v > 0), sum(1 for v in net2 if v <= 0)) / n
    print(f"  {'first-half metric':<24} {'spearman vs 2nd-half net':>25}")
    for key, label in (("wr1", "win_rate"), ("net1", "net_pnl"),
                       ("pf1", "profit_factor"), ("skillPnl", "leaderboard pnl")):
        xs = [s[key] for s in samples]
        # profit_factor can be inf (no losses); clamp for ranking
        xs = [min(x, 1e9) for x in xs]
        print(f"  {label:<24} {spearman(xs, net2):>+25.2f}")

    # Quadrant view: top vs bottom half by first-half win rate.
    by_wr = sorted(samples, key=lambda s: -s["wr1"])
    top, bot = by_wr[: n // 2], by_wr[n // 2:]
    med_top = _median([s["net2"] for s in top])
    med_bot = _median([s["net2"] for s in bot])
    pos_top = sum(1 for s in top if s["net2"] > 0) / len(top)
    pos_bot = sum(1 for s in bot if s["net2"] > 0) / len(bot)
    print(f"\n  by first-half win_rate:   median 2nd-half net    P(2nd-half net > 0)")
    print(f"    top half  ({len(top):>3})       {wc.fmt_usd(med_top):>12}"
          f"              {pos_top:>4.0%}")
    print(f"    bottom half ({len(bot):>3})     {wc.fmt_usd(med_bot):>12}"
          f"              {pos_bot:>4.0%}")
    print(f"    (const-guess base rate for sign of 2nd-half net: {base:.0%})")


# --- output ------------------------------------------------------------------

def print_table(rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: -r["metrics"]["net_pnl"])
    active = [r for r in rows if r["metrics"]["n_realized"] > 0]
    print(f"\nfills-based skill metrics ({len(active)}/{len(rows)} whales with "
          f"realized perp fills; top {min(TOP_N, len(active))} by net PnL):\n")
    print(f"  {'address':<12} {'fills':>5} {'days':>6} {'winR':>5} {'PF':>5} "
          f"{'realized':>10} {'fees':>8} {'net':>10} {'maxDD':>9} {'net/day':>9}")
    for r in active[:TOP_N]:
        m = r["metrics"]
        pf = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "inf"
        print(f"  {r['addr'][:10]+'..':<12} {m['n_fills']:>5} {m['span_days']:>6.1f} "
              f"{m['win_rate']:>5.0%} {pf:>5} {wc.fmt_usd(m['realized_pnl']):>10} "
              f"{wc.fmt_usd(m['fees']):>8} {wc.fmt_usd(m['net_pnl']):>10} "
              f"{wc.fmt_usd(m['max_dd']):>9} {wc.fmt_usd(m['pnl_per_day']):>9}")


def main(argv: list[str]) -> None:
    # Extra retries: the 1500-account scan right before drains the API's
    # rate budget, so the first fills calls often 429 until it replenishes.
    hl = HyperliquidInfo(retries=4)
    whales = wc.scan_whales(hl, progress=True)
    print(f"\nfetching fills for {len(whales)} whales ...")
    rows = collect(hl, whales)
    if "--persistence" in argv:
        persistence(rows)
    else:
        print_table(rows)


if __name__ == "__main__":
    main(sys.argv[1:])
