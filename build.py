#!/usr/bin/env python3
"""Build the Kaspaguy hub (kaspaguy.com) from data/ into dist/. Standard library only.

Every page is rendered from the JSON in data/, so an update is a commit, never a login.
  build.py            validate data/ and write dist/
  build.py --check    validate only (run before every commit)

Ages ("checked 12 days ago") are written at build time AND recomputed in the reader's browser,
so a hub nobody rebuilds still shows its entries going overdue instead of looking fresh.
"""
import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA, SITE, DIST = ROOT / "data", ROOT / "site", ROOT / "dist"
TODAY = dt.date.today()
STATUSES = {
    "idea": "Announced, nothing public to try or inspect yet.",
    "testnet": "Running on a Kaspa testnet. No real KAS at stake.",
    "mainnet": "Running on Kaspa mainnet with real KAS.",
    "abandoned": "No activity for 180+ days, or the builders say it has stopped.",
}
# How the project relates to Kaspaguy. Shown as a label on the card so the conflict is visible, not just disclosed.
RELATIONSHIPS = {"self": "our project", "competitor": "competes with KaspaChat", "none": None}
AUDITS = {"none": "No external audit", "internal": "Internal review only", "external": "External audit"}
ROADMAP_LABELS = {
    "live": "On mainnet now.",
    "targeted": "Has a named release or activation target from the core developers.",
    "research": "Designed or discussed, with no release target.",
    "unsupported": "Claimed around the community, with no source from the people building it.",
}
NAV = [("index", "Home"), ("ledger", "Ledger"), ("shipped", "What shipped"), ("roadmap", "Roadmap"),
       ("scams", "Scams & graveyard"), ("kaspachat", "KaspaChat"), ("trust", "Rules")]

e = html.escape


def load(name):
    return json.loads((DATA / name).read_text())


# ---------- validation ----------

def check_date(s, where, errs):
    try:
        d = dt.date.fromisoformat(s)
    except (TypeError, ValueError):
        errs.append(f"{where}: bad date {s!r}")
        return
    if d > TODAY:
        errs.append(f"{where}: date {s} is in the future")


def check_url(u, where, errs):
    if not isinstance(u, str) or not u.startswith("https://"):
        errs.append(f"{where}: link must start with https:// ({u!r})")


def validate(site, projects, shipped, roadmap, scams, lookalikes):
    errs = []
    cats = {c["id"] for c in site["categories"]}
    ids = set()
    for p in projects:
        w = f"projects/{p.get('id')}.json"
        for k in ("id", "name", "category", "summary", "builder", "relationship", "status", "self_claimed", "last_verified",
                  "evidence", "code", "audit"):
            if k not in p:
                errs.append(f"{w}: missing {k}")
        if p.get("id") in ids:
            errs.append(f"{w}: duplicate id")
        ids.add(p.get("id"))
        if p.get("category") not in cats:
            errs.append(f"{w}: unknown category {p.get('category')!r} (add it to site.json)")
        if p.get("relationship") not in RELATIONSHIPS:
            errs.append(f"{w}: relationship must be one of {list(RELATIONSHIPS)}")
        if p.get("status") not in STATUSES:
            errs.append(f"{w}: status must be one of {list(STATUSES)}")
        if p.get("audit", {}).get("status") not in AUDITS:
            errs.append(f"{w}: audit.status must be one of {list(AUDITS)}")
        if p.get("audit", {}).get("status") == "external" and not p["audit"].get("links"):
            errs.append(f"{w}: an external audit needs a link to the report")
        check_date(p.get("last_verified"), w, errs)
        if not p.get("evidence"):
            errs.append(f"{w}: at least one evidence link is required")
        for x in p.get("evidence", []) + p.get("official_links", []):
            check_url(x.get("url"), w, errs)
        for r in p.get("repos", []):
            if not re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+", r):
                errs.append(f"{w}: repos must be https://github.com/owner/name ({r})")
        if not p.get("self_claimed") and all(not x.get("public", True) for x in p.get("evidence", [])):
            errs.append(f"{w}: no public evidence, so self_claimed must be true")
    for p in projects:
        for r in p.get("related", []):
            if r.get("id") not in ids:
                errs.append(f"projects/{p['id']}.json: related id {r.get('id')!r} is not in the ledger")
            if not r.get("note"):
                errs.append(f"projects/{p['id']}.json: related {r.get('id')!r} needs a note saying how")
    for s in shipped:
        w = f"shipped/{s.get('_file')}"
        if s.get("in_progress"):
            # the current week: week_ending is the coming Sunday, "updated" is when we last added to it
            check_date(s.get("updated"), w + " updated", errs)
            try:
                left = (dt.date.fromisoformat(s["week_ending"]) - TODAY).days
                if not 0 <= left <= 6:
                    errs.append(f"{w}: in_progress week must end within the next 6 days (publish it as done)")
            except (KeyError, TypeError, ValueError):
                errs.append(f"{w}: bad week_ending {s.get('week_ending')!r}")
        else:
            check_date(s.get("week_ending"), w, errs)
        if s.get("compiled"):
            check_date(s["compiled"], w + " compiled", errs)
        for it in s.get("items", []):
            if not it.get("sources"):
                errs.append(f"shipped/{s['_file']}: every item needs a source ({it.get('what')!r})")
    for r in roadmap:
        if r.get("label") not in ROADMAP_LABELS:
            errs.append(f"roadmap: {r.get('feature')!r} label must be one of {list(ROADMAP_LABELS)}")
        if not r.get("sources"):
            errs.append(f"roadmap: {r.get('feature')!r} needs a source")
    for key, _, _ in SCAM_SECTIONS:
        for d in scams.get(key, []):
            w = f"scams.json {key}: {d.get('name')}"
            for k in ("name", "what", "added", "sources"):
                if not d.get(k):
                    errs.append(f"{w}: missing {k}")
            check_date(d.get("added"), w, errs)
            for x in d.get("sources", []):
                check_url(x.get("url"), w, errs)
                check_date(x.get("date"), f"{w} source", errs)
            if key == "confirmed" and not any(x.get("third_party") for x in d.get("sources", [])):
                errs.append(f"{w}: confirmed phishing needs a documented third-party report (third_party: true)")
            if d.get("state"):
                if d["state"] not in ("offline", "online"):
                    errs.append(f"{w}: state must be offline or online")
                check_date(d.get("state_checked"), f"{w} state_checked", errs)
            if key == "unverified" and not d.get("unknown"):
                errs.append(f"{w}: say what we don't know yet (unknown)")
    for k in scams:
        if k not in {x[0] for x in SCAM_SECTIONS}:
            errs.append(f"scams.json: unknown section {k!r}")
    check_date(lookalikes.get("checked"), "lookalikes.json", errs)
    for x in lookalikes.get("items", []):
        # a quote without a date is a future correction: project blurbs change
        check_date(x.get("says_date"), f"lookalikes.json {x.get('name')}: says_date", errs)
        check_url(x.get("says_source"), f"lookalikes.json {x.get('name')}: says_source", errs)
    return errs


