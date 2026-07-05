"""Profile GraphSense-labeled exchange addresses to grow the watchlist.

The community labels (labels_import.py) name ~60 candidate exchange wallets
beyond BitMEX's 336k deposit addresses — okx, bybit, huobi, kucoin, crypto.com,
deribit, swissborg, plus binance/bitfinex entries we may not watch yet. This
profiles each candidate with ONE Esplora call (balance + tx_count both come
from /address) and prints watchlist-ready entries for the ones that actually
hold coins, per the seed policy in watchlist.py (verify balance before trusting).

mempool.space throttles heavy sessions, so calls are spaced (SLEEP_SEC on top
of the client's 0.2s) and results are cached to data/btc_profile.json — reruns
only fetch addresses not yet profiled. This one-call-per-address pass is why
the expansion was feasible without a self-hosted node; do NOT bolt tx-history
pagination onto it.

Usage:
  python3 -m btc.expand              # profile candidates, print suggestions
  python3 -m btc.expand --refresh    # ignore the profile cache, refetch all
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .client import Esplora, SATS
from .labels_import import community_labels
from .watchlist import WATCHLIST

# --- knobs ---------------------------------------------------------------
SKIP_ENTITIES = {"bitmex", "bitwise"}  # 336k deposit addrs / known-stale ETF addr
MIN_BTC = 100.0        # suggest watchlist entries at or above this balance
HOT_TX_COUNT = 50_000  # tx_count at or above this -> exchange_hot guess
SLEEP_SEC = 0.5        # extra spacing between calls (politeness)
# -------------------------------------------------------------------------

PROFILE_CACHE = Path(__file__).resolve().parent.parent / "data" / "btc_profile.json"


def candidates() -> list[tuple[str, str, str]]:
    """(address, entity, label) for labeled addrs not skipped and not watched.
    Uses the original-case `addr` — base58 addresses are case-sensitive, the
    lowercased dict key would 404 on Esplora."""
    watched = {a.lower() for info in WATCHLIST.values() for a in info["addresses"]}
    out = []
    for key, v in community_labels().items():
        if v["entity"] in SKIP_ENTITIES or key in watched:
            continue
        out.append((v.get("addr", key), v["entity"], v.get("label", "")))
    return sorted(out, key=lambda t: t[1])


def load_cache() -> dict[str, dict]:
    if not PROFILE_CACHE.exists():
        return {}
    return json.loads(PROFILE_CACHE.read_text())


def save_cache(cache: dict[str, dict]) -> None:
    PROFILE_CACHE.parent.mkdir(exist_ok=True)
    tmp = PROFILE_CACHE.with_name(PROFILE_CACHE.name + ".tmp")
    tmp.write_text(json.dumps(cache))
    tmp.replace(PROFILE_CACHE)


def profile(es: Esplora, cands: list[tuple[str, str, str]],
            refresh: bool = False) -> dict[str, dict]:
    """addr -> {entity, label, balance_btc, tx_count, checked_ms}; cached."""
    cache = {} if refresh else load_cache()
    todo = [c for c in cands if c[0] not in cache]
    if todo:
        print(f"profiling {len(todo)} address(es) "
              f"({len(cands) - len(todo)} already cached) ...", file=sys.stderr)
    for i, (addr, entity, label) in enumerate(todo, 1):
        try:
            a = es.address(addr)
            cs = a["chain_stats"]
            cache[addr] = {
                "entity": entity, "label": label,
                "balance_btc": (cs["funded_txo_sum"] - cs["spent_txo_sum"]) / SATS,
                "tx_count": cs["tx_count"],
                "checked_ms": int(time.time() * 1000),
            }
        except Exception as e:  # noqa: BLE001 - keep going, cache what worked
            print(f"  ! {addr[:12]}… ({entity}) failed: {e!r}", file=sys.stderr)
        if i % 10 == 0:
            print(f"  ...{i}/{len(todo)}", file=sys.stderr)
            save_cache(cache)
        time.sleep(SLEEP_SEC)
    save_cache(cache)
    return {a: cache[a] for a, _, _ in cands if a in cache}


def print_report(profiled: dict[str, dict]) -> None:
    rows = sorted(profiled.items(), key=lambda kv: (kv[1]["entity"],
                                                    -kv[1]["balance_btc"]))
    print(f"\n{'entity':<12} {'address':<20} {'balance (BTC)':>14} {'txs':>9}  label")
    for addr, p in rows:
        print(f"{p['entity']:<12} {addr[:16] + '…':<20} {p['balance_btc']:>14,.2f} "
              f"{p['tx_count']:>9,}  {p['label'][:40]}")

    rich = {a: p for a, p in profiled.items() if p["balance_btc"] >= MIN_BTC}
    if not rich:
        print(f"\nno candidate holds >= {MIN_BTC:g} BTC — nothing to add.")
        return
    print(f"\nwatchlist-ready entries (balance >= {MIN_BTC:g} BTC, verified just "
          f"now; category guessed from tx_count, sanity-check before pasting):\n")
    today = time.strftime("%Y-%m-%d")
    by_entity: dict[str, list[tuple[str, dict]]] = {}
    for a, p in sorted(rich.items(), key=lambda kv: -kv[1]["balance_btc"]):
        by_entity.setdefault(p["entity"], []).append((a, p))
    for entity, addrs in by_entity.items():
        for i, (a, p) in enumerate(addrs):
            cat = "exchange_hot" if p["tx_count"] >= HOT_TX_COUNT else "exchange_cold"
            tag = ("hot" if cat == "exchange_hot" else "cold") + \
                  (f" {i + 1}" if len(addrs) > 1 else "")
            print(f'    "{entity.capitalize()} ({tag})": {{')
            print(f'        "category": "{cat}",')
            print(f'        # ~{p["balance_btc"]:,.0f} BTC, {p["tx_count"]:,} txs'
                  f' — GraphSense label: {p["label"] or "?"}')
            print(f'        "addresses": ["{a}"],')
            print(f'        "source": "GraphSense pack; balance verified live {today}",')
            print(f'    }},')


def main(argv: list[str]) -> None:
    cands = candidates()
    print(f"{len(cands)} labeled candidate address(es) outside the watchlist "
          f"(skipping {', '.join(sorted(SKIP_ENTITIES))})", file=sys.stderr)
    profiled = profile(Esplora(), cands, refresh="--refresh" in argv)
    print_report(profiled)


if __name__ == "__main__":
    main(sys.argv[1:])
