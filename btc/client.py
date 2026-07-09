"""Thin read-only client for the public Esplora Bitcoin API.

No auth required. Esplora is the block-explorer API served identically by
mempool.space and blockstream.info; we default to mempool.space and let the
base URL be overridden. All values on the wire are in **satoshis** (int);
this client returns them as-is — convert with sats/1e8 at the edges.

Docs: https://github.com/Blockstream/esplora/blob/master/API.md

Bitcoin has no per-account read like Hyperliquid — everything is UTXO/tx data
keyed by *address*. The whale workflow here is: watch known entity addresses
(see btc/watchlist.py) and read their recent txs to spot large movements.
"""
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

MEMPOOL_API = "https://mempool.space/api"
BLOCKSTREAM_API = "https://blockstream.info/api"

SATS = 100_000_000  # 1 BTC


class Esplora:
    """Read-only access to Bitcoin address/tx/block data via Esplora."""

    def __init__(self, base_url: str = MEMPOOL_API, timeout: float = 30.0, retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries

    # --- low level -------------------------------------------------------
    def _get(self, path: str) -> Any:
        url = self.base_url + path
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    out = json.load(r)
                time.sleep(0.2)  # be polite to the public endpoint
                return out
            except Exception as e:  # noqa: BLE001 - retry any transient failure
                last = e
                if attempt < self.retries:
                    time.sleep(2 ** attempt)  # exponential backoff: 1,2,4s
        raise RuntimeError(f"Esplora GET failed: {path}") from last

    # --- address ---------------------------------------------------------
    def address(self, addr: str) -> dict:
        """Address summary incl. chain_stats/mempool_stats (funded/spent sums)."""
        return self._get(f"/address/{addr}")

    def balance_sats(self, addr: str) -> int:
        """Confirmed balance in satoshis (funded - spent)."""
        cs = self.address(addr)["chain_stats"]
        return cs["funded_txo_sum"] - cs["spent_txo_sum"]

    def address_txs(self, addr: str) -> list[dict]:
        """Most recent txs for an address (up to 50: mempool + confirmed).

        Each tx carries full vin/vout: vin[].prevout.{scriptpubkey_address,value},
        vout[].{scriptpubkey_address,value}, and status.{confirmed,block_time}.
        """
        return self._get(f"/address/{addr}/txs")

    def address_txs_chain(self, addr: str, last_txid: str | None = None) -> list[dict]:
        """One page (25) of *confirmed* txs older than last_txid; page to go back.

        Pass the last txid of the previous page as last_txid. Empty list = end of
        history. Use to walk further back than address_txs' ~50-tx recent window.
        """
        path = f"/address/{addr}/txs/chain"
        if last_txid:
            path += f"/{last_txid}"
        return self._get(path)

    def address_txs_paged(self, addr: str, max_txs: int = 500) -> list[dict]:
        """Walk back through confirmed history up to max_txs (paginates for you)."""
        out = self.address_txs(addr)
        out = [t for t in out if t.get("status", {}).get("confirmed")]
        while out and len(out) < max_txs:
            page = self.address_txs_chain(addr, out[-1]["txid"])
            if not page:
                break
            out.extend(page)
        return out[:max_txs]

    # --- chain -----------------------------------------------------------
    def tip_height(self) -> int:
        return int(self._get("/blocks/tip/height"))
