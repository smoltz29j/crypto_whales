#!/usr/bin/env python3
"""Find skilled traders — any size — and fingerprint HOW they trade.

Direction pivot (2026-07-02): not whale-watching, and not copy-trading. The
question is "who is actually good, and what is their method?" Size is not a
selection criterion; a $30k account with a real edge matters more than a $30M
hedger. Scope restriction (same day): COINS = {"BTC"} — skill is verified and
fingerprinted on BTC fills only; the coin_share tag records whether BTC is
the trader's whole book or a side dish.

Funnel:
  1. Candidates from the full leaderboard by three routes: top month PnL,
     top week PnL (recency), and top month ROI with a volume floor — the ROI
     route is what lets small skilled accounts in.
  2. Verify skill from *fills* (leaderboard pnl alone is a weak proxy — see
     notes/skill_findings.md): enough realized closes over enough days,
     positive net-of-fees PnL, profit factor above a floor.
  3. Fingerprint each survivor's style from their fills:
       activity (fills/day), median round-trip hold time, maker vs taker share,
       long/short lean, coin concentration, median trade size
     and tag an archetype like "intraday taker BTC-specialist long-lean".

Usage:
  python3 skilled.py             # funnel -> verify -> style table + archetypes
  python3 skilled.py --addr 0x…  # deep style report for one address

Caveats: 2000-fill window (recent behavior only, spans differ per account);
round trips that straddle the window edge are dropped; win rate inherits the
"close winners, ride losers" bias — PF and net PnL matter more.
"""
from __future__ import annotations

import sys
from collections import defaultdict

from hl import HyperliquidInfo
import whales_coin as wc
import whales_skill as ws

# --- knobs (edit & rerun) ------------------------------------------------
COINS = {"BTC"}           # verify skill + fingerprint on these coins only (None = all)
TOP_MONTH_PNL = 150       # candidate route 1: biggest month pnl
TOP_WEEK_PNL = 100        # candidate route 2: biggest week pnl (recency)
TOP_MONTH_ROI = 150       # candidate route 3: best month roi (size-agnostic)
MIN_ROI_VLM = 1_000_000   # roi route needs volume, else it's one lucky punt
MIN_REALIZED_FILLS = 50   # verify: enough closed fills to judge
MIN_SPAN_DAYS = 7.0       # verify: metrics over at least a week of activity
MIN_PF = 1.5              # verify: profit factor floor
TOP_N = 40                # rows to print
# -------------------------------------------------------------------------


def window_perf(row: dict, window: str) -> dict:
    """The {pnl, roi, vlm} dict for one leaderboard window (list of pairs)."""
    for name, perf in row.get("windowPerformances", []):
        if name == window:
            return perf
    return {}


# --- candidate funnel --------------------------------------------------------

def candidates(lb: list[dict]) -> list[dict]:
    """Union of the three routes, deduped, order = first appearance."""
    routes = [
        sorted(lb, key=lambda r: -wc.fnum(window_perf(r, "month").get("pnl")))[:TOP_MONTH_PNL],
        sorted(lb, key=lambda r: -wc.fnum(window_perf(r, "week").get("pnl")))[:TOP_WEEK_PNL],
        sorted(
            [r for r in lb if wc.fnum(window_perf(r, "month").get("vlm")) >= MIN_ROI_VLM],
            key=lambda r: -wc.fnum(window_perf(r, "month").get("roi")),
        )[:TOP_MONTH_ROI],
    ]
    seen: set[str] = set()
    out: list[dict] = []
    for route in routes:
        for r in route:
            if r["ethAddress"] not in seen:
                seen.add(r["ethAddress"])
                out.append(r)
    return out


def coin_fills(fills: list[dict]) -> list[dict]:
    """The fills the analysis runs on (COINS restriction; None = everything)."""
    if not COINS:
        return fills
    return [f for f in fills if f["coin"] in COINS]


# --- style fingerprint --------------------------------------------------------

def _fill_delta(f: dict) -> float:
    """Signed position change of one fill (B adds, A/S subtracts)."""
    sz = wc.fnum(f.get("sz"))
    return sz if f.get("side") == "B" else -sz