# ---------- helpers ----------

def age_span(date_s, overdue, stale, prefix="checked"):
    d = dt.date.fromisoformat(date_s)
    n = (TODAY - d).days
    cls = "stale" if n > stale else "overdue" if n > overdue else ""
    return (f'<span class="age {cls}" data-date="{e(date_s)}" data-overdue="{overdue}" data-stale="{stale}" '
            f'data-prefix="{e(prefix)}">{e(prefix)} {e(date_s)} ({days(n)})</span>')


def days(n):
    return "today" if n <= 0 else "1 day ago" if n == 1 else f"{n} days ago"


def link(label, url, external=True):
    rel = ' rel="nofollow noopener"' if external else ""
    return f'<a href="{e(url)}"{rel}>{e(label)}</a>'


def draft(text):
    return f'<mark class="draft" title="Draft: needs Kaspaguy\'s confirmation">{text}</mark>'


AGE_JS = """<script>
document.querySelectorAll('.age[data-date]').forEach(function (el) {
  var n = Math.floor((Date.now() - Date.parse(el.dataset.date + 'T00:00:00Z')) / 864e5);
  var t = n <= 0 ? 'today' : n === 1 ? '1 day ago' : n + ' days ago';
  el.textContent = el.dataset.prefix + ' ' + el.dataset.date + ' (' + t + ')';
  el.classList.toggle('overdue', n > +el.dataset.overdue && n <= +el.dataset.stale);
  el.classList.toggle('stale', n > +el.dataset.stale);
});
</script>"""


