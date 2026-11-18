# CBBTC mean-reversion bot — btc-race-24h-20261118-1444

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/yonshu642/btc-race-bot/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/yonshu642/btc-race-bot/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

A long-only, unleveraged trading bot for the make.fun 24-hour BTC race.
It speaks `agent-fun/bars-replay/v1` (newline-delimited JSON on
stdin/stdout) in a single self-contained `main.py`: Python 3 standard
library only, no network, no wall clock, no file access, and no floats
in any decision, so a run is fully deterministic.

## Strategy

Mean reversion on 1-minute closes of CBBTC/USDC:

- Keep a rolling mean of the last **60** closes.
- **Buy** when a close falls to at least **1.50%** below that mean
  (spending 100% of current cash, never more than 100% of equity
  invested). If a first tranche was smaller (weight-capped), one more
  buy is allowed on a further dip to **2.50%** below the mean, spending
  50% of the cash then available.
- **Sell** the whole position when a close recovers to at least
  **0.75%** above the mean.
- At most one order per **15 bars**; every order carries a 500 bps
  max-slippage cap against the decision close. Orders are decided on a
  bar's close and fill at the next bar's open, so the thresholds sit
  far above the ~12 bps + pool-impact round-trip cost — the bot only
  trades dips that are deep compared with what a trade costs.

## Parameters

| Parameter       | Value | Meaning                                   |
| --------------- | ----- | ----------------------------------------- |
| `WINDOW`        | 60    | rolling-mean window (bars)                |
| `DIP_BPS`       | 150   | buy at close ≤ mean × (1 − 1.50%)         |
| `ADD_DIP_BPS`   | 100   | add tranche at close ≤ mean × (1 − 2.50%) |
| `EXIT_BPS`      | 75    | sell at close ≥ mean × (1 + 0.75%)        |
| `SIZE_BPS`      | 10000 | cash spent per buy (100%)                 |
| `COOLDOWN`      | 15    | minimum bars between orders               |
| `MAX_SLIPPAGE_BPS` | 500 | fill may move ≤ 5% from decision close    |

## Dev-window check

Graded locally against the kit's frozen 24 h dev window with a replay
that mirrors the harness fill model exactly (4 bps fee, 2 bps slippage,
constant-product impact against each bar's open depth, end-of-window
flattening):

- **Net PnL: +$10.45** on the $1,000 start (gate: above $0)
- Trades: 2 (one round trip: buy $1,000 @ 63,736.78, sell @ 64,454.20)
- Max drawdown: 1.50% · no rejected orders · two runs byte-identical

The parameters sit in the middle of a stable region of the sweep
(DIP 130–160 and EXIT 70–80 produce the identical fills), not on a
knife-edge optimum.

## License

MIT — see `LICENSE`.
