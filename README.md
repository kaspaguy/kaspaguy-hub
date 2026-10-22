# Kaspaguy hub

Source for kaspaguy.com: a dated, sourced record of what's being built on Kaspa, plus the KaspaChat page.
The site is static and built from the JSON in `data/`. Updating it means making a commit. There is no CMS and no login.

## Layout

| Path | What it holds |
|---|---|
| `data/site.json` | Site settings: staging flag (banner), indexable flag (search engines), contact, policy version, staleness thresholds, ledger categories |
| `data/projects/<id>.json` | One ledger entry per project (see the fields below) |
| `data/shipped/<YYYY-MM-DD>.json` | One weekly "what shipped" log, named for the week's last day |
| `data/roadmap.json` | Protocol features labelled live / targeted / research / unsupported |
| `data/scams.json` | Phishing domains and impersonation reports |
| `data/lookalikes.json` | The "which one is this?" table on the KaspaChat page |
| `site/` | Static assets copied as-is (style.css, icon.svg) |
| `build.py` | Validates `data/` and writes `dist/` |
| `scripts/check_staleness.py` | Lists overdue verifications (action) and quiet repos (information); writes `data/checks/repo_activity.json` |
| `scripts/pageviews.py` | Daily page-view counts from the IP-free nginx log (runs from cron on the server) |
| `assets-src/og.html` | Source of `site/og.png`, the 1200×630 social preview image |
| `scripts/find_payload_txs.py` | Scans our own mainnet node for transactions carrying a project's payload marker |

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
- `relationship` is `self`, `competitor` or `none`, and is shown as a label on the card.
- `related` is a list of `{id, note}` saying how this entry relates to another entry, such as a shared message format.
- `evidence_caveat` is optional. It is shown first on the card, for evidence that proves less than it seems to.

Only `last_verified` changes a card's colour. Code activity in `data/checks/repo_activity.json`, written by
`scripts/check_staleness.py`, is shown as information and never as a warning.

`data/scams.json` has three sections: `confirmed`, `unverified` and `label`. Every item needs `name`, `what`, `added`
and dated `sources`. A `confirmed` item needs at least one source marked `third_party: true`, and an `unverified` item
needs an `unknown` line. An optional `state` (`offline` or `online`) with `state_checked` shows in the item's title.

Weekly logs in `data/shipped/` are named by the Sunday the week ends. The current week can be published early with
`in_progress: true` and an `updated` date. A week written up after it ended carries `compiled`, its write-up date.

Every external link must be https. Dates can't be in the future. Every weekly-log item and every roadmap item needs a
source. The build stops on any of these errors.

## Licences

Data in `data/` and the site text: CC BY 4.0 (`LICENSE-DATA.md`). Quoted project descriptions are not covered and
belong to their authors; each needs `says_source` and `says_date`. Code (`build.py`, `scripts/`): MIT (`LICENSE`).

## Rules

The public rules are on /trust (`p_trust` in build.py). Any change to them bumps `policy_version` and `policy_date` in
`data/site.json`.
