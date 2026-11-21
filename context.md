# Mercy Works Outreach — Project Context

Read this before making any change to this repo. It is written so that a session that can see only the repo can pick the work up: what the organization is, how the site and the books are built, what has been decided and why, what must never be done, and what is still open.

> **This file is public.** The repo is public (GitHub Pages on a free account requires it), so this file is readable by anyone, including at `mercyworksoutreach.org/context.md`. Never put anything private here: no personal phone numbers, home addresses, personal email addresses or bank details, and nothing about other people that they have not agreed to publish.

**Contents:** 0. Start here · 1. The organization · 2. The five tenets · 3. The website · 4. Publishing documents and redaction · 5. The books · 6. Zeffy (online gifts) · 7. Hosting and deploy · 8. Never do · 9. In progress and undecided

---

## 0. Start here

**Who you are working for.** Dylan Brown, CPA, is the founder, a director, and the secretary and treasurer. He is an accountant, not a web developer: explain things in plain words, say what you decided and why, and flag anything he should check. John Mark Reimann ("JM") is the co-founder and president; where his wording for the site differs from Dylan's, his takes priority.

**How Dylan works.** He sends short requests, usually one change at a time, and expects each to be finished, committed and pushed. He hands over documents and expects them to be read for private details and redacted before anything is published, without being asked each time. He would rather be told about a problem than have it quietly worked around. If a document he calls "signed" is not signed, do not publish it; say so.

**What is in this repo and what is not.** Everything the public site serves is here. These folders exist only on Dylan's Mac, are git-ignored, and are **not visible to a session that sees only the repo**:

| Folder | What it holds | What that means without it |
|---|---|---|
| `Books/` | Private accounting records: original bank statements and receipts, `donors.csv` (who gave what), `zeffy-log.csv`, the Zeffy exports, donor acknowledgment letters | The donor-name check only warns. **The Zeffy import and payout commands refuse to run** (see section 6). Donor records cannot be updated. |
| `Formation_Docs/` | Unredacted originals of every published document, the ledger spec PDF | Published copies are the only copies you can see. Never try to "restore" redacted text. |
| `Document_Inbox/` | Where Dylan drops documents to be added | Documents will reach you some other way. See section 9, first item. |
| `MercyWorksOutreach_BrandKit/` | The brand kit | Its rules are written out in section 3; the logo, icons and fonts are already in the repo. |

**First commands** (all from the repo root; Python 3 standard library only, nothing to install):
```
python3 -m unittest tools/test_ledger.py tools/test_zeffy.py    18 tests, should all pass
python3 tools/ledger.py check                                    should print "check passed"
python3 tools/ledger.py summary                                  the books at a glance
```
Without `Books/`, `check` also prints one warning that donor names could not be checked against opt-ins. That is expected.

**After every change:** update this file if a fact, rule or status changed; commit with a short, clear message; push to `main`. GitHub Pages deploys by itself (section 7).

---

## 1. The organization

- **Name:** Mercy Works Outreach (decided Nov 18, 2026). It replaces the earlier working name "Face of Jesus Ministry."
- **What it is:** an independent, volunteer-run ministry rooted in the Catholic faith, serving people experiencing homelessness in the Twin Cities (Minneapolis, Minnesota and the surrounding area).
- **Legal form:** a Minnesota nonprofit corporation, incorporated Nov 18, 2026 (file number 1691131200023). Dylan Brown CPA LLC was the sole incorporator.
- **Public address and EIN (in the footer of every page):** 323 Washington Ave N, Ste 200, Minneapolis, MN 55401 (the registered office). EIN 43-3046884.
- **Public contact:** info@mercyworksoutreach.org. It is handled by Cloudflare Email Routing and forwarded to the directors; the forwarding addresses are not recorded here. There is **no phone number**: the ministry is volunteer-run, and email and mail go to a shared office rather than to one person.
- **Bank:** one checking account at Sunrise Banks, opened Nov 20, 2026. Online gifts are taken through Zeffy (section 6).

### Purpose (bylaws Section 1.3, summarized)
The main work is giving out food, clothing, blankets and hygiene items to people in need. Volunteers also offer prayer, Bibles and devotional materials to anyone who wants them. The draft bylaws word the purpose a little more broadly than today's work, to leave room to grow later.

### How an outreach morning runs (from the published minutes)
Volunteers attend 7:00 a.m. Mass with the Missionaries of Charity at their convent, make sandwiches, then drive out to distribute food and supplies, finishing by about 10:00 a.m. The work began in August 2025, before the organization existed.

### Governance
- **Directors (since Nov 19, 2026):** John Mark Reimann, Dylan Brown and Amara Miller. Draft bylaws: 3 to 7 directors, staggered two-year terms, a majority not related to each other.
- **Officers (elected Nov 19, 2026):** John Mark Reimann, president; Dylan Brown, secretary and treasurer. One person may be both secretary and treasurer, but the president cannot be the treasurer.
- **Money safeguards**, adopted as board policy in the written action authorizing the bank account (Nov 19, 2026): any payment over $500 needs both signers; no one approves a payment to themselves, a relative or their own business; the president reviews and initials the bank statement each month; any director may see the records.
- **Bylaws and a conflict-of-interest policy are drafted but not yet adopted.**

