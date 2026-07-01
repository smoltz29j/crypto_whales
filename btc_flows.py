#!/usr/bin/env python3
"""Watch known-entity Bitcoin addresses for large on-chain movements.

The watchlist (btc/watchlist.py) maps real-world entities to their addresses;
this script reads each watched address's recent transactions and flags balance
movements >= THRESHOLD_BTC, classified as IN (received) / OUT (sent) with the
counterparty labeled whenever the other side is also on the watchlist.

This is the "watchlist" approach: it only sees movements touching addresses you
have curated. Single-address entities (exchange cold wallets) are captured
cleanly; clustered entities (ETF custody) need a labeled API instead — see the
note in btc/watchlist.py.

Usage:
  python3 btc_flows.py                 # recent large movements per watched entity
  python3 btc_flows.py --hours 24      # only movements in the last 24h
  python3 btc_flows.py --min 100       # threshold = 100 BTC (default 50)
  python3 btc_flows.py --balances      # current balance of each watched entity
  python3 btc_flows.py --netflow --hours 24   # per-entity IN/OUT/NET over window
                                              # (exchange net-flow: sell vs buy pressure)

Counterparty names come from the curated watchlist overlaid on free community
labels (btc/labels_import.py -> data/btc_labels.json); run `python3 -m
btc.labels_import` once to populate them.
"""
from __future__ import annotations

import sys
import time

from btc import Esplora
from btc.client import SATS
from btc.labels_import import community_labels
from btc.watchlist import WATCHLIST, watched_addresses

# --- knobs ---------------------------------------------------------------
THRESHOLD_BTC = 50.0     # flag movements at or above this size
# -------------------------------------------------------------------------


def _addr_delta(tx: dict, addr: str) -> tuple[int, int]:
    """(received_sats, sent_sats) attributable to `addr` in this tx."""
    recv = sum(o.get("value", 0) for o in tx["vout"]
               if o.get("scriptpubkey_address") == addr)
    sent = sum(i["prevout"].get("value", 0) for i in tx["vin"]
               if i.get("prevout") and i["prevout"].get("scriptpubkey_address") == addr)
    return recv, sent


def label_map() -> dict[str, str]:
    """address(lower) -> display entity name; community labels overlaid by curated."""
    m = {a: v["entity"] for a, v in community_labels().items()}
    for name, info in WATCHLIST.items():  # curated names win over community
        for a in info["addresses"]:
            m[a.lower()] = name
    return m


def _counterparties(tx: dict, addr: str, outflow: bool, labels: dict[str, str]) -> list[tuple[str, int]]:
    """Aggregate the *other* side by label. outflow -> look at outputs, else inputs."""
    agg: dict[str, int] = {}
    side = tx["vout"] if outflow else [i.get("prevout", {}) for i in tx["vin"]]
    for entry in side:
        a = entry.get("scriptpubkey_address")
        if not a or a == addr:
            continue
        name = labels.get(a.lower()) or f"{a[:8]}…{a[-4:]}"
        agg[name] = agg.get(name, 0) + entry.get("value", 0)
    return sorted(agg.items(), key=lambda kv: -kv[1])


def collect_movements(hl: Esplora, min_btc: float, since_ms: int | None):
    labels = label_map()
    moves = []
    for addr, entity, category in watched_addresses():
        for tx in hl.address_txs(addr):
            st = tx.get("status", {})
            t_ms = (st.get("block_time") or int(time.time())) * 1000
            if since_ms is not None and t_ms < since_ms:
                continue
            recv, sent = _addr_delta(tx, addr)
            delta = recv - sent
            if abs(delta) < min_btc * SATS:
                continue
            outflow = delta < 0
            moves.append({
                "time_ms": t_ms,
                "confirmed": st.get("confirmed", False),
                "entity": entity,
                "category": category,
                "direction": "OUT" if outflow else "IN",
                "btc": abs(delta) / SATS,
                "counterparties": _counterparties(tx, addr, outflow, labels),
                "txid": tx["txid"],
            })
    moves.sort(key=lambda m: -m["time_ms"])
    return moves


def print_movements(moves) -> None:
    if not moves:
        print("no movements above threshold in range.")
        return
    for m in moves:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(m["time_ms"] / 1000))
        pend = "" if m["confirmed"] else "  (mempool/unconfirmed)"
        arrow = "→ out to" if m["direction"] == "OUT" else "← in from"
        cps = ", ".join(f"{n} {v / SATS:,.1f}₿" for n, v in m["counterparties"][:3]) or "?"
        print(f"{ts}  {m['entity']:<18} {m['direction']:<3} "
              f"{m['btc']:>10,.2f} BTC  {arrow} {cps}{pend}")
        print(f"                     tx {m['txid']}")


