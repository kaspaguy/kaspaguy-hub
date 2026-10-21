#!/usr/bin/env python3
"""List what to re-check first: ledger entries whose last_verified is overdue, and GitHub repos with no push
for repo_quiet_days. Read-only; prints a report and exits 1 if anything needs attention (fit for a weekly cron).

  scripts/check_staleness.py          uses GITHUB_TOKEN from the environment if set (60 requests/hour without it)
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
site = json.loads((ROOT / "data/site.json").read_text())
today = dt.date.today()
todo = []

for f in sorted((ROOT / "data/projects").glob("*.json")):
    p = json.loads(f.read_text())
    if p["status"] == "abandoned":
        continue
    age = (today - dt.date.fromisoformat(p["last_verified"])).days
    if age > site["overdue_days"]:
        todo.append(f"{p['id']}: last verified {age} days ago")
    for repo in p.get("repos", []):
        req = urllib.request.Request("https://api.github.com/repos/" + repo.removeprefix("https://github.com/"),
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "kaspaguy-hub"})
        if os.environ.get("GITHUB_TOKEN"):
            req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
        try:
            r = json.load(urllib.request.urlopen(req, timeout=20))
        except Exception as ex:  # 404 = repo deleted or made private: worth a look too
            todo.append(f"{p['id']}: {repo} could not be read ({ex})")
            continue
        quiet = (today - dt.date.fromisoformat(r["pushed_at"][:10])).days
        if r.get("archived"):
            todo.append(f"{p['id']}: {repo} is archived")
        elif quiet > site["repo_quiet_days"]:
            todo.append(f"{p['id']}: {repo} has had no push for {quiet} days")

print("\n".join(todo) or "nothing overdue")
sys.exit(1 if todo else 0)
