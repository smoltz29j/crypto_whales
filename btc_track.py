#!/usr/bin/env python3
"""Track exchange on-chain BTC net-flow over time, then test it predicts.

The on-chain sibling of whales_track.py: each run appends one snapshot to a
JSONL series — per watched entity (btc/watchlist.py) the confirmed balance and
the IN/OUT/NET flow since the *previous* snapshot — plus the current BTC mark
price (from Hyperliquid, so the series is self-contained for forward-return
tests). Once enough snapshots accumulate, `--analyze` asks whether hot-wallet
net flow *leads* BTC: net OUTflow from hot wallets ≈ withdrawal/accumulation
(bullish prior), net INflow ≈ deposits/sell-pressure (bearish prior).

Usage:
  python3 btc_track.py                  # take one snapshot, append to the series
  python3 btc_track.py --show           # print the raw series
  python3 btc_track.py --analyze        # signal -> forward-return test
  python3 btc_track.py --analyze --horizon 1,4,24

Build the series on a schedule (cron), e.g. hourly. Flows are measured from
confirmed txs only, over (prev_snapshot, now]; after a cron outage the window
is capped at MAX_WINDOW_H so one run never walks days of Binance-hot history
(mempool.space throttles heavy sessions — see notes/btc_onchain.md).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from btc import Esplora
from btc.client import SATS
from btc.watchlist import WATCHLIST
from btc_flows import _txs_since
from hl import HyperliquidInfo
from whales_track import _base_rate, _hit_rate, _median, _pearson, _horizons

# --- knobs ---------------------------------------------------------------
DEFAULT_WINDOW_H = 1.0   # first-ever snapshot looks back this far
MAX_WINDOW_H = 6.0       # cap the flow window after cron outages (API politeness)
HORIZON_STEPS = 1        # default forward look-ahead for --analyze
# -------------------------------------------------------------------------

SERIES_PATH = Path(__file__).resolve().parent / "data" / "btc_track.jsonl"


def btc_mark_px() -> float:
    """BTC price for the series (Hyperliquid mids; 0.0 when unavailable)."""
    try:
        return float(HyperliquidInfo().all_mids().get("BTC", 0.0))
    except Exception as e:  # noqa: BLE001 - price is context, not the signal
        print(f"warning: BTC price fetch failed ({e!r})", file=sys.stderr)
        return 0.0


def snapshot(es: Esplora, since_ms: int) -> dict:
    """One time-series point: per-entity balance + confirmed flow since since_ms."""
    entities: dict[str, dict] = {}
    n_failed = 0
    for name, info in WATCHLIST.items():
        try:
            bal = recv = sent = 0
            for addr in info["addresses"]:
                bal += es.balance_sats(addr)
                for tx in _txs_since(es, addr, since_ms):
                    recv += sum(o.get("value", 0) for o in tx["vout"]
                                if o.get("scriptpubkey_address") == addr)
                    sent += sum(i["prevout"].get("value", 0) for i in tx["vin"]
                                if i.get("prevout")
                                and i["prevout"].get("scriptpubkey_address") == addr)
            entities[name] = {"cat": info["category"], "bal": bal / SATS,
                              "in": recv / SATS, "out": sent / SATS,
                              "net": (recv - sent) / SATS}
        except Exception as e:  # noqa: BLE001 - one dead entity must not kill the row
            n_failed += 1
            print(f"warning: {name} snapshot failed ({e!r})", file=sys.stderr)
    return {"time_ms": int(time.time() * 1000), "since_ms": since_ms,
            "btc_px": btc_mark_px(), "n_failed": n_failed, "entities": entities}


def hot_net(snap: dict) -> float:
    """Summed NET flow (BTC) into exchange_hot wallets this window. The signal
    carrier: hot rows are real deposit/withdrawal traffic, cold rows storage."""
    return sum(e["net"] for e in snap["entities"].values()
               if e["cat"] == "exchange_hot")


def append_snapshot(snap: dict) -> None:
    SERIES_PATH.parent.mkdir(exist_ok=True)
    with SERIES_PATH.open("a") as f:
        f.write(json.dumps(snap) + "\n")


def load_series() -> list[dict]:
    if not SERIES_PATH.exists():
        return []
    return [json.loads(ln) for ln in SERIES_PATH.read_text().splitlines() if ln.strip()]


def analyze(series: list[dict], horizon: int = HORIZON_STEPS) -> None:
    """Signal = -hot_net (net OUTflow -> positive = accumulation lean) at t,
    vs BTC forward return t -> t+h. Same spacing guard as whales_track."""
    need = horizon + 2
    if len(series) < need:
        print(f"need >= {need} snapshots to analyze (have {len(series)}). "
              f"Run the snapshot on a schedule (cron) to accumulate the series.")
        return
    dts = [series[t + horizon]["time_ms"] - series[t]["time_ms"]
           for t in range(len(series) - horizon)]
    med = _median(dts)
    keep = [t for t, dt in enumerate(dts) if 0.5 * med <= dt <= 1.5 * med]
    print(f"analyzing {len(series)} snapshots, horizon = {horizon} step(s) "
          f"(median gap {med / 3.6e6:.2f}h), forward (lagged) returns:")
    if len(keep) < len(dts):
        print(f"  note: dropped {len(dts) - len(keep)} pair(s) with irregular spacing")

    sig, fwd = [], []
    for t in keep:
        p0, p1 = series[t]["btc_px"], series[t + horizon]["btc_px"]
        if p0 <= 0 or p1 <= 0:
            continue
        sig.append(-hot_net(series[t]))          # outflow -> bullish prior
        fwd.append(p1 / p0 - 1.0)
    hits, n = _hit_rate(sig, fwd)
    hr = f"{hits}/{n} ({hits / n:.0%})" if n else "n/a"
    print(f"\n  -hot_net_flow -> fwd BTC return : corr={_pearson(sig, fwd):>+5.2f}  "
          f"hit-rate={hr}  const-guess base={_base_rate(fwd):.0%}")
    print("  (signal>0 = net withdrawal from hot wallets = accumulation lean)")


def show(series: list[dict]) -> None:
    print(f"{'time':<17} {'win_h':>5} {'btc_px':>9} {'hot_net':>9} "
          f"{'total_net':>10} {'fail':>4}")
    for s in series:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["time_ms"] / 1000))
        win_h = (s["time_ms"] - s["since_ms"]) / 3.6e6
        total = sum(e["net"] for e in s["entities"].values())
        print(f"{ts:<17} {win_h:>5.1f} {s['btc_px']:>9,.0f} {hot_net(s):>+9.1f} "
              f"{total:>+10.1f} {s['n_failed']:>4}")


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

    series = load_series()
    now_ms = int(time.time() * 1000)
    since_ms = (max(series[-1]["time_ms"], now_ms - int(MAX_WINDOW_H * 3.6e6))
                if series else now_ms - int(DEFAULT_WINDOW_H * 3.6e6))
    snap = snapshot(Esplora(), since_ms)
    append_snapshot(snap)
    win_h = (snap["time_ms"] - since_ms) / 3.6e6
    print(f"\nsnapshot @ {time.strftime('%Y-%m-%d %H:%M')}  "
          f"(window {win_h:.1f}h, BTC ${snap['btc_px']:,.0f}"
          f"{', ' + str(snap['n_failed']) + ' entity fetches FAILED' if snap['n_failed'] else ''})")
    for name, e in sorted(snap["entities"].items(), key=lambda kv: kv[1]["net"]):
        print(f"  {name:<22} {e['cat']:<14} bal {e['bal']:>12,.1f}  "
              f"net {e['net']:>+10.2f}")
    print(f"  hot-wallet net: {hot_net(snap):+,.2f} BTC "
          f"({'deposits/sell-pressure lean' if hot_net(snap) > 0 else 'withdrawals/accumulation lean'})")
    print(f"  appended to {SERIES_PATH}  (total {len(series) + 1} snapshots)")


if __name__ == "__main__":
    main(sys.argv[1:])
