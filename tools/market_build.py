#!/usr/bin/env python3
"""Zycord Pulse market snapshot builder (v2, Zycord Pulse v1.0).

Reads CoinGecko's public API: every coin in the Layer 1 (L1) category (FDV, market cap, rank) and the
ids in the proof-of-work category. Writes data/market.json and data/market.js, the saved snapshot the
page shows when the visitor's browser cannot reach CoinGecko itself.

usage: market_build.py OUT_DIR
"""
import json, os, sys, time, urllib.request, urllib.error

API = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&category={cat}&order=market_cap_desc&per_page=250&page={page}"
UA = {"User-Agent": "zycord-pulse/1.0 (+https://pulse.brilliantnodes.com)", "Accept": "application/json"}


def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                time.sleep(45)
                continue
            raise


def category(cat, max_pages=8):
    out = []
    for page in range(1, max_pages + 1):
        rows = get(API.format(cat=cat, page=page))
        out += rows
        if len(rows) < 250:
            break
        time.sleep(8)
    return out


def main():
    out = sys.argv[1]
    l1 = category("layer-1")
    time.sleep(8)
    pow_ids = sorted({c["id"] for c in category("proof-of-work-pow")})
    rows = [[c["id"], (c.get("symbol") or "").upper(), c.get("name"), c.get("fully_diluted_valuation"),
             c.get("market_cap"), c.get("market_cap_rank"), c.get("last_updated")] for c in l1]
    if len(rows) < 100:
        sys.exit(f"too few Layer 1 coins ({len(rows)}); snapshot not written")
    asof = max((r[6] for r in rows if r[6]), default=None)
    m = dict(source="CoinGecko", source_url="https://www.coingecko.com/en/categories/layer-1", category="Layer 1 (L1)",
             fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), data_as_of_utc=asof,
             fields=["id", "symbol", "name", "fdv_usd", "market_cap_usd", "market_cap_rank", "last_updated"],
             rows=rows, pow_ids=pow_ids)
    s = json.dumps(m, ensure_ascii=False, separators=(",", ":"))
    os.makedirs(out, exist_ok=True)
    for name, body in (("market.json", s), ("market.js", "window.ZP_MARKET=" + s + ";")):
        tmp = os.path.join(out, name + ".tmp")
        open(tmp, "w").write(body)
        os.replace(tmp, os.path.join(out, name))
    print(f"market: {len(rows)} Layer 1 coins, {sum(1 for r in rows if r[3])} with FDV, {len(pow_ids)} proof-of-work ids, as of {asof}")


if __name__ == "__main__":
    main()
