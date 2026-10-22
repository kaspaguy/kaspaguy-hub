#!/usr/bin/env python3
"""Page views per page per day, from the nginx log (which has no IPs and is deleted after 30 days).

Keeps only counts, in a JSON file that outlives the logs: views per page per day, 404 paths (broken links worth
fixing) and referring sites. Bots are left out by user agent, which is rough but good enough to see a trend.

  scripts/pageviews.py [--log-dir /var/log/kaspaguy-site] [--out /var/lib/kaspaguy-stats/pageviews.json] [--days 14]
"""
import argparse
import collections
import gzip
import json
import re
import urllib.parse
from pathlib import Path

LINE = re.compile(r'^(\d{4}-\d\d-\d\d)T\S+ GET (\S+) (\d{3}) \d+ "([^"]*)" "([^"]*)"$')
BOT = re.compile(r"bot|crawl|spider|slurp|preview|monitor|curl|wget|python|go-http|headless|uptime", re.I)
ASSET = re.compile(r"\.(css|js|svg|png|ico|xml|txt|map)$")

ap = argparse.ArgumentParser()
ap.add_argument("--log-dir", default="/var/log/kaspaguy-site")
ap.add_argument("--out", default="/var/lib/kaspaguy-stats/pageviews.json")
ap.add_argument("--days", type=int, default=14, help="how many recent days to print")
a = ap.parse_args()

out = Path(a.out)
stats = json.loads(out.read_text()) if out.exists() else {"days": {}}
fresh = collections.defaultdict(lambda: {"views": collections.Counter(), "404": collections.Counter(),
                                         "referrers": collections.Counter()})
for f in sorted(Path(a.log_dir).glob("access.log*")):
    with (gzip.open(f, "rt", errors="replace") if f.suffix == ".gz" else open(f, errors="replace")) as fh:
        for line in fh:
            m = LINE.match(line.strip())
            if not m or BOT.search(m[5]):
                continue
            day, path, status, ref = m[1], m[2], m[3], m[4]
            if status == "404":
                fresh[day]["404"][path] += 1
            elif status == "200" and not ASSET.search(path):
                fresh[day]["views"][path.removesuffix(".html") or "/"] += 1
                host = urllib.parse.urlsplit(ref).hostname if ref not in ("", "-") else None
                if host and not host.endswith("kaspaguy.com"):
                    fresh[day]["referrers"][host] += 1

# the logs cover the last 30 days in full, so a day seen in them is recounted rather than added to
for day, c in fresh.items():
    stats["days"][day] = {k: dict(v.most_common()) for k, v in c.items()}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(stats, indent=1, sort_keys=True) + "\n")

for day in sorted(stats["days"])[-a.days:]:
    d = stats["days"][day]
    print(f"{day}  {sum(d['views'].values()):5} views  " + "  ".join(f"{p} {n}" for p, n in list(d["views"].items())[:6]))
    if d["404"]:
        print("            404: " + "  ".join(f"{p} {n}" for p, n in list(d["404"].items())[:5]))
    if d["referrers"]:
        print("            from: " + "  ".join(f"{h} {n}" for h, n in list(d["referrers"].items())[:5]))