def page(site, slug, title, body, desc, listed=True):
    nav = "".join(f'<a href="/{"" if s == "index" else s}"{" aria-current=page" if s == slug else ""}>{e(t)}</a>'
                  for s, t in NAV)
    banner = ('<div class="staging"><div class="wrap">Staging copy, not public yet.</div></div>') if site["staging"] else ""
    # "indexable" is separate from "staging": the site can go public quietly, unindexed, before it's announced
    robots = '' if site.get("indexable") and listed else '<meta name="robots" content="noindex, nofollow">'
    repo = (link("public data repo", site["data_repo_url"], external=False) if site["data_repo_url"]
            else "a public data repo (published at launch)")
    full = f"{title} · Kaspaguy" if slug != "index" else "Kaspaguy · What's being built on Kaspa"
    url = site["base_url"] + ("/" if slug == "index" else f"/{slug}")
    img = site["base_url"] + "/og.png"
    # the preview people see when a page is shared in Discord, Telegram or on X
    social = ((f'<link rel="canonical" href="{url}">' if listed else "") + f'<meta property="og:type" content="website">'
              f'<meta property="og:site_name" content="Kaspaguy"><meta property="og:title" content="{e(full)}">'
              f'<meta property="og:description" content="{e(desc)}">'
              + (f'<meta property="og:url" content="{url}">' if listed else "") +
              f'<meta property="og:image" content="{img}"><meta property="og:image:width" content="1200">'
              f'<meta property="og:image:height" content="630"><meta property="og:image:alt" '
              f'content="Kaspaguy: what\'s being built on Kaspa, with the evidence. Dated, sourced, no paid listings.">'
              f'<meta name="twitter:card" content="summary_large_image">')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full)}</title><meta name="description" content="{e(desc)}">{robots}
{social}
<link rel="icon" href="/icon.svg"><link rel="stylesheet" href="/style.css?v={STYLE_V}"></head>
<body>{banner}
<header class="top"><div class="wrap"><a class="brand" href="/"><img src="/icon.svg" width="26" height="26" alt="">Kaspaguy</a>
<nav aria-label="Main">{nav}</nav></div></header>
<main><div class="wrap">{body}</div></main>
<footer><div class="wrap">Kaspaguy keeps a dated, sourced record of what's being built on Kaspa. No paid listings.
Every page is built from {repo}, so every change is a public commit.
<a href="/trust">How we work</a> · <a href="/trust#licence">Data CC BY 4.0, code MIT</a> · Contact {e(site["contact"])} · <a href="/trust#privacy">No cookies or trackers</a> · Built {TODAY.isoformat()}</div></footer>
{AGE_JS}</body></html>
"""


# ---------- pages ----------

def p_home(site, projects, shipped):
    last = next((x["week_ending"] for x in shipped if not x.get("in_progress")), None)
    pulse = (f"Last full week logged: {age_span(last, 8, 21, 'week ending')}." if last
             else "The weekly log starts at launch.")
    return f"""
<h1>What's being built on Kaspa, with the evidence.</h1>
<p class="lead">Kaspaguy builds KaspaChat, a private messenger on Kaspa. We also keep a dated, sourced record of
what's being built on Kaspa: what stage each project has reached, when we last checked, and the links that prove it.
No paid listings.</p>
<p><a class="btn" href="/ledger">Open the ledger</a><a class="btn ghost" href="/trust">Read our rules first</a></p>

<div class="notice">We build KaspaChat, so we have a stake in this. Our own entry follows the same rules as everyone
else's: it's flagged as self-claimed, and it's never ranked above anyone. <a href="/trust#conflict">How we handle that</a>.</div>

<h2>What's here</h2>
<div class="grid">
<a class="card" href="/ledger"><h3>The ledger</h3><p class="muted">Projects with a status (idea, testnet, mainnet or
abandoned), the date we last checked, evidence links, audit status and a self-claimed flag.
{len(projects)} {"entry" if len(projects) == 1 else "entries"} so far.</p></a>
<a class="card" href="/shipped"><h3>What shipped</h3><p class="muted">A short weekly log of what actually went live,
with a source for every line. {pulse}</p></a>
<a class="card" href="/roadmap"><h3>Roadmap</h3><p class="muted">Protocol features, each labelled live, targeted,
research or unsupported, with sources.</p></a>
<a class="card" href="/scams"><h3>Scams &amp; graveyard</h3><p class="muted">Phishing domains, impersonators and
projects that stopped.</p></a>
</div>

<h2>What this isn't</h2>
<p>It's not a portal or a full directory, and it doesn't rank anything. Other people already do parts of this well,
so use them too:</p>
<ul>
<li>{link("KaspaHub", "https://kaspahub.org")} has the broadest directory of Kaspa projects.</li>
<li>{link("Kaspa Explained", "https://kaspaexplained.com/status")} labels protocol features by status.</li>
<li>{link("kaspa.org", "https://kaspa.org")} and the {link("KIPs", "https://github.com/kaspanet/kips")} are the official word on the protocol.</li>
</ul>
<p class="muted">We list fewer projects, and for each one we show the evidence and the date we checked it.</p>
"""


def code_activity(p, activity):
    """Information only: quiet code is often a finished app, so this never changes the card's colour."""
    out = []
    for r in p.get("repos", []):
        a = activity.get("repos", {}).get(r)
        if not a:
            continue
        line = f"{e(r.removeprefix('https://github.com/'))}: last change {age_span(a['pushed'], 10**6, 10**6, '')}"
        if a.get("release"):
            line += f", latest release {e(a['release']['tag'])} ({e(a['release']['date'])})"
        if a.get("archived"):
            line += " (archived by its owner)"
        out.append(f"<li>{line}</li>")
    if not out:
        return None
    return (f"<ul style='margin:0;padding-left:18px'>{''.join(out)}</ul>"
            f"<span class='small muted'>Read from GitHub {e(activity['checked'])}. Information, not a verdict.</span>")


