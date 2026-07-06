#!/usr/bin/env python3
"""Winners vs losers: do the behavioral signatures actually separate them?

Loads data/trips_btc.jsonl (verified skilled) and data/trips_btc_losers.jsonl
(verified losers, same activity bar — see trips.py --losers), computes one
feature vector per trader, and compares the two groups feature by feature
with a two-sided Mann-Whitney U across traders (the trader, not the trip, is
the independent unit).

The question that matters: is cut-losses-fast (hold ratio < 1) a *winner*
trait, or just how everyone on Hyperliquid trades?
"""
from __future__ import annotations

import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
MIN_WL = 3   # a trader needs >= this many wins AND losses for hold-ratio


def phi(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2))


def mwu_two_sided(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Two-sided Mann-Whitney U (normal approximation, tie-corrected)."""
    n1, n2 = len(xs), len(ys)
    allv = sorted([(v, 0) for v in xs] + [(v, 1) for v in ys])
    i = 0
    tie_term = 0.0
    rank_sum_x = 0.0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        avg = (i + j + 1) / 2.0
        t = j - i
        tie_term += t**3 - t
        rank_sum_x += sum(avg for k in range(i, j) if allv[k][1] == 0)
        i = j
    u1 = rank_sum_x - n1 * (n1 + 1) / 2.0
    n = n1 + n2
    var = n1 * n2 / 12.0 * ((n + 1) - tie_term / (n * (n - 1)))
    if var <= 0:
        return 0.0, 1.0
    z = (u1 - n1 * n2 / 2.0) / math.sqrt(var)
    return z, 2 * (1 - phi(abs(z)))


def aligned(t: dict) -> bool | None:
    r = t.get("ret_prior")
    if r is None or r == 0.0:
        return None
    return (r > 0) == (t["side"] == "L")


def features(trips: list[dict]) -> dict:
    """One row per trader: the behavioral signature."""
    w = [t for t in trips if t["pnl"] > 0]
    l = [t for t in trips if t["pnl"] <= 0]
    al = [a for a in (aligned(t) for t in trips) if a is not None]
    f = {
        "n_trips": len(trips),
        "wr": len(w) / len(trips),
        "med_hold_h": st.median([t["hold_h"] for t in trips]),
        "fade_share": 1 - sum(al) / len(al) if al else None,
        "pyr_rate": sum(1 for t in trips if t["n_adds"] > 0) / len(trips),
        "med_ntl": st.median([t["max_ntl"] for t in trips]),
    }
    if len(w) >= MIN_WL and len(l) >= MIN_WL:
        f["cut_ratio"] = st.median([t["hold_h"] for t in l]) / st.median([t["hold_h"] for t in w])
        aw = sum(t["pnl"] for t in w) / len(w)
        als = -sum(t["pnl"] for t in l) / len(l)
        f["payoff"] = aw / als if als else float("inf")
    else:
        f["cut_ratio"] = None
        f["payoff"] = None
    return f


def load(path: Path) -> list[dict]:
    by: dict[str, list[dict]] = defaultdict(list)
    for line in path.read_text().splitlines():
        t = json.loads(line)
        by[t["addr"]].append(t)
    return [features(ts) for ts in by.values()]


def main() -> None:
    winners = load(DATA / "trips_btc.jsonl")
    losers = load(DATA / "trips_btc_losers.jsonl")
    overlap = None  # addresses can't overlap: net>0 vs net<0 verification
    print(f"winners: {len(winners)} traders / {sum(f['n_trips'] for f in winners)} trips")
    print(f"losers : {len(losers)} traders / {sum(f['n_trips'] for f in losers)} trips\n")

    feats = [
        ("cut_ratio", "負け保有/勝ち保有 比率 (<1=損切り速い)"),
        ("payoff", "ペイオフ比 (平均勝ち/平均負け)"),
        ("wr", "トリップ勝率"),
        ("med_hold_h", "保有時間中央値 [h]"),
        ("fade_share", "逆張りエントリー率"),
        ("pyr_rate", "積み増し率"),
        ("med_ntl", "建玉中央値 [USD]"),
        ("n_trips", "トリップ数"),
    ]
    print(f"{'feature':<34} {'勝ち組(中央値)':>14} {'負け組(中央値)':>14} "
          f"{'z':>6} {'p(two-sided)':>12}")
    for key, label in feats:
        xs = [f[key] for f in winners if f.get(key) is not None]
        ys = [f[key] for f in losers if f.get(key) is not None]
        if not xs or not ys:
            continue
        # payoff can be inf: clamp for ranking
        xs_c = [min(x, 1e9) for x in xs]
        ys_c = [min(y, 1e9) for y in ys]
        z, p = mwu_two_sided(xs_c, ys_c)
        print(f"{label:<34} {st.median(xs):>14.3f} {st.median(ys):>14.3f} "
              f"{z:>+6.2f} {p:>12.4g}")

    # the headline: share of traders with cut_ratio < 1 in each group
    for name, grp in (("勝ち組", winners), ("負け組", losers)):
        rs = [f["cut_ratio"] for f in grp if f["cut_ratio"] is not None]
        below = sum(1 for r in rs if r < 1)
        print(f"\n{name}: cut_ratio < 1 は {below}/{len(rs)} 人 "
              f"(中央値 {st.median(rs):.2f})")


if __name__ == "__main__":
    main()
