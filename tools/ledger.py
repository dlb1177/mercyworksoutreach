#!/usr/bin/env python3
"""Mercy Works Outreach: check the public ledger and build the Financial Ledger page.

The ledger is the organization's books. One CSV file per year, financials/YYYY.csv,
is the book of record; git history is the audit trail. This script checks the
numbers and writes the page. It uses only the Python 3 standard library.

    python3 tools/ledger.py check            run every rule below; write nothing
    python3 tools/ledger.py build            run check, then write financials/index.html
                                             and one financials/YYYY.html per year
    python3 tools/ledger.py build --receipts-pending
                                             the same, but a receipt that has not been
                                             published yet shows as "Pending" on the page
                                             instead of stopping the build
    python3 tools/ledger.py summary [YYYY]   year-to-date totals and reporting warnings
    python3 tools/ledger.py support          public support percentage, read privately
                                             from Books/donors.csv; prints only

What check verifies (the numbers are the rule numbers printed with each problem):
  1  Header and format   exact columns in order; ISO dates; two-decimal amounts, never 0
  2  Ids                 unique and sequential, YYYY-001 upward, year matching the file
  3  Dates               inside the file's year, never earlier than the row above
  4  Categories, signs   category exists; "in" is positive and "out" negative, except on
                         a correction (a row with a ref whose description starts "Reverses")
  5  Running balance     bank rows move the balance; paid-directly rows do not
  6  Pairs               every paid-directly expense refs a paid-directly Contributions
                         row of the same date and opposite amount, and the reverse
  7  Receipts            every spending row has receipts/YYYY/<id>.pdf and the file
                         exists; every file in receipts/ belongs to exactly one row
  8  Approvals           filled on any payment over $500.00 and any payment to a
                         director or officer (the INSIDERS list below)
  9  Reconciliation      each closed month ties to its bank statement to the cent
  10 Privacy scan        no email addresses, phone numbers or runs of 9+ digits in the
                         public files; donors are named only if they opted in
  11 Git hygiene         nothing under Books/, Document_Inbox/ or Formation_Docs/ is tracked
"""

import csv
import html
import re
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Current directors and officers. A payment to any of them, or to a business
# carrying one of their names, needs an approval (rule 8).
INSIDERS = ["John Mark Reimann", "Dylan Brown", "Amara Miller"]

GENERIC_DONORS = ["Individual donor", "Foundation", "Church", "Government"]
GIFT_CATEGORIES = ["Contributions", "Grants"]
PRIVATE_DIRS = ["Books", "Document_Inbox", "Formation_Docs"]
APPROVAL_OVER = Decimal("500.00")
WARN_CONTRIBUTIONS = Decimal("20000.00")   # MN Attorney General registration is at $25,000
WARN_GROSS_RECEIPTS = Decimal("40000.00")  # Form 990-N limit is normally $50,000
HISTORY_URL = "https://github.com/dlb1177/mercyworksoutreach/commits/main/financials"

LEDGER_COLS = ["id", "date", "category", "counterparty", "description", "amount",
               "method", "balance", "receipt", "ref", "approval"]
CATEGORY_COLS = ["category", "kind", "form_990_function"]
RECON_COLS = ["month", "statement_ending_balance", "president_reviewed_on", "statement_file"]
INKIND_COLS = ["date", "description", "quantity", "estimated_value", "valuation_basis", "donor_type"]
IMPACT_COLS = ["date", "area", "volunteers", "people_served_estimate", "items"]
DONOR_COLS = ["ledger_id", "date", "donor_name", "household_key", "email", "mailing_address",
              "amount", "type", "public_name_ok", "acknowledged_on"]
FUNCTIONS = ["Program", "Management and general", "Fundraising"]