def entry_card(p, site, activity=None, names=None):
    flags = ['<span class="pill flag">self-claimed</span>'] if p["self_claimed"] else []
    rel = RELATIONSHIPS[p["relationship"]]
    if rel:
        flags.append(f'<span class="pill rel">{e(rel)}</span>')
    ev = "".join(
        f'<li>{link(x["label"], x["url"])}{"" if x.get("public", True) else " <span class=muted>(not public: " + e(x.get("note", "private")) + ")</span>"}</li>'
        for x in p["evidence"])
    off = " · ".join(link(x["label"], x["url"]) for x in p.get("official_links", []))
    code = p["code"]
    code_s = {"yes": "Open source", "partial": "Partly open source", "no": "Closed source"}.get(code.get("open"), "Unknown")
    if code.get("licence"):
        code_s += f" ({e(code['licence'])})"
    if code.get("note"):
        code_s += f". {e(code['note'])}"
    au = p["audit"]
    au_s = e(AUDITS[au["status"]]) + (f". {e(au['note'])}" if au.get("note") else "")
    au_s += "".join(" " + link("report", u) for u in au.get("links", []))
    repos = "".join(f"<li>{link(r.removeprefix('https://github.com/'), r)}</li>" for r in p.get("repos", []))
    rows = [
        ("Status", f"{e(p.get('status_note', ''))}"),
        ("Last verified", age_span(p["last_verified"], site["overdue_days"], site["stale_days"])),
        ("Built by", link(p["builder"]["name"], p["builder"]["url"]) if p["builder"].get("url") else e(p["builder"]["name"])),
        ("Official links", off or '<span class="muted">none</span>'),
        ("Evidence", f"<ul style='margin:0;padding-left:18px'>{ev}</ul>"),
        ("Code", code_s + (f"<ul style='margin:0;padding-left:18px'>{repos}</ul>" if repos else "")),
        ("Code activity", code_activity(p, activity or {})),
        ("Audit", au_s),
        ("KCC standard", e(p["kcc"]) if p.get("kcc") else '<span class="muted">none declared</span>'),
        ("Token", e(p["token"]) if p.get("token") else '<span class="muted">none</span>'),
    ]
    if p["self_claimed"]:
        rows.insert(2, ("Self-claimed", e(p.get("self_claimed_note") or "Only the builders' own statements back this up so far.")))
    if p.get("related"):
        rows.append(("Related", "<br>".join(
            f'<a href="#{e(r["id"])}">{e((names or {}).get(r["id"], r["id"]))}</a>: {e(r["note"])}' for r in p["related"])))
    if p.get("conflict"):
        rows.append(("Our interest", e(p["conflict"])))
    dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows if v is not None)
    return f"""<article class="card entry" id="{e(p['id'])}"><header><h3>{e(p['name'])}</h3>
<span class="pill {e(p['status'])}">{e(p['status'])}</span>{''.join(flags)}</header>
<p>{e(p['summary'])}</p>{f'<p class="caveat"><strong>Read this first:</strong> {e(p["evidence_caveat"])}</p>' if p.get("evidence_caveat") else ""}<dl>{dl}</dl></article>"""


def p_ledger(site, projects, activity):
    names = {p["id"]: p["name"] for p in projects}
    legend = "".join(f'<li><span class="pill {k}">{k}</span> {e(v)}</li>' for k, v in STATUSES.items())
    out = [f"""<h1>The ledger</h1>
<p class="lead">Kaspa projects, each with its stage, the date we last checked it and the evidence. Sorted A to Z,
never by who paid or who we like.</p>
<ul style="list-style:none;padding:0">{legend}
<li><span class="pill flag">self-claimed</span> Only the builders' own statements back this up so far.</li>
<li><span class="pill rel">our project</span> <span class="pill rel">competes with KaspaChat</span> How the project relates to
us. <a href="/trust#conflict">Why we label it</a>.</li></ul>
<p class="small muted">We re-check every entry at least monthly. A check older than {site['overdue_days']} days turns
yellow, and one older than {site['stale_days']} days turns red, so you can see when we fall behind. The colour is about
our checking, never about the project: quiet code is shown as information only.
<a href="/trust#rules">Full rules</a>.</p>"""]
    for c in site["categories"]:
        ps = sorted((p for p in projects if p["category"] == c["id"] and p["status"] != "abandoned"),
                    key=lambda p: p["name"].lower())
        out.append(f'<h2 id="{e(c["id"])}">{e(c["title"])}</h2>')
        out.append("".join(entry_card(p, site, activity, names) + "<div style='height:14px'></div>" for p in ps)
                   or '<div class="empty">No entries yet.</div>')
    if len(projects) == 1:
        out.append('<div class="notice">The first entry is our own, so you can see the rules applied to us before '
                   'anyone else. More messaging and social projects come next.</div>')
    return "".join(out)


