"""Import free community address→entity labels (GraphSense tagpacks) into our map.

The chain carries no names; this pulls an *open, no-key* attribution dataset and
turns it into a BTC address→(entity,label) lookup we can overlay on the curated
watchlist. It massively widens counterparty naming for free — every major
exchange's published hot/cold wallets, plus the Bitwise BITB ETF holdings address.

Source: https://github.com/graphsense/graphsense-tagpacks (packs/*.yaml). Confirmed
its Bitfinex pack (from Bitfinex's own wallets.txt) matches addresses we inferred
by flow analysis — good corroboration. Coverage is strong for exchanges, weak for
custodial/ETF clusters (BlackRock/Coinbase Prime/MicroStrategy) — those still need
Arkham (btc/arkham.py). Note BlackRock is absent but *Bitwise* disclosed one.

Tagpacks are YAML; we're stdlib-only, so we parse the regular subset we need
(top-level `actor`/`currency`, then a `tags:` list of address/currency/label).
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

RAW_BASE = "https://raw.githubusercontent.com/graphsense/graphsense-tagpacks/master/packs/"
CACHE = Path(__file__).resolve().parent.parent / "data" / "btc_labels.json"

# Curated BTC-relevant packs (exchanges + a publicly-disclosed ETF).
PACKS = [
    "binance.yaml", "exchange-wallets-binance.yaml", "exchange-wallets-bitfinexcom.yaml",
    "exchange-wallets-bybit.yaml", "exchange-wallets-cryptocom.yaml",
    "exchange-wallets-deribit.yaml", "exchange-wallets-huobi.yaml",
    "exchange-wallets-kucoin.yaml", "exchange-wallets-okx.yaml",
    "exchange-wallets-swissborg.yaml", "BITB_etf.yaml",
] + [f"exchange-wallets-bitmex_{i}.yaml" for i in range(7)]


def _looks_btc(addr: str) -> bool:
    return bool(addr) and (addr[0] in "13" or addr.startswith("bc1"))


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] in "'\"" and v[-1] == v[0]:
        v = v[1:-1]
    return v


def parse_tagpack(text: str) -> list[dict]:
    """Extract BTC tags from one tagpack: [{address, entity, label}]. Subset parser."""
    actor = ""
    default_cur = ""
    lines = text.splitlines()
    # header scalars before `tags:`
    i = 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s == "tags:" or s.startswith("tags:"):
            i += 1
            break
        if s.startswith("actor:"):
            actor = _unquote(s.split(":", 1)[1])
        elif s.startswith("currency:"):
            default_cur = _unquote(s.split(":", 1)[1]).upper()
    # tag list items
    out: list[dict] = []
    cur: dict | None = None
    for ln in lines[i:]:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("- "):
            if cur and _looks_btc(cur.get("address", "")):
                out.append(cur)
            cur = {"currency": default_cur, "label": "", "address": ""}
            s = s[2:].strip()  # allow "- address: X" on one line
        if cur is None:
            continue
        if s.startswith("address:"):
            cur["address"] = _unquote(s.split(":", 1)[1])
        elif s.startswith("currency:"):
            cur["currency"] = _unquote(s.split(":", 1)[1]).upper()
        elif s.startswith("label:"):
            cur["label"] = _unquote(s.split(":", 1)[1])
    if cur and _looks_btc(cur.get("address", "")):
        out.append(cur)
    # keep only BTC currency (or unspecified but BTC-looking address)
    return [{"address": t["address"], "entity": actor or "?", "label": t["label"]}
            for t in out if t["currency"] in ("", "BTC") and _looks_btc(t["address"])]


def _fetch(name: str) -> str:
    req = urllib.request.Request(RAW_BASE + name, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def refresh(packs: list[str] = PACKS) -> dict[str, dict]:
    """Fetch all packs, build address(lower)->{entity,label} for BTC, cache to disk."""
    labels: dict[str, dict] = {}
    for name in packs:
        try:
            for t in parse_tagpack(_fetch(name)):
                labels[t["address"].lower()] = {"entity": t["entity"], "label": t["label"]}
        except Exception as e:  # noqa: BLE001 - skip a bad/missing pack, keep going
            print(f"  ! skip {name}: {e}")
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(labels))
    return labels


def community_labels() -> dict[str, dict]:
    """Cached address(lower)->{entity,label}; empty until refresh() is run."""
    if not CACHE.exists():
        return {}
    return json.loads(CACHE.read_text())


if __name__ == "__main__":
    labels = refresh()
    by_entity: dict[str, int] = {}
    for v in labels.values():
        by_entity[v["entity"]] = by_entity.get(v["entity"], 0) + 1
    print(f"\ncached {len(labels)} BTC labels across {len(by_entity)} entities -> {CACHE}")
    for ent, n in sorted(by_entity.items(), key=lambda kv: -kv[1]):
        print(f"  {ent:<14} {n:>4}")
