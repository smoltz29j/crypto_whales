#!/usr/bin/env python3
"""Per-trip records + setup analysis for verified skilled BTC traders.

The next step from notes/skilled_findings.md: take the *directional* cluster
(verified skilled traders who actually complete flat->flat round trips) and
dump every round trip — entry/exit price, hold, adds, pnl — then look for
repeated **setups**:

  - time-of-day: when do their entries cluster (UTC / JST)?
  - momentum vs mean-reversion: is the entry aligned with or against the
    prior N-hour BTC move (1h candles)?
  - pyramiding: do they add to positions, and does it pay?
  - loss-cutting: are losing trips held shorter than winning ones?

Usage:
  python3 trips.py               # funnel -> directional traders -> setup report
  python3 trips.py --addr 0x…    # per-trip listing for one address

Every trip is also written to data/trips_btc.jsonl (one JSON object per
line, with the trader's address) for ad-hoc follow-up study.

Caveats: skill *verification* uses the recent-2000-fill window (skilled.py),
but trips are extracted from each verified trader's FULL paged fill history
(deep_fills, up to MAX_DEEP_FILLS); trips straddling a history edge are
dropped. Momentum stats need 1h candles; Hyperliquid keeps only the most
recent ~5000 (~200 days), older entries get no momentum read (excluded from
those stats, counted in the rest). A flip (long->short in one fill) closes
one trip and opens the next at the same fill. Times are UTC; JST = UTC+9.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from hl import HyperliquidInfo
import whales_coin as wc
import whales_skill as ws
import skilled

# --- knobs (edit & rerun) ------------------------------------------------
MIN_TRIPS = 8          # a trader needs this many complete trips to be studied
MOM_HOURS = 4          # "prior move" lookback for momentum-vs-reversion
BIG_MOVE = 0.01        # |prior move| >= this counts as "entry after a move"
TOP_N = 30             # trader rows to print
# Maximize the population (user decision 2026-07-05): widen the candidate
# funnel ~3x over skilled.py's defaults, and fetch each verified trader's
# FULL fill history (userFillsByTime pages forward from t=0, 2000/call)
# instead of the recent-2000 window. Verification still runs on the recent
# window (skill = recent); only the behavior stats use the deep history.
FUNNEL = {"TOP_MONTH_PNL": 400, "TOP_WEEK_PNL": 300, "TOP_MONTH_ROI": 400}
MAX_DEEP_FILLS = 12_000   # per-address cap on history pagination
DEEP_CACHE_AGE = 86_400.0  # deep history changes slowly; refetch daily
# -------------------------------------------------------------------------

OUT_PATH = Path(__file__).resolve().parent / "data" / "trips_btc.jsonl"
DEEP_CACHE_DIR = Path(__file__).resolve().parent / "data" / "fills_deep"


# --- deep fill history ---------------------------------------------------------

def _fill_key(f: dict) -> tuple:
    return (f.get("tid"), f.get("oid"), f.get("time"), f.get("px"), f.get("sz"))


def deep_fills(hl: HyperliquidInfo, addr: str) -> list[dict]:
    """Full fill history via userFillsByTime, paged forward from t=0
    (each call returns the oldest <= 2000 fills at or after startTime), merged
    with the recent user_fills window, deduped, oldest first. Disk-cached."""
    DEEP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = DEEP_CACHE_DIR / f"{addr}.json"
    if cache.exists() and (time.time() - cache.stat().st_mtime) < DEEP_CACHE_AGE:
        return json.loads(cache.read_text())
    out: list[dict] = []
    seen: set[tuple] = set()

    def add(fills: list[dict]) -> int:
        n = 0
        for f in fills:
            k = _fill_key(f)
            if k not in seen:
                seen.add(k)
                out.append(f)
                n += 1
        return n

    start = 0
    while len(out) < MAX_DEEP_FILLS:
        page = hl.user_fills_by_time(addr, start)
        if not page:
            break
        n_new = add(page)
        if len(page) < 2000:
            break
        # inclusive restart at the newest ms of the page so same-ms fills at
        # the boundary aren't skipped; dedup absorbs the overlap. n_new == 0
        # would mean an entire page of duplicates -> bail rather than spin.
        if n_new == 0:
            break
        start = max(f["time"] for f in page)
    add(ws.fetch_fills(hl, addr))       # newest window (cheap: usually cached)
    out.sort(key=lambda f: f.get("time", 0))
    tmp = cache.with_name(cache.name + ".tmp")
    tmp.write_text(json.dumps(out))
    tmp.replace(cache)
    return out


# --- trip extraction ---------------------------------------------------------

def _open_trip(coin: str, t_ms: int, px: float, sz: float, fee: float,
               maker: int, side: int) -> dict:
    return {"coin": coin, "side": side, "open_ms": t_ms, "first_px": px,
            "entry_val": px * sz, "entry_sz": sz, "exit_val": 0.0, "exit_sz": 0.0,
            "pnl": -fee, "n_fills": 1, "n_adds": 0, "maker": maker,
            "max_ntl": px * sz}


def _close_trip(cur: dict, t_ms: int) -> dict:
    return {
        "coin": cur["coin"],
        "side": "L" if cur["side"] > 0 else "S",
        "open_ms": cur["open_ms"],
        "close_ms": t_ms,
        "hold_h": (t_ms - cur["open_ms"]) / 3.6e6,
        "first_px": cur["first_px"],
        "entry_px": cur["entry_val"] / cur["entry_sz"] if cur["entry_sz"] else 0.0,
        "exit_px": cur["exit_val"] / cur["exit_sz"] if cur["exit_sz"] else 0.0,
        "max_ntl": cur["max_ntl"],
        "n_fills": cur["n_fills"],
        "n_adds": cur["n_adds"],
        "maker_share": cur["maker"] / cur["n_fills"],
        "pnl": cur["pnl"],
    }


def trip_records(fills: list[dict]) -> list[dict]:
    """Rich flat->flat episodes per coin. Same episode boundaries as
    skilled.round_trips (whose records keep only hours+pnl), plus entry/exit
    prices (size-weighted), adds, max notional, and per-trip maker share."""
    by_coin: dict[str, list[dict]] = defaultdict(list)
    for f in fills:
        by_coin[f["coin"]].append(f)
    trips: list[dict] = []
    for coin, fs in by_coin.items():
        cur: dict | None = None
        for f in fs:
            px, sz = wc.fnum(f.get("px")), wc.fnum(f.get("sz"))
            fee = wc.fnum(f.get("fee"))
            cpnl = wc.fnum(f.get("closedPnl"))
            start = wc.fnum(f.get("startPosition"))
            delta = sz if f.get("side") == "B" else -sz
            end = start + delta
            maker = 0 if f.get("crossed", True) else 1
            if cur is None:
                if start == 0.0 and end != 0.0:      # fresh open at a flat book
                    cur = _open_trip(coin, f["time"], px, abs(end), fee, maker,
                                     +1 if end > 0 else -1)
                continue                              # mid-window position: skip
            flat = abs(end) < 1e-9 * max(1.0, abs(start))
            flip = not flat and start != 0.0 and (start > 0) != (end > 0)
            if flat or flip:
                cur["exit_val"] += px * abs(start)
                cur["exit_sz"] += abs(start)
                cur["pnl"] += cpnl - fee
                cur["n_fills"] += 1
                cur["maker"] += maker
                trips.append(_close_trip(cur, f["time"]))
                cur = (None if flat else
                       _open_trip(coin, f["time"], px, abs(end), 0.0, 0,
                                  +1 if end > 0 else -1))
            elif abs(end) > abs(start):               # add (pyramid)
                cur["entry_val"] += px * sz
                cur["entry_sz"] += sz
                cur["pnl"] -= fee
                cur["n_adds"] += 1
                cur["n_fills"] += 1
                cur["maker"] += maker
                cur["max_ntl"] = max(cur["max_ntl"], abs(end) * px)
            else:                                     # partial close
                cur["exit_val"] += px * sz
                cur["exit_sz"] += sz
                cur["pnl"] += cpnl - fee
                cur["n_fills"] += 1
                cur["maker"] += maker
    return trips


# --- setup annotation (candles) -----------------------------------------------

def btc_hour_closes(hl: HyperliquidInfo, start_ms: int, end_ms: int) -> dict[int, float]:
    """hour-index (t // 3600e3) -> close px. Missing hours simply absent."""
    closes: dict[int, float] = {}
    for c in hl.candles("BTC", "1h", start_ms, end_ms):
        closes[int(c["t"]) // 3_600_000] = wc.fnum(c["c"])
    return closes


def prior_move(closes: dict[int, float], t_ms: int, px: float,
               hours: int) -> float | None:
    """Signed BTC return from `hours` before t_ms to the entry price px."""
    key = (t_ms - hours * 3_600_000) // 3_600_000
    ref = closes.get(key) or closes.get(key - 1)
    return px / ref - 1.0 if ref else None


def annotate(trips: list[dict], closes: dict[int, float]) -> None:
    for t in trips:
        t["ret_prior"] = prior_move(closes, t["open_ms"], t["first_px"], MOM_HOURS)
        t["hour_utc"] = int((t["open_ms"] // 3_600_000) % 24)
        gross = (t["exit_px"] / t["entry_px"] - 1.0) if t["entry_px"] else 0.0
        t["ret_trip"] = gross if t["side"] == "L" else -gross


def aligned(t: dict) -> bool | None:
    """Entry in the direction of the prior move? None when unknowable."""
    r = t.get("ret_prior")
    if r is None or r == 0.0:
        return None
    return (r > 0) == (t["side"] == "L")


# --- per-trader + pooled analysis ----------------------------------------------

def trader_summary(trips: list[dict]) -> dict:
    wins = [t for t in trips if t["pnl"] > 0]
    losses = [t for t in trips if t["pnl"] <= 0]
    al = [aligned(t) for t in trips]
    al = [a for a in al if a is not None]
    big = [t for t in trips if t.get("ret_prior") is not None
           and abs(t["ret_prior"]) >= BIG_MOVE]
    blocks: dict[int, int] = defaultdict(int)
    for t in trips:
        blocks[t["hour_utc"] // 4] += 1
    top_block, top_n = max(blocks.items(), key=lambda kv: kv[1])
    hold_w = ws._median([t["hold_h"] for t in wins]) if wins else 0.0
    hold_l = ws._median([t["hold_h"] for t in losses]) if losses else 0.0
    avg_w = sum(t["pnl"] for t in wins) / len(wins) if wins else 0.0
    avg_l = -sum(t["pnl"] for t in losses) / len(losses) if losses else 0.0
    return {
        "n": len(trips),
        "wr": len(wins) / len(trips),
        "hold": ws._median([t["hold_h"] for t in trips]),
        "payoff": avg_w / avg_l if avg_l else float("inf"),
        "pyr": sum(1 for t in trips if t["n_adds"] > 0) / len(trips),
        "cut": hold_l / hold_w if hold_w and losses else None,
        "mom": sum(al) / len(al) if al else None,
        "big": len(big) / len(trips),
        "long": sum(1 for t in trips if t["side"] == "L") / len(trips),
        "block": f"{top_block * 4:02d}-{top_block * 4 + 4:02d}",
        "block_share": top_n / len(trips),
        "med_ntl": ws._median([t["max_ntl"] for t in trips]),
        "net": sum(t["pnl"] for t in trips),
    }


def _fmt_h(h: float) -> str:
    return f"{h:.1f}h" if h < 48 else f"{h / 24:.1f}d"


def print_traders(traders: list[dict]) -> None:
    print(f"\nper-trader setups (>= {MIN_TRIPS} complete BTC trips; "
          f"mom = share of entries aligned with prior {MOM_HOURS}h move; "
          f"cut = median losing hold / winning hold, <1 cuts losses fast):\n")
    print(f"  {'address':<12} {'trips':>5} {'WR':>4} {'hold':>6} {'payoff':>6} "
          f"{'pyr%':>4} {'cut':>5} {'mom':>4} {'big%':>4} {'lng%':>4} "
          f"{'block(U)':>8} {'medNtl':>8} {'netPnl':>9}  archetype")
    for r in traders[:TOP_N]:
        s = r["tsum"]
        payoff = f"{s['payoff']:.1f}" if s["payoff"] != float("inf") else "inf"
        cut = f"{s['cut']:.2f}" if s["cut"] is not None else "-"
        mom = f"{s['mom']:.0%}" if s["mom"] is not None else "-"
        print(f"  {r['addr'][:10] + '..':<12} {s['n']:>5} {s['wr']:>4.0%} "
              f"{_fmt_h(s['hold']):>6} {payoff:>6} {s['pyr']:>4.0%} {cut:>5} "
              f"{mom:>4} {s['big']:>4.0%} {s['long']:>4.0%} "
              f"{s['block'] + f' {s['block_share']:.0%}':>8} "
              f"{wc.fmt_usd(s['med_ntl']):>8} {wc.fmt_usd(s['net']):>9}  "
              f"{r['archetype']}")


def print_pooled(all_trips: list[dict], n_traders: int) -> None:
    n = len(all_trips)
    wins = [t for t in all_trips if t["pnl"] > 0]
    losses = [t for t in all_trips if t["pnl"] <= 0]
    print(f"\npooled setups over {n} trips from {n_traders} traders:")

    # -- time of day ----------------------------------------------------
    hist: dict[int, int] = defaultdict(int)
    for t in all_trips:
        hist[t["hour_utc"]] += 1
    peak = max(hist.values())
    print(f"\n  entry time of day (UTC hour, JST in parens):")
    for h in range(24):
        c = hist.get(h, 0)
        bar = "#" * round(40 * c / peak)
        print(f"    {h:02d}U ({(h + 9) % 24:02d}J)  {c:>4}  {bar}")

    # -- momentum vs reversion -------------------------------------------
    def share(ts: list[dict]) -> tuple[float, int]:
        al = [aligned(t) for t in ts]
        al = [a for a in al if a is not None]
        return (sum(al) / len(al) if al else 0.0), len(al)

    s_all, n_all = share(all_trips)
    s_win, _ = share(wins)
    s_los, _ = share(losses)
    print(f"\n  momentum: {s_all:.0%} of entries aligned with the prior "
          f"{MOM_HOURS}h move ({n_all} readable)")
    print(f"    wins {s_win:.0%} aligned vs losses {s_los:.0%} aligned")
    for side in ("L", "S"):
        rs = [t["ret_prior"] for t in all_trips
              if t["side"] == side and t.get("ret_prior") is not None]
        if rs:
            print(f"    median prior-{MOM_HOURS}h move before "
                  f"{'LONG ' if side == 'L' else 'SHORT'} entries: "
                  f"{ws._median(rs):+.2%}  ({len(rs)} trips)")
    big = [t for t in all_trips if t.get("ret_prior") is not None
           and abs(t["ret_prior"]) >= BIG_MOVE]
    rest = [t for t in all_trips if t.get("ret_prior") is not None
            and abs(t["ret_prior"]) < BIG_MOVE]
    if big and rest:
        wr_b = sum(1 for t in big if t["pnl"] > 0) / len(big)
        wr_r = sum(1 for t in rest if t["pnl"] > 0) / len(rest)
        print(f"    entries after a big move (|{MOM_HOURS}h| >= {BIG_MOVE:.0%}): "
              f"{len(big)} ({len(big) / (len(big) + len(rest)):.0%}), "
              f"WR {wr_b:.0%} vs {wr_r:.0%} on quiet entries")

    # -- pyramiding -------------------------------------------------------
    pyr = [t for t in all_trips if t["n_adds"] > 0]
    single = [t for t in all_trips if t["n_adds"] == 0]
    if pyr and single:
        wr_p = sum(1 for t in pyr if t["pnl"] > 0) / len(pyr)
        wr_s = sum(1 for t in single if t["pnl"] > 0) / len(single)
        print(f"\n  pyramiding: {len(pyr) / n:.0%} of trips add to the position "
              f"(median {ws._median([t['n_adds'] for t in pyr]):.0f} adds); "
              f"WR {wr_p:.0%} with adds vs {wr_s:.0%} single-entry")

    # -- loss cutting -------------------------------------------------------
    if wins and losses:
        print(f"  holds: median win {_fmt_h(ws._median([t['hold_h'] for t in wins]))} "
              f"vs loss {_fmt_h(ws._median([t['hold_h'] for t in losses]))}; "
              f"trip WR {len(wins) / n:.0%}")


# --- single-address listing -----------------------------------------------------

def report_addr(hl: HyperliquidInfo, addr: str) -> None:
    fills = skilled.coin_fills(ws.perp_fills(ws.fetch_fills(hl, addr)))
    trips = trip_records(fills)
    if not trips:
        print(f"{addr}: no complete round trips in the window")
        return
    lo = min(t["open_ms"] for t in trips) - (MOM_HOURS + 1) * 3_600_000
    closes = btc_hour_closes(hl, lo, int(time.time() * 1000))
    annotate(trips, closes)
    s = trader_summary(trips)
    print(f"\n{addr} — {len(trips)} complete trips, WR {s['wr']:.0%}, "
          f"net {wc.fmt_usd(s['net'])}\n")
    print(f"  {'opened (UTC)':<17} {'side':<4} {'hold':>6} "
          f"{'entry -> exit':>21} {'ret':>7} {'adds':>4} {'ntl':>8} "
          f"{'pnl':>9} {'prior' + str(MOM_HOURS) + 'h':>8}")
    for t in sorted(trips, key=lambda t: t["open_ms"]):
        opened = time.strftime("%Y-%m-%d %H:%M", time.gmtime(t["open_ms"] / 1000))
        prior = f"{t['ret_prior']:+.2%}" if t.get("ret_prior") is not None else "-"
        print(f"  {opened:<17} {t['side']:<4} {_fmt_h(t['hold_h']):>6} "
              f"{t['entry_px']:>9,.0f} -> {t['exit_px']:>8,.0f} "
              f"{t['ret_trip']:>+7.2%} {t['n_adds']:>4} "
              f"{wc.fmt_usd(t['max_ntl']):>8} {wc.fmt_usd(t['pnl']):>9} {prior:>8}")


# --- main -----------------------------------------------------------------------

def main(argv: list[str]) -> None:
    hl = HyperliquidInfo(retries=4)
    if "--addr" in argv:
        report_addr(hl, argv[argv.index("--addr") + 1])
        return

    for k, v in FUNNEL.items():         # widen skilled.py's candidate routes
        setattr(skilled, k, v)
    lb = hl.leaderboard()
    cands = skilled.candidates(lb)
    print(f"funnel: {len(cands)} candidates; fetching fills ...")
    rows = ws.collect(hl, [{"addr": r["ethAddress"],
                            "acctValue": wc.fnum(r["accountValue"])} for r in cands])
    verified = skilled.verified_skilled(rows)
    print(f"verified skilled: {len(verified)}; fetching deep fill history ...")

    traders: list[dict] = []
    all_trips: list[dict] = []
    for i, r in enumerate(verified, 1):
        if i % 10 == 0:
            print(f"  ...{i}/{len(verified)} deep histories fetched")
        try:
            hist = skilled.coin_fills(ws.perp_fills(deep_fills(hl, r["addr"])))
        except Exception as e:  # noqa: BLE001 - fall back to the recent window
            print(f"warning: deep fetch failed for {r['addr'][:10]}.. ({e!r}); "
                  f"using recent window", file=sys.stderr)
            hist = skilled.coin_fills(r["fills"])
        trips = trip_records(hist)
        if len(trips) < MIN_TRIPS:
            continue
        for t in trips:
            t["addr"] = r["addr"]
        traders.append({**r, "trips": trips})
        all_trips.extend(trips)
    print(f"directional: {len(traders)} of {len(verified)} verified skilled have "
          f">= {MIN_TRIPS} complete trips ({len(all_trips)} trips total)")
    if not traders:
        return

    lo = min(t["open_ms"] for t in all_trips) - (MOM_HOURS + 1) * 3_600_000
    closes = btc_hour_closes(hl, lo, int(time.time() * 1000))
    annotate(all_trips, closes)
    for r in traders:
        r["tsum"] = trader_summary(r["trips"])
    traders.sort(key=lambda r: -r["tsum"]["net"])

    OUT_PATH.parent.mkdir(exist_ok=True)
    tmp = OUT_PATH.with_name(OUT_PATH.name + ".tmp")
    with tmp.open("w") as fh:
        for t in all_trips:
            fh.write(json.dumps(t) + "\n")
    tmp.replace(OUT_PATH)
    print(f"wrote {len(all_trips)} trips to {OUT_PATH.relative_to(Path.cwd())}"
          if OUT_PATH.is_relative_to(Path.cwd()) else
          f"wrote {len(all_trips)} trips to {OUT_PATH}")

    print_traders(traders)
    print_pooled(all_trips, len(traders))


if __name__ == "__main__":
    main(sys.argv[1:])