def _txs_since(hl: Esplora, addr: str, since_ms: int) -> list[dict]:
    """All confirmed txs for addr with block_time >= since_ms (paginates back)."""
    out = [t for t in hl.address_txs(addr) if t.get("status", {}).get("confirmed")]
    while out and out[-1]["status"].get("block_time", 0) * 1000 >= since_ms:
        page = hl.address_txs_chain(addr, out[-1]["txid"])
        if not page:
            break
        out.extend(page)
    return [t for t in out if t["status"].get("block_time", 0) * 1000 >= since_ms]


def entity_netflow(hl: Esplora, since_ms: int) -> list[dict]:
    """Per-entity received/sent/net (BTC) over the window. Exchange-flow signal:
    net INflow to exchange wallets ~ sell pressure; net OUTflow ~ accumulation."""
    rows = []
    for name, info in WATCHLIST.items():
        recv = sent = 0
        for addr in info["addresses"]:
            for tx in _txs_since(hl, addr, since_ms):
                recv += sum(o.get("value", 0) for o in tx["vout"]
                            if o.get("scriptpubkey_address") == addr)
                sent += sum(i["prevout"].get("value", 0) for i in tx["vin"]
                            if i.get("prevout") and i["prevout"].get("scriptpubkey_address") == addr)
        rows.append({"entity": name, "category": info["category"],
                     "in": recv / SATS, "out": sent / SATS, "net": (recv - sent) / SATS})
    return rows


def print_netflow(rows: list[dict], hours: float) -> None:
    print(f"Exchange net-flow over last {hours:g}h  (net>0 = into wallet; for hot "
          f"wallets that ≈ deposits/sell-pressure)\n")
    print(f"{'entity':<22} {'category':<14} {'IN':>12} {'OUT':>12} {'NET':>12}")
    tin = tout = 0.0
    for r in sorted(rows, key=lambda x: x["net"]):
        print(f"{r['entity']:<22} {r['category']:<14} {r['in']:>12,.2f} "
              f"{r['out']:>12,.2f} {r['net']:>+12,.2f}")
        tin += r["in"]; tout += r["out"]
    print(f"{'':<22} {'TOTAL':<14} {tin:>12,.2f} {tout:>12,.2f} {tin - tout:>+12,.2f}")
    net = tin - tout
    lean = "net INflow → leans sell-pressure" if net > 0 else "net OUTflow → leans accumulation"
    print(f"\n  {lean} ({net:+,.2f} BTC across watched wallets).")
    print("  caveat: includes internal transfers between watched wallets; hot-wallet "
          "rows carry the real signal, cold rows are storage moves.")


def print_balances(hl: Esplora) -> None:
    print(f"{'entity':<22} {'category':<14} {'balance (BTC)':>16}")
    total = 0
    for name, info in WATCHLIST.items():
        bal = sum(hl.balance_sats(a) for a in info["addresses"])
        total += bal
        print(f"{name:<22} {info['category']:<14} {bal / SATS:>16,.2f}")
    print(f"{'':<22} {'TOTAL':<14} {total / SATS:>16,.2f}")


def main(argv: list[str]) -> None:
    hl = Esplora()
    if "--balances" in argv:
        print_balances(hl)
        return

    if "--netflow" in argv:
        hours = float(argv[argv.index("--hours") + 1]) if "--hours" in argv else 24.0
        since_ms = int((time.time() - hours * 3600) * 1000)
        print_netflow(entity_netflow(hl, since_ms), hours)
        return

    min_btc = THRESHOLD_BTC
    if "--min" in argv:
        min_btc = float(argv[argv.index("--min") + 1])
    since_ms = None
    if "--hours" in argv:
        hours = float(argv[argv.index("--hours") + 1])
        since_ms = int((time.time() - hours * 3600) * 1000)

    scope = f"last {argv[argv.index('--hours') + 1]}h" if since_ms else "recent txs"
    print(f"watching {len(watched_addresses())} address(es) across "
          f"{len(WATCHLIST)} entit(ies); movements >= {min_btc:g} BTC, {scope}:\n")
    print_movements(collect_movements(hl, min_btc, since_ms))


if __name__ == "__main__":
    main(sys.argv[1:])
