#!/usr/bin/env python3
"""Rank whales by their position in specific coins (default: BTC, ETH).

The leaderboard ranks by *total account value*, not by per-coin exposure, so to
find "BTC/ETH whales" we scan the top accounts and keep only those holding a
meaningful position in the target coins, then rank by that coin notional.

Run:  python3 whales_coin.py
Tweak the knobs below and rerun.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from hl import HyperliquidInfo

# --- knobs (edit & rerun) ------------------------------------------------
COINS = {"BTC", "ETH"}          # which coins define the whale
SCAN_TOP_N = 1500               # how many top-accountValue addresses to inspect
MIN_COIN_NOTIONAL = 1_000_000   # USD: min summed BTC+ETH position to count as a whale
TOP_N = 25                      # how many whales to print
WORKERS = 10                    # concurrent clearinghouse_state queries
BIAS_THRESHOLD = 0.05           # |net_bias| below this -> NEUTRAL (else LONG/SHORT)
SKILL_WINDOW = "allTime"        # which leaderboard window defines "skill" (pnl)
MIN_SKILL_PNL = 0.0             # only whales with window pnl above this vote in skill bias
# -------------------------------------------------------------------------


def fnum(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def window_pnl(row: dict, window: str = SKILL_WINDOW) -> float:
    """allTime/day/week/month pnl from a leaderboard row's windowPerformances.

    windowPerformances is a list of [name, {pnl, roi, vlm}] pairs (not a dict).
    """
    for name, perf in row.get("windowPerformances", []):
        if name == window:
            return fnum(perf.get("pnl"))
    return 0.0


def fmt_usd(v: float) -> str:
    """Compact signed USD: $1.2B / $220.2M / $809K / $42."""
    sign = "-" if v < 0 else ""
    a = abs(v)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return f"{sign}${a / div:.1f}{suf}"
    return f"{sign}${a:.0f}"


def aggregate_sentiment(whales: list[dict]) -> dict[str, dict]:
    """Notional-weighted long/short aggregate over the whale set, per coin (#3).

    For each target coin, sum |positionValue| on each side and count wallets,
    then derive net_bias = (long - short) / gross in [-1, +1] (#1). The dual
    notional+wallet signal exposes concentration: a big net with 1L/4S is one
    whale, not a crowd.

    Caveat: this cohort is selected by *size* (MIN_COIN_NOTIONAL), not skill, so
    the aggregate is notional-weighted, not skill-weighted -- see
    notes/reference_repos.md.
    """
    agg: dict[str, dict] = {}
    for w in whales:
        for coin, p in w["positions"].items():
            szi = fnum(p["szi"])
            notional = abs(fnum(p.get("positionValue")))
            a = agg.setdefault(
                coin,
                {"long_ntl": 0.0, "short_ntl": 0.0, "long_n": 0, "short_n": 0},
            )
            if szi > 0:
                a["long_ntl"] += notional
                a["long_n"] += 1
            elif szi < 0:
                a["short_ntl"] += notional
                a["short_n"] += 1
    for a in agg.values():
        gross = a["long_ntl"] + a["short_ntl"]
        a["gross"] = gross
        a["net"] = a["long_ntl"] - a["short_ntl"]
        a["net_bias"] = a["net"] / gross if gross else 0.0
        b = a["net_bias"]
        a["lean"] = "LONG" if b > BIAS_THRESHOLD else "SHORT" if b < -BIAS_THRESHOLD else "NEUTRAL"
    return agg


def print_sentiment(agg: dict[str, dict]) -> None:
    if not agg:
        return
    print("\nwhale positioning by coin (notional-weighted, net_bias in [-1,+1]):\n")
    print(f"  {'COIN':4s}  {'LONG':>9s}  {'SHORT':>9s}  {'NET':>9s}  "
          f"{'BIAS':>6s}  {'LEAN':<8s} wallets")
    for coin in sorted(agg, key=lambda c: -agg[c]["gross"]):
        a = agg[coin]
        print(f"  {coin:4s}  {fmt_usd(a['long_ntl']):>9s}  {fmt_usd(a['short_ntl']):>9s}  "
              f"{fmt_usd(a['net']):>9s}  {a['net_bias']:>+6.2f}  {a['lean']:<8s} "
              f"{a['long_n']}L/{a['short_n']}S")


def skill_weighted_sentiment(whales: list[dict]) -> dict[str, dict]:
    """Directional bias weighted by trader skill instead of position size.

    Counts only *proven* whales (window pnl > MIN_SKILL_PNL) and weights each
    one's directional vote (long=+1 / short=-1) by their skill pnl, so the
    signal is "what do the good traders lean" -- decoupled from notional size
    (cf. MEMORY: whale = skill, not size). skill_bias in [-1, +1].
    """
    agg: dict[str, dict] = {}
    for w in whales:
        skill = w.get("skillPnl", 0.0)
        if skill <= MIN_SKILL_PNL:
            continue
        for coin, p in w["positions"].items():
            szi = fnum(p["szi"])
            if szi == 0:
                continue
            a = agg.setdefault(
                coin, {"signed_w": 0.0, "total_w": 0.0, "long_n": 0, "short_n": 0}
            )
            direction = 1.0 if szi > 0 else -1.0
            a["signed_w"] += direction * skill
            a["total_w"] += skill
            if szi > 0:
                a["long_n"] += 1
            else:
                a["short_n"] += 1
    for a in agg.values():
        b = a["signed_w"] / a["total_w"] if a["total_w"] else 0.0
        a["skill_bias"] = b
        a["lean"] = "LONG" if b > BIAS_THRESHOLD else "SHORT" if b < -BIAS_THRESHOLD else "NEUTRAL"
    return agg


def print_skill_sentiment(agg: dict[str, dict], n_skilled: int, n_total: int) -> None:
    if not agg:
        return
    print(f"\nskill-weighted positioning ({n_skilled}/{n_total} whales with "
          f"{SKILL_WINDOW} pnl > ${MIN_SKILL_PNL:,.0f}, vote weighted by pnl):\n")
    print(f"  {'COIN':4s}  {'SKILL_BIAS':>10s}  {'LEAN':<8s} skilled wallets")
    for coin in sorted(agg, key=lambda c: -abs(agg[c]["skill_bias"])):
        a = agg[coin]
        print(f"  {coin:4s}  {a['skill_bias']:>+10.2f}  {a['lean']:<8s} "
              f"{a['long_n']}L/{a['short_n']}S")


def coin_positions(chs: dict) -> dict[str, dict]:
    """coin -> position dict, restricted to COINS and nonzero size."""
    out = {}
    for ap in chs.get("assetPositions", []):
        p = ap["position"]
        if p["coin"] in COINS and fnum(p["szi"]) != 0:
            out[p["coin"]] = p
    return out


def scan_address(hl: HyperliquidInfo, row: dict) -> dict | None:
    """None = scanned but not a whale. Fetch errors propagate — scan_whales
    counts them so a time series can tell 'fewer whales' from 'more errors'."""
    addr = row["ethAddress"]
    chs = hl.clearinghouse_state(addr)
    pos = coin_positions(chs)
    if not pos:
        return None
    notional = sum(abs(fnum(p.get("positionValue"))) for p in pos.values())
    if notional < MIN_COIN_NOTIONAL:
        return None
    return {
        "addr": addr,
        "accountValue": fnum(chs["marginSummary"]["accountValue"]),
        "coinNotional": notional,
        "skillPnl": window_pnl(row),
        "positions": pos,
    }


def scan_whales(hl: HyperliquidInfo, progress: bool = False,
                stats: dict | None = None) -> list[dict]:
    """Scan the top SCAN_TOP_N accounts and return those that are COINS whales,
    sorted by coin notional. Reused by main() and whales_track.py.

    Pass a `stats` dict to receive n_scanned/n_failed — a snapshot with many
    failed fetches is a degraded reading, not a smaller whale cohort.
    """
    lb = hl.leaderboard()
    lb.sort(key=lambda r: -fnum(r["accountValue"]))
    candidates = lb[:SCAN_TOP_N]
    if progress:
        print(f"scanning top {len(candidates):,} accounts for {sorted(COINS)} "
              f"positions >= ${MIN_COIN_NOTIONAL:,} ...")
    whales: list[dict] = []
    n_failed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(scan_address, hl, r) for r in candidates]
        for i, fut in enumerate(as_completed(futs), 1):
            if progress and i % 250 == 0:
                print(f"  ...{i}/{len(candidates)} scanned, {len(whales)} whales so far")
            try:
                res = fut.result()
            except Exception:
                n_failed += 1
                continue
            if res:
                whales.append(res)
    if n_failed:
        print(f"warning: {n_failed}/{len(candidates)} account fetches failed "
              f"(after retries); cohort is incomplete", file=sys.stderr)
    if stats is not None:
        stats["n_scanned"] = len(candidates)
        stats["n_failed"] = n_failed
    whales.sort(key=lambda w: -w["coinNotional"])
    return whales


def main() -> None:
    hl = HyperliquidInfo()
    whales = scan_whales(hl, progress=True)
    print(f"\nfound {len(whales)} {sorted(COINS)} whales "
          f"(showing top {min(TOP_N, len(whales))} by coin notional)\n")

    for w in whales[:TOP_N]:
        print(f"{w['addr']}  acctValue=${w['accountValue']:>13,.0f}  "
              f"{'+'.join(sorted(COINS))}Notional=${w['coinNotional']:>13,.0f}")
        for coin in sorted(w["positions"]):
            p = w["positions"][coin]
            side = "LONG " if fnum(p["szi"]) > 0 else "SHORT"
            print(f"     {side} {coin:4s} ${abs(fnum(p.get('positionValue'))):>13,.0f}  "
                  f"szi={p['szi']:>14s}  uPnL=${fnum(p['unrealizedPnl']):>+12,.0f}  "
                  f"lev={p['leverage']['value']}x  liqPx={p.get('liquidationPx')}")

    print_sentiment(aggregate_sentiment(whales))
    n_skilled = sum(1 for w in whales if w.get("skillPnl", 0.0) > MIN_SKILL_PNL)
    print_skill_sentiment(skill_weighted_sentiment(whales), n_skilled, len(whales))


if __name__ == "__main__":
    main()
