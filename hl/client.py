"""Thin client for the Hyperliquid HyperCore public Info API.

No auth required. All market/account *reads* go through the single POST
endpoint https://api.hyperliquid.xyz/info with a JSON body {"type": ...}.
The whale leaderboard lives on a separate static-stats host.

Docs: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

INFO_URL = "https://api.hyperliquid.xyz/info"
LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class HyperliquidInfo:
    """Read-only access to HyperCore market and per-account state."""

    def __init__(self, timeout: float = 20.0, retries: int = 2):
        self.timeout = timeout
        self.retries = retries

    # --- low level -------------------------------------------------------
    def _post(self, body: dict[str, Any]) -> Any:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            INFO_URL, data=data, headers={"Content-Type": "application/json"}
        )
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                last = e
                if attempt < self.retries:
                    # 429 = rate-limit budget exhausted (burst scans hit this);
                    # back off long enough for the budget to replenish.
                    time.sleep(2.0 ** (attempt + 1) if e.code == 429 else 0.5 * (attempt + 1))
            except Exception as e:  # noqa: BLE001 - retry any transient failure
                last = e
                if attempt < self.retries:
                    time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"Info API request failed: {body.get('type')}") from last

    # --- market-wide -----------------------------------------------------
    def meta_and_asset_ctxs(self) -> tuple[dict, list]:
        """(meta, asset_ctxs): perps universe + per-asset OI/funding/mark/vol."""
        meta, ctxs = self._post({"type": "metaAndAssetCtxs"})
        return meta, ctxs

    def all_mids(self) -> dict[str, str]:
        """coin -> mid price (str)."""
        return self._post({"type": "allMids"})

    # --- whale discovery -------------------------------------------------
    def leaderboard(self, max_age_sec: float = 3600.0) -> list[dict]:
        """All ranked traders with accountValue + windowed pnl/roi/vlm.

        ~32MB. Cached to data/leaderboard.json; refetched when older than
        max_age_sec. Pass max_age_sec=0 to force a refresh.
        """
        DATA_DIR.mkdir(exist_ok=True)
        cache = DATA_DIR / "leaderboard.json"
        fresh = cache.exists() and (time.time() - cache.stat().st_mtime) < max_age_sec
        d = None
        if not fresh:
            try:
                with urllib.request.urlopen(LEADERBOARD_URL, timeout=120) as r:
                    raw = r.read()
                d = json.loads(raw)  # validate before replacing the cache
                tmp = cache.with_name(cache.name + ".tmp")
                tmp.write_bytes(raw)
                tmp.replace(cache)  # atomic: a truncated download never poisons the cache
            except Exception as e:  # noqa: BLE001
                if not cache.exists():
                    raise
                d = None
                print(f"leaderboard refresh failed ({e!r}); using stale cache",
                      file=sys.stderr)
        if d is None:
            d = json.loads(cache.read_text())
        return d["leaderboardRows"] if isinstance(d, dict) else d

    # --- per-account -----------------------------------------------------
    def clearinghouse_state(self, address: str) -> dict:
        """Current perp positions + margin summary for one address."""
        return self._post({"type": "clearinghouseState", "user": address})

    def user_fills(self, address: str) -> list[dict]:
        """Most recent fills (up to 2000) for one address."""
        return self._post({"type": "userFills", "user": address})

    def user_fills_by_time(self, address: str, start_ms: int, end_ms: int | None = None) -> list[dict]:
        """Fills in [start_ms, end_ms]; use for incremental polling."""
        body = {"type": "userFillsByTime", "user": address, "startTime": start_ms}
        if end_ms is not None:
            body["endTime"] = end_ms
        return self._post(body)