### Formation status (as of Nov 21, 2026)
| # | Step | Status |
|---|------|--------|
| 1 | Choose a name | ✅ Done |
| 2 | File Articles of Incorporation with the MN Secretary of State ($90) | ✅ Filed Nov 18, 2026 |
| 3 | Get an EIN from the IRS | ✅ Assigned Nov 18, 2026 |
| 4 | Choose the board of directors | ✅ Done: three initial directors |
| 5 | Incorporator's written action electing the board | ✅ Signed by the incorporator and all three directors Nov 19, 2026; published |
| 6 | Organize the board: adopt bylaws and a conflict-of-interest policy, elect officers, approve a bank account | ⏳ An introductory meeting was held Nov 19, 2026 (no votes); officers were elected and the bank account authorized by written actions the same day. **Still to do: adopt the bylaws and the conflict-of-interest policy** |
| 7 | Open a bank account | ✅ Opened at Sunrise Banks Nov 20, 2026, with a $100.00 deposit |
| 8 | Apply for 501(c)(3) recognition on IRS Form 1023-EZ ($275) | ✅ Filed Nov 19, 2026. ⏳ **Waiting for the IRS determination letter** |
| 9 | Minnesota Attorney General, and Minnesota sales tax exemption | Attorney General: ✅ the Charitable Organization Exemption Form (used in place of registration while yearly contributions stay under $25,000) was emailed Nov 21, 2026 with a financial statement. The organization must tell the Attorney General if it stops qualifying. **Sales tax exemption: not yet applied for** |
| 10 | Get insurance quotes | ⏳ Not yet |

Update this table whenever a step is completed.

### The tax-status rule
Until this file says the IRS determination letter has arrived, the site must **not** say the organization is a 501(c)(3), tax-exempt, or that gifts are tax-deductible. "Incorporated" and "Minnesota nonprofit corporation" are accurate. The Minnesota "exemption" form is about charity registration, not taxes; never let that word be read as tax-exempt status.

---

## 2. The five core tenets (in Dylan's words, lightly condensed)

In priority order, most important first. The site lists them in this order. The rules for the site and the books follow from them.

1. **Fearless without being careless.** Never let fear get in the way of serving people directly. Approach every person the way Jesus would: get down to their level, don't be afraid to touch them or talk with them closely, and treat them with dignity, one to one, like a member of your own family. Always stay aware of your surroundings and put safety first.
2. **Focused on the core mission.** Do exactly what Section 1.3 of the bylaws says and nothing more. Expand only if every corner of Minneapolis and the surrounding area has been served as fully as possible, which is unlikely.
3. **Highly efficient.** No money goes to fundraising, advertising or administration beyond the essentials. Choose simple systems over complex ones. Learn from the Missionaries of Charity's careful use of resources.
4. **100% volunteer-run.** Zero payroll, ever. The limit keeps the ministry small and personal.
5. **Radical transparency.** Outsiders can see the formation documents, the minutes, and every single transaction, down to the penny. That is far more than nonprofits must disclose.

**Design inspiration:** Warren Buffett's Berkshire Hathaway website: no frills, text first, with links to every past document. Take that model with a slightly updated design.

---

## 3. The website

### Rules
- **Plain HTML and CSS only.** No frameworks, no build step, no npm, no static-site generator. Every page is a hand-editable `.html` file. Why: tenet 3, simple over complex. **One exception:** `tools/ledger.py` writes the pages under `financials/` and `inventory/`, and that output is committed, so GitHub Pages still serves plain static files. Never edit those generated pages by hand (each says so in a comment at the top).
- **No JavaScript** unless a feature truly cannot work without it. There is none today.
- **No tracking, analytics, cookies, ads, pop-ups, or third-party scripts, fonts or embeds.** A plain link to another site is fine. This is why the fonts are self-hosted and the map is a static image.
- **Free hosting only:** GitHub Pages. No paid services.
- **Honest copy:** short, factual, warm. No marketing language and nothing that is not true yet.
- **Accessible and fast:** semantic HTML, good contrast, works on phones, light-only (no dark mode). Check a change at a desktop width and at about 390 px.

