#!/usr/bin/env python3
"""Dump a sample of every data source so we can see what HyperCore exposes.

Run:  python3 explore.py
Prints market overview, leaderboard shape, and one whale's positions/fills.
This is a scratch/experiment script -- edit it freely.
"""
from hl import HyperliquidInfo


def fnum(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def main() -> None:
    hl = HyperliquidInfo()

    print("=== market: top perps by notional open interest ===")
    meta, ctxs = hl.meta_and_asset_ctxs()
    rows = []
    for u, c in zip(meta["universe"], ctxs):
        oi = fnum(c.get("openInterest")) * fnum(c.get("markPx"))
        rows.append((u["name"], oi, c.get("funding"), c.get("markPx")))
    rows.sort(key=lambda r: -r[1])
    for name, oi, funding, mark in rows[:10]:
        print(f"  {name:8s} OI=${oi:>16,.0f}  funding={funding:>14}  mark={mark}")

    print("\n=== leaderboard: top accounts by value ===")
    lb = hl.leaderboard()
    lb.sort(key=lambda r: -fnum(r["accountValue"]))
    print(f"  {len(lb):,} ranked traders total")
    for r in lb[:5]:
        perf = {w: p for w, p in r["windowPerformances"]}
        day = perf.get("day", {})
        print(f"  {r['ethAddress']}  value=${fnum(r['accountValue']):>14,.0f}"
              f"  dayPnL={fnum(day.get('pnl')):>+12,.0f}  dayROI={fnum(day.get('roi')):+.4f}")

    print("\n=== one whale: current positions + recent fills ===")
    addr = lb[0]["ethAddress"]
    chs = hl.clearinghouse_state(addr)
    ms = chs["marginSummary"]
    print(f"  {addr}")
    print(f"  accountValue=${fnum(ms['accountValue']):,.0f}  notionalPos=${fnum(ms['totalNtlPos']):,.0f}"
          f"  open positions={len(chs['assetPositions'])}")
    for ap in chs["assetPositions"][:5]:
        p = ap["position"]
        print(f"    {p['coin']:6s} szi={p['szi']:>14s} posVal=${fnum(p.get('positionValue')):>14,.0f}"
              f" uPnL=${fnum(p['unrealizedPnl']):>+12,.0f} liqPx={p.get('liquidationPx')}"
              f" lev={p['leverage']['value']}x")

    fills = hl.user_fills(addr)
    print(f"  recent fills: {len(fills)} (showing 5)")
    for f in fills[:5]:
        print(f"    {f['coin']:6s} {f['dir']:18s} sz={f['sz']:>12s} px={f['px']:>10s}"
              f" closedPnl={fnum(f.get('closedPnl')):>+10,.2f}")


if __name__ == "__main__":
    main()