def round_trips(fills: list[dict]) -> list[dict]:
    """Flat->flat episodes per coin: [{coin, hours, pnl}]. Trips that straddle
    the 2000-fill window edge (start with a position already open, or never
    return to flat) are dropped — we can't know their true length."""
    by_coin: dict[str, list[dict]] = defaultdict(list)
    for f in fills:
        by_coin[f["coin"]].append(f)
    trips: list[dict] = []
    for coin, fs in by_coin.items():
        open_ms: int | None = None
        pnl = 0.0
        for f in fs:
            start = wc.fnum(f.get("startPosition"))
            end = start + _fill_delta(f)
            if open_ms is None:
                if start == 0.0 and end != 0.0:      # fresh open at a flat book
                    open_ms = f["time"]
                    pnl = -wc.fnum(f.get("fee"))
                continue                              # mid-window position: skip
            pnl += wc.fnum(f.get("closedPnl")) - wc.fnum(f.get("fee"))
            if abs(end) < 1e-9 * max(1.0, abs(start)):  # back to flat
                trips.append({"coin": coin,
                              "hours": (f["time"] - open_ms) / 3.6e6,
                              "pnl": pnl})
                open_ms = None
            elif start != 0.0 and (start > 0) != (end > 0):  # flip = close + reopen
                trips.append({"coin": coin,
                              "hours": (f["time"] - open_ms) / 3.6e6,
                              "pnl": pnl})
                open_ms = f["time"]
                pnl = 0.0
    return trips


def style(fills: list[dict]) -> dict:
    """Behavioral fingerprint from one account's perp fills (oldest first)."""
    span_days = ((fills[-1]["time"] - fills[0]["time"]) / 86_400_000
                 if len(fills) >= 2 else 0.0)
    opens = [f for f in fills if str(f.get("dir", "")).startswith("Open")]
    n_long = sum(1 for f in opens if f["dir"] == "Open Long")
    maker = sum(1 for f in fills if not f.get("crossed", True))
    by_coin: dict[str, int] = defaultdict(int)
    for f in fills:
        by_coin[f["coin"]] += 1
    top_coin, top_n = max(by_coin.items(), key=lambda kv: kv[1]) if by_coin else ("-", 0)
    sizes = sorted(wc.fnum(f["px"]) * wc.fnum(f["sz"]) for f in fills)
    trips = round_trips(fills)
    hold = ws._median([t["hours"] for t in trips]) if trips else 0.0
    return {
        "fills_per_day": len(fills) / span_days if span_days else 0.0,
        "hold_hours": hold,
        "n_trips": len(trips),
        "trip_win_rate": (sum(1 for t in trips if t["pnl"] > 0) / len(trips)
                          if trips else 0.0),
        "maker_share": maker / len(fills) if fills else 0.0,
        "long_share": n_long / len(opens) if opens else 0.5,
        "top_coin": top_coin,
        "top_coin_share": top_n / len(fills) if fills else 0.0,
        "n_coins": len(by_coin),
        "med_size": ws._median(sizes) if sizes else 0.0,
    }


def archetype(st: dict) -> str:
    h = st["hold_hours"]
    hold = ("scalp" if h < 0.5 else "intraday" if h < 24
            else "swing" if h < 168 else "position") if st["n_trips"] else "hodl?"
    exe = ("maker" if st["maker_share"] > 0.6
           else "taker" if st["maker_share"] < 0.2 else "mixed")
    if COINS:
        # focus = how much of the trader's *total* perp activity the target
        # coins are: specialist vs side dish.
        share = st.get("coin_share", 1.0)
        tag = "+".join(sorted(COINS))
        focus = (f"{tag}-only" if share > 0.9 else f"{tag}-main" if share > 0.5
                 else f"{tag}-side")
    else:
        focus = (f"{st['top_coin']}-spec" if st["top_coin_share"] > 0.7
                 else "multi" if st["n_coins"] >= 5 else "few-coin")
    lean = ("long" if st["long_share"] > 0.7
            else "short" if st["long_share"] < 0.3 else "both")
    return f"{hold}/{exe}/{focus}/{lean}"


# --- output ------------------------------------------------------------------

def verified_skilled(rows: list[dict]) -> list[dict]:
    """Verify + fingerprint on the COINS-restricted fills; metrics are
    recomputed on that subset (ws.collect computed them over all perp fills)."""
    out = []
    for r in rows:
        cf = coin_fills(r["fills"])
        if not cf:
            continue
        m = ws.fill_metrics(cf)
        if (m["n_realized"] >= MIN_REALIZED_FILLS and m["span_days"] >= MIN_SPAN_DAYS
                and m["net_pnl"] > 0 and m["profit_factor"] >= MIN_PF):
            r["metrics"] = m
            r["style"] = style(cf)
            r["style"]["coin_share"] = len(cf) / len(r["fills"])
            r["archetype"] = archetype(r["style"])
            out.append(r)
    out.sort(key=lambda r: -min(r["metrics"]["profit_factor"], 50.0))
    return out


