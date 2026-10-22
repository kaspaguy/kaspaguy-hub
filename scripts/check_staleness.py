#!/usr/bin/env python3
"""What to re-check first, plus code activity for the cards.

- ACTION: entries whose last_verified is older than overdue_days, and repos that are gone or archived. Exit 1 if any.
- INFO: repos with no push for repo_quiet_days. Quiet code is often a finished app, so this never fails the check
  and never colours a card; the date is shown on the card as information.
Writes data/checks/repo_activity.json (last push, archived, latest release per repo), which build.py renders.

  scripts/check_staleness.py          uses GITHUB_TOKEN from the environment if set (60 requests/hour without it)
"""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
site = json.loads((ROOT / "data/site.json").read_text())
today = dt.date.today()
action, info, activity = [], [], {}


def gh(path):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "kaspaguy-hub"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    return json.load(urllib.request.urlopen(req, timeout=20))


for f in sorted((ROOT / "data/projects").glob("*.json")):
    p = json.loads(f.read_text())
    if p["status"] == "abandoned":
        continue
    age = (today - dt.date.fromisoformat(p["last_verified"])).days
    if age > site["overdue_days"]:
        action.append(f"{p['id']}: last verified {age} days ago (re-verify)")
    for repo in p.get("repos", []):
        name = repo.removeprefix("https://github.com/")
        try:
            r = gh("repos/" + name)
        except Exception as ex:  # 404 = repo deleted or made private
            action.append(f"{p['id']}: {repo} could not be read ({ex})")
            continue
        a = {"pushed": r["pushed_at"][:10], "archived": r.get("archived", False)}
        try:
            rel = gh(f"repos/{name}/releases/latest")
            a["release"] = {"tag": rel["tag_name"], "date": rel["published_at"][:10]}
        except urllib.error.HTTPError:
            pass  # no releases
        activity[repo] = a
        quiet = (today - dt.date.fromisoformat(a["pushed"])).days
        if a["archived"]:
            action.append(f"{p['id']}: {repo} is archived (check whether the project stopped)")
        elif quiet > site["repo_quiet_days"]:
            info.append(f"{p['id']}: {repo} has had no push for {quiet} days (information only)")

out = ROOT / "data/checks/repo_activity.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({"checked": today.isoformat(), "repos": activity}, indent=1) + "\n")
print("ACTION\n  " + ("\n  ".join(action) or "nothing overdue"))
print("INFO\n  " + ("\n  ".join(info) or "nothing to note"))
sys.exit(1 if action else 0)
