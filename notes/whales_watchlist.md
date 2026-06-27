# Whale watchlist — BTC/ETH (snapshot 2026-06-27)

Addresses surfaced by `whales_coin.py` (top accounts holding >= $1M summed
BTC+ETH notional). **Positions are a live snapshot and will drift** — re-run
the script to refresh; addresses are the durable part, use them as a
watchlist seed (`clearinghouse_state(addr)` / `user_fills(addr)`).

Run: 147 whales detected in top 1,500 by accountValue; top 25 below by coin notional.

## Cohort positioning (notional-weighted, net_bias in [-1,+1])
```
COIN       LONG      SHORT        NET    BIAS  LEAN     wallets
BTC     $580.7M    $547.7M     $33.0M   +0.03  NEUTRAL  61L/62S
ETH     $374.4M    $378.8M     -$4.4M   -0.01  NEUTRAL  37L/51S
```
Both BTC and ETH effectively NEUTRAL across this size-selected cohort.

## Top whales by BTC+ETH notional

| # | address | acctValue | coinNotional | positions (side coin notional @lev) |
|---|---------|-----------|--------------|--------------------------------------|
| 1 | `0x50b309f78e774a756a2230e1769729094cac9f20` | $6.8M | $103.5M | LONG BTC $28.3M @20x; SHORT ETH $75.2M @23x |
| 2 | `0x0ddf9bae2af4b874b96d287a5ad42eb47138a902` | $24.4M | $79.2M | SHORT ETH $79.2M @3x |
| 3 | `0x92ea19eceb7a8de0f50978a1583a5d8b018050e9` | $26.9M | $76.6M | LONG BTC $76.6M @5x |
| 4 | `0x77eeda199553e33b246e4b4666849b9ad0972902` | $9.1M | $73.4M | SHORT BTC $38.6M @40x; SHORT ETH $34.8M @25x |
| 5 | `0xaeaab54bbf65bfd6efed7d2eb68372298e3c2416` | $5.0M | $71.0M | SHORT BTC $55.2M @20x; SHORT ETH $15.9M @20x |
| 6 | `0xa5b0edf6b55128e0ddae8e51ac538c3188401d41` | $5.9M | $63.3M | LONG ETH $63.3M @15x |
| 7 | `0x6c8512516ce5669d35113a11ca8b8de322fd84f6` | $6.9M | $63.3M | LONG ETH $63.3M @20x |
| 8 | `0x8ea85cbd59affca28162fc286d5c093dd0f8edbc` | $13.2M | $60.4M | LONG BTC $60.4M @4x |
| 9 | `0x3e7a0eca8b624b75034ad820fa291425f21f1589` | $3.9M | $52.2M | SHORT BTC $36.3M @20x; SHORT ETH $15.9M @20x |
| 10 | `0xa875890465da20062bcf3b024bf7d54e69c725a8` | $4.5M | $47.5M | LONG ETH $47.5M @20x |
| 11 | `0xf822fa0fd364c573fcdb7009fcf47601bc8be01a` | $37.5M | $46.4M | SHORT BTC $29.2M @3x; SHORT ETH $17.2M @3x |
| 12 | `0x069ad3d4dd1ca686ef78d065fbc6208fdcede58d` | $3.8M | $46.2M | SHORT BTC $46.2M @40x |
| 13 | `0xcf90cfecf74e631feea816d02e757c0c8e895c0e` | $15.5M | $46.1M | SHORT BTC $46.1M @15x |
| 14 | `0x4be5f249c4df500ede3fed4171bd37b8563420c0` | $3.7M | $30.2M | LONG BTC $30.2M @20x |
| 15 | `0x3b7f4282f983c37526f04bbac7dab772ee743998` | $2.2M | $30.2M | LONG BTC $30.2M @20x |
| 16 | `0xa1830e8d9f019feb448478a171bb37cc6c4c0482` | $4.1M | $28.6M | SHORT BTC $28.6M @20x |
| 17 | `0xec0b9ebf2a304c99cafe85c548c14dd7783cb078` | $1.8M | $26.1M | LONG BTC $15.0M @40x; LONG ETH $11.1M @25x |
| 18 | `0x7fdafde5cfb5465924316eced2d3715494c517d1` | $15.3M | $23.4M | LONG BTC $16.2M @20x; SHORT ETH $7.2M @15x |
| 19 | `0x023a3d058020fb76cca98f01b3c48c8938a22355` | $11.9M | $21.3M | SHORT BTC $617.2K @40x; LONG ETH $20.7M @25x |
| 20 | `0xd260b2216b735277da6771564a01c04856e78321` | $5.7M | $21.2M | LONG BTC $21.2M @3x |
| 21 | `0x6315c7d325ea3508ad503f197d1671e097d0074a` | $13.2M | $21.1M | LONG ETH $21.1M @20x |
| 22 | `0xf83ff544ed6f00fe7a74782aee3fd9ea54d96728` | $1.7M | $20.3M | SHORT ETH $20.3M @20x |
| 23 | `0xb798aef79972ce8f73d47b9ebbcda6bbb7ec4fbf` | $9.4M | $18.8M | SHORT BTC $18.7M @2x; SHORT ETH $139.2K @2x |
| 24 | `0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00` | $26.8M | $18.2M | LONG BTC $16.7M @20x; SHORT ETH $1.5M @15x |
| 25 | `0xad227f63d34e7251c1d0ab65e64eeea07aee4e44` | $2.4M | $18.1M | SHORT BTC $18.1M @40x; SHORT ETH $11 @25x |