def print_skilled(skilled: list[dict], n_candidates: int) -> None:
    scope = f" in {'+'.join(sorted(COINS))}" if COINS else ""
    print(f"\nverified skilled traders{scope}: {len(skilled)} of {n_candidates} "
          f"candidates (>= {MIN_REALIZED_FILLS} closes over >= {MIN_SPAN_DAYS:.0f}d, "
          f"net > 0, PF >= {MIN_PF}); top {min(TOP_N, len(skilled))} by PF:\n")
    print(f"  {'address':<12} {'acctVal':>8} {'days':>5} {'f/day':>6} {'PF':>6} "
          f"{'net':>9} {'hold':>7} {'tripWR':>6} {'mkr%':>5} {'lng%':>5} "
          f"{'medSz':>8}  archetype")
    for r in skilled[:TOP_N]:
        m, st = r["metrics"], r["style"]
        pf = f"{m['profit_factor']:.1f}" if m["profit_factor"] != float("inf") else "inf"
        hold = (f"{st['hold_hours']:.1f}h" if st["hold_hours"] < 48
                else f"{st['hold_hours'] / 24:.1f}d") if st["n_trips"] else "-"
        print(f"  {r['addr'][:10] + '..':<12} {wc.fmt_usd(r['acctValue']):>8} "
              f"{m['span_days']:>5.0f} {st['fills_per_day']:>6.0f} {pf:>6} "
              f"{wc.fmt_usd(m['net_pnl']):>9} {hold:>7} {st['trip_win_rate']:>6.0%} "
              f"{st['maker_share']:>5.0%} {st['long_share']:>5.0%} "
              f"{wc.fmt_usd(st['med_size']):>8}  {r['archetype']}")

    counts: dict[str, int] = defaultdict(int)
    for r in skilled:
        counts[r["archetype"]] += 1
    print(f"\narchetypes across all {len(skilled)} verified "
          f"(hold/execution/focus/lean):")
    for a, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>3}  {a}")


def report_one(hl: HyperliquidInfo, addr: str) -> None:
    all_fills = ws.perp_fills(ws.fetch_fills(hl, addr))
    fills = coin_fills(all_fills)
    if not fills:
        scope = f"{'+'.join(sorted(COINS))} " if COINS else ""
        print(f"{addr}: no {scope}perp fills in the recent window "
              f"({len(all_fills)} perp fills total)")
        return
    m, st = ws.fill_metrics(fills), style(fills)
    st["coin_share"] = len(fills) / len(all_fills)
    pf = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "inf"
    print(f"\n{addr}\n  archetype: {archetype(st)}")
    print(f"  window: {m['n_fills']} fills / {m['span_days']:.1f} days "
          f"({st['fills_per_day']:.1f}/day), {m['n_realized']} realized")
    print(f"  performance: net {wc.fmt_usd(m['net_pnl'])} "
          f"(realized {wc.fmt_usd(m['realized_pnl'])} - fees {wc.fmt_usd(m['fees'])}), "
          f"PF {pf}, fill winR {m['win_rate']:.0%}, maxDD {wc.fmt_usd(m['max_dd'])}")
    print(f"  round trips: {st['n_trips']} complete, median hold "
          f"{st['hold_hours']:.1f}h, trip winR {st['trip_win_rate']:.0%}")
    print(f"  execution: maker {st['maker_share']:.0%}, median clip "
          f"{wc.fmt_usd(st['med_size'])}, long share of opens {st['long_share']:.0%}")
    by_coin: dict[str, dict] = defaultdict(lambda: {"n": 0, "pnl": 0.0})
    for f in all_fills:                    # context: everything they trade
        c = by_coin[f["coin"]]
        c["n"] += 1
        c["pnl"] += wc.fnum(f.get("closedPnl")) - wc.fnum(f.get("fee"))
    print(f"  coins across all perp fills ({len(by_coin)}; analysis restricted "
          f"to {'+'.join(sorted(COINS)) if COINS else 'all'}, "
          f"{st['coin_share']:.0%} of fills):")
    for coin, c in sorted(by_coin.items(), key=lambda kv: -kv[1]["pnl"])[:8]:
        print(f"    {coin:<8} {c['n']:>5} fills  net {wc.fmt_usd(c['pnl']):>9}")


def main(argv: list[str]) -> None:
    hl = HyperliquidInfo(retries=4)
    if "--addr" in argv:
        report_one(hl, argv[argv.index("--addr") + 1])
        return
    lb = hl.leaderboard()
    cands = candidates(lb)
    print(f"funnel: {len(cands)} candidates from {len(lb):,} leaderboard rows "
          f"(month-pnl {TOP_MONTH_PNL} + week-pnl {TOP_WEEK_PNL} + "
          f"month-roi {TOP_MONTH_ROI}, deduped)")
    print(f"fetching fills for {len(cands)} candidates ...")
    rows = ws.collect(hl, [{"addr": r["ethAddress"],
                            "acctValue": wc.fnum(r["accountValue"])} for r in cands])
    print_skilled(verified_skilled(rows), len(cands))


if __name__ == "__main__":
    main(sys.argv[1:])