def p_shipped(shipped):
    if not shipped:
        body = '<div class="empty">No weeks logged yet. The first log comes out the week the site goes public.</div>'
    else:
        parts = []
        for s in shipped:
            items = "".join(
                f"<li><strong>{e(it.get('project', ''))}</strong> {e(it['what'])} "
                + " ".join(link(x["label"], x["url"]) for x in it["sources"]) + "</li>" for it in s.get("items", []))
            when = (f'This week, to {e(s["week_ending"])} <span class="pill">in progress</span>' if s.get("in_progress")
                    else f'Week ending {e(s["week_ending"])}')
            if s.get("in_progress"):
                when += f'<br><span class="small muted">Last added to on {e(s["updated"])}.</span>'
            elif s.get("compiled") and s["compiled"] > s["week_ending"]:
                when += f'<br><span class="small muted">Compiled afterwards, on {e(s["compiled"])}, from dated public sources.</span>'
            parts.append(f'<section class="card" id="w{e(s["week_ending"])}"><h3>{when}</h3>'
                         + (f"<ul>{items}</ul>" if items else f"<p class='muted'>{e(s.get('note') or 'Nothing shipped that we could verify.')}</p>")
                         + "</section><div style='height:14px'></div>")
        body = "".join(parts)
    done = [s for s in shipped if not s.get("in_progress")]
    head = (f"Latest full week: {age_span(done[0]['week_ending'], 8, 21, 'week ending')}." if done else "")
    return f"""<h1>What shipped</h1>
<p class="lead">Every week, a short, dated list of what actually went live on Kaspa, each line with its source.
A quiet week says so. A missed week shows as a gap.</p>
<p class="small muted">"Went live" means released, activated or formally adopted. Code merged but not yet released
doesn't count, and neither does an announcement.</p><p class="muted small">{head}</p>{body}"""


def p_roadmap(roadmap):
    legend = "".join(f"<li><strong>{k}</strong>: {e(v)}</li>" for k, v in ROADMAP_LABELS.items())
    if roadmap:
        rows = "".join(
            f"<tr><td data-label='Feature'>{e(r['feature'])}</td><td data-label='Label'><strong>{e(r['label'])}</strong></td>"
            f"<td data-label='Notes'>{e(r.get('note', ''))}</td>"
            f"<td data-label='Sources'>{' · '.join(link(x['label'], x['url']) for x in r['sources'])}</td></tr>" for r in roadmap)
        table = (f'<div class="tablewrap"><table class="table stack"><tr><th>Feature</th><th>Label</th><th>Notes</th>'
                 f'<th>Sources</th></tr>{rows}</table></div>')
    else:
        table = '<div class="empty">The roadmap table is being sourced. Every item will link to the people building it.</div>'
    return f"""<h1>Roadmap</h1>
<p class="lead">Kaspa protocol features, each with a label and a source, so you can tell what's live from what's
only talked about.</p><ul>{legend}</ul>
<p class="small muted">When a target date passes, we keep the old target on the page, link to where it was published
and say that it was missed. Targets quietly disappearing is exactly what makes Kaspa's roadmap hard to follow.</p>{table}"""


SCAM_SECTIONS = [
    ("confirmed", "Confirmed phishing",
     "Sites built to steal recovery phrases or funds. Listed only with a documented report from someone other than us, "
     "such as a phishing database or a security firm."),
    ("unverified", "Impersonation and unverified domains",
     "Lookalike names and domains we can't yet confirm either way. Being here is not an accusation. Each one says what "
     "we know, what we don't, and what would settle it."),
    ("label", "Riding the Kaspa name",
     "Projects that aren't part of Kaspa but are marketed with its name, often through paid articles. We describe what "
     "they are, with sources, and nothing more."),
]


def scam_item(d, key):
    src = " · ".join(link(f"{x['label']} ({x['date']})", x["url"]) for x in d["sources"])
    body = [f"<p>{e(d['what'])}</p>"]
    if key == "unverified":
        body.append(f"<p class='small'><strong>Not known yet:</strong> {e(d['unknown'])}</p>")
    state = (f" <span class='pill'>{'now offline' if d['state'] == 'offline' else 'still online'}, checked {e(d['state_checked'])}</span>"
             if d.get("state") else "")
    return (f"<div class='card'><h3><code>{e(d['name'])}</code>{state}</h3>{''.join(body)}"
            f"<p class='small muted'>Added {e(d['added'])}. Sources: {src}</p></div><div style='height:12px'></div>")


