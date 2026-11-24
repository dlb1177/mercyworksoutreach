# CLAUDE.md

This repo is the website and the public books of Mercy Works Outreach (mercyworksoutreach.org), a volunteer-run Catholic ministry serving people experiencing homelessness in the Twin Cities.

**Read `context.md` before every change.** It is the full handover: the organization, the rules for the site, how documents are redacted, how the ledger and the Zeffy import work, everything that has been decided and why, what must never be done, and what is still open (section 9). This file is only the short version.

**Both this file and `context.md` are public** (the whole repo is served by GitHub Pages). Never write anything private in them.

## Working with Dylan

Dylan Brown, CPA, is the founder and treasurer. He is not a web developer. Explain in plain words, finish each request, say what you decided and why, and flag what he should check. He hands over documents and expects them redacted before anything is published.

## Commands

Run from the repo root. Python 3 standard library only; nothing to install.

```
python3 -m unittest tools/test_ledger.py tools/test_zeffy.py   all tests (25)
python3 tools/ledger.py check      check the books against all 13 rules; writes nothing
python3 tools/ledger.py build      check, then rewrite the pages under financials/ and inventory/
python3 tools/ledger.py summary    the books at a glance
python3 tools/zeffy.py status      what Zeffy still owes, and anything waiting on a person
```

After any change to a CSV under `financials/`, `inventory/` or `impact/`: `check`, then `build`, then look at the pages.

## What is not in the repo

`Books/` (private accounting records and donor names), `Formation_Docs/` (unredacted originals), `Document_Inbox/` (where documents arrive) and the brand kit exist only on Dylan's Mac and are git-ignored. Without `Books/`, `check` prints one warning about donor names. That is expected. Nothing else needs it.

## The daily Zeffy sync

A scheduled task reads Zeffy once a day, enters new online gifts and pushes to `main` by itself. If you are that run, follow `context.md` section 6, "The daily run, step by step", exactly and do nothing else. Otherwise: pull before you start, never enter an online gift by hand, and never edit `financials/zeffy-log.csv` by hand.

The PDF redaction scripts in `tools/mac/` need macOS. Elsewhere, use another tool that truly removes content and verify the same way (`context.md` section 4).

## Rules

- Plain HTML and CSS only. No frameworks, no JavaScript, no build step, no tracking, no third-party scripts, fonts or embeds. The one exception: `tools/ledger.py` writes the pages under `financials/` and `inventory/`. Never edit those pages by hand.
- Keep the Berkshire Hathaway–style look: simple, text-first, no frills. Use the brand colors and the self-hosted fonts in `/fonts`. Never load Google Fonts.
- **Never claim 501(c)(3) status, tax-exempt status or tax-deductibility** until `context.md` says the IRS determination letter has arrived.
- **Never write a donor's name, email address or home address to any file.** Donor details live in Zeffy only.
- **Never commit or publish private data:** originals of redacted documents, bank account numbers, donor names without consent, home addresses, personal emails or phone numbers, or anything identifying the people served.
- **Never name a director or officer in the financial files or pages.** Use "Donor" or "Director".
- **Redaction must remove the content, not cover it,** and must be verified before committing.
- Publish only signed documents as executed. Check the signatures yourself.
- Never link to or mention the GitHub history on the site.
- Never edit a ledger row in a closed month, reuse an id, or force a balance. Enter rows with `ledger.add_rows()`.
- Never change or remove a row of the inventory log (`inventory/inventory-log.csv`) unless Dylan asks. Stock is given out as kits: packing and giving out are new rows (`context.md` section 5).
- Never add a donate button, a ledger category or a menu item unless Dylan asks.
- Never rewrite git history or force-push unless Dylan asks.
- The full list is `context.md` section 8.

## Finishing a change

1. Update `context.md` if a fact, rule or status changed. When a formation step is completed, update its status table.
2. Commit with a short, clear message that says what changed.
3. Push to `main`. GitHub Pages deploys automatically in about a minute; `context.md` section 7 says how to confirm it.
