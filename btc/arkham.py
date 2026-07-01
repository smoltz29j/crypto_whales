"""Thin client for the Arkham Intel API — the labeled-entity layer.

This is the *paid-DB* path we reach for only when raw-chain + hand watchlist
can't attribute an address (custodial / omnibus / rotating clusters: Coinbase,
BlackRock/IBIT, MicroStrategy). Arkham resolves entity <-> address and serves
label-annotated transfers, which is exactly what "BlackRock -> Coinbase" needs.

Auth: an `API-Key` header. Get a key at https://intel.arkm.com/api (there is a
free tier — limited rate/history but $0). Put it in the ARKHAM_API_KEY env var;
this client reads it and raises a clear error if it's missing. Without a key
every call fails, so nothing here can run until you set it.

Docs: https://intel.arkm.com/api/docs   (base https://api.arkm.com)
Rate limits: standard 20 req/s; /transfers is HEAVY at 1 req/s.

Field names below follow the documented shapes; if a response key differs on
the live API, adjust the extractors in arkham_flows.py rather than here.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = "https://api.arkm.com"
API_KEY_ENV = "ARKHAM_API_KEY"


class ArkhamAuthError(RuntimeError):
    """Raised when no API key is configured."""


class Arkham:
    """Read-only access to Arkham entity/label/transfer intelligence."""

    def __init__(self, api_key: str | None = None, timeout: float = 30.0, retries: int = 3):
        self.api_key = api_key or os.environ.get(API_KEY_ENV)
        self.timeout = timeout
        self.retries = retries

    def _require_key(self) -> str:
        if not self.api_key:
            raise ArkhamAuthError(
                f"No Arkham API key. Get a (free-tier) key at "
                f"https://intel.arkm.com/api and set {API_KEY_ENV}=<key>."
            )
        return self.api_key

    # --- low level -------------------------------------------------------
    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        key = self._require_key()
        url = BASE_URL + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        req = urllib.request.Request(url, headers={"API-Key": key, "User-Agent": "Mozilla/5.0"})
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
                # 429 = rate limited (heavy endpoint is 1 req/s) -> back off and retry
                if e.code == 429 and attempt < self.retries:
                    time.sleep(2 ** attempt)
                    last = e
                    continue
                raise
            except Exception as e:  # noqa: BLE001
                last = e
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Arkham GET failed: {path}") from last

    # --- endpoints -------------------------------------------------------
    def address_intel(self, address: str, chain: str | None = None) -> dict:
        """Entity/label for one address (arkhamEntity, arkhamLabel, contract)."""
        return self._get(f"/intelligence/address/{address}", {"chain": chain})

    def entity_addresses(self, entity_id: str) -> dict:
        """All addresses of an entity, keyed by chain. entity_id e.g. 'blackrock'."""
        return self._get(f"/user/entities/{entity_id}")

    def transfers(self, base: str, flow: str = "all", chains: str = "bitcoin",
                  usd_gte: float | None = None, time_last: str | None = None,
                  time_gte: int | None = None, time_lte: int | None = None,
                  limit: int = 50, offset: int = 0) -> Any:
        """Label-annotated transfers for an entity/address. HEAVY: 1 req/s.

        base:  entity id or address (e.g. 'blackrock', 'coinbase', 'microstrategy')
        flow:  'in' | 'out' | 'self' | 'all'
        usd_gte: min USD value; time_last: e.g. '24h'/'7d'; time_* are ms.
        """
        return self._get("/transfers", {
            "base": base, "flow": flow, "chains": chains,
            "usdGte": usd_gte, "timeLast": time_last,
            "timeGte": time_gte, "timeLte": time_lte,
            "limit": limit, "offset": offset,
        })