def p_scams(scams, projects, site):
    sections = []
    for key, title, intro in SCAM_SECTIONS:
        items = "".join(scam_item(d, key) for d in scams.get(key, []))
        sections.append(f"<h2 id='{key}'>{e(title)}</h2><p class='muted small'>{e(intro)}</p>"
                        + (items or '<div class="empty">None listed yet.</div>'))
    dead = [p for p in projects if p["status"] == "abandoned"]
    return f"""<h1>Scams &amp; graveyard</h1>
<p class="lead">Fake sites, impersonators, projects borrowing Kaspa's name, and projects that stopped. Nobody official
keeps a list like this for Kaspa, so we do.</p>
<div class="notice">Kaspa developers, wallet makers and Kaspaguy will never message you first, ask for your recovery
phrase or offer to recover lost funds. Anyone who does is a scammer.</div>
<div class="notice"><strong>Listed by mistake?</strong> Email {e(site['corrections'])} with your evidence. We look at
every request within a week, and a confirmed mistake comes off the page the same day, with the change visible in our
public history.</div>
<h2>How this page works</h2>
<p>This page accuses people, so its rules are stricter than the ledger's:</p>
<ul>
<li>A domain goes under <strong>confirmed phishing</strong> only with a documented report from someone other than us.
Our own suspicion is never enough.</li>
<li>Anything we can't confirm goes under <strong>unverified</strong>, with what we don't know written out.</li>
<li>Every claim carries the date we added it and dated sources.</li>
<li>We describe what happened. We don't guess at anyone's motives.</li>
</ul>
{''.join(sections)}
<h2 id="graveyard">Graveyard</h2>
<p class="muted small">Projects from the ledger marked abandoned. They stay here so you can check before you send them
money.</p>{''.join(entry_card(p, site, None, {q["id"]: q["name"] for q in projects}) for p in dead) or '<div class="empty">None yet.</div>'}"""


def p_kaspachat(site, lookalikes):
    rows = [f"""<tr><td data-label="Name"><strong>KaspaChat</strong><br><span class="small muted">this one</span></td>
<td data-label="What it says it is">Private messenger. Hides who talks to whom, not just what's said. Sign up with a 24-word recovery phrase.</td>
<td data-label="Official site">{link("kaspachat.com", "https://kaspachat.com", external=False)}</td>
<td data-label="Code">Protocol: {link("kaspaveil.com", "https://kaspaveil.com", external=False)}</td><td data-label="Made by">Kaspaguy</td></tr>"""]
    for x in lookalikes["items"]:
        code = " ".join(link(u.removeprefix("https://github.com/"), u) for u in x["code"])
        rows.append(f"""<tr><td data-label="Name"><strong>{e(x['name'])}</strong>{'<br><span class="small muted">' + e(x['relation']) + '</span>' if x.get('relation') else ''}</td><td data-label="What it says it is">“{e(x['says'])}”<br><span class="small muted">quoted from {link(x['says_source'].removeprefix('https://'), x['says_source'])}, {e(x['says_date'])}</span></td>
<td data-label="Official site">{link(x['site'].removeprefix('https://'), x['site'])}</td>
<td data-label="Code">{code}{'<br>' if code else ''}<span class="small muted">{e(x.get('code_note', ''))}</span></td><td data-label="Made by">{e(x['maker'])}</td></tr>""")
    return f"""<h1>KaspaChat</h1>
<p class="lead">A private messenger built on Kaspa. You sign up with a 24-word recovery phrase instead of a phone
number or email. Messages are end-to-end encrypted on your device, and nobody, including us, can read them or see who
you talk to.</p>
<p><a class="btn" href="https://kaspachat.com">Go to kaspachat.com</a><a class="btn ghost" href="/ledger#kaspachat">See its ledger entry</a></p>

<h2>Where it stands</h2>
<div class="grid">
<div class="card"><h3>Status: testnet</h3><p class="muted">KaspaChat runs on Kaspa testnet-10 and isn't on mainnet
yet. It runs in your browser on a phone or computer. The Android and iPhone apps aren't released yet.</p></div>
<div class="card"><h3>What's open source</h3><p class="muted">The Kaspaveil protocol (its encryption and test vectors)
and its contracts are open source under AGPL-3.0 at kaspaveil.com. The KaspaChat apps and Kaspaguy's servers are
closed source.</p></div>
<div class="card"><h3>Audit</h3><p class="muted">No external audit yet, only our own review. The ledger will link the
report when there is one.</p></div>
</div>

<h2>The only official addresses</h2>
<ul>
<li>App and website: <strong>kaspachat.com</strong></li>
<li>Protocol, specification and contracts: <strong>kaspaveil.com</strong></li>
<li>Maker: <strong>Kaspaguy</strong>, at kaspaguy.com and {e(site["contact"])}</li>
</ul>
<p>KaspaChat has no token and no coin sale. If someone offers you a KaspaChat token, it's a scam. We'll never message
you first or ask for your recovery phrase.</p>

<h2 id="which-one">Which one is this?</h2>
<div class="notice"><strong>Kaspaguy is not associated with Kasia or KaChat.</strong> They are separate projects by
separate teams. We share no code, team or money with them, and neither side endorses the other.</div>
<p>Several Kaspa messengers have similar names. Here's how to tell them apart, so you end up in the one you meant.
We link each project's own site so you can go straight there. The descriptions are short quotes in their own words,
dated, and they belong to their authors.</p>
<div class="tablewrap"><table class="table stack">
<tr><th>Name</th><th>What it says it is</th><th>Official site</th><th>Code</th><th>Made by</th></tr>
{''.join(rows)}
</table></div>
<p class="small muted">Checked {e(lookalikes['checked'])}. All three are in <a href="/ledger#messaging">our ledger</a>
under the same rules, sorted A to Z. If we've described your project wrongly, email {e(site["corrections"])} and we'll fix it the
same week.</p>
<p class="small"><strong>Again: Kaspaguy and KaspaChat are not associated with Kasia, KaChat or the .kachat names
project.</strong></p>
"""


