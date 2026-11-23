#!/usr/bin/env python3
"""Zycord Pulse: node and network snapshot (read-only). Numbers only: no addresses, no peer IPs.

Reads a Zycord node's RPC (/status, /metrics, /network, /fees) and the public Zycord Lab network file
(seed status, reorganisations). Writes one JSON document to stdout.

usage: export_now.py [RPC_URL]      (default http://127.0.0.1:9420)
"""
import collections, json, sys, time, urllib.request

RPC = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9420").rstrip("/")
LAB = "https://lab.zycord.com/tools/network/data/mainnet.json"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "zycord-pulse/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def num(d):
    return {k: v for k, v in d.items() if isinstance(v, (int, float, bool))} if isinstance(d, dict) else {}


st, me, nw, fe = (get(RPC + p) for p in ("/status", "/metrics", "/network", "/fees"))
try:
    lab = get(LAB)
except Exception:
    lab = {}
ro = lab.get("reorgs", {}) if isinstance(lab.get("reorgs"), dict) else {}
rec = [x for x in ro.get("recent", []) if isinstance(x, dict)]
hs = [int(x["at_height"]) for x in rec if "at_height" in x]
depths = collections.Counter(int(x.get("depth", 0)) for x in rec)

print(json.dumps(dict(
    read_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    status=num(st), metrics=num(me), network=dict(known_peers=nw.get("known_peers")), fees=num(fe),
    lab_generated=lab.get("generated_at"), lab_chain=num(lab.get("chain", {})), lab_reorgs=num(ro),
    reorg_depths=dict(events=ro.get("events"), deepest=ro.get("deepest"), recent_len=len(rec),
                      recent_from_height=min(hs) if hs else None, recent_to_height=max(hs) if hs else None,
                      by_depth={str(k): v for k, v in sorted(depths.items())}),
    seeds=[dict(name=s.get("name"), up=s.get("up"), peers=s.get("peers"), inbound=s.get("inbound"))
           for s in lab.get("seeds", []) if isinstance(s, dict)])))
