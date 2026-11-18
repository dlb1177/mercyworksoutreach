# Mercy Works Outreach — Project Context

Read this before making any change to this repo. It explains what the organization is, what it believes, and how the website should be built.

> **Note:** This repo is public (GitHub Pages on a free account requires it), so this file is publicly readable too, including at `mercyworksoutreach.org/context.md`. Don't add anything private here: no personal phone numbers, home addresses or bank details, and nothing about other people that they haven't agreed to publish.

---

## 1. The organization

- **Name:** Mercy Works Outreach (decided Nov 18, 2026). It replaces the earlier working name "Face of Jesus Ministry."
- **Website:** mercyworksoutreach.org
- **Location:** Minneapolis, Minnesota and the surrounding area
- **Founder:** Dylan Brown, CPA. Dylan Brown CPA LLC is the incorporator.
- **Type:** A street outreach ministry rooted in Catholic faith. Incorporated as a Minnesota nonprofit corporation on Nov 18, 2026 (file number 1691131200023). It will apply for 501(c)(3) status.
- **Public contact:** info@mercyworksoutreach.org (Cloudflare Email Routing, forwards to Dylan).

### Purpose (bylaws Section 1.3, summarized)
The main work is giving out **clothing, blankets, hygiene items and food** to people in need. Volunteers also offer **prayer, Bibles and devotional materials** to anyone who wants them. The bylaws word the purpose a little more broadly than today's work, to leave room to grow later.

### Governance (draft bylaws)
- **Board (Article III):** 3 to 7 directors serving staggered two-year terms. A majority must not be related to each other.
- **Officers (Article V):** president, treasurer and secretary. One person may be both treasurer and secretary, but the president can't also be the treasurer. Proposed: Dylan as secretary/treasurer and a co-founder as president. This becomes final at the first board meeting.
- **Money safeguards (Article VII):** any payment over $500 needs two signers. The president reviews and initials the bank statement every month. No one can approve a payment to themselves.

### Formation status (as of Nov 18, 2026)
| # | Step | Status |
|---|------|--------|
| 1 | Choose a name | ✅ Done: Mercy Works Outreach |
| 2 | Confirm the name is available on the MN Secretary of State site; file Articles of Incorporation ($90 online) | ✅ Done: filed Nov 18, 2026 |
| 3 | Get an EIN from the IRS | ✅ Done: assigned Nov 18, 2026 |
| 4 | Choose prospective board of directors | ⏳ In progress |
| 5 | Incorporator signs a written action electing the board | ⏳ Not yet |
| 6 | First board meeting: adopt bylaws and a conflict-of-interest policy, elect officers, approve a bank account and the tax-exemption application | ⏳ Not yet |
| 7 | Open a bank account in the organization's name | ⏳ Not yet |
| 8 | Apply for 501(c)(3) on IRS Form 1023-EZ ($275) | ⏳ Not yet |
| 9 | Register with the MN Attorney General; apply for the MN sales tax exemption | ⏳ Not yet |
| 10 | Get insurance quotes | ⏳ Not yet |

**How the site describes the ministry (Dylan, Nov 18, 2026):** call it "an outreach ministry," not "a Christian outreach ministry." Its Catholic identity is stated in the tenets list and in the phrase "as an expression of Catholic faith." (The Articles of Incorporation say "Christian faith"; that is the legal text and stays as filed.)

**Important for website copy:** Until the IRS issues a determination letter, the site must **not** say the organization is a 501(c)(3) or that donations are tax-deductible. The Articles are filed, so "incorporated" and "Minnesota nonprofit corporation" are accurate. Update this table as steps are completed. (The home page no longer shows this list.)

---

## 2. The five core tenets (in Dylan's words, lightly condensed)

Listed in priority order, most important first. The site lists them in this same order.

### 1. Fearless without being careless
Never let fear get in the way of serving people directly. Approach every person the way Jesus would: get down to their level, don't be afraid to touch them or talk with them closely, and treat them with dignity, one to one, like a member of your own family. Always stay aware of your surroundings and put safety first.

### 2. Focused on the core mission
Do exactly what Section 1.3 of the bylaws says and nothing more. Expand into other services only if every corner of Minneapolis and the surrounding area has been served as fully as possible, which is unlikely given how much need there is.

### 3. Highly efficient
No money goes to non-program costs (fundraising, advertising, administration) beyond the minimum administrative fees the law requires. Choose simple systems over complex ones and traditional technology over complicated technology. Learn from the Missionaries of Charity's careful use of resources.

### 4. 100% volunteer-run
Zero payroll, ever. This is a healthy limit most organizations wouldn't choose. It keeps the ministry from growing out of control and keeps it close to the ethos of the Missionaries of Charity.

### 5. Radical transparency
The website should be extremely simple and to the point. Outsiders, including donors, can see all formation documents, meeting minutes, and **every single transaction line item and all financial data**. That goes far beyond what nonprofits are required to disclose, so anyone who supports the ministry can see down to the penny where the money goes. With today's AI and financial-reporting tools this is finally achievable for an organization of any size, and it could be the first nonprofit to do it.

