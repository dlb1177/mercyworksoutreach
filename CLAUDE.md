# CLAUDE.md

This repo is the website for Mercy Works Outreach (mercyworksoutreach.org).

**Read `context.md` before every change.** It holds the organization's mission, its five core tenets, its formation status, and the rules for how the site is built.

Quick rules:
- Plain HTML and CSS only. No frameworks, no build step, no tracking or third-party scripts. The one exception: `tools/ledger.py` checks the books and writes the Financial Ledger page (see the Ledger section of `context.md`).
- Keep the Berkshire Hathaway–style look: simple, text-first, no frills.
- Use the brand kit's logo, colors and fonts as described in `context.md`. Fonts are served from `/fonts`, never from Google Fonts.
- Never claim 501(c)(3) status or tax-deductibility until `context.md` says the IRS determination letter has arrived.
- Never publish private data: bank account numbers, donor names without consent, or details of the people served.
- When a formation step is completed, update the status table in `context.md`.
- After each change, commit with a short, clear message and push to `main`. GitHub Pages deploys automatically.
