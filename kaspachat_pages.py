"""KaspaChat testnet pages, from data/kaspachat_testnet.md: the approved text (public_pages.md, sha256
ab69e364…, 2026-10-30). The markdown is kept as approved; this turns its small subset (headings, paragraphs, lists,
tables, bold, italics) into HTML."""
import html
import re
from pathlib import Path

e = html.escape
SRC = Path(__file__).parent / "data" / "kaspachat_testnet.md"

# section number in the approved file -> (slug, title, description)
PAGES = {
    "5": ("testnet", "KaspaChat testnet", "Start on the KaspaChat testnet in 60 seconds, and see whether it is running normally."),
    "1": ("testnet-privacy", "KaspaChat testnet privacy", "What KaspaChat collects during the testnet, why, and for how long."),
    "2": ("testnet-terms", "KaspaChat testnet terms", "The terms of the KaspaChat public testnet on Kaspa testnet-10."),
    "3": ("bounty", "KaspaChat bug bounty", "Real KAS for valid KaspaChat testnet bugs: severity, amounts and rules."),
    "4": ("group-rules", "KaspaChat group rules", "The rules of the KaspaChat Telegram group."),
}
LINKS = [("testnet", "Guide and status"), ("testnet-privacy", "Privacy"), ("testnet-terms", "Terms"),
         ("bounty", "Bug bounty"), ("group-rules", "Group rules")]

STATUS_JS = """<script>
var el = document.getElementById('kc-status');
fetch('/testnet-status.json', {cache: 'no-store'}).then(function (r) { return r.ok ? r.json() : null; }).then(function (s) {
  if (!s || !s.text) throw 0;
  el.textContent = s.text;
  el.className = 'kc-status ' + s.state;
}).catch(function () { el.textContent = 'The testnet status is unavailable right now.'; });
</script>"""


def inline(t):
    t = e(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", t)
    t = re.sub(r"\b([\w.-]+@kaspachat\.com)\b", r'<a href="mailto:\1">\1</a>', t)
    return t


def md(text):
    out, lines, i = [], text.strip("\n").split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip() or ln.strip() == "---":
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            head = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
            body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
            out.append(f'<div class="tablewrap"><table class="table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')
        elif re.match(r"(- |\d+\. )", ln):
            tag = "ol" if ln[0].isdigit() else "ul"
            items = []
            while i < len(lines) and (re.match(r"(- |\d+\. )", lines[i]) or (lines[i].startswith("  ") and items)):
                if lines[i].startswith("  "):
                    items[-1] += " " + lines[i].strip()
                else:
                    items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"(- |\d+\. |\||---)", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


def sections():
    parts = re.split(r"^## (\d)\. .*$", SRC.read_text(), flags=re.M)
    return {parts[k]: parts[k + 1] for k in range(1, len(parts), 2)}


def nav(slug):
    return '<p class="kc-links">' + " · ".join(
        f'<a href="/{s}"{" aria-current=page" if s == slug else ""}>{e(t)}</a>' for s, t in LINKS) + "</p>"


def pages():
    """slug -> (title, body, description)"""
    secs = sections()
    out = {}
    for num, (slug, title, desc) in PAGES.items():
        body = md(secs[num])
        if slug == "testnet":
            body = ('<p id="kc-status" class="kc-status">Checking the testnet status…</p>'
                    f'<h2>Testnet in 60 seconds</h2>{body}'
                    '<p><a class="btn" href="https://kaspachat.com/?src=kaspaguy">Get KaspaChat</a></p>' + STATUS_JS)
        out[slug] = (title, f'<div class="doc"><h1>{e(title)}</h1>{nav(slug)}{body}</div>', desc)
    return out
