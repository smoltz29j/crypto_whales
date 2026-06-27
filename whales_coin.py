#!/usr/bin/env python3
"""Rank whales by their position in specific coins (default: BTC, ETH).

The leaderboard ranks by *total account value*, not by per-coin exposure, so to
find "BTC/ETH whales" we scan the top accounts and keep only those holding a
meaningful position in the target coins, then rank by that coin notional.

Run:  python3 whales_coin.py
Tweak the knobs below and rerun.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from hl import HyperliquidInfo

# --- knobs (edit & rerun) ------------------------------------------------
COINS = {"BTC", "ETH"}          # which coins define the whale
SCAN_TOP_N = 1500               # how many top-accountValue addresses to inspect
MIN_COIN_NOTIONAL = 1_000_000   # USD: min summed BTC+ETH position to count as a whale
TOP_N = 25                      # how many whales to print
WORKERS = 10                    # concurrent clearinghouse_state queries
# -------------------------------------------------------------------------


def fnum(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def coin_positions(chs: dict) -> dict[str, dict]:
    """coin -> position dict, restricted to COINS and nonzero size."""
    out = {}
    for ap in chs.get("assetPositions", []):
        p = ap["position"]
        if p["coin"] in COINS and fnum(p["szi"]) != 0:
            out[p["coin"]] = p
    return out


def scan_address(hl: HyperliquidInfo, row: dict) -> dict | None:
    addr = row["ethAddress"]
    try:
        chs = hl.clearinghouse_state(addr)
    except Exception:
        return None
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
        "positions": pos,
    }


def main() -> None:
    hl = HyperliquidInfo()
    lb = hl.leaderboard()
    lb.sort(key=lambda r: -fnum(r["accountValue"]))
    candidates = lb[:SCAN_TOP_N]
    print(f"scanning top {len(candidates):,} accounts for {sorted(COINS)} "
          f"positions >= ${MIN_COIN_NOTIONAL:,} ...")

    whales: list[dict] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(scan_address, hl, r) for r in candidates]
        for i, fut in enumerate(as_completed(futs), 1):
            if i % 250 == 0:
                print(f"  ...{i}/{len(candidates)} scanned, {len(whales)} whales so far")
            res = fut.result()
            if res:
                whales.append(res)

    whales.sort(key=lambda w: -w["coinNotional"])
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


if __name__ == "__main__":
    main()
