#!/usr/bin/env python3
"""Track skilled-whale BTC/ETH positioning over time, then test it predicts.

Each run appends one snapshot (skilled-whale skill_bias + notional net_bias per
coin, plus current mark prices and the BTC/ETH ratio) to a JSONL time series.
Once enough snapshots accumulate, `--analyze` measures whether the signal *leads*
price: it correlates the signal at time t against the **forward** return over the
next H steps and reports a directional hit-rate.

This deliberately avoids the reference backtest's flaw of correlating against the
*contemporaneous* (zero-lag) price change, which measures herding, not prediction
(see notes/reference_repos.md).

Usage:
  python3 whales_track.py                        # take one snapshot, append to the series
  python3 whales_track.py --analyze              # analyze the accumulated series
  python3 whales_track.py --analyze --horizon 4  # ... at a specific horizon (or "1,4,24")
  python3 whales_track.py --show                 # print the raw series

Build a series by running the snapshot on a schedule (cron / `/loop`), e.g. hourly.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from hl import HyperliquidInfo
import whales_coin as wc

# --- knobs ---------------------------------------------------------------
RATIO_COINS = ("BTC", "ETH")     # ratio = price[0] / price[1]
HORIZON_STEPS = 1                 # forward look-ahead (in snapshots) for prediction test
# -------------------------------------------------------------------------

SERIES_PATH = Path(__file__).resolve().parent / "data" / "whale_track.jsonl"


def mark_prices(hl: HyperliquidInfo, coins) -> dict[str, float]:
    """coin -> mark price, from metaAndAssetCtxs (universe and ctxs are parallel)."""
    meta, ctxs = hl.meta_and_asset_ctxs()
    out: dict[str, float] = {}
    for asset, ctx in zip(meta["universe"], ctxs):
        if asset["name"] in coins:
            out[asset["name"]] = wc.fnum(ctx.get("markPx"))
    return out


def snapshot(hl: HyperliquidInfo) -> dict:
    """One time-series point: prices + skilled/notional bias per coin."""
    stats: dict = {}
    whales = wc.scan_whales(hl, progress=True, stats=stats)
    skill = wc.skill_weighted_sentiment(whales)
    ntl = wc.aggregate_sentiment(whales)
    prices = mark_prices(hl, set(RATIO_COINS))
    n_skilled = sum(1 for w in whales if w.get("skillPnl", 0.0) > wc.MIN_SKILL_PNL)
    return {
        "time_ms": int(time.time() * 1000),
        "n_whales": len(whales),
        "n_skilled": n_skilled,
        "n_failed": stats.get("n_failed", 0),
        "prices": prices,
        "skill_bias": {c: skill.get(c, {}).get("skill_bias", 0.0) for c in RATIO_COINS},
        "ntl_bias": {c: ntl.get(c, {}).get("net_bias", 0.0) for c in RATIO_COINS},
    }


def append_snapshot(snap: dict) -> None:
    SERIES_PATH.parent.mkdir(exist_ok=True)
    with SERIES_PATH.open("a") as f:
        f.write(json.dumps(snap) + "\n")


def load_series() -> list[dict]:
    if not SERIES_PATH.exists():
        return []
    return [json.loads(line) for line in SERIES_PATH.read_text().splitlines() if line.strip()]


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    return cov / (vx * vy) ** 0.5 if vx and vy else 0.0


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _base_rate(fwd_rets: list[float]) -> float:
    """Best constant-guess hit-rate (always-up or always-down, whichever wins).
    A hit-rate is only informative above this."""
    ups = sum(1 for r in fwd_rets if r > 0)
    downs = sum(1 for r in fwd_rets if r < 0)
    return max(ups, downs) / (ups + downs) if (ups + downs) else 0.0


def _hit_rate(signals: list[float], fwd_rets: list[float]) -> tuple[int, int]:
    """(hits, n): hit = sign(signal) matches sign(forward return); skips zeros."""
    hits = n = 0
    for s, r in zip(signals, fwd_rets):
        if s == 0 or r == 0:
            continue
        n += 1
        if (s > 0) == (r > 0):
            hits += 1
    return hits, n


def analyze(series: list[dict], horizon: int = HORIZON_STEPS) -> None:
    a, b = RATIO_COINS
    need = horizon + 2
    if len(series) < need:
        print(f"need >= {need} snapshots to analyze (have {len(series)}). "
              f"Run the snapshot on a schedule to accumulate the series.")
        return

    def px(s, c):
        return s["prices"].get(c, 0.0)

    # A "horizon" is measured in *steps*, so it only means a fixed time span if
    # snapshots are evenly spaced. Missed cron runs create 2-3h gaps whose
    # returns aren't comparable to 1h ones — drop pairs far from the median gap.
    dts = [series[t + horizon]["time_ms"] - series[t]["time_ms"]
           for t in range(len(series) - horizon)]
    med = _median(dts)
    keep = [t for t, dt in enumerate(dts) if 0.5 * med <= dt <= 1.5 * med]

    print(f"analyzing {len(series)} snapshots, horizon = {horizon} step(s) "
          f"(median gap {med / 3.6e6:.2f}h), forward (lagged) returns:")
    if len(keep) < len(dts):
        print(f"  note: dropped {len(dts) - len(keep)} pair(s) with irregular "
              f"spacing (outside 0.5-1.5x the median gap)")
    print()

    # Per-coin: skill_bias(t) vs that coin's forward return.
    for c in RATIO_COINS:
        sig, fwd = [], []
        for t in keep:
            p0, p1 = px(series[t], c), px(series[t + horizon], c)
            if p0 <= 0 or p1 <= 0:
                continue
            sig.append(series[t]["skill_bias"][c])
            fwd.append(p1 / p0 - 1.0)
        hits, n = _hit_rate(sig, fwd)
        corr = _pearson(sig, fwd)
        hr = f"{hits}/{n} ({hits / n:.0%})" if n else "n/a"
        print(f"  {c:4s} skill_bias -> fwd return : corr={corr:>+5.2f}  "
              f"hit-rate={hr}  const-guess base={_base_rate(fwd):.0%}")

    # Ratio (the pairs/dominance trade): skill_bias[a] - skill_bias[b] vs fwd ratio return.
    sig, fwd = [], []
    for t in keep:
        r0a, r0b = px(series[t], a), px(series[t], b)
        r1a, r1b = px(series[t + horizon], a), px(series[t + horizon], b)
        if min(r0a, r0b, r1a, r1b) <= 0:
            continue
        ratio0, ratio1 = r0a / r0b, r1a / r1b
        sig.append(series[t]["skill_bias"][a] - series[t]["skill_bias"][b])
        fwd.append(ratio1 / ratio0 - 1.0)
    hits, n = _hit_rate(sig, fwd)
    corr = _pearson(sig, fwd)
    hr = f"{hits}/{n} ({hits / n:.0%})" if n else "n/a"
    print(f"\n  ({a}-{b}) skill_bias spread -> fwd {a}/{b} ratio return : "
          f"corr={corr:>+5.2f}  hit-rate={hr}  const-guess base={_base_rate(fwd):.0%}")
    print(f"  (positive spread = lean long {a} / short {b})")


def show(series: list[dict]) -> None:
    a, b = RATIO_COINS
    print(f"{'time':<20} {'n_sk':>5} {a+'_px':>10} {b+'_px':>9} "
          f"{'ratio':>7} {a+'_skB':>7} {b+'_skB':>7}")
    for s in series:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["time_ms"] / 1000))
        pa, pb = s["prices"].get(a, 0.0), s["prices"].get(b, 0.0)
        ratio = pa / pb if pb else 0.0
        print(f"{ts:<20} {s['n_skilled']:>5} {pa:>10,.0f} {pb:>9,.0f} "
              f"{ratio:>7.2f} {s['skill_bias'][a]:>+7.2f} {s['skill_bias'][b]:>+7.2f}")


def _horizons(argv: list[str]) -> list[int]:
    """Parse --horizon N or --horizon N,M,... (defaults to [HORIZON_STEPS])."""
    if "--horizon" not in argv:
        return [HORIZON_STEPS]
    try:
        raw = argv[argv.index("--horizon") + 1]
        hs = [int(x) for x in raw.split(",")]
        if not hs or any(h < 1 for h in hs):
            raise ValueError(raw)
        return hs
    except (IndexError, ValueError):
        sys.exit("--horizon needs a positive step count, e.g. --horizon 4 or --horizon 1,4,24")


def main(argv: list[str]) -> None:
    if "--analyze" in argv:
        series = load_series()
        for i, h in enumerate(_horizons(argv)):
            if i:
                print()
            analyze(series, horizon=h)
        return
    if "--show" in argv:
        show(load_series())
        return
    hl = HyperliquidInfo()
    snap = snapshot(hl)
    append_snapshot(snap)
    a, b = RATIO_COINS
    pa, pb = snap["prices"].get(a, 0.0), snap["prices"].get(b, 0.0)
    ratio = pa / pb if pb else 0.0
    print(f"\nsnapshot @ {time.strftime('%Y-%m-%d %H:%M')}  "
          f"({snap['n_skilled']}/{snap['n_whales']} skilled whales)")
    print(f"  {a}=${pa:,.0f}  {b}=${pb:,.0f}  {a}/{b} ratio={ratio:.2f}")
    print(f"  skill_bias: {a} {snap['skill_bias'][a]:+.2f}  {b} {snap['skill_bias'][b]:+.2f}")
    print(f"  appended to {SERIES_PATH}  (total {len(load_series())} snapshots)")
    print(f"  run with --analyze once several snapshots accumulate.")


if __name__ == "__main__":
    main(sys.argv[1:])
