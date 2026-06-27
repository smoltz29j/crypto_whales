#!/usr/bin/env python3
"""Discover whales from the leaderboard and inspect their live positions.

This is the experiment surface for "how do we define a whale?". Tweak the
filters below -- account-value threshold, performance window, win/lose
inclusion -- and rerun to see how the cohort changes.

Run:  python3 whales.py
"""
from __future__ import annotations

from hl import HyperliquidInfo


def fnum(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


# --- whale definition knobs (edit & rerun) -------------------------------
MIN_ACCOUNT_VALUE = 5_000_000   # USD: "whale" size floor
WINDOW = "allTime"              # day | week | month | allTime  (for ranking)
INCLUDE_LOSERS = True          # if False, drop traders with negative pnl in WINDOW
TOP_N = 15                      # how many to inspect live
# -------------------------------------------------------------------------


def perf(row: dict, window: str) -> dict:
    return {w: p for w, p in row["windowPerformances"]}.get(window, {})


def select_whales(lb: list[dict]) -> list[dict]:
    out = []
    for r in lb:
        if fnum(r["accountValue"]) < MIN_ACCOUNT_VALUE:
            continue
        p = perf(r, WINDOW)
        if not INCLUDE_LOSERS and fnum(p.get("pnl")) <= 0:
            continue
        out.append(r)
    out.sort(key=lambda r: -fnum(perf(r, WINDOW).get("pnl")))
    return out


def main() -> None:
    hl = HyperliquidInfo()
    lb = hl.leaderboard()
    whales = select_whales(lb)
    print(f"matched {len(whales):,} whales "
          f"(accountValue>=${MIN_ACCOUNT_VALUE:,}, window={WINDOW}, "
          f"include_losers={INCLUDE_LOSERS})\n")

    for r in whales[:TOP_N]:
        addr = r["ethAddress"]
        p = perf(r, WINDOW)
        chs = hl.clearinghouse_state(addr)
        aps = chs["assetPositions"]
        notional = fnum(chs["marginSummary"]["totalNtlPos"])
        print(f"{addr}  value=${fnum(r['accountValue']):>13,.0f}  "
              f"{WINDOW}PnL=${fnum(p.get('pnl')):>+13,.0f}  roi={fnum(p.get('roi')):+.3f}  "
              f"liveNotional=${notional:>13,.0f}  positions={len(aps)}")
        # biggest live position by notional
        biggest = sorted(aps, key=lambda a: -fnum(a["position"].get("positionValue")))[:3]
        for ap in biggest:
            pos = ap["position"]
            side = "LONG" if fnum(pos["szi"]) > 0 else "SHORT"
            print(f"     {side:5s} {pos['coin']:6s} "
                  f"${fnum(pos.get('positionValue')):>13,.0f}  "
                  f"uPnL=${fnum(pos['unrealizedPnl']):>+11,.0f}  lev={pos['leverage']['value']}x")


if __name__ == "__main__":
    main()
