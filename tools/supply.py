#!/usr/bin/env python3
"""Zycord Pulse: exact ZCD supply at a block height, from Zycord's own emission parameters (v1, Zycord Pulse v1.1).

Rules (tools/pulsescan/params_mainnet.json, zycord-node v0.7.1):
  - 1 ZCD = 100,000,000 base units. The genesis block pays nothing.
  - Rate for epoch e (2,880 blocks): genesis_emission, reduced by one part in 1,054 each epoch (integer floor);
    from epoch 4,376 (height 12,602,880) a fixed tail of 0.33 ZCD per block.
  - Slow start: below height 86,400 a block pays floor(height x rate_at_86400 / 86,400).
  - Of every block subsidy: 3% founder (floored, credited directly, until height 3,153,600), 3% treasury
    (floored; from height 3,153,600 the treasury also takes the founder's share), the rest to the block producer.
    Fees are not part of the subsidy and are not counted here.

Definitions used for the public endpoints:
  total supply       = every ZCD created by block subsidies up to the height (nothing is subtracted).
  circulating supply = total supply minus the treasury, which is held by the protocol and is not in anyone's hands.

usage: supply.py HEIGHT [OUT_DIR]      prints JSON; with OUT_DIR also writes total-supply.txt,
                                       circulating-supply.txt and supply.json there.
"""
import json, os, sys, time

P = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pulsescan", "params_mainnet.json")))
UNIT = 100_000_000
EPOCH = int(P["epoch_length"])
G = int(P["genesis_emission"])
DIV = int(P["emission_decay_divisor"])
RAMP = int(P["emission_ramp_blocks"])
TAIL = int(P["tail_emission"])
TAIL_EPOCH = 4376
T_BPS = int(P["treasury_share_bps"])
F_BPS = int(P["founder_share"]["bps"])
F_END = int(P["founder_share"]["end_height"])


def rates(n_epochs):
    r, out = G, []
    for e in range(n_epochs):
        out.append(r if e < TAIL_EPOCH else TAIL)
        r -= r // DIV
    return out


def supply_at(height):
    """Base units issued by subsidies at blocks 1..height, split producer / founder / treasury."""
    R = rates(height // EPOCH + 2)
    r_ramp = R[RAMP // EPOCH]
    total = founder = treasury = 0
    h = 1
    while h <= height:
        if h < RAMP:  # ramp: per-block subsidy changes every block
            s = h * r_ramp // RAMP
            f = s * F_BPS // 10_000 if h < F_END else 0
            t = s * T_BPS // 10_000 + (0 if h < F_END else s * F_BPS // 10_000)
            total += s; founder += f; treasury += t
            h += 1
            continue
        e = h // EPOCH
        last = min(height, (e + 1) * EPOCH - 1)
        if h < F_END <= last:  # split a span at the founder end height
            last = F_END - 1
        n = last - h + 1
        s = R[e]
        f = s * F_BPS // 10_000 if h < F_END else 0
        t = s * T_BPS // 10_000 + (0 if h < F_END else s * F_BPS // 10_000)
        total += n * s; founder += n * f; treasury += n * t
        h = last + 1
    return total, founder, treasury


def fmt8(x):
    return f"{x // UNIT}.{x % UNIT:08d}"


def main():
    height = int(sys.argv[1])
    total, founder, treasury = supply_at(height)
    circ = total - treasury
    doc = dict(
        height=height, computed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), unit="ZCD",
        total_supply=fmt8(total), circulating_supply=fmt8(circ), treasury=fmt8(treasury),
        founder_allocation=fmt8(founder), to_block_producers=fmt8(total - founder - treasury),
        max_supply=None,
        notes={
            "total_supply": "Every ZCD created by block subsidies up to this height, computed exactly from Zycord's emission parameters.",
            "circulating_supply": "Total supply minus the treasury, which is held by the protocol.",
            "founder_allocation": "3% of each block subsidy until height 3,153,600, credited directly to the founder's address. Counted as circulating.",
            "max_supply": "None. The decaying schedule issues 61,836,900.03 ZCD up to height 12,602,879; after that a tail of 0.33 ZCD per block continues.",
            "fees": "Transaction fees are not part of the subsidy and are not counted.",
        },
        source="https://github.com/brilliantnodes/zycord-pulse/blob/main/tools/supply.py")
    if len(sys.argv) > 2:
        out = sys.argv[2]
        os.makedirs(out, exist_ok=True)
        for name, body in (("total-supply.txt", fmt8(total) + "\n"), ("circulating-supply.txt", fmt8(circ) + "\n"),
                           ("supply.json", json.dumps(doc, indent=1) + "\n")):
            tmp = os.path.join(out, name + ".tmp")
            open(tmp, "w").write(body)
            os.replace(tmp, os.path.join(out, name))
    print(json.dumps(doc))


if __name__ == "__main__":
    main()