### Brand (brand kit v1, November 2026)
- **Logo:** the "I Thirst" cup with a drop of water. `/logo.svg` is the stacked full-color version. At least 150 px wide with clear space; never recolor, stretch or add effects.
- **Colors:** Mercy Blue `#2A5599` (logo, links), Deep Blue `#1D3F75` (headings, hover), Water Blue `#7FA3D6` (thin rules and accents only, never text), Slate `#5B6472` (secondary text), Mist `#EEF3F9` (light panels), White (most of every page). They are CSS variables at the top of `style.css`.
- **Type:** EB Garamond Medium for headings; EB Garamond Regular for the tagline, the vision statement, the prayer and titles on the board page; Source Sans 3 Regular for body and SemiBold for small uppercase labels. Served from `/fonts` with their licenses. **Never load fonts from Google Fonts.**
- **One plain 6 px band of Mercy Blue across the top of every page.** Keep it a single solid band. JM suggested a border like the blue and white stripes of the Missionaries of Charity saris; it was not built because that three-stripe border is their registered trademark and this ministry is not affiliated with them. Revisit only with their written permission.
- **Mother Teresa:** never pair the logo with her name or image, and never use her image. At Dylan's direction the home page's Inspiration section names the Missionaries of Charity and "St. Teresa of Calcutta" (JM's preferred form; spelled Teresa, not Theresa) and quotes one of her prayers, opening with "Mercy Works Outreach is not affiliated with the Missionaries of Charity." Keep that sentence, and keep her name out of the masthead, footer and logo lockups.

### Pages
```
/index.html                 Home
/info/index.html            Info: the hub page that links to everything else
/contact/index.html         Contact, with contact/map.jpg
/support/index.html         Support
/board/index.html           Current Board Leadership           (opened from Info)
/board-actions/index.html   Board Actions and Meeting Minutes  (opened from Info)
/tax-documents/index.html   Tax Documents                      (opened from Info)
/financials/                Financial Ledger and the books     (opened from Info; generated, section 5)
/inventory/                 Inventory and Stock Log            (opened from Info; generated, section 5)
/links/index.html           Only forwards the old /links/ address to /info/
/documents/index.html       Only forwards the old /documents/ address to /info/
/documents/                 Published PDFs: articles-of-incorporation.pdf, board-actions/, tax/, volunteer/
/impact/distribution-log.csv   One row per outreach (no page yet)
/style.css                  The one stylesheet shared by every page
/logo.svg, /fonts/, favicons, site.webmanifest, open-graph-share-image-1200x630.png
/tools/                     ledger.py, zeffy.py, their tests and fixtures, and mac/ (helper scripts)
```
**To add a page:** copy an existing one of the same kind (for a list page, `tax-documents/index.html`) and keep its `<head>`, masthead and footer exactly. Every page has the same masthead (logo, tagline, menu) and the same full-width Mist footer with the name, "A Minnesota nonprofit corporation · EIN 43-3046884", the address and the copyright line.

**Menu on every page:** Home, Info, Contact, Support. "Support" is a solid blue pill to set it apart. The current page's item has `aria-current="page"`; on pages opened from Info, the Info item has `aria-current="true"` (both are underlined). The ledger spec asked for a "Financials" menu item; Dylan chose to reach the ledger from Info instead, so the menu stays at four items. "Info" was called "Links" until Nov 20, 2026.

**Tagline:** "Called to Love. Sent to Serve." under the logo on every page. JM proposed it as a trial, so it may change.

**Which links open in a new tab (Dylan, Nov 19, 2026):** links to documents (PDFs) and to other websites carry `target="_blank" rel="noopener"`. Links to other pages of this site, the menu, the logo and `mailto:` links stay in the same tab.

**Placeholders** are plain text marked "Coming" (`<span class="pending">` with `<span class="meta">Coming</span>`), never dead links. When the thing exists, turn the placeholder into a link.

#### Home
- Opens with one statement, centered in a Mist panel like the prayer: "Mercy Works Outreach is an independent, volunteer-run ministry rooted in the Catholic faith, serving people experiencing homelessness in the Twin Cities. We provide food, clothing, blankets, and hygiene items, free of charge, to one person at a time."
- Say **"Catholic," not "Christian."** In lists of what is given, **food comes first**. (The Articles say "Christian faith"; that is the legal text and stays as filed.)
- "What we do" carries JM's vision as a pull-quote: the ministry is not seeking to solve homelessness; it dignifies each person by name, with a momentary break from hunger, thirst and cold, and from despair, invisibility and hopelessness.
- "What we hold to" lists the five tenets with JM's edits. Tenet 2 links to the Articles of Incorporation. Tenet 3 says administration is limited to "the essentials, such as the fees the law requires, insurance and the small cost of this website" (JM asked how insurance and web fees fit "only the fees the law requires"). Tenet 5 links "every transaction, down to the penny" to `/financials/`. Tenet 1 no longer has a sentence about fear and safety; JM removed it (see section 9).
- "Inspiration" explains the cup (John 19:28, Matthew 25:35), the not-affiliated statement, and the prayer.
- The city is not repeated under the logo; the address is in the footer. The home page does not show the formation checklist.

#### Info
No visible page heading (a visually hidden `<h1>`); it opens with the "New and still forming" notice (an inline SVG warning triangle in Mercy Blue, not an emoji). Then four sections, in this order:
1. **Impact:** Impact Updates and Newsletters, both placeholders, with a note that updates will give basic data on goods delivered and people served.
2. **Volunteer Resources:** Orientation Video (placeholder); Volunteer Sign-Up and Volunteer Schedule, which both link to a **legacy SignUpGenius page** that predates the organization; What a Volunteer Day Looks Like (placeholder); Participant Waiver (placeholder); Distribution Log Form (a fillable PDF, section 5). Keep the note saying the SignUpGenius volunteers are not affiliated with Mercy Works Outreach until those links are replaced with the organization's own sign-up.
3. **Finance:** Financial Ledger, Inventory, Quarterly Financial Reports (placeholder), Tax Documents.
4. **Governance** (called "Documents" until Nov 20, 2026): Articles of Incorporation, Bylaws (placeholder), Guiding Principles (placeholder), Organization Policies (placeholder), Current Board Leadership, Board Actions and Meeting Minutes. Names only, no descriptions.

#### Contact
Email and mailing address only, with a sentence that there is no phone number and that both go to a shared office. The map is a static image made once from OpenStreetMap tiles with a pin at the office, so no map service loads on the site. Keep the "© OpenStreetMap contributors" credit under it. Never embed Google Maps or any live map; the plain link to Google Maps is fine.

#### Support
Everything is "coming soon": a panel saying gifts can't be accepted yet, a "Non-Monetary Donations" list to come, and a placeholder for a video for donors. **No donate button** until Dylan asks for one (the ledger spec says not before the bank account is open and the determination letter has arrived). When real ways to give are added, follow the tax-status rule. See section 9: the Zeffy form is live but this page does not link to it yet.

#### Current Board Leadership
Kept very basic: one sentence, then one list of the directors with no separate officers section. Each name is in the heading face (EB Garamond Medium, Deep Blue) with a title under it in the tagline's face (EB Garamond Regular, Slate): the officer's role, or "Director". Names and roles only.

#### Board Actions and Meeting Minutes
One row per written action or set of minutes, in date order with the **oldest first**, each with the date of the meeting or the date the action took effect. Only signed documents are published. A document that is out for signature is listed by name without a link, marked "Pending signatures". Published, all dated Nov 19, 2026: Minutes of the Introductory Meeting of the Initial Directors; Written Action of the Sole Incorporator; Unanimous Written Action: Election of Officers; Unanimous Written Action: Authorization of Bank Account.

#### Tax Documents
One row per filing with the IRS or the State of Minnesota, oldest first, with the date filed. Published: Form 1023-EZ (filed Nov 19, 2026) and the Minnesota Charitable Organization Exemption Form (filed Nov 21, 2026). Placeholder: Annual Tax Returns. The Minnesota form is not a tax filing; it is here because this is the one page for government filings, and the note under the list says so. The notes also say the 1023-EZ has not been decided. When the determination letter arrives: publish it here, update that note, the formation table and the tax-status rule. Link each year's Form 990-N confirmation here once filed.

---

## 4. Publishing documents and redaction

- **Read every document for private details before publishing it.** Publish only a redacted copy; the original is never committed.
- **Only signed documents are published as executed.** Check the signature lines yourself. A file can be called "signed" and not be.
- **File names:** lowercase, hyphenated, `YYYY-MM-DD-short-title.pdf`, in `documents/board-actions/`, `documents/tax/` or `documents/volunteer/`. Receipts and statements have their own naming (section 5).
- **A filing is published as one file showing what was actually sent,** in the order sent (for the Minnesota form: the cover email, the signed form with its signing record, and the financial statement).

### What to remove
| Kind of document | Remove | Keep |
|---|---|---|
| Any | Home addresses; personal email addresses; personal phone and fax numbers | The organization's own address, EIN and info@ address; names and titles of directors and officers |
| E-signature audit pages (Adobe Acrobat Sign) | Every signer's and sender's email address | Names, timestamps, the transaction id |
| Emails Dylan sent for the organization | His firm email address and the phone number in his signature (the site says the organization has no phone) | His name, title, firm name and license numbers |
| Receipts | The payer's name, address, email and phone; card numbers except the last 4; loyalty numbers | Vendor (including the vendor's own address and email), date, items, tax, total |
| Bank statements | Full account and routing numbers; donor names in deposit lines; home addresses | Last 4 of the account, dates, amounts, balances, the president's initials |
| Donor acknowledgment letters | Never published | |

