#!/usr/bin/env python3
"""Zycord Pulse site data builder (v6, Zycord Pulse v1.2: supply endpoints, and the exact supply inside pulse.json).

Inputs:  the current data/pulse.json (keeps the reward schedule, milestones, development figures, sources and
         the delivery list), the daily aggregate (pulse_agg.py) and the node snapshot (export_now.py).
Outputs: pulse.json, pulse.js, pulse_daily.csv, pulse_schedule.csv, total-supply.txt, circulating-supply.txt and
         supply.json in OUT_DIR. Counts and shares only: no addresses.

usage: build_site_data.py CURRENT_PULSE_JSON DAILY_JSON NOW_JSON OUT_DIR
"""
import csv, json, os, sys, time

cur_p, daily_p, now_p, out = sys.argv[1:5]
old = json.load(open(cur_p)); A = json.load(open(daily_p)); N = json.load(open(now_p))
days = sorted(A["days"], key=lambda d: d["day"])
full = [d for d in days if d.get("full_day")]
if not full:
    sys.exit("no full day in the daily aggregate; nothing written")

new = dict(old)
new["schema"] = 2
new["built_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
new["coverage"] = {k: A[k] for k in ["scanned_from_height", "scanned_to_height", "history_complete", "blocks_scanned",
                                       "certs_scanned", "total_senders_seen", "total_payout_addresses_seen"]}
new["reliability"] = A["reliability"]
mt = A.get("milestone_times", {})
new["delivery"] = []
for m in old["delivery"]:
    act = mt.get(str(m["height"]), m.get("actual_utc"))
    new["delivery"].append(dict(m, actual_utc=act, diff_min=round((act - m["scheduled_utc"]) / 60) if act else m.get("diff_min")))
mx_c = max(days, key=lambda d: d["max_certs_block"]); mx_b = max(days, key=lambda d: d["max_bytes_block"])
st, me, fe = N["status"], N["metrics"], N["fees"]
seeds = N.get("seeds") or old.get("seeds", [])
new["now"] = dict(
    read_utc=N["read_utc"], height=st["height"], certs_applied=me.get("certs_applied"),
    lab_hashrate_khs=round(N["lab_chain"]["hashrate"] / 1000, 1) if N.get("lab_chain", {}).get("hashrate") else old["now"].get("lab_hashrate_khs"),
    reorg_events=N["lab_reorgs"].get("events", old["now"].get("reorg_events")),
    deepest_reorg=N["lab_reorgs"].get("deepest", old["now"].get("deepest_reorg")),
    known_peers=N["network"].get("known_peers"), seeds_up=sum(1 for s in seeds if s.get("up")),
    seed_peers_max=max((s.get("peers") or 0) for s in seeds) if seeds else None,
    max_certs_per_block=fe.get("max_certs_per_block"), block_byte_limit=fe.get("block_byte_limit"),
    largest_block_certs=mx_c["max_certs_block"], largest_block_bytes=mx_b["max_bytes_block"],
    avg_bytes_block_last=full[-1]["avg_bytes_block"])
new["seeds"] = seeds
RG = N.get("reorg_depths") or {}
if RG.get("recent_len"):
    new["reorgs"] = dict(events=RG["events"], deepest=RG["deepest"], recent_count=RG["recent_len"],
                         recent_from_height=RG["recent_from_height"], recent_to_height=RG["recent_to_height"],
                         recent_by_depth=RG["by_depth"])
new["daily"] = [{k: v for k, v in d.items() if k != "kinds"} for d in days]
# v6: exact supply at the node height, so the page shows the same figure as the supply endpoints
import importlib.util
_spec = importlib.util.spec_from_file_location("zp_supply", os.path.join(os.path.dirname(os.path.abspath(__file__)), "supply.py"))
_sup = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_sup)
_t, _f, _tr = _sup.supply_at(int(new["now"]["height"]))
new["supply_exact"] = dict(height=int(new["now"]["height"]), total=_t / _sup.UNIT, circulating=(_t - _tr) / _sup.UNIT,
                           treasury=_tr / _sup.UNIT, founder=_f / _sup.UNIT)
new["downloads"] = ["data/pulse_daily.csv", "data/pulse_schedule.csv", "data/pulse.json"]
REORG_SRC = "Reorganisation depths: the most recent events kept in the Zycord Lab network file; the all-time count and deepest come from the same file."
new["sources"] = list(dict.fromkeys(list(old.get("sources", [])) + [REORG_SRC]))

os.makedirs(out, exist_ok=True)
def write(name, body):
    tmp = os.path.join(out, name + ".tmp")
    with open(tmp, "w", newline="") as f:
        body(f) if callable(body) else f.write(body)
    os.replace(tmp, os.path.join(out, name))

s = json.dumps(new, ensure_ascii=False, separators=(",", ":"))
write("pulse.json", s)
write("pulse.js", "window.ZP_DATA=" + s + ";")
cols = ["day", "full_day", "blocks", "avg_block_s", "max_gap_s", "hashrate_khs", "txs", "transfers", "contract_calls",
        "contracts_deployed", "contract_callers", "contracts_called", "active_senders", "new_senders", "recipients", "zcd_sent",
        "payout_addresses", "top1_share_pct", "top3_share_pct", "max_certs_block", "max_bytes_block", "avg_bytes_block",
        "cum_txs", "cum_senders", "cum_zcd_sent", "cum_payout_addresses"]
def daily_csv(f):
    w = csv.writer(f); w.writerow(cols)
    for d in days:
        w.writerow([d.get(c, "") for c in cols])
write("pulse_daily.csv", daily_csv)
sc = ["epoch", "height", "date", "reward_per_block", "miner_per_block", "issued_per_day", "supply"]
def sched_csv(f):
    w = csv.writer(f); w.writerow(sc)
    for r in old["schedule"]:
        w.writerow([r.get(c, "") for c in sc])
write("pulse_schedule.csv", sched_csv)
# supply endpoints (v5): exact, from Zycord's emission parameters, at the node's height
import subprocess
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "supply.py"),
                str(new["now"]["height"]), out], check=True, stdout=subprocess.DEVNULL)
print("built", new["built_utc"], "height", new["now"]["height"], "days", len(days))
