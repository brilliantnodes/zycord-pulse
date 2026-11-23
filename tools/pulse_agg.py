#!/usr/bin/env python3
"""Zycord Pulse aggregator v3 (read-only). Output holds counts and shares only: no addresses, no keys.

v3 adds, per UTC day: longest gap between blocks, largest block (certs, bytes), average block bytes,
cumulative ZCD sent; and globally: reliability summary and the actual times of milestone heights.

blocks.tsv: height, time, emission_addr, n_certs, bytes, target
certs.tsv:  height, time, cert_id, kind, signers, srcs, dsts, native_drops, acting, target, deploy
"""
import json, sys, os, collections, datetime

d = sys.argv[1] if len(sys.argv) > 1 else "pulse"
DROPS = 10**8
TWO256 = 1 << 256
CALL_KINDS = {4, 11, 12, 16}
MILESTONES = [0, 1, 2880, 77760, 80640, 86400]

def day_of(t):
    return datetime.datetime.fromtimestamp(int(t), datetime.timezone.utc).strftime("%Y-%m-%d")

blocks = {}
with open(os.path.join(d, "blocks.tsv")) as f:
    for line in f:
        p = line.rstrip("\n").split("\t")
        if len(p) < 6 or not p[0].isdigit():
            continue
        blocks[int(p[0])] = (int(p[1]), p[2], int(p[3]), int(p[4]), int(p[5]))

certs = []
with open(os.path.join(d, "certs.tsv")) as f:
    for line in f:
        p = line.rstrip("\n").split("\t")
        if len(p) < 11 or not p[0].isdigit():
            continue
        certs.append(p)

hs = sorted(blocks)
lo, hi = hs[0], hs[-1]
complete = lo <= 1 and len(hs) == hi - lo + 1

days = collections.OrderedDict()
def D(k):
    if k not in days:
        days[k] = dict(blocks=0, tmin=None, tmax=None, work=0, bytes=0, payout=collections.Counter(),
                       txs=0, transfers=0, calls=0, deploys=0, other=0, senders=set(), recipients=set(),
                       drops=0, kinds=collections.Counter(), callers=set(), called=set(),
                       max_gap=0, max_certs=0, max_bytes=0)
    return days[k]

prev_t = None
gaps_over_5m = 0
longest = (0, None)
for h in hs:
    t, addr, nc, nb, tgt = blocks[h]
    x = D(day_of(t))
    x["blocks"] += 1
    x["tmin"] = t if x["tmin"] is None else min(x["tmin"], t)
    x["tmax"] = t if x["tmax"] is None else max(x["tmax"], t)
    x["work"] += TWO256 // (tgt + 1)
    x["bytes"] += nb
    x["payout"][addr] += 1
    x["max_certs"] = max(x["max_certs"], nc)
    x["max_bytes"] = max(x["max_bytes"], nb)
    if prev_t is not None and h > 1:
        g = t - prev_t
        x["max_gap"] = max(x["max_gap"], g)
        if g > 300:
            gaps_over_5m += 1
        if g > longest[0]:
            longest = (g, h)
    prev_t = t

seen = set()
for p in certs:
    if p[2] in seen:
        continue
    seen.add(p[2])
    x = D(day_of(p[1]))
    k = int(p[3])
    x["txs"] += 1
    x["kinds"][k] += 1
    if k == 0:
        x["transfers"] += 1
        x["drops"] += int(p[7] or 0)
        for r in filter(None, p[6].split(",")):
            x["recipients"].add(r)
    elif k in CALL_KINDS:
        if p[10] == "1":
            x["deploys"] += 1
        else:
            x["calls"] += 1
            if p[8]: x["callers"].add(p[8])
            if p[9]: x["called"].add(p[9])
    else:
        x["other"] += 1
    for s in filter(None, p[4].split(",")):
        x["senders"].add(s)

rows = []
ever_senders, ever_payout = set(), set()
cum_tx = cum_dep = cum_drops = cum_calls = 0
first_day, last_day = min(days), max(days)
for k in sorted(days):
    x = days[k]
    n = x["blocks"]
    top = [c for _, c in x["payout"].most_common(3)]
    new_senders = len(x["senders"] - ever_senders)
    ever_senders |= x["senders"]
    ever_payout |= set(x["payout"])
    cum_tx += x["txs"]; cum_dep += x["deploys"]; cum_drops += x["drops"]; cum_calls += x["calls"]
    full = (k != last_day) and (k != first_day or complete)
    span = 86400 if full else max(1, x["tmax"] - x["tmin"])
    rows.append(dict(
        day=k, full_day=full, blocks=n,
        avg_block_s=round(span / n, 1) if n else None,
        max_gap_s=x["max_gap"],
        max_certs_block=x["max_certs"], max_bytes_block=x["max_bytes"],
        avg_bytes_block=round(x["bytes"] / n) if n else None,
        hashrate_khs=round(x["work"] / span / 1000, 1),
        txs=x["txs"], transfers=x["transfers"], contract_calls=x["calls"],
        contracts_deployed=x["deploys"], other_txs=x["other"],
        contract_callers=len(x["callers"]), contracts_called=len(x["called"]),
        active_senders=len(x["senders"]),
        new_senders=new_senders if complete else None,
        recipients=len(x["recipients"]),
        zcd_sent=round(x["drops"] / DROPS, 2),
        payout_addresses=len(x["payout"]),
        top1_share_pct=round(100 * top[0] / n, 1) if n else None,
        top3_share_pct=round(100 * sum(top) / n, 1) if n else None,
        cum_txs=cum_tx if complete else None,
        cum_senders=len(ever_senders) if complete else None,
        cum_contracts_deployed=cum_dep if complete else None,
        cum_contract_calls=cum_calls if complete else None,
        cum_zcd_sent=round(cum_drops / DROPS) if complete else None,
        cum_payout_addresses=len(ever_payout) if complete else None,
        kinds={str(a): b for a, b in sorted(x["kinds"].items())},
    ))

full_rows = [r for r in rows if r["full_day"]]
out = dict(
    generated_utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    scanned_from_height=lo, scanned_to_height=hi, history_complete=complete,
    blocks_scanned=len(hs), certs_scanned=len(seen),
    total_senders_seen=len(ever_senders), total_payout_addresses_seen=len(ever_payout),
    reliability=dict(
        days_running=len(rows), days_without_blocks=0 if complete else None,
        longest_gap_s=longest[0], longest_gap_height=longest[1], gaps_over_5_min=gaps_over_5m,
        avg_block_s_all=round((blocks[hi][0] - blocks[max(lo, 1)][0]) / max(1, hi - max(lo, 1)), 2),
        full_days_blocks_min=min((r["blocks"] for r in full_rows), default=None),
        full_days_blocks_max=max((r["blocks"] for r in full_rows), default=None),
    ),
    milestone_times={str(h): blocks[h][0] for h in MILESTONES if h in blocks},
    days=rows,
)
json.dump(out, sys.stdout, separators=(",", ":"))
print()