**In anything about money, a director is never named.** See "No names" in section 5.

### How to redact
**Redaction must remove the content, not cover it.** A black box drawn over text leaves the text selectable underneath. The method used so far:
1. Flatten every page that needs a redaction to an image, with black boxes drawn over the private parts. Pages that need nothing are copied as they are.
2. Write the result as a fresh PDF, so the original's metadata and form data do not come along.
3. **A phone scan or photo carries hidden camera data even when nothing printed on it is private. Flatten it too.**
4. Verify, every time: extract the text of the result and confirm none of the removed values can be found; search the raw bytes for them as well; then open the result and look at every page.

The scripts that do this are in `tools/mac/` and **run only on macOS** (they use Apple's PDFKit through Swift): `redact.swift` (black out strings, or boxes with `rect:PAGE:X,Y,W,H` when text wraps across lines; `ALLOW_AT=1` when a vendor's or agency's email address must stay), `pages.swift` (render pages to PNG for a look), `join.swift` (join redacted PDFs or chosen pages into one). Each file's first lines say how to build and run it. **On another system, use whatever tool is available that truly removes content, and do the same four steps.** Do not use PDFKit to add form fields to a PDF: it leaves out the form dictionary that Adobe Reader needs.

### Already published, with what was removed
- **Form 1023-EZ:** the three directors' home street addresses and the contact phone and fax numbers.
- **The three written actions and the Minnesota form:** all email addresses on the signing records; on the Minnesota filing also Dylan's firm email and signature phone number.
- **Opening receipts and the donated-goods invoice:** the payer's name, address, phone and email.
- **The minutes** were published as given. They name one person who is not a director and give a director's background (see section 9).
- The IRS EIN letter is **not** published (removed at Dylan's request); the EIN is in the footer instead.

---

## 5. The books

Built Nov 20, 2026 from Dylan's "Ledger & Accounting Spec (for Claude Code)", then changed at his direction. Where the two differ, the decisions below win. The rules are also written at the top of `tools/ledger.py` and `tools/zeffy.py`.

**What it is.** A public ledger that is itself the organization's books. There is no accounting software. One general ledger file is the book of record, git history is the audit trail, and `tools/ledger.py` checks the numbers and writes the pages. This carries out tenet 5.

### Decisions, and why
- **Cash basis, calendar year.** One checking account, one debit card; all cash deposited intact; no petty cash.
- **One cumulative general ledger** (`financials/general-ledger.csv`), every transaction since inception. Dylan does not want it broken into a file per year, as the spec first had it. The summary page still shows one year at a time.
- **The balance moves on every row.** It is all funds: cash in the bank plus online gifts Zeffy has not paid out. A bill a donor paid directly raises it and the matching expense lowers it again. (The spec first had such rows leave the balance unchanged; Dylan asked for this instead, knowing the balance is then not the bank balance mid-pair.) "Cash in the bank" on the page is worked out from the `bank` rows alone.
- **Ids are permanent and rows stay in date order.** A row gets the next unused number for its year when it is entered (`2026-008`) and keeps it forever; ids are never reused. A row entered late goes in at its date, so ids do not always run in order down the file, and the balances after it are worked out again. Why: gifts and bank rows arrive at different times, and renumbering would break receipt file names and references.
- **No names in the public books (Dylan, Nov 20, 2026).** A gift from a director is shown as "Donor". Any other mention of a director or officer, such as a payment to one, is "Director". Other donors are "Individual donor", "Foundation", "Church" or "Government" unless they have asked to be named (`public_name_ok = yes` in the private donor record). The script fails if a director's name appears in a public CSV or page, and receipts are redacted to match.
- **Goods are not cash.** Donated goods stay out of the general ledger, in the gift log, valued when given (for new goods, the price the donor paid before sales tax). Goods someone bought personally and then handed over are a gift of goods on the handover date, not a paid-directly pair. Donated goods count with cash toward the Form 990-N and Attorney General warnings (Claude's reading of those rules; Dylan has not confirmed it).
- **A stock log, built like the money ledger.** Everything received traces to a gift-log line or a ledger purchase; everything given out traces to an outreach in the distribution log. Counted in units, from a short fixed item list. Never publish where stock is kept or who received what.
- **The $395.90 of formation fees** a director paid before the bank account existed is recorded as contributions (paid directly), not as reimbursements.
- **Salaries and fundraising** are both shown on the summary page, and both are expected to read $0.00.
- **The category list is fixed.** Adding a category is a change Dylan approves. `Transfers` was added Nov 21, 2026 for Zeffy payouts.

### Files
```
financials/general-ledger.csv     book of record: id, date, category, counterparty, description, amount,
                                  method, balance, receipt, ref, approval
financials/categories.csv         category, kind (in | out | transfer), form_990_function
financials/reconciliations.csv    one row per closed month: month, statement_ending_balance,
                                  president_reviewed_on, statement_file
financials/receipts/YYYY/<id>.pdf     redacted receipt, named by ledger id
financials/statements/YYYY-MM.pdf     redacted bank statement initialed by the president (none yet)
financials/donated-goods.csv      the gift log: id (G2026-001), date, description, quantity, estimated_value,
                                  valuation_basis, donor_type, document
financials/donated-goods/<id>.pdf     redacted support for a gift, named by its first line's id
inventory/items.csv               item, unit, category
inventory/stock-log.csv           id (S2026-001), date, item, type (received | distributed | adjustment),
                                  quantity, on_hand, ref, note
impact/distribution-log.csv       one row per outreach: date, area, volunteers, people_served_estimate, items
                                  (area is a general neighborhood, never an exact place; never names or photos)
documents/volunteer/distribution-log.pdf   the fillable form volunteers complete after each outreach

Generated by tools/ledger.py build; never edit by hand:
financials/index.html             Financial Ledger: summary of the latest year
financials/YYYY.html              the same summary for each year
financials/ledger.html            General Ledger: every transaction, newest month first
financials/donated-goods.html     Donated Goods: every gift of goods
inventory/index.html              Inventory: received, given out and on hand for each item
inventory/log.html                Stock Log: every movement
```
Always read and write the CSV files with Python's `csv` module (some text contains commas).

### The ledger columns
- `amount`: positive is money in, negative is money out, two decimals, never 0.
- `method`: `bank` (on the bank statement), `paid-directly` (someone paid the organization's bill with their own money and does not want it back), or `zeffy` (given online, not yet paid out; section 6).
- `receipt`: required on every spending row, as `receipts/YYYY/<id>.pdf`. A money-in row may carry one too, such as a bank deposit receipt.
- `ref`: links the second row of a pair to the first, or a correction to the row it reverses.
- `approval`: required on any payment over $500.00 and any payment to a director or officer (counterparty "Director"); it names the approval, such as "Written action 2027-02-03".
- **A paid-directly gift is two rows on the same date:** a Contributions row for +X, then the expense for −X with `ref` set to the contribution's id, both `paid-directly`.
- **Reimbursements are discouraged.** If the board approves one, the bank payment is categorized as the underlying expense, with the original receipt and the approval of two disinterested directors.
- **Closed months are append-only.** A mistake in a closed month is fixed with a row that reverses it (`ref` to the wrong row, description starting "Reverses") plus a correct row. Rows in a month that is not closed may be edited normally. A balance that does not tie is found and fixed, never forced with a plug row.

### The script
```
python3 tools/ledger.py check       run all 13 rules; write nothing; exit 1 if any problem
python3 tools/ledger.py build       check, then write the six kinds of page above (refuses if check fails)
python3 tools/ledger.py build --receipts-pending    as build, but a receipt not yet published shows "Pending"
python3 tools/ledger.py summary [YYYY]    year-to-date totals, the payout receivable, stock on hand, warnings
python3 tools/ledger.py support     public support percentage; reads Books/donors.csv; prints only, writes nothing
```
`check` prints each problem with its file, its row, the rule number and a plain fix. The rules:

| # | Rule |
|---|---|
| 1 | Header and format: exact columns in order, real ISO dates, two-decimal amounts, valid method |
| 2 | Ids: `YYYY-NNN` with the year of the row's date; unique; within a year the numbers run 001 to n with no gaps |
| 3 | Dates never earlier than the row above |
| 4 | Category exists; "in" is positive and "out" negative, except on a correction |
| 5 | Each balance is the balance above plus the amount, starting from 0.00 |
| 6 | Pairs: every paid-directly expense matches a paid-directly contribution; every Zeffy payout is a matched pair of Transfers rows; Zeffy never pays out more than was given |
| 7 | Every spending row has its receipt file; every file under `receipts/` and `donated-goods/` belongs to a row |
| 8 | Approval on payments over $500.00 and payments to a director or officer |
| 9 | Each closed month's bank rows add up to the statement balance; the president's review date is filled; the statement file exists; no month is skipped |
| 10 | Privacy: no email addresses, phone numbers, runs of 9 or more digits, or directors' names in the public CSVs and generated pages; a donor is named only if opted in |
| 11 | Nothing under `Books/`, `Document_Inbox/` or `Formation_Docs/` is tracked by git, and `.gitignore` lists all three |
| 12 | Stock log: ids, dates, items and types valid; received positive, distributed negative; each on-hand count adds up and never goes below zero; an adjustment has a note |
| 13 | Stock links: goods received trace to a gift or a ledger purchase and add up to the quantity given; goods distributed trace to an outreach on that date |

Warnings (printed, do not fail): contributions over $20,000 in a year (Attorney General registration is required within 30 days of passing $25,000); gross receipts over $40,000 (Form 990-N is for $50,000 or less); any Fundraising row; `Books/donors.csv` not on this machine.

**Keep the `INSIDERS` list at the top of `tools/ledger.py` current** when the board changes. It is what the name check uses.

**To enter rows, call `ledger.add_rows(root, [...])`** rather than appending by hand. It gives each row its id, puts it at its date, works out every balance again, and refuses a date in a closed month. Its docstring shows the row format (`receipt: "auto"`, `ref: "@0"` for the first row of the batch).

### Tests
```
python3 -m unittest tools/test_ledger.py tools/test_zeffy.py
```
`tools/fixtures/clean/` is a small made-up set of books (all dated 2030, with invented names) that passes every rule. Each folder in `tools/fixtures/broken/` holds only the files that differ from the clean set (and `remove.txt` lists files to delete), and breaks exactly one rule; its name starts with that rule's number. One test runs every broken fixture and requires that it breaks only its own rule, so a new check must not make an old fixture fail a second rule. **When you add a rule, add a broken fixture for it.** The Zeffy tests write their own small made-up export.

### The pages
- The Financial Ledger page is a summary: the year at a glance (Received, Spent, Cash in the bank, Share spent on programs, Paid in salaries, Spent on fundraising), a line for online gifts on their way to the bank, totals by category, a link to the General Ledger, the monthly bank check, donated goods, and downloads (General Ledger, Monthly Bank Checks, Donated Goods Log).
- The transactions are on their own page so the summary stays short (Dylan chose a separate page over a collapsible section).
- "Share spent on programs" is program spending divided by all spending. It reads 0% now because the formation fees are the only costs so far.
- **Removed at Dylan's request, do not add back:** a "How to read this page" section; a link labeled "Every change to these books" to the GitHub history; a download of the category list; a note that the bank account was not open.
- **Never link to or mention the GitHub history anywhere on the site.**
- Short footnotes under the General Ledger explain "Paid directly by donor" and "Given online". Dylan has seen them and has not objected.

### The Distribution Log form, and stock
- The form is one page, fillable, and deliberately generic: it lists no stock items, so it never changes when the inventory does. Volunteers fill one in after each outreach and Dylan passes it on.
- **When a filled form arrives:** add one row to `impact/distribution-log.csv`; add one `distributed` row to the stock log for each item on the form that is a stock item (match the volunteer's wording to `inventory/items.csv`; ask Dylan if a match is unclear). Things that are not stock items, such as sandwiches made that morning, go only in the distribution log's `items` text. Then `check` and `build`. The filled form itself is not published.
- **When goods arrive:** a gift gets one gift-log line per kind of item and a `received` row in the stock log; a purchase gets its ledger row and a `received` row pointing to it. Add a new kind of item to `inventory/items.csv` first.
- A count that differs from the book is an `adjustment` row with a note. Never edit old rows to make a count fit.
- The form is made by `tools/mac/make-distribution-form.py`: Chromium prints the page to PDF, then the script appends a standard PDF form (AcroForm) in plain Python. Set the `CHROME` environment variable to a Chromium binary; only its last, optional checking step needs a Mac.

### Monthly close
Close each month within 15 days of the statement date, even a quiet month; the reconciliation is the proof the books are right.
1. Dylan provides the bank statement and every receipt for the month.
2. Enter one row per statement line, with category, counterparty and description (use `add_rows`).
3. For each Zeffy deposit on the statement, clear the payout (section 6).
4. Record donors privately in `Books/donors.csv`. The public row uses a generic label.
5. Publish redacted receipts as `financials/receipts/YYYY/<id>.pdf`.
6. The president reviews and initials the statement. Its redacted copy goes to `financials/statements/YYYY-MM.pdf`.
7. Add the month to `reconciliations.csv` with the statement's ending balance and the date of the president's review. (Rule 9 fails while that date is blank, so the row can only be added once the review is done.)
8. `check` until it passes, `build`, look at the pages against the statement.
9. Commit with a message that says what changed, such as "Close 2026-12: 14 rows, ties to statement $1,240.17", and push.
10. Dylan sends a written acknowledgment for any single gift of $250 or more.

### Year-end and reporting
- Each board meeting: treasurer's report from `summary`.
- By January 31: written acknowledgment to each donor of a single gift of $250 or more (date, amount, and that no goods or services were given in return; if the donor is an officer, another officer signs).
- January: close December. The ledger and the other logs simply continue into the new year.
- By May 15: IRS Form 990-N (e-Postcard) while gross receipts are normally $50,000 or less.
- Within 30 days of passing $25,000 in a year's contributions: register with the Minnesota Attorney General (the exemption form no longer applies).
- By December 31, 2027, then yearly: Minnesota Secretary of State annual renewal.
- Public support test (one-third of support from the public over five years, each household counted up to 2%): `support` prints it from the private donor record. It reads about 2% while one donor has given everything, which is expected this early.

### Where the books stand (Nov 21, 2026)
- **General ledger: 8 rows.** Six opening rows (three paid-directly pairs for the $395.90 of formation fees), the $100.00 opening deposit by check (2026-007), and a $250.00 gift given online (2026-008, method `zeffy`). Received $745.90, spent $395.90, balance $350.00: **cash in the bank $100.00, payout receivable $250.00.** All four receipts are published.
- **No month has been closed.** No bank statement has arrived. When the November statement comes, confirm the posting date of the $100.00 deposit against it (it was made at 4:03 p.m. on Friday, Nov 20) before closing.
- **Gift log: 4 lines**, $585.00 of goods given Nov 20, 2026, with the redacted invoice. **Stock: 500 units on hand** (100 hand sanitizers, 100 emergency blankets, 200 hand-warmer 2-packs, 100 winter sets). Nothing has been given out, so the distribution log is empty.
- Every gift so far, cash and goods, came from one director.

---

## 6. Zeffy (online gifts)

Zeffy is the online donation platform. Dylan exports its payments to an `.xlsx` file from time to time and hands it over; `tools/zeffy.py` finds what is new and enters it.

### How a gift moves through the books
1. **Given.** The export shows the payment with a payout date of "Upcoming". `import` enters it in the ledger on the day it was given, as a Contributions row with method `zeffy`, description "Gift given online". It is now a **payout receivable**: part of the balance, not yet cash in the bank. Dylan asked for it to be handled this way.
2. **Paid out.** A later export shows the real payout date. `import` records it and reports which payout to look for on the bank statement.
3. **Cleared.** When the bank statement shows the deposit, `payout` enters a pair of `Transfers` rows on the posting date: the amount leaving Zeffy (method `zeffy`, negative), then the same amount reaching the bank (method `bank`, positive, `ref` to the first). The receivable falls and cash in the bank rises by the same amount.

### Commands
```
python3 tools/zeffy.py import <export.xlsx>     enter the new online gifts, then file the export in Books/zeffy/
python3 tools/zeffy.py status                   what Zeffy still owes, and anything that needs a person
python3 tools/zeffy.py payout YYYY-MM-DD [--posted YYYY-MM-DD]   clear a payout that is on the bank statement
python3 tools/zeffy.py match "<key>" <ledger ids>   tie a hand-entered Zeffy payment to rows already in the ledger
```
After `import` or `payout`: `ledger.py check`, `build`, look at the pages, commit and push.

### What the importer does and does not do
- It knows what it has already entered from a private log, `Books/zeffy-log.csv`, so the same payments in a later export are never entered twice.
- **Without that log it refuses to run.** `Books/` is never committed, so on a machine that has the repo but not `Books/` (a fresh clone, a cloud session), every gift would look new. `import` and `payout` stop with a message instead. Do not work around this by entering Zeffy gifts by hand unless Dylan says so; the private log and donor record would then be behind.
- The public row says only "Donor" (the donor's name matches a director in `INSIDERS`) or "Individual donor", with the date and amount. The name, email and home address go only to `Books/donors.csv` and `Books/zeffy-log.csv`.
- **Payments Dylan entered into Zeffy by hand** (cheque, cash, in kind) have no payout date and never pass through Zeffy. They are **not** entered from the export; they reach the books from the deposit slip or receipt. The importer matches each to an existing ledger row when the amount and date make it unambiguous; otherwise it reports it and `match` records the tie.
- **Left for a person, reported with "ATTENTION":** refunds, failed or pending payments, and gifts from an organization (which need a public label).
- Zeffy charges the organization no fees, so a payout equals the sum of the gifts in it.

### The export's columns the importer relies on
Payment Date, Payment Time, Total Amount, Payment Method, Payment Status, Payout Date (blank for hand-entered payments, "Upcoming", or a date), Refund Amount, First Name, Last Name, Email, Company Name, Address, City, State, Postal Code. There is no payment id, so a payment is identified by its date, time, amount and email.

### Where Zeffy stands (Nov 21, 2026)
One export has been imported. It held one online gift ($250.00, Nov 20, payout upcoming) and two payments Dylan had entered by hand (the $395.90 formation costs and the $100.00 cheque), both matched to rows already in the ledger. The campaign is called "Help Launch Mercy Works Outreach".

---

## 7. Hosting and deploy

- **Repo:** `dlb1177/mercyworksoutreach` on GitHub, public.
- **Host:** GitHub Pages, from the `main` branch, root folder. `.nojekyll` tells GitHub to serve the files as they are. There is no build step and there are no GitHub Actions.
- **Custom domain:** `mercyworksoutreach.org`, registered at Cloudflare, connected through the `CNAME` file in the repo root. "Enforce HTTPS" is on; GitHub renews the certificate.
- **DNS at Cloudflare:** four A records for `@` to `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`, and a CNAME for `www` to `dlb1177.github.io`. **They must stay "DNS only" (grey cloud), not proxied,** or GitHub cannot issue the certificate.
- **To deploy:** commit and push to `main`. The site is live in about a minute.
- **To confirm a deploy:** `gh api repos/dlb1177/mercyworksoutreach/pages/builds/latest --jq '.status+" "+.commit'` shows `built` and the commit. The CDN caches pages for about ten minutes, so check the live site with a throwaway query string, such as `curl -s "https://mercyworksoutreach.org/info/?v=123"`.
- **Do not change the Pages custom-domain setting unless something is broken.** Saving it through GitHub's settings or API makes GitHub commit to `CNAME` on the remote, and the next push needs `git pull --rebase origin main` first.
- Because the whole repo is served, everything in it is public at its path, including this file, `CLAUDE.md` and `tools/`.

---

## 8. Never do

1. **Never claim 501(c)(3) status, tax-exempt status or tax-deductibility** until this file says the determination letter has arrived.
2. **Never commit or publish private data:** originals of redacted documents; bank account or routing numbers; donor names without consent; home addresses, personal emails or phone numbers; anything identifying the people served, including names, photos and exact locations.
3. **Never commit anything from `Books/`, `Document_Inbox/` or `Formation_Docs/`,** and never remove them from `.gitignore`.
4. **Never name a director or officer in the financial files or pages.** Use "Donor" or "Director".
5. **Never publish a redaction that only covers text.** Remove it, and verify.
6. **Never publish an unsigned document as executed.**
7. **Never add** tracking, analytics, cookies, third-party scripts, fonts or embeds (including Google Fonts and Google Maps), a framework, or a build step beyond `tools/ledger.py`.
8. **Never edit the generated pages** under `financials/` and `inventory/` by hand.
9. **Never link to or mention the GitHub history on the site.**
10. **Never add blue stripes resembling the Missionaries of Charity sari border, never use Mother Teresa's image, and never pair the logo with her name.**
11. **Never edit or delete a ledger row in a closed month, reuse an id, or force a balance with a plug row.**
12. **Never enter Zeffy gifts without the private log** (section 6).
13. **Never add a donate button, a ledger category, or a menu item** without Dylan asking.
14. **Never publish where stock is stored.**
15. **Never rewrite git history or force-push** without Dylan's explicit say-so (see section 9).
16. **Never put private details in this file or in `CLAUDE.md`.** Both are public.

---

## 9. In progress and undecided

### Needs a decision from Dylan
- **Where private records live when working from the cloud.** `Books/`, `Formation_Docs/` and `Document_Inbox/` are only on his Mac. A session that sees only the repo can maintain the site and enter bank and stock rows from documents it is given, but it cannot run the Zeffy import, update the donor record, or file originals. Options: keep doing those steps on the Mac; keep the private folders in a private store the cloud session can also reach; or hand the session `Books/zeffy-log.csv` and `Books/donors.csv` each time and take the updated copies back. Until he decides, a cloud session that receives a private document should publish only the redacted copy, never commit the original, and tell him the original and the private records still need filing.
- **The Support page says gifts can't be accepted yet, but the Zeffy donation form is live.** He has not said whether to link to it. Any change must follow the tax-status rule.
- **The financial statement sent to the Attorney General** ran through Nov 20, 2026 and shows contributions of $1,080.90. The ledger now also shows a $250.00 online gift dated the evening of Nov 20, which was not in it. It does not affect the exemption. He was told and has not replied.
- **A director's name is in the repo's public git history.** The first version of the ledger, live for about half an hour on Nov 20, 2026, named the donor on the opening rows. Removing it means rewriting history; he was told and has not asked for it.
- **The published minutes** name one person who is not a director and give a director's background. He was told and has not asked for a change.
- **Tenet 1 on the site** no longer mentions fear or safety, though its title is "Fearless without being careless". JM deleted the sentence; Dylan was asked whether that was intended and has not said.
- **The home page's opening statement** is 1.35rem on desktop (his choice) and 1.42rem on phones. Offered to align; no answer.
- **Whether donated goods count toward the Form 990-N gross receipts figure.** The script assumes they do. He has not confirmed.
- **A budget file** for actual-versus-budget reports (the spec raised it for 2027). Not built.
- **Inventory ideas he heard but did not choose:** a "loaded minus returned" tally per outreach; a monthly stock count shown like the monthly bank check; driving the Support page's "items we need" list from target stock levels.

### Waiting on something
- **IRS determination letter** for the 1023-EZ filed Nov 19, 2026.
- **The $250.00 Zeffy payout,** still "Upcoming". Clear it when it appears on a bank statement.
- **The November bank statement,** to close the first month.
- **Bylaws and the conflict-of-interest policy:** drafted, not adopted. When adopted and signed, publish them (the Info page has a Bylaws placeholder) and list the adopting action on the Board Actions page.
- **Minnesota sales tax exemption** and **insurance quotes:** not started.
- **An acknowledgment letter** to the director who gave, covering the formation gifts, the cheque, the online gift and the goods, signed by the president.
- **The Distribution Log form** has been filled and checked on a Mac only. Dylan was asked to try it in Adobe Reader and on a phone.
- **The first filled Distribution Log form.** No outreach has been recorded yet.

### Placeholders on the site, to fill when the thing exists
Impact Updates; Newsletters; Orientation Video for New Volunteers; What a Volunteer Day Looks Like; Participant Waiver; the organization's own volunteer sign-up and schedule (to replace the legacy SignUpGenius links and their note); Quarterly Financial Reports; Bylaws; Guiding Principles; Organization Policies; Annual Tax Returns; the Non-Monetary Donations list and the donor video on the Support page. An optional `/about/` page with a longer statement of the tenets was once planned; do not build it unless asked.

### Small things a new session might trip on
- The tagline is a trial and may change.
- The email forwarding to a second director was set up by Dylan in Cloudflare and has never been verified from this side.
- `tools/mac/` scripts need macOS; `tools/ledger.py`, `tools/zeffy.py` and the tests run anywhere with Python 3.
- The brand kit's own CSS file starts with a Google Fonts `@import`. It is not used and must not be.
