"""Curated Bitcoin entity watchlist — the labels the blockchain does not carry.

The chain has only addresses; attribution is external. This file is that
external layer, kept small, human-curated, and honest about confidence. An
entity may own *many* addresses; we key by entity and list its address(es).

Seed policy: only addresses whose balance we have sanity-checked live (a claimed
"exchange cold wallet" must actually hold a huge balance). Add new ones the same
way — paste the address, note the source, verify the balance before trusting it.

  ⚠️ Clustered entities (ETFs / custodians). BlackRock's IBIT does NOT have a
  single address: per Arkham, Coinbase Prime custodies it across *many* rotating
  addresses each holding <=300-600 BTC. Hand-listing them is a losing game and
  goes stale fast — that specific "BlackRock -> Coinbase" attribution is what a
  labeled API (Arkham/Whale Alert) is for. The `addresses` list per entity is a
  list precisely so you *can* paste a cluster here if you obtain one, but treat
  coverage as best-effort, not complete.
"""
from __future__ import annotations

# entity name -> {"category": ..., "addresses": [...], "source": ...}
# category is free-form: exchange_cold / exchange_hot / custody / etf / fund / misc
WATCHLIST: dict[str, dict] = {
    "Binance (cold)": {
        "category": "exchange_cold",
        # The single largest BTC address; ~248k BTC. Widely attributed to Binance.
        # Dormant deep vault: in the last ~615d it only received dust/marker outputs
        # (net +0.06 BTC) -> not a useful trace origin; watch the hot wallet instead.
        "addresses": ["34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo"],
        "source": "public/Arkham; balance verified live",
    },
    "Binance (hot)": {
        "category": "exchange_hot",
        # Hyper-active operational hub: 2.26M+ txs, ~14.6k BTC balance, 59M BTC
        # cumulative throughput. This is where Binance's real daily flow happens.
        # First inferred from co-occurrence w/ Binance cold; CONFIRMED binance by
        # GraphSense binance pack (labels_import).
        "addresses": ["bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h"],
        "source": "GraphSense binance pack; also balance/behavior verified live (2026-07-01)",
    },
    "Bitfinex (cold)": {
        "category": "exchange_cold",
        # ~130k BTC cold storage. Widely attributed to Bitfinex.
        "addresses": ["bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97"],
        "source": "GraphSense bitfinex pack (Bitfinex's own wallets.txt); balance verified live",
    },
    "Bitfinex (hot)": {
        "category": "exchange_hot",
        # High-throughput operational wallet: 484k+ txs, ~5.4k BTC balance,
        # fed by Bitfinex (cold) in 5k-12k BTC tranches. First inferred from the
        # cold->hot flow; CONFIRMED "bitfinex BTC hot wallet" by GraphSense
        # (Bitfinex's own wallets.txt).
        "addresses": ["1Kr6QSydW9bFQG1mXiPNNu6WpJGmUa9i1g"],
        "source": "GraphSense bitfinex pack (Bitfinex's own wallets.txt); flow-inferred then confirmed",
    },
    "Bitfinex (cold 2)": {
        "category": "exchange_cold",
        # ~11.7k BTC, receives repeatedly from Bitfinex (hot) (hot->cold sweep).
        # First flagged "cold?" (internal-vs-external unknown); CONFIRMED
        # "bitfinex BTC cold wallet" by GraphSense (Bitfinex's own wallets.txt).
        "addresses": ["3JZq4atUahhuA9rLhXLMhhTo133J9rF97j"],
        "source": "GraphSense bitfinex pack (Bitfinex's own wallets.txt); flow-inferred then confirmed",
    },
    # --- add your own below (verify the balance first) ----------------------
    # "Coinbase Prime (deposit)": {"category": "custody", "addresses": [...],
    #     "source": "Arkham entity export"},
    # "BlackRock IBIT (cluster)": {"category": "etf", "addresses": [ ...many... ],
    #     "source": "Arkham; partial — rotates across <=300 BTC addrs"},
}


def address_labels() -> dict[str, tuple[str, str]]:
    """Reverse map: address -> (entity_name, category), lowercased keys."""
    out: dict[str, tuple[str, str]] = {}
    for name, info in WATCHLIST.items():
        for addr in info["addresses"]:
            out[addr.lower()] = (name, info["category"])
    return out


def watched_addresses() -> list[tuple[str, str, str]]:
    """Flat list of (address, entity_name, category)."""
    return [
        (addr, name, info["category"])
        for name, info in WATCHLIST.items()
        for addr in info["addresses"]
    ]
