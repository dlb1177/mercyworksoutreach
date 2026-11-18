# Mercy Works Outreach — Project Context

Read this before making any change to this repo. It explains what the organization is, what it believes, and how the website should be built.

> **Note:** This repo is public (GitHub Pages on a free account requires it), so this file is publicly readable too, including at `mercyworksoutreach.org/context.md`. Don't add anything private here: no personal phone numbers, home addresses or bank details, and nothing about other people that they haven't agreed to publish.

---

## 1. The organization

- **Name:** Mercy Works Outreach (decided Nov 18, 2026). It replaces the earlier working name "Face of Jesus Ministry."
- **Website:** mercyworksoutreach.org
- **Location:** Minneapolis, Minnesota and the surrounding area
- **Founder:** Dylan Brown, CPA. Dylan Brown CPA LLC is the incorporator.
- **Type:** A Christian street outreach ministry, being formed as a Minnesota nonprofit corporation that will apply for 501(c)(3) status.

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
| 2 | Confirm the name is available on the MN Secretary of State site; file Articles of Incorporation ($90 online) | ⏳ Not yet |
| 3 | Get an EIN from the IRS | ⏳ Not yet |
| 4 | Choose prospective board of directors | ⏳ In progress |
| 5 | Incorporator signs a written action electing the board | ⏳ Not yet |
| 6 | First board meeting: adopt bylaws and a conflict-of-interest policy, elect officers, approve a bank account and the tax-exemption application | ⏳ Not yet |
| 7 | Open a bank account in the organization's name | ⏳ Not yet |
| 8 | Apply for 501(c)(3) on IRS Form 1023-EZ ($275) | ⏳ Not yet |
| 9 | Register with the MN Attorney General; apply for the MN sales tax exemption | ⏳ Not yet |
| 10 | Get insurance quotes | ⏳ Not yet |

**Important for website copy:** Until the IRS issues a determination letter, the site must **not** say the organization is a 501(c)(3) or that donations are tax-deductible. Until the Articles are filed, don't call it "incorporated." Update this table as steps are completed.

---

## 2. The five core tenets (in Dylan's words, lightly condensed)

### 1. Radical transparency
The website should be extremely simple and to the point. Outsiders, including donors, can see all formation documents, meeting minutes, and **every single transaction line item and all financial data**. That goes far beyond what nonprofits are required to disclose, so anyone who supports the ministry can see down to the penny where the money goes. With today's AI and financial-reporting tools this is finally achievable for an organization of any size, and it could be the first nonprofit to do it.

**Inspiration:** Warren Buffett's Berkshire Hathaway website: no-frills, no-nonsense, with links back to every historical shareholder letter. Take that model with a slightly updated design.

### 2. 100% volunteer-run
Zero payroll, ever. This is a healthy limit most organizations wouldn't choose. It keeps the ministry from growing out of control and keeps it close to the ethos of the Missionaries of Charity.

### 3. Highly efficient
No money goes to non-program costs (fundraising, advertising, administration) beyond the minimum administrative fees the law requires. Choose simple systems over complex ones and traditional technology over complicated technology. Learn from the Missionaries of Charity's careful use of resources.

### 4. Focused on the core mission
Do exactly what Section 1.3 of the bylaws says and nothing more. Expand into other services only if every corner of Minneapolis and the surrounding area has been served as fully as possible, which is unlikely given how much need there is.

### 5. Fearless without being careless
Never let fear get in the way of serving people directly. Approach every person the way Jesus would: get down to their level, don't be afraid to touch them or talk with them closely, and treat them with dignity, one to one, like a member of your own family. Always stay aware of your surroundings and put safety first.

---

## 3. How the website should be built

The tenets lead directly to these rules:

- **Plain HTML and CSS only.** No frameworks, no build step, no npm, no static-site generator. Every page is a hand-editable `.html` file. (Tenet 3: simple over complex.)
- **No JavaScript** unless a feature truly can't work without it, and even then keep it small and inline.
- **No tracking, analytics, cookies, ads, pop-ups, or third-party scripts and fonts.** Use system fonts (Georgia/serif for the Berkshire feel).
- **Berkshire-style look:** a single narrow column of text, plain links, lots of white space, almost no imagery. A slightly modern update is fine: readable font size, works on phones, supports dark mode.
- **Accessible and fast:** semantic HTML, good contrast, every page well under 100 KB.
- **Free hosting only:** GitHub Pages. No paid services. (Tenet 3: no admin spending.)
- **Honest copy:** short, factual, warm. No marketing language and no claims that aren't true yet (see the formation status above).

### Planned site structure (build when asked; don't build ahead)
```
/                     Home: who we are, what we do, the five tenets, links
/documents/           Articles of Incorporation, bylaws, conflict-of-interest policy, IRS letters (PDFs)
/minutes/             Board meeting minutes, one PDF or HTML page per meeting, newest first
/financials/          Every transaction, line by line
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
- **Custom domain:** `mercyworksoutreach.org`, with a `CNAME` file in the repo root once the domain is connected.
  - DNS at the registrar: four **A** records for `@` → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`; one **CNAME** for `www` → `dlb1177.github.io`.
  - Turn on "Enforce HTTPS" in Settings → Pages once DNS resolves.
- **Workflow:** edit → `git commit` → `git push` → the site is live in about a minute. No build step.