**Inspiration:** Warren Buffett's Berkshire Hathaway website: no-frills, no-nonsense, with links back to every historical shareholder letter. Take that model with a slightly updated design.


---

## 3. How the website should be built

The tenets lead directly to these rules:

- **Plain HTML and CSS only.** No frameworks, no build step, no npm, no static-site generator. Every page is a hand-editable `.html` file. (Tenet 3, highly efficient: simple over complex.)
- **No JavaScript** unless a feature truly can't work without it, and even then keep it small and inline.
- **No tracking, analytics, cookies, ads, pop-ups, or third-party scripts and fonts.** The brand fonts are served from this site's own `/fonts` folder. Never load them from Google Fonts (the `@import` line in the brand kit's `brand-colors.css` is not used).
- **Follow the brand kit** (v1, November 2026; Dylan keeps the full kit locally in `MercyWorksOutreach_BrandKit/`, which is git-ignored):
  - Logo: the "I Thirst" cup. `/logo.svg` is the stacked full-color version. Full logo at least 150 px wide, with clear space around it. Don't recolor, stretch or add effects.
  - Colors: Mercy Blue `#2A5599` (logo, links), Deep Blue `#1D3F75` (headings, hover), Water Blue `#7FA3D6` (thin rules and accents only, never text), Slate `#5B6472` (secondary text), Mist `#EEF3F9` (light panels), White (most of every page).
  - Type: EB Garamond Medium for headings, Source Sans 3 for body (Regular) and labels (SemiBold).
  - Don't add blue stripes or bands resembling the Missionaries of Charity sari border, and don't pair the logo with Mother Teresa's name or image. Both are protected.
- **Berkshire-style look:** a single narrow column of text, plain links, lots of white space, almost no imagery beyond the logo. Readable font size, works on phones. The site is light-only (mostly white, one blue, per the brand guide); there is no dark mode.
- **Accessible and fast:** semantic HTML, good contrast, every page's HTML and CSS well under 100 KB. The three font files add about 130 KB once and are then cached.
- **Free hosting only:** GitHub Pages. No paid services. (Tenet 3: no admin spending.)
- **Honest copy:** short, factual, warm. No marketing language and no claims that aren't true yet (see the formation status above).

### What exists now
```
/index.html           Home: what we do, the five tenets, a short note on inspiration
/documents/index.html A plain list of document names. PDFs live in this folder.
/style.css            The one stylesheet shared by every page
/logo.svg             Brand logo (stacked, full color)
/fonts/               EB Garamond Medium, Source Sans 3 Regular and SemiBold, with their licenses
/favicon.*, /apple-touch-icon.png, /android-chrome-*.png, /site.webmanifest,
/open-graph-share-image-1200x630.png      Icons and link-preview image from the brand kit
```
- "Contact" in the menu is a `mailto:` link to info@mercyworksoutreach.org. There is no contact page or section.
- The documents page shows names only, no descriptions.
- Placeholders on the documents page are plain text marked "Coming", not dead links. When a document exists, add the file and turn the placeholder into a link.
- `Formation_Docs/` is Dylan's local drop folder for originals and is git-ignored. Copy a file into `documents/` with a lowercase-hyphenated name to publish it. Read every document for private data before publishing.

### Planned site structure (build when asked; don't build ahead)
```
/minutes/             Board meeting minutes, one PDF or HTML page per meeting, newest first
/financials/          Every transaction, line by line; quarterly reports
/about/               (optional) Longer statement of the tenets
```

### Financial transparency approach (future)
- Keep the books in a simple CSV per year, e.g. `financials/2026.csv` with columns `date, description, category, amount, running_balance`, plus a receipt or reference column if useful.
- Each year's page shows the CSV as a plain HTML table, plus summary totals: money in, money out, and the share spent on programs vs. required admin fees.
- Offer the raw CSV as a link so anyone can download it.
- Never publish bank account numbers, donor names (unless a donor opts in), or personal details of the people served.

---

## 4. Hosting and deploy

- **GitHub repo:** `dlb1177/mercyworksoutreach` (public). It's set up the same way as Dylan's `alphastpeter.com` site.
- **Host:** GitHub Pages, deploying from the `main` branch, root folder. The `.nojekyll` file tells GitHub to serve files as-is.
- **Custom domain:** `mercyworksoutreach.org` (registered at Cloudflare Nov 18, 2026), connected through the `CNAME` file in the repo root. DNS records must stay "DNS only" (grey cloud) in Cloudflare, not proxied.
  - DNS at the registrar: four **A** records for `@` → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`; one **CNAME** for `www` → `dlb1177.github.io`.
  - "Enforce HTTPS" is on (certificate issued Nov 18, 2026; GitHub renews it automatically).
- **Workflow:** edit → `git commit` → `git push` → the site is live in about a minute. No build step.
