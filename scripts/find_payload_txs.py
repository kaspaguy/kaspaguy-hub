#!/usr/bin/env python3
"""Find recent mainnet transactions whose payload starts with given text prefixes, as on-chain evidence for a ledger
entry. Walks back from the DAG tips through a local kaspad's JSON wRPC; read-only.

  scripts/find_payload_txs.py [--rpc ws://127.0.0.1:18110] [--blocks 20000] PREFIX [PREFIX ...]
Prints up to 3 transaction ids per prefix, with block time, for linking at https://explorer.kaspa.org/txs/<id>.
"""
import argparse
import asyncio
import datetime as dt
import json

import websockets


async def main(a):
    want = {p: p.encode().hex() for p in a.prefix}
    found = {p: [] for p in a.prefix}
    async with websockets.connect(a.rpc, max_size=64 << 20) as ws:
        n = 0

        async def call(method, params):
            nonlocal n
            n += 1
            await ws.send(json.dumps({"id": n, "method": method, "params": params}))
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == n:
                    if "error" in r and r["error"]:
                        raise RuntimeError(r["error"])
                    return r["params"]

        info = await call("getBlockDagInfo", {})
        queue, seen, scanned = list(info["tipHashes"]), set(), 0
        while queue and scanned < a.blocks and not all(len(v) >= 3 for v in found.values()):
            h = queue.pop(0)
            if h in seen:
                continue
            seen.add(h)
            b = (await call("getBlock", {"hash": h, "includeTransactions": True}))["block"]
            scanned += 1
            for tx in b.get("transactions", []):
                pl = (tx.get("payload") or "").lower()
                for p, hx in want.items():
                    # one transaction can sit in several parallel blocks: count it once
                    txid = tx["verboseData"]["transactionId"]
                    if pl.startswith(hx) and len(found[p]) < 3 and txid not in {x[0] for x in found[p]}:
                        t = dt.datetime.fromtimestamp(int(b["header"]["timestamp"]) / 1000, dt.timezone.utc)
                        found[p].append((txid, t.strftime("%Y-%m-%d %H:%M UTC")))
            lvl0 = b["header"]["parentsByLevel"][0] if b["header"].get("parentsByLevel") else b["header"]["parents"][0]["parentHashes"]
            queue.extend(x for x in lvl0 if x not in seen)
    print(json.dumps({"scanned_blocks": scanned, "found": found}, indent=1))


ap = argparse.ArgumentParser()
ap.add_argument("--rpc", default="ws://127.0.0.1:18110")
ap.add_argument("--blocks", type=int, default=20000)
ap.add_argument("prefix", nargs="+")
asyncio.run(main(ap.parse_args()))
