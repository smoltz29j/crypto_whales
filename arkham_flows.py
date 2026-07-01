#!/usr/bin/env python3
"""Query Arkham for label-annotated transfers of an entity ("BlackRock -> Coinbase").

This is the labeled path that the free raw-chain watchlist (btc_flows.py) can't
do for custodial/omnibus/clustered entities (Coinbase, BlackRock/IBIT,
MicroStrategy). It needs an Arkham API key in ARKHAM_API_KEY — get a free-tier
key at https://intel.arkm.com/api. Without one it prints how to set it and exits.

Usage:
  python3 arkham_flows.py blackrock                 # recent BTC transfers, both directions
  python3 arkham_flows.py blackrock --flow out      # only outgoing (e.g. deposits to Coinbase)
  python3 arkham_flows.py microstrategy --last 7d --min-usd 1000000
  python3 arkham_flows.py coinbase --chains bitcoin --flow in

Entity ids are Arkham's slugs (blackrock, coinbase, microstrategy, binance, ...).
"""
from __future__ import annotations

import sys
import time

from btc.arkham import Arkham, ArkhamAuthError


def _side_name(transfer: dict, side: str) -> str:
    """Best-effort display name for from/to side across possible response shapes."""
    # try nested object first: transfer['fromAddress'] = {address, arkhamEntity{name}, arkhamLabel{name}}
    obj = transfer.get(f"{side}Address")
    if isinstance(obj, dict):
        ent = obj.get("arkhamEntity") or {}
        lab = obj.get("arkhamLabel") or {}
        return ent.get("name") or lab.get("name") or _short(obj.get("address"))
    # flat fallbacks
    ent = transfer.get(f"{side}ArkhamEntity") or {}
    if ent.get("name"):
        return ent["name"]
    return _short(transfer.get(f"{side}Address") if isinstance(transfer.get(f"{side}Address"), str) else None)


def _short(a: str | None) -> str:
    return f"{a[:8]}…{a[-4:]}" if a and len(a) > 14 else (a or "?")


def _rows(resp) -> list[dict]:
    if isinstance(resp, dict):
        return resp.get("transfers") or resp.get("data") or []
    return resp if isinstance(resp, list) else []


def main(argv: list[str]) -> None:
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return
    entity = argv[0]

    def opt(flag, default=None):
        return argv[argv.index(flag) + 1] if flag in argv else default

    flow = opt("--flow", "all")
    chains = opt("--chains", "bitcoin")
    last = opt("--last", "24h")
    min_usd = float(opt("--min-usd", 0)) or None

    ark = Arkham()
    try:
        resp = ark.transfers(base=entity, flow=flow, chains=chains,
                             usd_gte=min_usd, time_last=last, limit=50)
    except ArkhamAuthError as e:
        print(e)
        return

    rows = _rows(resp)
    print(f"Arkham transfers  base={entity}  flow={flow}  chains={chains}  "
          f"last={last}{f'  >=${min_usd:,.0f}' if min_usd else ''}  ({len(rows)} rows)\n")
    if not rows:
        print("no transfers matched (widen --last / lower --min-usd, or check the entity slug).")
        return
    for t in rows:
        ts_ms = t.get("blockTimestamp") or t.get("time") or 0
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts_ms / 1000)) if ts_ms else "?"
        frm, to = _side_name(t, "from"), _side_name(t, "to")
        usd = t.get("historicalUSD") or t.get("usd") or 0
        sym = t.get("tokenSymbol") or t.get("tokenName") or ""
        amt = t.get("unitValue") or t.get("amount") or ""
        txid = t.get("transactionHash") or t.get("txid") or ""
        print(f"{ts}  {frm}  →  {to}   {amt} {sym}  (${float(usd):,.0f})")
        if txid:
            print(f"                     tx {txid}")


if __name__ == "__main__":
    main(sys.argv[1:])
