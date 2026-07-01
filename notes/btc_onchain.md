# On-chain BTC entity tracking — watchlist approach (2026-07-01)

A second data domain alongside the Hyperliquid perp work: watch **known-entity
Bitcoin addresses** on the base chain for large movements (e.g. "exchange cold
wallet sent 12,000 BTC"). Complementary signal — HL = perp *positioning*,
on-chain = spot *custody/exchange flow* (real in/out of storage).

## What we built
- **`btc/client.py` — `Esplora`**: read-only client for the public Esplora API
  (mempool.space; blockstream.info is the same API). No auth. Values on the wire
  are **satoshis**. Methods: `address`, `balance_sats`, `address_txs` (last ~50
  txs w/ full vin/vout), `tip_height`. Retry w/ exponential backoff + UA header.
- **`btc/watchlist.py`**: the label layer the chain doesn't carry. Entity → its
  address(es). 5 entities / ~410k BTC watched, all balance-verified:
  Binance cold (~248.6k, dormant vault), Binance hot [inferred]
  (`bc1qm34l…`, ~14.6k, 2.26M txs — the real Binance flow hub), Bitfinex cold
  (~130.0k), Bitfinex hot [inferred] (`1Kr6QSyd…`, ~5.4k), Bitfinex-linked
  cold? [inferred] (`3JZq4…`, ~11.7k — hot→cold sweep sink).
- **`btc_flows.py`**: reads each watched address's recent txs, flags net balance
  moves ≥ `THRESHOLD_BTC` as IN/OUT, labels the counterparty (curated + community
  labels). `--balances`, `--hours N`, `--min BTC`, and **`--netflow --hours N`** =
  per-entity IN/OUT/NET over the window — the exchange net-flow signal (net INflow
  to hot wallets ≈ deposits/sell-pressure; net OUTflow ≈ accumulation). First run:
  48h across Binance+Bitfinex hot showed NET −1,823 BTC (mild accumulation lean).

## Key finding — why "BlackRock → Coinbase" is hard to self-host
The transparency is free; **attribution** is the whole problem. Per Arkham,
BlackRock's IBIT has **no single address** — Coinbase Prime custodies it across
*many rotating* addresses each ≤300–600 BTC. So:
- **Single-address entities** (exchange cold wallets) → watchlist works cleanly.
  This is where our tool is strong and fully free.
- **Clustered entities** (ETF custody / BlackRock) → hand-listing hundreds of
  rotating addresses goes stale immediately; that specific attribution is what a
  labeled API (Arkham / Whale Alert) exists to sell. `watchlist.py` keeps a
  *list* per entity so a cluster can be pasted in, but coverage is best-effort.

## Entity map discovered by 芋づる tracing (2026-07-01)
Starting from two known cold wallets, counterparty analysis surfaced the
operational wallets — the ones actually moving money:
```
Binance:  34xp… cold (248.6k, DORMANT: net +0.06 BTC over 615d, dust-only)
          bc1qm34l… hot (14.6k, 2.26M txs)  <- real daily flow is here
Bitfinex: cold (130k) --replenish 5-12k--> 1Kr6QSyd… hot (5.4k, 485k txs)
                                            └--sweep--> 3JZq4… (11.7k) cold?
```
Key contrast: **Binance separates a dormant vault from a hyper-active hot wallet**
(watch the hot, the cold is a dead end for tracing); **Bitfinex's cold actively
feeds its hot**, so the cold is itself a useful trace origin. Method that found
the hot wallets: `address_txs_paged` back ~600 txs, aggregate net-delta flows by
counterparty, rank, then profile top recurring addresses (balance / tx_count /
throughput) to classify vault vs hot vs relay. NB: aggregate the *net delta per
watched address*, not raw tx input/output sums — in batched multi-output txs the
watched address is often a tiny marker output, so raw sums wildly overcount the
counterparty (this bit us once on Binance cold). `btc_flows.py` already uses net
delta and is correct.

## To extend
- Add entities to `WATCHLIST` — **verify the balance live first** (a claimed cold
  wallet must actually hold a huge balance). Repeated counterparties surfaced by
  `btc_flows.py` are good candidates (e.g. Bitfinex's recurring `1Kr6QSyd…9i1g`
  sink — likely an internal/hot wallet — worth labeling and adding).
- For real BlackRock/Coinbase/MicroStrategy coverage, use the labeled path:
  `btc/arkham.py` (`Arkham`) + `arkham_flows.py` — `/transfers?base=blackrock&
  flow=out` returns label-annotated transfers (from-entity → to-entity), which is
  exactly "BlackRock → Coinbase". Needs an ARKHAM_API_KEY (free tier at
  intel.arkm.com/api; $0 but requires signup). Runs the moment the key is set.

## Attribution sources — what's reachable for free (tested 2026-07-01)
The chain has no names; labels come from elsewhere. Empirically:
- **Labeled APIs are gated.** `api.arkm.com` → 403 Cloudflare, Blockchair → 430
  "get a key", both no-key. Even free tiers need signup/approval.
- **WalletExplorer** (`/api/1/address`, no key) → 200, gives free *clustering*
  (wallet_id + sibling addresses; Binance cold clustered 35 addrs) but **no modern
  names** — our entities all return hex cluster ids, `label:None`. Its naming
  froze ~2016, so Binance/MSTR/BlackRock are unnamed. Clustering-only.
- **Others are already doing this** — reuse their output instead of rebuilding:
  - *Read* (free, human): Lookonchain / Whale Alert (post "BlackRock → Coinbase X
    BTC" live); Arkham free web UI (entity pages browse even though API 403s).
  - *Reuse as data* (free, into watchlist): **GraphSense tagpacks** (GitHub, open
    address→entity tags), GitHub exchange-wallet lists, **Dune** community `labels`.
    Strong for exchanges, weak for MSTR/BlackRock custody (Arkham's off-chain intel).
    **DONE** — `btc/labels_import.py` pulls the GraphSense exchange/ETF packs (no
    key) into `data/btc_labels.json`: ~336k BTC labels (BitMEX publishes all its
    deposit addresses → 336k of them; plus binance/bitfinex/okx/bybit/huobi/kucoin/
    crypto.com/deribit/swissborg and the Bitwise BITB ETF). `btc_flows.py` overlays
    them (curated names win) so any counterparty in the set gets named for free.
    Corroboration win: the pack labels **confirmed all three addresses we'd inferred
    by flow analysis** — `bc1qm34l…`=binance, `1Kr6QSyd…`=bitfinex hot,
    `3JZq4…`=bitfinex cold (its source is Bitfinex's own wallets.txt). We dropped the
    `[inferred]` tags accordingly.
    Caveat re ETFs: the one publicly-disclosed ETF address (Bitwise `1CKVsz…`) is now
    **empty** (last activity 2024-10-23, balance 0) — even disclosed ETF addresses
    rotate, so don't actively watch a stale one; verify balance before trusting.
  - *Aggregate signal* (free): Glassnode / CryptoQuant exchange net-flow charts —
    the in/out pressure without needing the addresses.
  Bottom line: exchange labels are gettable free; custodial/ETF/MSTR attribution
  realistically still needs Arkham (free-tier key or paid).

## Caveats (observed)
- Cold wallets move rarely — `--hours 24` is usually empty; that's correct, not a
  bug. Recent txs on a cold address can be months old.
- Net-delta detection nets out self-consolidation (change back to the same
  address), so internal reshuffles show ~0 and are correctly ignored.
- `address_txs` returns only the latest ~50 txs; for busy addresses this is a
  recent window, not full history (paginate via `/txs/chain/:last_txid` if needed).
- **mempool.space throttles heavy sessions.** After a few hundred calls, single
  `/address` calls slid from <1s to ~24s. Don't fan out large profiling loops on
  the public host; batch/space calls, cache, or run your own Esplora/electrs. This
  is why the multi-exchange hot-wallet expansion (OKX/Huobi/Bybit/… from the
  labels) is deferred — the labels are cached, the profiling just needs a calmer
  API window or a self-hosted node.