def p_trust(site):
    return f"""<div class="doc">
<h1>Our rules</h1>
<p class="lead">How we decide what goes in, how we label it, and why we're not paid to. We published these before the
first entry. Version {e(site['policy_version'])}, {e(site['policy_date'])}.</p>

<h2 id="rules">How an entry gets its status</h2>
<p>Every project in the ledger has one status, and each status needs evidence you can check yourself:</p>
<ul>
<li><span class="pill mainnet">mainnet</span> a mainnet transaction or covenant you can look up in a block explorer,
or a public app that uses real KAS.</li>
<li><span class="pill testnet">testnet</span> a public deployment on a Kaspa testnet.</li>
<li><span class="pill idea">idea</span> announced, with nothing public to try or inspect yet.</li>
<li><span class="pill abandoned">abandoned</span> no code or on-chain activity for 180 days and no answer from the
team, or the team says it has stopped. These move to the <a href="/scams">graveyard</a>, they aren't deleted.</li>
</ul>
<p>We prefer evidence in this order: on-chain records, public code (a repository, commit or release), the team's own
documentation, then an independent write-up. If the only backing is the builders' own announcement, the entry carries
a <span class="pill flag">self-claimed</span> flag until someone independent can confirm it.</p>

<h2 id="dates">Two dates, two meanings</h2>
<p>Each entry shows two different dates, and they mean different things:</p>
<ul>
<li><strong>Last verified</strong> is the day we opened the evidence ourselves, not the day someone told us about it.
This is the only date that changes colour. We re-check every entry at least once a month. A check older than
{site['overdue_days']} days shows in yellow, and one older than {site['stale_days']} days in red. These ages update in
your browser, so a page we forgot to rebuild still shows its age. The colour measures us, not the project.</li>
<li><strong>Code activity</strong> is when the project's public code last changed, read from GitHub. It's information,
never a warning colour.</li>
</ul>
<p><strong>Stale code is information, not a verdict.</strong> An entry can be freshly verified and still have quiet
code. That's often a mature app, not an abandoned one. A project only becomes "abandoned" under the rule above: no code
<em>and</em> no on-chain activity for 180 days and no answer from the team, or the team says it has stopped.</p>
<p>The weekly "what shipped" log is dated too. If we miss a week, you'll see the gap.</p>

<h2 id="method">How we confirm a project is on mainnet</h2>
<p>Many Kaspa apps mark their transactions with a short prefix in the transaction's data, or use a known contract.
When an entry cites a mainnet transaction, this is how we found and checked it:</p>
<ol>
<li>Find the project's marker in its own public code, so we know what its transactions look like.</li>
<li>Scan recent blocks on our own Kaspa mainnet node for transactions carrying that marker.</li>
<li>Confirm each transaction on a public Kaspa explorer, so you can check it without trusting our node.</li>
<li>Check whether any other project uses the same marker. If one does, we say so on the entry: the transaction then
proves the format is in use on mainnet, not which app sent it.</li>
<li>Link the transactions on the entry, with the date we found them.</li>
</ol>
<p>We don't take someone else's count or label as evidence, including dashboards we respect. We use them to know where to
look, then check the chain ourselves. The scanning script is in the data repo, so anyone can repeat the check.</p>

<h2>Audits and standards</h2>
<p>We don't audit projects. We report what exists: no external audit, internal review only, or an external audit with
a link to the report. If a project uses a Kaspa covenant standard (KCC), we note the version it says it follows.</p>

<h2 id="paid">No paid listings</h2>
<p>We don't accept money, tokens, airdrops, allocations or referral fees to list a project, change its status or
change what we write about it. There are no ads on this site. If that ever changes, this page will say so first, with
the date.</p>

<h2 id="conflict">Our conflict of interest</h2>
<p>Kaspaguy builds KaspaChat, a private messenger on Kaspa. That makes us a competitor of other Kaspa messengers,
including some in this ledger. Here's how we handle it:</p>
<ul>
<li>KaspaChat's entry follows the same rules as every other entry. It carries the self-claimed flag until someone
independent has checked it, and it shows no external audit until there is one.</li>
<li>Entries are sorted A to Z. We never rank KaspaChat, or anything else, above another project.</li>
<li>Every entry carries a relationship label: <span class="pill rel">our project</span> for KaspaChat and
<span class="pill rel">competes with KaspaChat</span> for its competitors, so you can weigh what we write.</li>
<li>We describe other messengers in their own words and link to their official sites.</li>
</ul>
<p id="holdings"><strong>Kaspaguy holds KAS.</strong> For a site about Kaspa that's not a conflict, but we'd rather you
heard it from us. If we ever hold the token of a project in the ledger, that project's entry says so.</p>

<h2 id="corrections">Corrections</h2>
<p>If something here is wrong or out of date, email {e(site['corrections'])}
{"or open an issue in the " + link("public data repo", site['data_repo_url'], external=False) if site['data_repo_url'] else "or, once it's public, open an issue in the data repo"}.
Send a link to the evidence. We fix confirmed mistakes the same week, and the commit history shows what changed and
when.</p>

<h2>Where the data comes from</h2>
<p>Every page is built from plain files in a public repository, one file per project. Every change is a commit, so
anyone can see who changed what and when. We write our own entries from the evidence. We don't copy other directories:
KaspaHub's data has no licence, so we link to KaspaHub rather than reuse its list.</p>

<h2 id="licence">Reusing our data</h2>
<ul>
<li><strong>Data and text:</strong> the JSON data and our own writing on this site are under
{link("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/")}. Reuse them freely, with credit to Kaspaguy and a
link back.</li>
<li><strong>Quotes stay theirs:</strong> where we quote a project describing itself, the words belong to that
project. We quote short excerpts so you can tell projects apart, and CC BY doesn't cover them. Every quote shows where
it came from and the date we copied it, because project descriptions change.</li>
<li><strong>Code:</strong> the scripts that build and check this site are under the
{link("MIT licence", "https://opensource.org/license/mit")}.</li>
</ul>

<h2 id="privacy">What we record about visitors</h2>
<p>We count page views from our own server logs. The logs don't record IP addresses, and we delete them after
30 days. What we keep after that is counts only: views per page per day, addresses that came back "not found" (so we
can fix broken links), and which websites linked to us. This site has no cookies, no trackers and no third-party
scripts. Requests pass through Cloudflare, which protects the server and handles traffic under its own privacy policy.</p>
</div>"""


