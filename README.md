# Kaspaguy hub

Source for kaspaguy.com: a dated, sourced record of what's being built on Kaspa, plus the KaspaChat page.
The site is static and built from the JSON in `data/`. Updating it means making a commit. There is no CMS and no login.

## Layout

| Path | What it holds |
|---|---|
| `data/site.json` | Site settings: staging flag, contact, policy version, staleness thresholds, ledger categories |
| `data/projects/<id>.json` | One ledger entry per project (see the fields below) |
| `data/shipped/<YYYY-MM-DD>.json` | One weekly "what shipped" log, named for the week's last day |
| `data/roadmap.json` | Protocol features labelled live / targeted / research / unsupported |
| `data/scams.json` | Phishing domains and impersonation reports |
| `data/lookalikes.json` | The "which one is this?" table on the KaspaChat page |
| `site/` | Static assets copied as-is (style.css, icon.svg) |
| `build.py` | Validates `data/` and writes `dist/` |
| `scripts/check_staleness.py` | Lists overdue entries and quiet or archived GitHub repos |

## Workflow

```
python3 build.py --check          # validate before every commit
python3 build.py                  # write dist/
rsync -a --delete dist/ /var/www/kaspaguy-site/
python3 scripts/check_staleness.py
```

## Ledger entry fields

- `status` is one of `idea`, `testnet`, `mainnet` or `abandoned`. The evidence each one needs is defined on /trust.
- `self_claimed` must be `true` when the only backing is the builders' own word. The build refuses `false` when no
  evidence link is public.
- `last_verified` is the date someone opened the evidence. It is not the date of the commit.
- `evidence` is a list of `{label, url, public, note}`. At least one is required.
- `repos` lists GitHub repos for the staleness check, as `https://github.com/owner/name`.
- `code`, `audit`, `kcc`, `token` and `conflict`: see `data/projects/kaspachat.json`.

Every external link must be https. Dates can't be in the future. Every weekly-log item and every roadmap item needs a
source. The build stops on any of these errors.

## Rules

The public rules are on /trust (`p_trust` in build.py). Any change to them bumps `policy_version` and `policy_date` in
`data/site.json`.