MONEY = re.compile(r"^-?\d+\.\d{2}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
YEAR_FILE = re.compile(r"^\d{4}\.csv$")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(?:\(\d{3}\)\s?|\d{3}[-.\s])\d{3}[-.\s]\d{4}(?!\d)")
LONG_DIGITS = re.compile(r"\d{9,}")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


class Problem:
    def __init__(self, rule, where, message, fix, code=""):
        self.rule, self.where, self.message, self.fix, self.code = rule, where, message, fix, code

    def __str__(self):
        return "%s [rule %d]: %s Fix: %s" % (self.where, self.rule, self.message, self.fix)


def parse_date(text):
    if not ISO_DATE.match(text or ""):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_money(text):
    return Decimal(text) if MONEY.match(text or "") else None


def month_end(year, month):
    return date(year + (month == 12), month % 12 + 1, 1).toordinal() - 1


class Books:
    """Everything read from the repo, plus the problems and warnings found."""

    def __init__(self, root, tracked=None):
        self.root = Path(root)
        self.fin = self.root / "financials"
        self.tracked = tracked          # list of tracked paths; None means ask git
        self.problems, self.warnings = [], []
        self.categories = {}            # name -> (kind, function), in file order
        self.years = {}                 # year -> list of row dicts, in file order
        self.opening = {}               # year -> Decimal
        self.closing = {}               # year -> Decimal
        self.recs = []                  # reconciliation rows
        self.inkind = {}                # year -> list of rows
        self.pending_receipts = set()   # ids whose receipt file is not there yet
        self.unreadable = set()         # years whose ledger file could not be read

    def problem(self, rule, where, message, fix, code=""):
        self.problems.append(Problem(rule, where, message, fix, code))

    def warn(self, text):
        self.warnings.append(text)

    # ---------- reading ----------

    def read_table(self, rel, cols):
        path = self.root / rel
        if not path.is_file():
            self.problem(1, rel, "The file is missing.",
                         "Create it with this header line: " + ",".join(cols))
            return None
        with open(path, newline="", encoding="utf-8") as f:
            raw = list(csv.reader(f))
        if not raw or raw[0] != cols:
            self.problem(1, rel + " line 1", "The header is not the expected columns in the expected order.",
                         "Make the first line exactly: " + ",".join(cols))
            return None
        rows = []
        for n, fields in enumerate(raw[1:], start=2):
            if len(fields) != len(cols):
                self.problem(1, "%s line %d" % (rel, n),
                             "The line has %d fields, not %d." % (len(fields), len(cols)),
                             "Look for a missing or extra comma, and quote any text that contains a comma.")
                continue
            row = dict(zip(cols, fields))
            row["_line"] = n
            rows.append(row)
        return rows

    def load(self):
        self.load_categories()
        files = sorted(p.name for p in self.fin.glob("*.csv") if YEAR_FILE.match(p.name)) if self.fin.is_dir() else []
        if not files:
            self.problem(1, "financials/", "There is no ledger file.", "Create financials/YYYY.csv for the first year.")
        for name in files:
            year = int(name[:4])
            rows = self.read_table("financials/" + name, LEDGER_COLS)
            if rows is not None:
                self.years[year] = rows
            else:
                self.unreadable.add(year)
        self.recs = self.read_table("financials/reconciliations.csv", RECON_COLS) or []
        for year in self.years:
            self.inkind[year] = self.read_table("financials/inkind-%d.csv" % year, INKIND_COLS) or []
            self.check_inkind(year)
            self.check_impact(year, self.read_table("impact/%d.csv" % year, IMPACT_COLS) or [])

    def load_categories(self):
        rows = self.read_table("financials/categories.csv", CATEGORY_COLS) or []
        for r in rows:
            where = "financials/categories.csv line %d" % r["_line"]
            if r["kind"] not in ("in", "out"):
                self.problem(1, where, 'The kind "%s" is not "in" or "out".' % r["kind"], "Use in or out.")
                continue
            allowed = ["n/a"] if r["kind"] == "in" else FUNCTIONS
            if r["form_990_function"] not in allowed:
                self.problem(1, where, 'The function "%s" is not allowed for kind "%s".' % (r["form_990_function"], r["kind"]),
                             "Use one of: " + ", ".join(allowed) + ".")
                continue
            if not r["category"] or r["category"] in self.categories:
                self.problem(1, where, "The category name is blank or repeated.", "Give every category one unique name.")
                continue
            self.categories[r["category"]] = (r["kind"], r["form_990_function"])

    def check_inkind(self, year):
        for r in self.inkind[year]:
            where = "financials/inkind-%d.csv line %d" % (year, r["_line"])
            d = parse_date(r["date"])
            if d is None or d.year != year:
                self.problem(1, where, 'The date "%s" is not a date in %d.' % (r["date"], year), "Use YYYY-MM-DD.")
            if parse_money(r["estimated_value"]) is None or parse_money(r["estimated_value"]) < 0:
                self.problem(1, where, 'The estimated value "%s" is not an amount.' % r["estimated_value"],
                             "Use two decimals, such as 45.00.")
            if not r["description"] or not r["quantity"] or not r["valuation_basis"] or not r["donor_type"]:
                self.problem(1, where, "A field is blank.", "Fill in description, quantity, valuation_basis and donor_type.")

    def check_impact(self, year, rows):
        for r in rows:
            where = "impact/%d.csv line %d" % (year, r["_line"])
            d = parse_date(r["date"])
            if d is None or d.year != year:
                self.problem(1, where, 'The date "%s" is not a date in %d.' % (r["date"], year), "Use YYYY-MM-DD.")
            for col in ("volunteers", "people_served_estimate"):
                if not r[col].isdigit():
                    self.problem(1, where, 'The %s value "%s" is not a whole number.' % (col, r[col]), "Use a whole number.")
            if not r["area"] or not r["items"]:
                self.problem(1, where, "A field is blank.", "Fill in area and items.")

    # ---------- the ledger rules ----------

    def kind(self, row):
        return self.categories.get(row["category"], (None, None))[0]

    def function(self, row):
        return self.categories.get(row["category"], (None, None))[1]

    @staticmethod
    def is_reversal(row):
        return bool(row["ref"]) and row["description"].startswith("Reverses")

    def is_spending(self, row):
        """A money-out row: negative, in an "out" category."""
        return self.kind(row) == "out" and row["amt"] is not None and row["amt"] < 0

    def check_year(self, year, opening):
        rel = "financials/%d.csv" % year
        rows = self.years[year]
        by_id = {}
        prev_date, prev_balance = None, opening
        for i, r in enumerate(rows, start=1):
            where = "%s row %s" % (rel, r["id"] or "(line %d)" % r["_line"])
            r["_where"] = where
            r["amt"] = parse_money(r["amount"])
            r["bal"] = parse_money(r["balance"])
            r["d"] = parse_date(r["date"])

            # Rule 1: format
            if r["d"] is None:
                self.problem(1, where, 'The date "%s" is not a real date written YYYY-MM-DD.' % r["date"], "Use the bank posting date as YYYY-MM-DD.")
            if r["amt"] is None:
                self.problem(1, where, 'The amount "%s" is not a number with two decimals.' % r["amount"], "Write it like 90.00 or -90.00.")
            elif r["amt"] == 0:
                self.problem(1, where, "The amount is 0.", "Remove the row, or enter the real amount.")
            if r["bal"] is None:
                self.problem(1, where, 'The balance "%s" is not a number with two decimals.' % r["balance"], "Write it like 123.45.")
            if r["method"] not in ("bank", "paid-directly"):
                self.problem(1, where, 'The method "%s" is not bank or paid-directly.' % r["method"], "Use bank or paid-directly.")
            if not r["counterparty"]:
                self.problem(1, where, "The counterparty is blank.", "Name the vendor, or use a donor label such as Individual donor.")
            if not r["description"] or len(r["description"]) >= 80:
                self.problem(1, where, "The description is blank or 80 characters or longer.", "Write one plain line under 80 characters.")

            # Rule 2: ids
            expected = "%d-%03d" % (year, i)
            if r["id"] != expected:
                self.problem(2, where, 'The id should be %s (ids run in order with no gaps or repeats).' % expected, "Change the id to %s." % expected)
            if r["id"] and r["id"] not in by_id:
                by_id[r["id"]] = r

            # Rule 3: dates
            if r["d"] is not None:
                if r["d"].year != year:
                    self.problem(3, where, "The date %s is not in %d." % (r["date"], year), "Move the row to the file for its year.")
                if prev_date is not None and r["d"] < prev_date:
                    self.problem(3, where, "The date %s is earlier than the row above it." % r["date"], "Put the rows in date order and renumber the ids.")
                prev_date = r["d"]

            # Rule 5: running balance
            if r["amt"] is not None and r["bal"] is not None and r["method"] in ("bank", "paid-directly"):
                want = prev_balance + r["amt"] if r["method"] == "bank" else prev_balance
                if r["bal"] != want:
                    why = "the balance above plus this amount" if r["method"] == "bank" else "the balance above, because paid-directly rows do not move the bank balance"
                    self.problem(5, where, "The balance is %s but should be %s (%s)." % (r["balance"], want, why), "Change the balance to %s, or correct the amount." % want)
            if r["bal"] is not None:
                prev_balance = r["bal"]   # carry on from the stated balance, so one mistake is reported once

        for r in rows:
            where = r["_where"]
            target = by_id.get(r["ref"]) if r["ref"] else None
            if r["ref"] and (target is None or target is r or target["_line"] > r["_line"]):
                self.problem(1, where, 'The ref "%s" does not point to an earlier row in this file.' % r["ref"], "Use the id of the row this one pairs with or reverses, or leave ref blank.")
                target = None

            # Rule 4: categories and signs
            if r["category"] not in self.categories:
                self.problem(4, where, 'The category "%s" is not in categories.csv.' % r["category"], "Use a category from financials/categories.csv, spelled exactly.")
            elif self.is_reversal(r):
                if target is not None and (target["category"] != r["category"] or target["method"] != r["method"]
                                           or target["amt"] is None or r["amt"] is None or r["amt"] != -target["amt"]):
                    self.problem(4, where, "A reversing row must have the same category and method as row %s and the opposite amount." % r["ref"], "Copy the category and method from %s and flip the sign of its amount." % r["ref"])
            elif r["amt"] is not None and r["amt"] != 0:
                if self.kind(r) == "in" and r["amt"] < 0:
                    self.problem(4, where, 'The category "%s" is money in, but the amount is negative.' % r["category"], 'Make the amount positive, or, if this corrects an earlier row, set ref to that row and start the description with "Reverses".')
                if self.kind(r) == "out" and r["amt"] > 0:
                    self.problem(4, where, 'The category "%s" is money out, but the amount is positive.' % r["category"], 'Make the amount negative, or, if this corrects an earlier row, set ref to that row and start the description with "Reverses".')

            # Rule 7: receipts
            want_receipt = "receipts/%d/%s.pdf" % (year, r["id"])
            if self.is_spending(r) and r["receipt"] != want_receipt:
                self.problem(7, where, 'A spending row needs its receipt path, which should be %s.' % want_receipt, "Set receipt to %s and publish the redacted receipt there." % want_receipt)
            elif r["receipt"]:
                if r["receipt"] != want_receipt:
                    self.problem(7, where, 'The receipt path should be %s.' % want_receipt, "Rename the file and the path to match the row id.")
                elif not (self.fin / r["receipt"]).is_file():
                    self.pending_receipts.add(r["id"])
                    self.problem(7, where, "The receipt file financials/%s does not exist." % r["receipt"], "Redact the receipt and save it at that path.", code="receipt-missing")

            # Rule 8: approvals
            if self.is_spending(r) and not r["approval"]:
                insider = [n for n in INSIDERS if n.lower() in r["counterparty"].lower()]
                if -r["amt"] > APPROVAL_OVER:
                    self.problem(8, where, "A payment over $500.00 needs an approval.", 'Fill approval with the approving action, such as "Written action 2027-02-03".')
                elif insider:
                    self.problem(8, where, "A payment to a director or officer (%s) needs an approval." % insider[0], "Fill approval with the two disinterested directors' written approval.")

        # Rule 6: paid-directly pairs
        refs_to = {}
        for r in rows:
            if r["method"] == "paid-directly" and not self.is_reversal(r) and self.kind(r) == "out" and r["ref"]:
                refs_to.setdefault(r["ref"], []).append(r)
        for r in rows:
            if r["method"] != "paid-directly" or self.is_reversal(r) or r["category"] not in self.categories:
                continue
            where = r["_where"]
            if self.kind(r) == "out":
                t = by_id.get(r["ref"])
                if t is None:
                    self.problem(6, where, "A paid-directly expense must have a ref to its Contributions row.", "Add the Contributions row above it and set ref to that row's id.")
                elif (t["method"] != "paid-directly" or t["category"] != "Contributions" or t["date"] != r["date"]
                      or t["amt"] is None or r["amt"] is None or t["amt"] != -r["amt"]):
                    self.problem(6, where, "Row %s is not a paid-directly Contributions row with the same date and the opposite amount." % r["ref"], "Make the two rows match: same date, same amount with opposite signs, both paid-directly.")
            elif r["category"] == "Contributions":
                n = len(refs_to.get(r["id"], []))
                if n != 1:
                    self.problem(6, where, "A paid-directly contribution must be matched by exactly one paid-directly expense row; this one has %d." % n, "Add the expense row for what the donor paid, with ref set to %s." % r["id"])
            else:
                self.problem(6, where, "A paid-directly row must be a Contributions row or an expense.", "Use method bank, or change the category.")

        self.opening[year] = opening
        self.closing[year] = prev_balance

    def check_orphan_receipts(self):
        base = self.fin / "receipts"
        if not base.is_dir():
            return
        used = {}
        for rows in self.years.values():
            for r in rows:
                if r["receipt"]:
                    used[r["receipt"]] = used.get(r["receipt"], 0) + 1
        for p in sorted(base.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                rel = p.relative_to(self.fin).as_posix()
                if rel.split("/")[1].isdigit() and int(rel.split("/")[1]) in self.unreadable:
                    continue   # that year's ledger could not be read; its header problem is already reported
                if used.get(rel, 0) != 1:
                    self.problem(7, "financials/" + rel, "The receipt file is referenced by %d ledger rows, not exactly one." % used.get(rel, 0), "Name it after its ledger row id, or remove it.")

    def bank_rows(self):
        for year in sorted(self.years):
            for r in self.years[year]:
                if r["method"] == "bank" and r["d"] is not None and r["bal"] is not None:
                    yield r

    def ledger_balance_at(self, year, month):
        """Bank balance after the last bank row on or before the end of the month."""
        end = month_end(year, month)
        first = min(self.years) if self.years else year
        balance = self.opening.get(first, Decimal("0.00"))
        for r in self.bank_rows():
            if r["d"].toordinal() <= end:
                balance = r["bal"]
        return balance

    def check_reconciliations(self):
        rel = "financials/reconciliations.csv"
        seen, last = [], None
        for r in self.recs:
            where = "%s row %s" % (rel, r["month"] or "(line %d)" % r["_line"])
            m = re.match(r"^(\d{4})-(\d{2})$", r["month"])
            stated = parse_money(r["statement_ending_balance"])
            if not m or not 1 <= int(m.group(2)) <= 12:
                self.problem(9, where, 'The month "%s" is not written YYYY-MM.' % r["month"], "Write it like 2026-12.")
                continue
            r["_ym"] = (int(m.group(1)), int(m.group(2)))
            if last is not None and r["_ym"] <= last:
                self.problem(9, where, "The months are repeated or out of order.", "List each closed month once, oldest first.")
            last = r["_ym"]
            seen.append(r["_ym"])
            if r["_ym"][0] in self.unreadable:
                continue
            if r["_ym"][0] not in self.years:
                self.problem(9, where, "There is no ledger file for %d." % r["_ym"][0], "Remove this row or create the ledger file.")
                continue
            if stated is None:
                self.problem(9, where, 'The statement ending balance "%s" is not a number with two decimals.' % r["statement_ending_balance"], "Copy the ending balance from the statement, like 1240.17.")
            else:
                r["_ledger"] = self.ledger_balance_at(*r["_ym"])
                r["_stated"] = stated
                if r["_ledger"] != stated:
                    self.problem(9, where, "The ledger balance at month end is %s but the statement says %s." % (r["_ledger"], stated), "Find the missing or wrong row. Never force it with a plug row.")
            if parse_date(r["president_reviewed_on"]) is None:
                self.problem(9, where, "The date the president reviewed the statement is blank or not a date.", "Fill president_reviewed_on once the president has initialed the statement.")
            want = "statements/%s.pdf" % r["month"]
            if r["statement_file"] != want or not (self.fin / want).is_file():
                self.problem(9, where, "The redacted statement financials/%s is missing or the path is wrong." % want, "Save the redacted, initialed statement there and set statement_file to %s." % want)
        if seen:
            latest = max(seen)
            for ym in sorted({(r["d"].year, r["d"].month) for r in self.bank_rows()}):
                if ym < latest and ym not in seen:
                    self.problem(9, "%s month %d-%02d" % (rel, ym[0], ym[1]), "This month has bank rows and a later month is closed, but this month is not.", "Close the month: add its row with the statement's ending balance.")

    # ---------- privacy and git ----------

    def public_files(self):
        out = []
        for folder, patterns in (("financials", ("*.csv", "*.html")), ("impact", ("*.csv",))):
            for pat in patterns:
                out += sorted((self.root / folder).glob(pat))
        return out

    def scan_text(self, where, text, code=""):
        for n, line in enumerate(text.splitlines(), start=1):
            for what, rx in (("an email address", EMAIL), ("a phone number", PHONE), ("a run of 9 or more digits", LONG_DIGITS)):
                found = rx.search(line)
                if found:
                    self.problem(10, "%s line %d" % (where, n), 'The line contains %s ("%s").' % (what, found.group(0)), "Remove it. Private details stay in Books/.", code=code)

    def check_privacy(self):
        for p in self.public_files():
            # A generated page is rewritten and scanned again by build, so a problem
            # in the old copy must not stop the build that would replace it.
            self.scan_text(p.relative_to(self.root).as_posix(), p.read_text(encoding="utf-8"),
                           code="old-page" if p.suffix == ".html" else "")
        donors = self.root / "Books" / "donors.csv"
        if not donors.is_file():
            self.warn("Books/donors.csv is not on this machine, so donor names in the ledger could not be checked against opt-ins.")
            return
        with open(donors, newline="", encoding="utf-8") as f:
            named = {d.get("donor_name", "") for d in csv.DictReader(f) if d.get("public_name_ok", "").strip().lower() == "yes"}
        for year, rows in self.years.items():
            for r in rows:
                if r["category"] in GIFT_CATEGORIES and r["counterparty"] not in GENERIC_DONORS and r["counterparty"] not in named:
                    self.problem(10, r["_where"], 'The donor "%s" is named, but Books/donors.csv has no opt-in for that name.' % r["counterparty"], "Use Individual donor, Foundation, Church or Government, or record public_name_ok = yes if the donor asked to be named.")

    def check_git(self):
        ignore = self.root / ".gitignore"
        lines = [l.strip().lstrip("/") for l in ignore.read_text(encoding="utf-8").splitlines()] if ignore.is_file() else []
        for d in PRIVATE_DIRS:
            if d + "/" not in lines:
                self.problem(11, ".gitignore", "%s/ is not listed." % d, "Add a line reading %s/ to .gitignore." % d)
        tracked = self.tracked
        if tracked is None:
            try:
                tracked = subprocess.run(["git", "-C", str(self.root), "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
            except (OSError, subprocess.CalledProcessError):
                self.problem(11, "git", "Could not list the tracked files.", "Run this from inside the git repository.")
                return
        for path in tracked:
            if path.split("/")[0] in PRIVATE_DIRS:
                self.problem(11, path, "A private file is tracked by git.", "Run: git rm --cached \"%s\"" % path)

    # ---------- totals and warnings ----------

    def totals(self, year):
        by_cat = {name: Decimal("0.00") for name in self.categories}
        for r in self.years[year]:
            if r["category"] in by_cat and r["amt"] is not None:
                by_cat[r["category"]] += r["amt"]
        received = sum((v for k, v in by_cat.items() if self.categories[k][0] == "in"), Decimal("0.00"))
        by_fn = {fn: -sum((v for k, v in by_cat.items() if self.categories[k][1] == fn), Decimal("0.00")) for fn in FUNCTIONS}
        spent = sum(by_fn.values(), Decimal("0.00"))
        return {"by_cat": by_cat, "received": received, "spent": spent, "by_fn": by_fn,
                "cash": self.closing.get(year, Decimal("0.00")),
                "share": (by_fn["Program"] * 100 / spent) if spent > 0 else None}

    def add_warnings(self):
        for year in sorted(self.years):
            t = self.totals(year)
            if t["by_cat"].get("Contributions", 0) > WARN_CONTRIBUTIONS:
                self.warn("%d contributions are %s. Registration with the Minnesota Attorney General is required within 30 days of passing $25,000." % (year, money(t["by_cat"]["Contributions"])))
            if t["received"] > WARN_GROSS_RECEIPTS:
                self.warn("%d gross receipts are %s. Form 990-N is only for gross receipts normally $50,000 or less." % (year, money(t["received"])))
            if any(self.function(r) == "Fundraising" for r in self.years[year]):
                self.warn("%d has Fundraising rows. They are allowed, but the tenets aim for $0." % year)

    def run(self):
        self.load()
        opening = Decimal("0.00")
        for year in sorted(self.years):
            if year - 1 not in self.years and year != min(self.years):
                self.problem(5, "financials/%d.csv" % year, "There is no ledger file for %d, so the opening balance is unknown." % (year - 1), "Add financials/%d.csv." % (year - 1))
            self.check_year(year, opening)
            opening = self.closing[year]
        self.check_orphan_receipts()
        self.check_reconciliations()
        self.check_privacy()
        self.check_git()
        self.add_warnings()
        return self


def run_check(root, tracked=None):
    return Books(root, tracked).run()


# ---------- the page ----------

def money(value):
    text = "${:,.2f}".format(abs(value))
    return "−" + text if value < 0 else text


def esc(text):
    return html.escape(str(text), quote=True)


def long_date(d):
    return "%s %d, %d" % (MONTHS[d.month - 1], d.day, d.year)


def short_date(d):
    return "%s %d" % (MONTHS[d.month - 1][:3], d.day)


HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Mercy Works Outreach</title>
  <meta name="description" content="Every dollar Mercy Works Outreach has received and spent, with the receipt and bank statement behind it.">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="manifest" href="/site.webmanifest">
  <meta name="theme-color" content="#2A5599">
  <meta property="og:title" content="{title} — Mercy Works Outreach">
  <meta property="og:image" content="https://mercyworksoutreach.org/open-graph-share-image-1200x630.png">
  <link rel="canonical" href="https://mercyworksoutreach.org/financials/{canonical}">
  <link rel="stylesheet" href="../style.css">
</head>
<body>
  <!-- This page is written by tools/ledger.py from the CSV files in this folder.
       Do not edit it by hand: change the CSV, then run python3 tools/ledger.py build -->
  <div class="page page-wide">

    <header class="masthead">
      <p class="logo"><a href="../"><img src="../logo.svg" alt="Mercy Works Outreach" width="230" height="217"></a></p>
      <p class="tagline">Called to Love. Sent to Serve.</p>
      <nav aria-label="Site">
        <a href="../">Home</a>
        <a href="../info/" aria-current="true">Info</a>
        <a href="../contact/">Contact</a>
        <a href="../support/" class="support">Support</a>
      </nav>
    </header>

    <main class="fin">
"""

FOOT = """    </main>

  </div>

  <footer class="site-footer">
    <p class="org">Mercy Works Outreach</p>
    <p>A Minnesota nonprofit corporation &middot; EIN 43-3046884</p>
    <p>323 Washington Ave N, Ste 200, Minneapolis, MN 55401</p>
    <p>&copy; 2026 Mercy Works Outreach</p>
  </footer>
</body>
</html>
"""


def render(books, year, is_index):
    years = sorted(books.years, reverse=True)
    rows = books.years[year]
    t = books.totals(year)
    latest = years[0]
    o = []
    w = o.append

    w('      <h1 class="title">Financial Ledger</h1>')
    w('      <p class="fin-lead">Every dollar Mercy Works Outreach has received and spent, with the receipt and bank statement behind it.</p>')
    closed = [r for r in books.recs if r.get("_ym", (0, 0))[0] == year and "_ledger" in r]
    any_bank = any(r["d"].year <= year for r in books.bank_rows())
    if closed:
        ym = closed[-1]["_ym"]
        status = "Checked against the bank statement through %s." % long_date(date.fromordinal(month_end(*ym)))
    elif not any_bank:
        status = "The bank account is not open yet, so no bank transactions have posted and the cash balance is $0.00. The rows below are bills a donor paid directly."
    else:
        status = "No month of %d has been closed against a bank statement yet." % year
    w('      <p class="fin-status">%s</p>' % esc(status))
    if len(years) > 1:
        links = []
        for y in years:
            if y == year:
                links.append('<strong>%d</strong>' % y)
            else:
                links.append('<a href="%s">%d</a>' % ("./" if y == latest else "%d.html" % y, y))
        w('      <p class="fin-years">Years: %s</p>' % " &middot; ".join(links))

    share = "n/a" if t["share"] is None else ("%.1f" % t["share"]).replace(".0", "") + "%"
    w('')
    w('      <h2 id="summary">%d at a glance</h2>' % year)
    w('      <dl class="stats">')
    for label, value in (("Received", money(t["received"])), ("Spent", money(t["spent"])),
                         ("Cash in the bank", money(t["cash"])), ("Share spent on programs", share),
                         ("Paid in salaries", money(Decimal("0.00"))), ("Spent on fundraising", money(t["by_fn"]["Fundraising"]))):
        w('        <div><dt>%s</dt><dd>%s</dd></div>' % (label, value))
    w('      </dl>')

    w('')
    w('      <h2 id="categories">Totals by category</h2>')
    w('      <table class="fin-table totals">')
    w('        <thead><tr><th scope="col">Category</th><th scope="col" class="num">Amount</th></tr></thead>')
    groups = [("Received", [k for k, v in books.categories.items() if v[0] == "in"], t["received"])]
    groups += [(fn, [k for k, v in books.categories.items() if v[1] == fn], -t["by_fn"][fn]) for fn in FUNCTIONS]
    for name, cats, total in groups:
        w('        <tbody>')
        w('          <tr class="group"><th scope="rowgroup" colspan="2">%s</th></tr>' % esc(name))
        for c in cats:
            w('          <tr><td>%s</td><td class="num">%s</td></tr>' % (esc(c), money(t["by_cat"][c])))
        w('          <tr class="subtotal"><td>Total %s</td><td class="num">%s</td></tr>' % (esc(name[0].lower() + name[1:]), money(total)))
        w('        </tbody>')
    w('      </table>')

    w('')
    w('      <h2 id="ledger">Every transaction</h2>')
    w('      <table class="fin-table ledger stack">')
    w('        <thead><tr><th scope="col">Date</th><th scope="col">Description</th><th scope="col">Category</th><th scope="col">Counterparty</th><th scope="col" class="num">Amount</th><th scope="col" class="num">Balance</th><th scope="col">Receipt</th></tr></thead>')
    months = sorted({(r["d"].year, r["d"].month) for r in rows}, reverse=True)
    for ym in months:
        w('        <tbody>')
        w('          <tr class="group"><th scope="rowgroup" colspan="7">%s %d</th></tr>' % (MONTHS[ym[1] - 1], ym[0]))
        for r in rows:
            if (r["d"].year, r["d"].month) != ym:
                continue
            note = '<span class="paid-note">Paid directly by donor</span>' if r["method"] == "paid-directly" else ""
            if r["receipt"] and r["id"] in books.pending_receipts:
                receipt = '<span class="pending">Pending</span>'
            elif r["receipt"]:
                receipt = '<a href="%s" target="_blank" rel="noopener">Receipt<span class="visually-hidden"> for %s</span></a>' % (esc(r["receipt"]), esc(r["id"]))
            else:
                receipt = '<span class="none">&ndash;</span>'
            w('          <tr id="r%s">' % esc(r["id"]))
            w('            <td data-label="Date" class="date"><time datetime="%s">%s</time> <span class="rowid">%s</span></td>' % (esc(r["date"]), short_date(r["d"]), esc(r["id"])))
            w('            <td class="desc">%s%s</td>' % (esc(r["description"]), note))
            w('            <td data-label="Category">%s</td>' % esc(r["category"]))
            w('            <td data-label="Counterparty">%s</td>' % esc(r["counterparty"]))
            w('            <td data-label="Amount" class="num%s">%s</td>' % (" out" if r["amt"] < 0 else "", money(r["amt"])))
            w('            <td data-label="Balance" class="num">%s</td>' % money(r["bal"]))
            w('            <td data-label="Receipt">%s</td>' % receipt)
            w('          </tr>')
        w('        </tbody>')
    w('      </table>')
    if not rows:
        w('      <p class="note">No transactions have been recorded for %d yet.</p>' % year)
    if any(r["id"] in books.pending_receipts for r in rows):
        w('      <p class="note"><strong>Receipts marked Pending.</strong> These receipts are being prepared for publication, with card numbers and personal details removed. Each will be linked here.</p>')

    w('')
    w('      <h2 id="bank-check">Monthly bank check</h2>')
    if closed:
        w('      <table class="fin-table stack">')
        w('        <thead><tr><th scope="col">Month</th><th scope="col" class="num">Statement balance</th><th scope="col" class="num">Ledger balance</th><th scope="col" class="num">Difference</th><th scope="col">President reviewed</th><th scope="col">Statement</th></tr></thead>')
        w('        <tbody>')
        for r in reversed(closed):
            ym = r["_ym"]
            w('          <tr>')
            w('            <td class="desc">%s %d</td>' % (MONTHS[ym[1] - 1], ym[0]))
            w('            <td data-label="Statement balance" class="num">%s</td>' % money(r["_stated"]))
            w('            <td data-label="Ledger balance" class="num">%s</td>' % money(r["_ledger"]))
            w('            <td data-label="Difference" class="num">%s</td>' % money(r["_stated"] - r["_ledger"]))
            w('            <td data-label="President reviewed">%s</td>' % esc(long_date(parse_date(r["president_reviewed_on"]))))
            w('            <td data-label="Statement"><a href="%s" target="_blank" rel="noopener">Statement<span class="visually-hidden"> for %s</span></a></td>' % (esc(r["statement_file"]), esc(r["month"])))
            w('          </tr>')
        w('        </tbody>')
        w('      </table>')
        w('      <p class="note">Each month the ledger is compared with the bank statement, and the president reviews and initials the statement. The difference is always $0.00.</p>')
    else:
        w('      <p>No month has been closed yet. Once the bank account is open, each month&rsquo;s ledger balance will be compared here with the bank statement, alongside the date the president reviewed it and a copy of the statement.</p>')

    kind_total = sum((parse_money(r["estimated_value"]) or Decimal("0.00") for r in books.inkind.get(year, [])), Decimal("0.00"))
    count = len(books.inkind.get(year, []))
    w('')
    w('      <h2 id="donated-goods">Donated goods</h2>')
    w('      <p>Goods given to us, such as clothing or food, are not cash, so they are kept out of the ledger above and listed in their own log. In %d so far: %d %s, with an estimated value of %s. <a href="inkind-%d.csv">Donated goods log (CSV)</a></p>' % (year, count, "gift" if count == 1 else "gifts", money(kind_total), year))

    w('')
    w('      <h2 id="how-to-read">How to read this page</h2>')
    w('      <ul class="plain">')
    w('        <li><strong>Cash basis, calendar year.</strong> A row is recorded on the date money actually moves, not when a bill arrives or a gift is promised. The year runs January 1 to December 31.</li>')
    w('        <li><strong>Amounts.</strong> Money in is positive. Money out has a minus sign. Balance is the bank balance after that row.</li>')
    w('        <li><strong>Paid directly by donor.</strong> Sometimes a donor pays one of our bills with their own money and does not want it back. That appears as two rows on the same date: the gift and the matching expense. No money passes through the bank, so the balance does not move.</li>')
    w('        <li><strong>Receipts and statements.</strong> Every expense links to its receipt, and every closed month links to its bank statement. Before publishing we remove card numbers and account numbers except the last four digits, routing numbers, personal addresses and phone numbers, and donor names. Nothing else is changed.</li>')
    w('        <li><strong>Donor names.</strong> Donors are listed as Individual donor, Foundation, Church or Government unless a donor asks to be named.</li>')
    w('        <li><strong>Salaries.</strong> No one is paid, so there is no salary category and the figure is always $0.00.</li>')
    if year == min(books.years):
        w('        <li><strong>Share spent on programs.</strong> Program spending divided by all spending for the year. The first year reads low because the fees to form the organization are its only costs so far.</li>')
    else:
        w('        <li><strong>Share spent on programs.</strong> Program spending divided by all spending for the year.</li>')
    w('        <li><strong>Corrections.</strong> Once a month is closed, its rows are never edited or deleted. A mistake is fixed in the open with a row that reverses it and a new, correct row.</li>')
    w('      </ul>')

    w('')
    w('      <h2 id="downloads">Downloads and history</h2>')
    w('      <ul class="rows">')
    w('        <li><a href="%d.csv">Ledger for %d (CSV)</a></li>' % (year, year))
    w('        <li><a href="categories.csv">Category list (CSV)</a></li>')
    w('        <li><a href="reconciliations.csv">Monthly bank checks (CSV)</a></li>')
    w('        <li><a href="inkind-%d.csv">Donated goods log for %d (CSV)</a></li>' % (year, year))
    w('        <li><a href="../tools/ledger.py">The script that checks these books</a></li>')
    w('        <li><a href="%s" target="_blank" rel="noopener">Every change to these books</a> <span class="meta">GitHub history</span></li>' % HISTORY_URL)
    w('      </ul>')

    title = "Financial Ledger" if is_index else "Financial Ledger %d" % year
    canonical = "" if year == latest else "%d.html" % year
    return HEAD.format(title=title, canonical=canonical) + "\n".join(o) + "\n" + FOOT


def build(root, receipts_pending=False):
    books = run_check(root)
    blocking = [p for p in books.problems
                if p.code != "old-page" and not (receipts_pending and p.code == "receipt-missing")]
    if blocking:
        return books, blocking, []
    latest = max(books.years)
    pages = {"index.html": render(books, latest, True)}
    for year in books.years:
        pages["%d.html" % year] = render(books, year, False)
    before = len(books.problems)
    for name, text in pages.items():
        books.scan_text("financials/" + name, text)
    if len(books.problems) > before:
        return books, books.problems[before:], []
    for name, text in pages.items():
        (books.fin / name).write_text(text, encoding="utf-8")
    return books, [], sorted(pages)


# ---------- commands ----------

def print_report(books, problems):
    for p in problems:
        print(p)
    for wtext in books.warnings:
        print("Warning: " + wtext)


def cmd_check(root):
    books = run_check(root)
    print_report(books, books.problems)
    if books.problems:
        print("\ncheck FAILED: %d problem%s." % (len(books.problems), "" if len(books.problems) == 1 else "s"))
        return 1
    print("check passed: %s." % ", ".join("%d has %d rows" % (y, len(books.years[y])) for y in sorted(books.years)))
    return 0


def cmd_build(root, receipts_pending):
    books, blocking, written = build(root, receipts_pending)
    print_report(books, blocking)
    if blocking:
        print("\nbuild STOPPED: %d problem%s. Nothing was written." % (len(blocking), "" if len(blocking) == 1 else "s"))
        return 1
    for p in books.problems:
        if p.code == "receipt-missing":
            print("Pending: " + str(p))
    print("build wrote: " + ", ".join("financials/" + n for n in written))
    return 0


def cmd_summary(root, year):
    books = run_check(root)
    if not books.years:
        print_report(books, books.problems)
        return 1
    year = year or max(books.years)
    if year not in books.years:
        print("There is no ledger file for %d." % year)
        return 1
    t = books.totals(year)
    print("Mercy Works Outreach, %d year to date (cash basis)\n" % year)
    width = max(len(c) for c in books.categories) + 2
    for c, (kind, fn) in books.categories.items():
        print("  %-*s %12s   %s" % (width, c, money(t["by_cat"][c]).replace("−", "-"), "money in" if kind == "in" else fn))
    print()
    print("  Gross receipts (all money in, including paid-directly gifts): %s" % money(t["received"]))
    print("  Spent: %s  (Program %s, Management and general %s, Fundraising %s)" % tuple(money(v) for v in (t["spent"], t["by_fn"]["Program"], t["by_fn"]["Management and general"], t["by_fn"]["Fundraising"])))
    print("  Share spent on programs: %s" % ("n/a" if t["share"] is None else "%.1f%%" % t["share"]))
    print("  Cash in the bank: %s" % money(t["cash"]))
    print("  Contributions year to date: %s  (Attorney General registration at $25,000)" % money(t["by_cat"].get("Contributions", Decimal("0.00"))))
    print("  Form 990-N: gross receipts must normally be $50,000 or less; now %s" % money(t["received"]))
    print()
    print_report(books, books.problems)
    if not books.problems and not books.warnings:
        print("No problems and no warnings.")
    return 1 if books.problems else 0


def cmd_support(root):
    """Public support test, printed only. It works from donor names, so it never writes a file."""
    path = Path(root) / "Books" / "donors.csv"
    if not path.is_file():
        print("Books/donors.csv is not on this machine, so the public support test cannot be run here.")
        return 1
    households, total = {}, Decimal("0.00")
    with open(path, newline="", encoding="utf-8") as f:
        for d in csv.DictReader(f):
            amount = parse_money(d.get("amount", ""))
            if amount is None:
                print("Skipped a line with no valid amount: ledger_id %s" % d.get("ledger_id", "?"))
                continue
            key = d.get("household_key") or d.get("donor_name") or "unknown"
            households[key] = households.get(key, Decimal("0.00")) + amount
            total += amount
    books = run_check(root)
    interest = sum((books.totals(y)["by_cat"].get("Interest", Decimal("0.00")) for y in books.years), Decimal("0.00"))
    total += interest
    if total <= 0:
        print("No support has been recorded yet.")
        return 0
    cap = total * 2 / 100
    public = sum((min(v, cap) for v in households.values()), Decimal("0.00"))
    pct = public * 100 / total
    print("Public support test (all years on file; the first test covers years 1 to 5 together)")
    print("  Total support: %s  (gifts and grants %s, interest %s)" % (money(total), money(total - interest), money(interest)))
    print("  Households: %d   2%% cap per household: %s" % (len(households), money(cap)))
    print("  Public support: %s = %.1f%% of total  (the test needs at least 33.3%%)" % (money(public), pct))
    print("  Note: every household is capped at 2% here. Grants from governments and public charities are")
    print("  not capped under the real test, so this figure is a floor.")
    if pct < Decimal("33.34"):
        print("  Below one-third. This is expected while a few donors give most of the support.")
    return 0


def main(argv):
    root = Path(__file__).resolve().parent.parent
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "check":
        return cmd_check(root)
    if cmd == "build":
        return cmd_build(root, "--receipts-pending" in argv[2:])
    if cmd == "summary":
        return cmd_summary(root, int(argv[2]) if len(argv) > 2 else None)
    if cmd == "support":
        return cmd_support(root)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
