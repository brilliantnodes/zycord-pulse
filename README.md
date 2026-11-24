# Zycord Pulse

**Independent, open statistics for the Zycord mainnet: [pulse.brilliantnodes.com](https://pulse.brilliantnodes.com)**

Zycord Pulse shows how the Zycord blockchain is used and how it runs: transactions, active signing keys, contracts,
network hashrate, block times, reorganisations, the delivery record of scheduled upgrades, issued supply and the road
to staking. Every chain figure is read from every block on a Zycord full node and decoded with Zycord's own code.

Version **1.2** (24 November 2026): supply wording and FDV use the exact 61.8 million. 1.1: supply endpoints. 1.0: first release.

## What is on the page

| Section | Source | Updated |
|---|---|---|
| Usage, network & reliability, delivery record, issued supply | Every block, read from our own Zycord full node | Every hour |
| Seed nodes, reorganisations | Zycord Lab network file | Every hour |
| Reward schedule, road to staking | Zycord's own parameter code | With a new Zycord release |
| Development | Public repository `gitlab.com/zycord-group/zycord-node`, dev branch | By hand; date shown on the page |
| Market statistics | CoinGecko public API, Layer 1 category | Live in the visitor's browser; saved snapshot every 6 hours |
| Speed comparison | Chainspect; the Zycord row from our node | Snapshot, date shown in the panel |
| Mine Zycord calculator | Public RandomX CPU benchmarks; network hashrate from our node | CPU figures are approximate |

How each number is measured is set out on the page itself, in the **Methods** section.

## Open data

- [`data/pulse_daily.csv`](data/pulse_daily.csv): one row per UTC day (blocks, block time, hashrate, transactions, contract use, signing keys, payout addresses, block sizes and running totals).
- [`data/pulse_schedule.csv`](data/pulse_schedule.csv): the block reward schedule from Zycord's parameters.
- [`data/pulse.json`](data/pulse.json): everything the page draws.

The data holds counts and shares only. It names no address and no key.

## Supply endpoints

Plain-text numbers in ZCD, for data sites such as CoinGecko and CoinMarketCap. They are rebuilt every hour at our node's current height.

| Endpoint | Value |
|---|---|
| [`/data/total-supply.txt`](https://pulse.brilliantnodes.com/data/total-supply.txt) | Every ZCD created by block subsidies so far. |
| [`/data/circulating-supply.txt`](https://pulse.brilliantnodes.com/data/circulating-supply.txt) | Total supply minus the treasury, which is held by the protocol. |
| [`/data/supply.json`](https://pulse.brilliantnodes.com/data/supply.json) | Both, with the height, the treasury, the founder allocation and the definitions. |

[`tools/supply.py`](tools/supply.py) computes these exactly, to the base unit, from Zycord's own emission parameters
(`tools/pulsescan/params_mainnet.json`, zycord-node v0.7.1). It reproduces the totals quoted in those parameters:
62,744,838.47 ZCD for the decaying schedule, 907,917.44 ZCD withheld by the slow start, and 61,836,900.03 ZCD issued
before the tail emission of 0.33 ZCD per block begins at height 12,602,880. Zycord has no fixed maximum supply.

- The founder's 3% of each block subsidy (until height 3,153,600) is credited straight to the founder's address and counted as circulating.
- Transaction fees are not part of the subsidy and are not counted.
- Coins in the 240-block maturity window are counted once their block exists.

## Run it yourself

Everything that builds the data is in [`tools/`](tools), so anyone with a synced Zycord node can check or reproduce the figures.

1. Build the block reader. Check out `zycord-node` v0.7.1 (commit `bc9389b0`) next to `tools/pulsescan` as `tools/base`, then:
   ```
   cd tools/pulsescan && go build -o pulsescan .
   ```
2. Run the whole pipeline against your node's RPC:
   ```
   tools/refresh.sh http://127.0.0.1:9420
   ```
   The first run reads the whole chain (it stays under 240 requests a minute); later runs read only new blocks.
3. Open `index.html`, or serve the folder with any static web server.

| Tool | What it does |
|---|---|
| `tools/pulsescan/` | Reads every block from a node's RPC and writes one line per block and per certificate (Go, read-only, resumable). |
| `tools/pulse_agg.py` | Turns those lines into daily counts and shares. |
| `tools/export_now.py` | Node status, fee parameters, seed status and reorganisations (numbers only). |
| `tools/build_site_data.py` | Builds `data/pulse.json`, `data/pulse.js` and the CSV files. |
| `tools/market_build.py` | Builds the CoinGecko snapshot in `data/market.json` and `data/market.js`. |

The page is static HTML with one vendored library ([d3](https://d3js.org) 7.9.2, ISC licence). It loads no trackers,
no fonts and no third-party scripts. The only outside request is to CoinGecko's public API, for the market panel.

## Disclosure

Zycord Pulse is built and run by [Brilliant Nodes](https://brilliantnodes.com). **Brilliant Nodes mines and holds ZCD.**
The project is independent: it is not affiliated with or endorsed by the Zycord project. Nothing here is investment advice.

Corrections and suggestions are welcome as issues on this repository.

## Licence

[MIT](LICENSE). The vendored d3 library keeps its own ISC licence ([`vendor/LICENSE-d3.txt`](vendor/LICENSE-d3.txt)).