STYLE_V = ""


def main():
    global STYLE_V
    import hashlib
    STYLE_V = hashlib.md5((SITE / "style.css").read_bytes()).hexdigest()[:8]
    site = load("site.json")
    projects = [json.loads(f.read_text()) for f in sorted((DATA / "projects").glob("*.json"))]
    shipped = []
    for f in sorted((DATA / "shipped").glob("*.json"), reverse=True):
        s = json.loads(f.read_text())
        s["_file"] = f.name
        shipped.append(s)
    roadmap, scams, lookalikes = load("roadmap.json"), load("scams.json"), load("lookalikes.json")
    act_file = DATA / "checks" / "repo_activity.json"
    activity = json.loads(act_file.read_text()) if act_file.exists() else {}
    errs = validate(site, projects, shipped, roadmap, scams, lookalikes)
    if errs:
        sys.exit("data errors:\n  " + "\n  ".join(errs))
    print(f"data ok: {len(projects)} projects, {len(shipped)} weekly logs, {len(roadmap)} roadmap items")
    if "--check" in sys.argv:
        return
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    pages = {
        "index": ("Home", p_home(site, projects, shipped), "A dated, sourced record of what's being built on Kaspa. No paid listings."),
        "ledger": ("The ledger", p_ledger(site, projects, activity), "Kaspa projects with status, last-verified date, evidence and audit status."),
        "shipped": ("What shipped", p_shipped(shipped), "A weekly, sourced log of what went live on Kaspa."),
        "roadmap": ("Roadmap", p_roadmap(roadmap), "Kaspa protocol features labelled live, targeted, research or unsupported."),
        "scams": ("Scams & graveyard", p_scams(scams, projects, site), "Kaspa phishing domains, impersonators and abandoned projects."),
        "kaspachat": ("KaspaChat", p_kaspachat(site, lookalikes), "KaspaChat by Kaspaguy, and how to tell it apart from Kasia and KaChat."),
        "trust": ("Our rules", p_trust(site), "How Kaspaguy sources entries, why there are no paid listings, and our conflict of interest."),
    }
    for slug, (title, body, desc) in pages.items():
        (DIST / f"{slug}.html").write_text(page(site, slug, title, body, desc))
    nf = page(site, "404", "Page not found", """<h1>Page not found</h1>
<p class="lead">There's nothing at this address. If a link on our site brought you here, tell us at """
              + e(site["corrections"]) + """ and we'll fix it.</p>
<p><a class="btn" href="/ledger">Open the ledger</a><a class="btn ghost" href="/">Home</a></p>""",
              "Page not found.", listed=False)
    (DIST / "404.html").write_text(nf)
    locs = "".join(f"<url><loc>{site['base_url']}{'/' if s == 'index' else '/' + s}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>"
                   for s in pages)
    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                      f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>\n')
    for f in SITE.iterdir():
        shutil.copy(f, DIST / f.name)
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site['base_url']}/sitemap.xml\n"
                                     if site.get("indexable") else "User-agent: *\nDisallow: /\n")
    print(f"wrote {len(pages)} pages to {DIST}")


if __name__ == "__main__":
    main()
