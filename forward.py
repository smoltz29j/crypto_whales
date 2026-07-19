#!/usr/bin/env python3
"""Forward validation of the 2026-07-02 verified-skilled BTC cohort.

The 07-02 skilled.py run verified 43 traders on data available *then*; the
printed top-40-by-PF table was recovered from the session transcript and the
truncated addresses resolved against the fills caches (data/seed_2026-07-02.json,
40 of 43 — the 3 lowest-PF rows were never printed and are lost). Everything
those traders did after the run moment (CUTOFF_MS) is out-of-sample.

Measures, per the HANDOFF §11 plan:
  1. Out-of-period performance: full fills since CUTOFF_MS per seed trader
     (userFillsByTime paged forward, disk-cached in data/fills_fwd/), metrics
     recomputed on the BTC subset with the same knobs skilled.py used.
  2. Survivor overlap: re-run today's funnel (same three routes, same knobs)
     and check who verifies again on fresh data.

Honesty notes: no control group here — the share of seed traders with
positive OOS net is tested against a 50% coin-flip base rate, which ignores
market beta and the fee drag that makes random trading negative-sum. Maker
archetypes are expected to persist for structural (not predictive) reasons;
read the directional cluster separately.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from hl import HyperliquidInfo
import whales_coin as wc
import whales_skill as ws
import skilled

# --- knobs (edit & rerun) ------------------------------------------------
SEED_PATH = Path("data/seed_2026-07-02.json")
CUTOFF_MS = 1782948004000       # 2026-07-01T23:20:04Z = the 07-02 run moment (JST 08:20)
FWD_CACHE_DIR = Path("data/fills_fwd")
FWD_CACHE_AGE = 3600            # s
OUT_PATH = Path("data/forward_2026-07.json")
WORKERS = 4
# same verification knobs as skilled.py, applied to the OOS window
MIN_REALIZED_FILLS = skilled.MIN_REALIZED_FILLS
MIN_SPAN_DAYS = skilled.MIN_SPAN_DAYS
MIN_PF = skilled.MIN_PF
# -------------------------------------------------------------------------


def fills_since(hl: HyperliquidInfo, addr: str, start_ms: int) -> list[dict]:
    """All fills at/after start_ms, paged forward (deep_fills pattern),
    disk-cached FWD_CACHE_AGE."""
    FWD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = FWD_CACHE_DIR / f"{addr}.json"
    if cache.exists() and (time.time() - cache.stat().st_mtime) < FWD_CACHE_AGE:
        # cached file may be a superset (fetched from an earlier start): filter
        return [f for f in json.loads(cache.read_text())
                if f.get("time", 0) >= start_ms]
    out: list[dict] = []
    seen: set[tuple] = set()
    start = start_ms
    while True:
        page = hl.user_fills_by_time(addr, start)
        if not page:
            break
        n_new = 0
        for f in page:
            k = (f.get("tid"), f.get("time"), f.get("coin"))
            if k not in seen:
                seen.add(k)
                out.append(f)
                n_new += 1
        if len(page) < 2000 or n_new == 0:
            break
        start = max(f["time"] for f in page)  # inclusive restart; dedup absorbs
    out.sort(key=lambda f: f.get("time", 0))
    tmp = cache.with_name(cache.name + ".tmp")
    tmp.write_text(json.dumps(out))
    tmp.replace(cache)
    return out


def oos_row(hl: HyperliquidInfo, addr: str) -> dict:
    fills = ws.perp_fills(fills_since(hl, addr, CUTOFF_MS))
    btc = [f for f in fills if f["coin"] in skilled.COINS] if skilled.COINS else fills
    m = ws.fill_metrics(btc) if btc else None
    still = bool(m and m["n_realized"] >= MIN_REALIZED_FILLS
                 and m["span_days"] >= MIN_SPAN_DAYS
                 and m["net_pnl"] > 0 and m["profit_factor"] >= MIN_PF)
    return {"addr": addr, "n_fills_all": len(fills), "n_btc": len(btc),
            "metrics": m, "still_verified_oos": still}


def main(argv: list[str]) -> None:
    hl = HyperliquidInfo(retries=4)
    seed = json.loads(SEED_PATH.read_text())
    days = (time.time() * 1000 - CUTOFF_MS) / 86_400_000
    print(f"forward validation: {len(seed)} seed traders (verified 2026-07-02), "
          f"OOS window {days:.1f} days since cutoff\n")

    # 1) out-of-sample performance ---------------------------------------
    from concurrent.futures import ThreadPoolExecutor
    n_err = 0
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(oos_row, hl, a): a for a in seed}
        for fut, a in futs.items():
            try:
                rows.append(fut.result())
            except Exception as e:
                n_err += 1
                print(f"warning: OOS fetch failed for {a}: {e}", file=sys.stderr)
    if n_err:
        print(f"warning: {n_err} OOS fills fetches failed", file=sys.stderr)
    rows.sort(key=lambda r: -(r["metrics"]["net_pnl"] if r["metrics"] else -1e18))

    print(f"  {'address':<12} {'fills':>6} {'BTCf':>6} {'days':>5} {'closes':>6} "
          f"{'PF':>6} {'netOOS':>9}  still?")
    for r in rows:
        m = r["metrics"]
        if not m or not r["n_btc"]:
            print(f"  {r['addr'][:10] + '..':<12} {r['n_fills_all']:>6} "
                  f"{r['n_btc']:>6}     -      -      -         -  (no BTC fills)")
            continue
        pf = ("inf" if m["profit_factor"] == float("inf")
              else f"{min(m['profit_factor'], 999.0):.1f}")
        print(f"  {r['addr'][:10] + '..':<12} {r['n_fills_all']:>6} {r['n_btc']:>6} "
              f"{m['span_days']:>5.1f} {m['n_realized']:>6} {pf:>6} "
              f"{wc.fmt_usd(m['net_pnl']):>9}  "
              f"{'YES' if r['still_verified_oos'] else 'no'}")

    active = [r for r in rows if r["metrics"] and r["metrics"]["n_realized"] > 0]
    pos = [r for r in active if r["metrics"]["net_pnl"] > 0]
    gone = [r for r in rows if not r["n_btc"]]
    still = [r for r in rows if r["still_verified_oos"]]
    tot = sum(r["metrics"]["net_pnl"] for r in active)
    print(f"\n  active in BTC OOS: {len(active)}/{len(rows)} "
          f"(no BTC fills at all: {len(gone)})")
    if active:
        print(f"  OOS net > 0: {len(pos)}/{len(active)} "
              f"({len(pos)/len(active):.0%} vs 50% coin-flip base rate)")
        print(f"  re-verify on OOS window alone (same knobs): "
              f"{len(still)}/{len(active)}")
        print(f"  summed OOS net (survivor-free, all {len(active)} active): "
              f"{wc.fmt_usd(tot)}")

    # 2) survivor overlap with a fresh funnel run ------------------------
    print("\nre-running today's funnel (same knobs) for survivor overlap ...")
    lb = hl.leaderboard()
    cands = skilled.candidates(lb)
    cand_addrs = {r["ethAddress"].lower() for r in cands}
    coll = ws.collect(hl, [{"addr": r["ethAddress"],
                            "acctValue": wc.fnum(r["accountValue"])} for r in cands])
    verified = skilled.verified_skilled(coll)
    ver_addrs = {r["addr"].lower() for r in verified}
    seed_l = {a.lower() for a in seed}
    in_funnel = seed_l & cand_addrs
    in_verified = seed_l & ver_addrs
    print(f"  today: {len(cands)} candidates -> {len(verified)} verified in "
          f"{'+'.join(sorted(skilled.COINS)) if skilled.COINS else 'all coins'}")
    print(f"  seed still in funnel:   {len(in_funnel)}/{len(seed)}")
    print(f"  seed verified again:    {len(in_verified)}/{len(seed)}")
    for a in sorted(in_verified):
        print(f"    {a}")

    OUT_PATH.write_text(json.dumps({
        "cutoff_ms": CUTOFF_MS, "generated_ms": int(time.time() * 1000),
        "seed": seed, "oos": rows,
        "today_candidates": len(cands), "today_verified": sorted(ver_addrs),
        "seed_in_funnel": sorted(in_funnel),
        "seed_verified_again": sorted(in_verified),
    }, default=lambda x: None))
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])
