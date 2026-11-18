#!/usr/bin/env python3
"""Mean-reversion bot for the make.fun btc-race (agent-fun/bars-replay/v1).

Long-only, no leverage. Keeps a rolling mean of the last WINDOW closes of
CBBTC; buys a dip when the close falls at least DIP_BPS below that mean,
may add one more tranche on a further ADD_DIP_BPS dip, and sells the whole
position when the close recovers to EXIT_BPS above the mean. Orders are
decided on a bar's close and fill at the next bar's open, paying fee +
slippage + pool impact, so the thresholds are kept well above that
round-trip cost (~12 bps + impact).

Protocol is implemented directly here: newline-delimited JSON on
stdin/stdout, one reply per batch echoing its seq. Standard library only,
no network, no clock, no file access, no floats in any decision (all
comparisons are exact integer arithmetic at the hello-declared scales),
so two runs over the same feed produce byte-identical replies.
"""

import json
import sys
from collections import deque

SYMBOL = "CBBTC"

# --- strategy parameters -------------------------------------------------
WINDOW = 60            # rolling-mean window, in bars (1 bar = 1 minute)
DIP_BPS = 150          # first buy: close <= mean * (1 - DIP_BPS / 10_000)
ADD_DIP_BPS = 100      # second buy needs DIP_BPS + ADD_DIP_BPS below mean
EXIT_BPS = 75          # sell all: close >= mean * (1 + EXIT_BPS / 10_000)
SIZE_BPS = 10000       # each buy spends SIZE_BPS / 10_000 of current cash
COOLDOWN = 15          # minimum bars between two orders
MAX_SLIPPAGE_BPS = 500  # fill may move at most 5% from the decision close

BPS = 10_000


def main():
    quote_scale = 6
    price_scale = 5
    qty_scale = 8
    min_notional = 1_000_000
    max_weight_bps = BPS
    warmup_bars = 0

    cash = 0
    equity = 0
    held_qty = 0

    closes = deque()
    close_sum = 0
    order_seq = 0
    tranches = 0
    since_order = COOLDOWN  # history permitting, the first signal may act

    out = sys.stdout

    for raw in sys.stdin.buffer:
        line = raw.strip()
        if not line:
            continue
        msg = json.loads(line)
        kind = msg.get("type")

        if kind == "hello":
            for s in msg["symbols"]:
                if s["symbol"] == SYMBOL:
                    price_scale = s["price_scale"]
                    qty_scale = s["qty_scale"]
            cap = msg["capital"]
            quote_scale = cap["quote_scale"]
            cash = equity = int(cap["quote_units"])
            min_notional = int(msg["fees"]["min_notional_quote_units"])
            max_weight_bps = msg["caps"]["max_weight_bps"]
            warmup_bars = msg.get("warmup_bars", 0)
            continue

        if kind == "done":
            break
        if kind != "batch":
            continue

        seq = msg["seq"]
        account = msg["account"]
        cash = int(account["cash_quote_units"])
        equity = int(account["equity_quote_units"])
        held_qty = 0
        for pos in account["positions"]:
            if pos["symbol"] == SYMBOL:
                held_qty = int(pos["qty"])
        if held_qty == 0:
            tranches = 0

        bar = None
        for b in msg["bars"]:
            if b["symbol"] == SYMBOL:
                bar = b

        close = None
        if bar is not None:
            close = int(bar["c"])
            closes.append(close)
            close_sum += close
            if len(closes) > WINDOW:
                close_sum -= closes.popleft()

        since_order += 1
        orders = []

        if (
            bar is not None
            and seq >= warmup_bars
            and len(closes) == WINDOW
            and since_order >= COOLDOWN
        ):
            # Compare close against mean * (1 +/- bps/10_000) without floats:
            # close * WINDOW * 10_000  vs  close_sum * (10_000 +/- bps).
            lhs = close * WINDOW * BPS
            if held_qty > 0 and lhs >= close_sum * (BPS + EXIT_BPS):
                order_seq += 1
                orders.append(
                    {
                        "side": "sell",
                        "client_id": "o%d" % order_seq,
                        "symbol": SYMBOL,
                        "qty": str(held_qty),
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    }
                )
                since_order = 0
            elif lhs <= close_sum * (BPS - DIP_BPS) and (
                held_qty == 0 or tranches == 1
            ):
                if held_qty > 0 and lhs > close_sum * (
                    BPS - DIP_BPS - ADD_DIP_BPS
                ):
                    pass  # holding one tranche but the dip is not deep enough to add
                else:
                    notional = cash * SIZE_BPS // BPS
                    held_value = (
                        held_qty
                        * close
                        * 10**quote_scale
                        // 10 ** (qty_scale + price_scale)
                    )
                    room = max_weight_bps * equity // BPS - held_value
                    if room < notional:
                        notional = room
                    if notional >= min_notional:
                        order_seq += 1
                        orders.append(
                            {
                                "side": "buy",
                                "client_id": "o%d" % order_seq,
                                "symbol": SYMBOL,
                                "notional_quote_units": str(notional),
                                "max_slippage_bps": MAX_SLIPPAGE_BPS,
                            }
                        )
                        tranches += 1
                        since_order = 0

        reply = json.dumps(
            {"type": "reply", "seq": seq, "orders": orders},
            separators=(",", ":"),
        )
        out.write(reply + "\n")
        out.flush()


if __name__ == "__main__":
    main()
