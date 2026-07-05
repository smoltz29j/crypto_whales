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
    # --- expansion 2026-07-05: btc/expand.py profiled every GraphSense-labeled
    # address (one /address call each: balance + tx_count); only funded ones
    # added, per seed policy. Zero-balance labeled wallets (kucoin, swissborg,
    # deribit, Binance's old 1NDyJtNT… hot hub w/ 1.19M txs) were left out —
    # rotated/drained addresses, verify again before ever adding.
    "Binance (cold 2)": {
        "category": "exchange_cold",
        # GraphSense "binance reserve wallets BTC": ~174.9k + ~68.2k BTC, low
        # tx counts (565 / 168) -> reserve vaults, like 34xp… above.
        "addresses": ["3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6",
                      "3LYJfcfHPXYJreMsASk2jkn69LWEYKzexb"],
        "source": "GraphSense binance pack; balances verified live 2026-07-05",
    },
    "Crypto.com (hot)": {
        "category": "exchange_hot",
        # ~23.5k BTC and 96k txs -> active operational wallet.
        "addresses": ["bc1qr4dl5wa7kl8yu792dceg9z5knl2gkn220lk7a9"],
        "source": "GraphSense cryptocom pack; balance verified live 2026-07-05",
    },
    "OKX (cold)": {
        "category": "exchange_cold",
        # 15 funded vault tranches (round 3k/5k/6k/10k balances, tx_count <= 115),
        # ~68.1k BTC total. GraphSense okex pack; 8 more labeled addrs were empty.
        "addresses": ["1CY7fykRLWXeSbKB885Kr4KjQxmDdvW923",
                      "16rF2zwSJ9goQ9fZfYoti5LsUqqegb5RnA",
                      "1FY6RL8Ju9b6CGsHTK68yYEcnzUasufyCe",
                      "1BsdDaJtgFZrLfzEXvh6cD4VhtHHSHhMea",
                      "178E8tYZ5WJ6PpADdpmmZd67Se7uPhJCLX",
                      "1Lj2mCPJYbbC2X6oYwV6sXnE8CZ4heK5UD",
                      "1LnoZawVFFQihU8d8ntxLMpYheZUfyeVAK",
                      "18QUDxjDZAqAJorr4jkSEWHUDGLBF9uRCc",
                      "14kHu26yWkVD8qAnBfcFXHXxgquNoSpKum",
                      "1DVTB9YKi4KNjyEbAHPp17T8R1Pp17nSmA",
                      "1DnHx95d2t5URq2SYvVk6kxGryvTEbTnTs",
                      "15Exz1BAVan4Eweagy1rcPJnfyc6KJ4GvL",
                      "1M6E6vPaYsuCb34mDNS2aepu2aJyL6xBG4",
                      "13jTtHxBPFwZkaCdm6BwJMMJkqvTpBZccw",
                      "1CE8chGD6Nu8qjcDF2uR1wMKyoWb8Kyxwz"],
        "source": "GraphSense okex pack; balances verified live 2026-07-05",
    },
    "Huobi (cold)": {
        "category": "exchange_cold",
        # GraphSense "huobi reserve wallets BTC": ~6.3k + ~1.0k + ~0.3k BTC.
        "addresses": ["143gLvWYUojXaWZRrxquRKpVNTkhmr415B",
                      "12qTdZHx6f77aQ74CPCZGSY47VaRwYjVD8",
                      "14XKsv8tT6tt8P8mfDQZgNF8wtN5erNu5D"],
        "source": "GraphSense huobi pack; balances verified live 2026-07-05",
    },
    "Bybit (cold)": {
        "category": "exchange_cold",
        # ~1.3k BTC, 267 txs.
        "addresses": ["bc1q2qqqt87kh33s0er58akh7v9cwjgd83z5smh9rp"],
        "source": "GraphSense bybit pack; balance verified live 2026-07-05",
    },
    "Bybit (hot)": {
        "category": "exchange_hot",
        # ~547 BTC but 445k txs -> operational hot wallet.
        "addresses": ["1GrwDkr33gT6LuumniYjKEGjTLhsL5kmqC"],
        "source": "GraphSense bybit pack; balance verified live 2026-07-05",
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
