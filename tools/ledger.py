#!/usr/bin/env python3
"""Mercy Works Outreach: check the public ledger and build the Financial Ledger pages.

The ledger is the organization's books. One file, financials/general-ledger.csv,
holds every transaction since the organization began and is the book of record;
git history is the audit trail. This script checks the numbers and writes the
pages. It uses only the Python 3 standard library.

    python3 tools/ledger.py check            run every rule below; write nothing
    python3 tools/ledger.py build            run check, then write
                                             financials/index.html     summary of the latest year
                                             financials/YYYY.html      summary of each year
                                             financials/ledger.html    every transaction, newest first
                                             financials/donated-goods.html   every gift of goods
                                             inventory/index.html      what is on hand
                                             inventory/log.html        every stock movement
    python3 tools/ledger.py build --receipts-pending
                                             the same, but a receipt that has not been
                                             published yet shows as "Pending" on the page
                                             instead of stopping the build
    python3 tools/ledger.py summary [YYYY]   year-to-date totals and reporting warnings
    python3 tools/ledger.py support          public support percentage, read privately
                                             from Books/donors.csv; prints only

What check verifies (the numbers are the rule numbers printed with each problem):
  1  Header and format   exact columns in order; ISO dates; two-decimal amounts, never 0
  2  Ids                 YYYY-NNN, where YYYY is the year of the row's date. An id is
                         given once, when the row is entered, and never changes or is
                         reused; within a year the numbers run 001 to n with no gaps
  3  Dates               never earlier than the row above
  4  Categories, signs   category exists; "in" is positive and "out" negative, except on
                         a correction (a row with a ref whose description starts "Reverses")
  5  Running balance     every row's balance is the balance above plus its amount,
                         starting from 0.00. A paid-directly gift and its expense move
                         it up and back down, so each pair leaves it unchanged. The
                         balance is all funds: cash in the bank plus online gifts
                         that Zeffy has not paid out yet
  6  Pairs               every paid-directly expense refs a paid-directly Contributions
                         row of the same date and opposite amount, and the reverse.
                         A payout from Zeffy is a pair of Transfers rows on one date:
                         the amount leaving Zeffy (method zeffy, negative) and the same
                         amount reaching the bank (method bank, positive, ref to the
                         first). Zeffy can never have paid out more than was given
  7  Receipts            every spending row has receipts/YYYY/<id>.pdf and the file
                         exists; every file in receipts/ belongs to exactly one row
  8  Approvals           filled on any payment over $500.00 and any payment to a
                         director or officer (counterparty "Director")
  9  Reconciliation      each closed month's bank rows tie to its statement to the cent
  10 Privacy scan        no email addresses, phone numbers, runs of 9+ digits or
                         directors' names in the public files; a donor is named only
                         if they opted in
  11 Git hygiene         nothing under Books/, Document_Inbox/ or Formation_Docs/ is tracked
  12 Stock log           ids, dates and items are valid; received is positive and
                         distributed negative; each row's on_hand is that item's on_hand
                         above plus its quantity, and never below zero
  13 Stock links         goods received trace to a donated-goods line or a purchase in
                         the ledger, and add up to the quantity donated; goods
                         distributed trace to an outreach in the distribution log

The method column says where the money moved:
  bank            on the bank statement
  paid-directly   someone paid the organization's bill with their own money
  zeffy           through Zeffy, the online donation platform. A gift is recorded when
                  it is given; it is a payout receivable until Zeffy pays it out to the
                  bank. tools/zeffy.py enters these rows from Zeffy once a day

Rows are kept in date order. A row entered late goes in at its date (add_rows below),
keeps the id it was given, and the balances after it are worked out again. Nothing can
be entered into a month that has been closed.

The other books, each one file since inception:
  financials/donated-goods.csv   gifts of goods (not cash), valued when given
  impact/distribution-log.csv    one row per outreach
  inventory/items.csv            the items we stock
  inventory/stock-log.csv        every movement of stock in and out
"""

import csv
import html
import re
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Current directors and officers. Their names must never appear in the public
# files (rule 10): a gift from one of them is shown as "Donor" or "Director",
# and a payment to one of them as "Director", which needs an approval (rule 8).
INSIDERS = ["John Mark Reimann", "Dylan Brown", "Amara Miller"]

GENERIC_DONORS = ["Donor", "Director", "Individual donor", "Foundation", "Church", "Government"]
GIFT_CATEGORIES = ["Contributions", "Grants"]
PRIVATE_DIRS = ["Books", "Document_Inbox", "Formation_Docs"]
APPROVAL_OVER = Decimal("500.00")
WARN_CONTRIBUTIONS = Decimal("20000.00")   # MN Attorney General registration is at $25,000
WARN_GROSS_RECEIPTS = Decimal("40000.00")  # Form 990-N limit is normally $50,000
ZERO = Decimal("0.00")
METHODS = ("bank", "paid-directly", "zeffy")

LEDGER = "financials/general-ledger.csv"
LEDGER_COLS = ["id", "date", "category", "counterparty", "description", "amount",
               "method", "balance", "receipt", "ref", "approval"]
CATEGORY_COLS = ["category", "kind", "form_990_function"]
RECON_COLS = ["month", "statement_ending_balance", "president_reviewed_on", "statement_file"]
GOODS = "financials/donated-goods.csv"
GOODS_COLS = ["id", "date", "description", "quantity", "estimated_value", "valuation_basis", "donor_type", "document"]
DISTRIBUTIONS = "impact/distribution-log.csv"
IMPACT_COLS = ["date", "area", "volunteers", "people_served_estimate", "items"]
ITEMS = "inventory/items.csv"
ITEM_COLS = ["item", "unit", "category"]
STOCK = "inventory/stock-log.csv"
STOCK_COLS = ["id", "date", "item", "type", "quantity", "on_hand", "ref", "note"]
STOCK_TYPES = {"received": "Received", "distributed": "Given out", "adjustment": "Adjustment"}
FUNCTIONS = ["Program", "Management and general", "Fundraising"]

MONEY = re.compile(r"^-?\d+\.\d{2}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
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
        self.rows = []                  # every ledger row, in file order
        self.ledger_ok = False          # False if the ledger file could not be read
        self.sums_ok = False            # False if any row's date or amount could not be read
        self.years = []                 # the years that have rows, oldest first
        self.recs = []                  # reconciliation rows
        self.goods = []                 # donated goods, in file order
        self.goods_by_id = {}
        self.distributions = []         # one row per outreach
        self.outreach = {}              # date text -> distribution row
        self.items = {}                 # item -> (unit, category), in file order
        self.stock = []                 # stock movements, in file order
        self.on_hand = {}               # item -> units on hand now
        self.moved = {}                 # item -> {"received": n, "distributed": n, "adjustment": n}
        self.pending_receipts = set()   # ids whose receipt file is not there yet

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
        rows = self.read_table(LEDGER, LEDGER_COLS)
        self.ledger_ok = rows is not None
        self.rows = rows or []
        for r in self.rows:
            r["amt"] = parse_money(r["amount"])
            r["bal"] = parse_money(r["balance"])
            r["d"] = parse_date(r["date"])
            r["_where"] = "%s row %s" % (LEDGER, r["id"] or "(line %d)" % r["_line"])
        # The bank rows can only be added up if every row has a real date and amount
        self.sums_ok = self.ledger_ok and all(r["d"] is not None and r["amt"] is not None for r in self.rows)
        self.years = sorted({r["d"].year for r in self.rows if r["d"] is not None})
        self.recs = self.read_table("financials/reconciliations.csv", RECON_COLS) or []
        self.goods = self.read_table(GOODS, GOODS_COLS) or []
        self.distributions = self.read_table(DISTRIBUTIONS, IMPACT_COLS) or []
        for r in self.read_table(ITEMS, ITEM_COLS) or []:
            where = "%s line %d" % (ITEMS, r["_line"])
            if not r["item"] or r["item"] in self.items or not r["unit"]:
                self.problem(1, where, "The item name is blank or repeated, or the unit is blank.", "Give every item one unique name and a unit, such as bottles.")
            elif r["category"] not in self.categories or self.categories[r["category"]][0] != "out":
                self.problem(1, where, 'The category "%s" is not a spending category in categories.csv.' % r["category"], "Use a Program category from financials/categories.csv.")
            else:
                self.items[r["item"]] = (r["unit"], r["category"])
        stock = self.read_table(STOCK, STOCK_COLS)
        self.stock_ok = stock is not None
        self.stock = stock or []

    def load_categories(self):
        rows = self.read_table("financials/categories.csv", CATEGORY_COLS) or []
        for r in rows:
            where = "financials/categories.csv line %d" % r["_line"]
            if r["kind"] not in ("in", "out", "transfer"):
                self.problem(1, where, 'The kind "%s" is not "in", "out" or "transfer".' % r["kind"], "Use in, out or transfer.")
                continue
            allowed = FUNCTIONS if r["kind"] == "out" else ["n/a"]
            if r["form_990_function"] not in allowed:
                self.problem(1, where, 'The function "%s" is not allowed for kind "%s".' % (r["form_990_function"], r["kind"]),
                             "Use one of: " + ", ".join(allowed) + ".")
                continue
            if not r["category"] or r["category"] in self.categories:
                self.problem(1, where, "The category name is blank or repeated.", "Give every category one unique name.")
                continue
            self.categories[r["category"]] = (r["kind"], r["form_990_function"])

    def check_goods(self):
        count, prev = {}, None
        for r in self.goods:
            where = r["_where"] = "%s row %s" % (GOODS, r["id"] or "(line %d)" % r["_line"])
            r["d"] = parse_date(r["date"])
            r["value"] = parse_money(r["estimated_value"])
            if r["d"] is None:
                self.problem(1, where, 'The date "%s" is not a real date written YYYY-MM-DD.' % r["date"], "Use the date the goods were handed over, as YYYY-MM-DD.")
            else:
                year = r["d"].year
                count[year] = count.get(year, 0) + 1
                expected = "G%d-%03d" % (year, count[year])
                if r["id"] != expected:
                    self.problem(2, where, "The id should be %s (G, the year of the date, then a number that counts up)." % expected, "Change the id to %s." % expected)
                if prev is not None and r["d"] < prev:
                    self.problem(3, where, "The date %s is earlier than the row above it." % r["date"], "Put the rows in date order and renumber the ids.")
                prev = r["d"]
            if r["value"] is None or r["value"] < 0:
                self.problem(1, where, 'The estimated value "%s" is not an amount.' % r["estimated_value"], "Use two decimals, such as 45.00.")
            if not r["quantity"].isdigit() or int(r["quantity"]) == 0:
                self.problem(1, where, 'The quantity "%s" is not a whole number of units.' % r["quantity"], "Count the units, such as 100.")
            if not r["description"] or not r["valuation_basis"] or not r["donor_type"]:
                self.problem(1, where, "A field is blank.", "Fill in description, valuation_basis and donor_type.")
            if r["document"] and (not r["document"].startswith("donated-goods/") or not (self.fin / r["document"]).is_file()):
                self.problem(7, where, "The supporting document financials/%s does not exist." % r["document"], "Save the redacted document under financials/donated-goods/, or leave document blank.")
            if r["id"] and r["id"] not in self.goods_by_id:
                self.goods_by_id[r["id"]] = r
        base = self.fin / "donated-goods"
        used = {r["document"] for r in self.goods}
        for p in sorted(base.rglob("*")) if base.is_dir() else []:
            if p.is_file() and not p.name.startswith(".") and p.relative_to(self.fin).as_posix() not in used:
                self.problem(7, "financials/" + p.relative_to(self.fin).as_posix(), "No donated-goods line uses this document.", "Set it as the document of the line it supports, or remove it.")

    def check_distributions(self):
        prev = None
        for r in self.distributions:
            where = "%s line %d" % (DISTRIBUTIONS, r["_line"])
            d = parse_date(r["date"])
            if d is None:
                self.problem(1, where, 'The date "%s" is not a real date written YYYY-MM-DD.' % r["date"], "Use YYYY-MM-DD.")
            else:
                if prev is not None and d < prev:
                    self.problem(3, where, "The date %s is earlier than the row above it." % r["date"], "Put the rows in date order.")
                prev = d
                self.outreach.setdefault(r["date"], r)
            for col in ("volunteers", "people_served_estimate"):
                if not r[col].isdigit():
                    self.problem(1, where, 'The %s value "%s" is not a whole number.' % (col, r[col]), "Use a whole number.")
            if not r["area"] or not r["items"]:
                self.problem(1, where, "A field is blank.", "Fill in area and items.")

    def check_stock(self):
        count, prev, received_for = {}, None, {}
        ledger_ids = {r["id"]: r for r in self.rows}
        for r in self.stock:
            where = r["_where"] = "%s row %s" % (STOCK, r["id"] or "(line %d)" % r["_line"])
            r["d"] = parse_date(r["date"])
            qty = r["qty"] = int(r["quantity"]) if re.match(r"^-?\d+$", r["quantity"]) else None
            have = int(r["on_hand"]) if re.match(r"^-?\d+$", r["on_hand"]) else None

            # Rule 12: the stock log's own arithmetic
            if r["d"] is None:
                self.problem(12, where, 'The date "%s" is not a real date written YYYY-MM-DD.' % r["date"], "Use YYYY-MM-DD.")
            else:
                year = r["d"].year
                count[year] = count.get(year, 0) + 1
                expected = "S%d-%03d" % (year, count[year])
                if r["id"] != expected:
                    self.problem(12, where, "The id should be %s (S, the year of the date, then a number that counts up)." % expected, "Change the id to %s." % expected)
                if prev is not None and r["d"] < prev:
                    self.problem(12, where, "The date %s is earlier than the row above it." % r["date"], "Put the rows in date order and renumber the ids.")
                prev = r["d"]
            if r["item"] not in self.items:
                self.problem(12, where, 'The item "%s" is not in inventory/items.csv.' % r["item"], "Use an item from inventory/items.csv, spelled exactly, or add the item there first.")
                continue
            if r["type"] not in STOCK_TYPES:
                self.problem(12, where, 'The type "%s" is not received, distributed or adjustment.' % r["type"], "Use received, distributed or adjustment.")
                continue
            if qty is None or qty == 0 or have is None:
                self.problem(12, where, "The quantity and on_hand must be whole numbers, and the quantity cannot be 0.", "Write whole numbers of units, such as 100 or -20.")
                continue
            if (r["type"] == "received" and qty < 0) or (r["type"] == "distributed" and qty > 0):
                self.problem(12, where, "Received must be positive and distributed negative.", "Flip the sign of the quantity, or change the type.")
            want = self.on_hand.get(r["item"], 0) + qty
            if have != want:
                self.problem(12, where, "The on_hand is %d but should be %d (this item's on_hand above plus this quantity)." % (have, want), "Change on_hand to %d, or correct the quantity." % want)
            elif have < 0:
                self.problem(12, where, "The on_hand would go below zero.", "More was given out than was on hand. Find the missing receipt of stock, or correct the count.")
            self.on_hand[r["item"]] = have
            totals = self.moved.setdefault(r["item"], {"received": 0, "distributed": 0, "adjustment": 0})
            totals[r["type"]] += qty
            if r["type"] == "adjustment" and not r["note"]:
                self.problem(12, where, "An adjustment needs a note saying why.", "Fill note, such as \"Count on 2027-01-31 found 3 fewer\".")

            # Rule 13: where the goods came from and where they went
            if r["type"] == "received":
                if r["ref"] in self.goods_by_id:
                    received_for[r["ref"]] = received_for.get(r["ref"], 0) + qty
                elif not self.ledger_ok and re.match(r"^\d{4}-\d{3}$", r["ref"]):
                    pass   # the ledger could not be read; that problem is already reported
                elif r["ref"] not in ledger_ids or not self.is_spending(ledger_ids[r["ref"]]):
                    self.problem(13, where, 'The ref "%s" is not a donated-goods line or a purchase in the general ledger.' % r["ref"], "Set ref to the id of the gift (such as G2026-001) or of the ledger row that bought the goods.")
            elif r["type"] == "distributed":
                if r["ref"] != r["date"] or r["date"] not in self.outreach:
                    self.problem(13, where, "Goods given out must point to an outreach on the same date in the distribution log.", "Add the outreach to impact/distribution-log.csv and set ref to its date.")
            elif r["ref"]:
                self.problem(13, where, "An adjustment has no ref.", "Leave ref blank and explain the adjustment in note.")
        for gid, got in received_for.items():
            g = self.goods_by_id[gid]
            if g["quantity"].isdigit() and int(g["quantity"]) != got:
                self.problem(13, g["_where"], "The gift is %s units but the stock log received %d from it." % (g["quantity"], got), "Make the stock log's received rows for %s add up to %s." % (gid, g["quantity"]))

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

    def year_rows(self, year):
        return [r for r in self.rows if r["d"] is not None and r["d"].year == year]

    def check_ledger(self):
        rows = self.rows
        by_id = {}
        count = {}                      # year -> rows so far in that year
        numbered = []                   # (year, number, row) for every well-formed id
        prev_date, prev_balance, prev_year = None, ZERO, None
        for r in rows:
            where = r["_where"]

            # Rule 1: format
            if r["d"] is None:
                self.problem(1, where, 'The date "%s" is not a real date written YYYY-MM-DD.' % r["date"], "Use the bank posting date as YYYY-MM-DD.")
            if r["amt"] is None:
                self.problem(1, where, 'The amount "%s" is not a number with two decimals.' % r["amount"], "Write it like 90.00 or -90.00.")
            elif r["amt"] == 0:
                self.problem(1, where, "The amount is 0.", "Remove the row, or enter the real amount.")
            if r["bal"] is None:
                self.problem(1, where, 'The balance "%s" is not a number with two decimals.' % r["balance"], "Write it like 123.45.")
            if r["method"] not in METHODS:
                self.problem(1, where, 'The method "%s" is not bank, paid-directly or zeffy.' % r["method"], "Use bank, paid-directly or zeffy.")
            if not r["counterparty"]:
                self.problem(1, where, "The counterparty is blank.", "Name the vendor, or use a donor label such as Donor.")
            if not r["description"] or len(r["description"]) >= 80:
                self.problem(1, where, "The description is blank or 80 characters or longer.", "Write one plain line under 80 characters.")

            # Rule 2: ids. The year comes from the row's date. The number is the order of
            # entry within the year, so it need not run in order down the file.
            year = r["d"].year if r["d"] is not None else prev_year
            if year is not None:
                count[year] = count.get(year, 0) + 1
                prev_year = year
                m = re.match(r"^(\d{4})-(\d{3})$", r["id"])
                if not m or int(m.group(1)) != year or int(m.group(2)) == 0:
                    self.problem(2, where, "The id should be %d-NNN: the year of the row's date, then a three-digit number." % year, "Give the row the next unused number for %d." % year)
                elif r["id"] in by_id:
                    self.problem(2, where, "The id %s is used by more than one row." % r["id"], "Give this row the next unused number for %d." % year)
                else:
                    numbered.append((year, int(m.group(2)), r))
            if r["id"] and r["id"] not in by_id:
                by_id[r["id"]] = r

            # Rule 3: dates
            if r["d"] is not None:
                if prev_date is not None and r["d"] < prev_date:
                    self.problem(3, where, "The date %s is earlier than the row above it." % r["date"], "Move the row up to its place in date order, keep its id, and work out the balances again.")
                prev_date = r["d"]

            # Rule 5: running balance. Every row moves it, bank or paid-directly.
            if r["amt"] is not None and r["bal"] is not None:
                want = prev_balance + r["amt"]
                if r["bal"] != want:
                    self.problem(5, where, "The balance is %s but should be %s (the balance above plus this amount)." % (r["balance"], want), "Change the balance to %s, or correct the amount." % want)
            if r["bal"] is not None:
                prev_balance = r["bal"]   # carry on from the stated balance, so one mistake is reported once

        for year, number, r in numbered:
            if number > count[year]:
                self.problem(2, r["_where"], "There are %d rows dated %d, so their ids must use every number from 001 to %03d; this one is higher." % (count[year], year, count[year]), "Give the row the unused number in that range.")

        for r in rows:
            where = r["_where"]
            target = by_id.get(r["ref"]) if r["ref"] else None
            if r["ref"] and (target is None or target is r or target["_line"] > r["_line"]):
                self.problem(1, where, 'The ref "%s" does not point to an earlier row.' % r["ref"], "Use the id of the row this one pairs with or reverses, or leave ref blank.")
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
            want_receipt = "receipts/%s/%s.pdf" % (r["id"][:4], r["id"])
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
                if -r["amt"] > APPROVAL_OVER:
                    self.problem(8, where, "A payment over $500.00 needs an approval.", 'Fill approval with the approving action, such as "Written action 2027-02-03".')
                elif "director" in r["counterparty"].lower() or "officer" in r["counterparty"].lower():
                    self.problem(8, where, "A payment to a director or officer needs an approval.", "Fill approval with the two disinterested directors' written approval.")

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

        # Rule 6, continued: gifts through Zeffy and their payouts to the bank
        paid_to = {}
        for r in rows:
            if self.kind(r) == "transfer" and r["method"] == "bank" and r["ref"]:
                paid_to.setdefault(r["ref"], []).append(r)
        owed = ZERO                     # the payout receivable: given through Zeffy, not yet paid out
        for r in rows:
            where = r["_where"]
            if self.kind(r) == "transfer" and not self.is_reversal(r) and r["amt"] is not None:
                if r["method"] == "zeffy":
                    n = len(paid_to.get(r["id"], []))
                    if r["amt"] > 0 or n != 1:
                        self.problem(6, where, "A payout leaving Zeffy must be negative and matched by exactly one Transfers row reaching the bank; this one has %d." % n, "Add the bank row for the same amount on the same date, with ref set to %s." % r["id"])
                elif r["method"] == "bank":
                    t = by_id.get(r["ref"])
                    if (t is None or self.kind(t) != "transfer" or t["method"] != "zeffy" or t["date"] != r["date"]
                            or t["amt"] is None or t["amt"] != -r["amt"] or r["amt"] < 0):
                        self.problem(6, where, "A payout reaching the bank must be positive, with a ref to the Transfers row leaving Zeffy on the same date for the same amount.", "Enter the pair together: the amount leaving Zeffy, then the same amount reaching the bank.")
                else:
                    self.problem(6, where, "A Transfers row must have method zeffy or bank.", "Change the method, or the category.")
            if r["method"] == "zeffy" and r["amt"] is not None:
                if r["category"] in self.categories and self.kind(r) == "out":
                    self.problem(6, where, "Nothing is spent through Zeffy.", "Use method bank or paid-directly for spending.")
                owed += r["amt"]
                if owed < 0:
                    self.problem(6, where, "This would mean Zeffy has paid out %s more than was given through it." % -owed, "Find the online gift that has not been entered, or correct the payout amount.")
                    owed = ZERO

    def check_orphan_receipts(self):
        base = self.fin / "receipts"
        if not base.is_dir() or not self.ledger_ok:
            return
        used = {}
        for r in self.rows:
            if r["receipt"]:
                used[r["receipt"]] = used.get(r["receipt"], 0) + 1
        for p in sorted(base.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                rel = p.relative_to(self.fin).as_posix()
                if used.get(rel, 0) != 1:
                    self.problem(7, "financials/" + rel, "The receipt file is referenced by %d ledger rows, not exactly one." % used.get(rel, 0), "Name it after its ledger row id, or remove it.")

    def bank_rows(self):
        return [r for r in self.rows if r["method"] == "bank" and r["d"] is not None and r["amt"] is not None]

    def bank_balance(self, through):
        """What the bank account should hold at the end of a day: the sum of the bank rows so far."""
        return sum((r["amt"] for r in self.bank_rows() if r["d"].toordinal() <= through), ZERO)

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
            if not self.sums_ok:
                continue   # the ledger's own format problems are already reported
            if stated is None:
                self.problem(9, where, 'The statement ending balance "%s" is not a number with two decimals.' % r["statement_ending_balance"], "Copy the ending balance from the statement, like 1240.17.")
            else:
                r["_ledger"] = self.bank_balance(month_end(*r["_ym"]))
                r["_stated"] = stated
                if r["_ledger"] != stated:
                    self.problem(9, where, "The ledger's bank rows add up to %s at month end but the statement says %s." % (r["_ledger"], stated), "Find the missing or wrong row. Never force it with a plug row.")
            if parse_date(r["president_reviewed_on"]) is None:
                self.problem(9, where, "The date the president reviewed the statement is blank or not a date.", "Fill president_reviewed_on once the president has initialed the statement.")
            want = "statements/%s.pdf" % r["month"]
            if r["statement_file"] != want or not (self.fin / want).is_file():
                self.problem(9, where, "The redacted statement financials/%s is missing or the path is wrong." % want, "Save the redacted, initialed statement there and set statement_file to %s." % want)
        if seen and self.sums_ok:
            latest = max(seen)
            for ym in sorted({(r["d"].year, r["d"].month) for r in self.bank_rows()}):
                if ym < latest and ym not in seen:
                    self.problem(9, "%s month %d-%02d" % (rel, ym[0], ym[1]), "This month has bank rows and a later month is closed, but this month is not.", "Close the month: add its row with the statement's ending balance.")

    # ---------- privacy and git ----------

    def public_files(self):
        out = []
        for folder, patterns in (("financials", ("*.csv", "*.html")), ("impact", ("*.csv",)), ("inventory", ("*.csv", "*.html"))):
            for pat in patterns:
                out += sorted((self.root / folder).glob(pat))
        return out

    def scan_text(self, where, text, code=""):
        for n, line in enumerate(text.splitlines(), start=1):
            for what, rx in (("an email address", EMAIL), ("a phone number", PHONE), ("a run of 9 or more digits", LONG_DIGITS)):
                found = rx.search(line)
                if found:
                    self.problem(10, "%s line %d" % (where, n), 'The line contains %s ("%s").' % (what, found.group(0)), "Remove it. Private details stay in Books/.", code=code)
            for name in INSIDERS:
                if name.lower() in line.lower():
                    self.problem(10, "%s line %d" % (where, n), "The line names a director or officer.", 'Use "Donor" for a gift or "Director" for a payment. Names stay in Books/.', code=code)

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
        for r in self.rows:
            if r["category"] in GIFT_CATEGORIES and r["counterparty"] not in GENERIC_DONORS and r["counterparty"] not in named:
                self.problem(10, r["_where"], 'The donor "%s" is named, but Books/donors.csv has no opt-in for that name.' % r["counterparty"], "Use one of: %s. Or record public_name_ok = yes if the donor asked to be named." % ", ".join(GENERIC_DONORS))

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
        by_cat = {name: ZERO for name in self.categories}
        for r in self.year_rows(year):
            if r["category"] in by_cat and r["amt"] is not None:
                by_cat[r["category"]] += r["amt"]
        received = sum((v for k, v in by_cat.items() if self.categories[k][0] == "in"), ZERO)
        by_fn = {fn: -sum((v for k, v in by_cat.items() if self.categories[k][1] == fn), ZERO) for fn in FUNCTIONS}
        spent = sum(by_fn.values(), ZERO)
        goods = [g for g in self.goods if g.get("d") is not None and g["d"].year == year]
        goods_value = sum((g["value"] or ZERO for g in goods), ZERO)
        return {"goods": goods, "goods_value": goods_value,
                "by_cat": by_cat, "received": received, "spent": spent, "by_fn": by_fn,
                "cash": self.bank_balance(month_end(year, 12)),
                "in_transit": sum((r["amt"] for r in self.rows if r["method"] == "zeffy" and r["amt"] is not None
                                   and r["d"] is not None and r["d"].year <= year), ZERO),
                "share": (by_fn["Program"] * 100 / spent) if spent > 0 else None}

    def add_warnings(self):
        for year in self.years:
            t = self.totals(year)
            given = t["by_cat"].get("Contributions", ZERO) + t["goods_value"]
            if given > WARN_CONTRIBUTIONS:
                self.warn("%d contributions, cash and donated goods together, are %s. Registration with the Minnesota Attorney General is required within 30 days of passing $25,000." % (year, money(given)))
            if t["received"] + t["goods_value"] > WARN_GROSS_RECEIPTS:
                self.warn("%d gross receipts, cash and donated goods together, are %s. Form 990-N is only for gross receipts normally $50,000 or less." % (year, money(t["received"] + t["goods_value"])))
            if any(self.function(r) == "Fundraising" for r in self.year_rows(year)):
                self.warn("%d has Fundraising rows. They are allowed, but the tenets aim for $0." % year)

    def run(self):
        self.load()
        self.check_ledger()
        self.check_goods()
        self.check_distributions()
        self.check_stock()
        self.check_orphan_receipts()
        self.check_reconciliations()
        self.check_privacy()
        self.check_git()
        self.add_warnings()
        return self


def run_check(root, tracked=None):
    return Books(root, tracked).run()


def add_rows(root, new_rows):
    """Enter rows in the general ledger and return the ids they were given.

    Each new row is a dict with date, category, counterparty, description, amount
    and method, and optionally receipt, ref and approval. receipt "auto" becomes
    receipts/YYYY/<id>.pdf, and ref "@0" means the id given to the first row of
    this batch ("@1" the second, and so on).

    A row goes in after the last existing row with the same or an earlier date, so
    the file stays in date order. It gets the next unused number for its year, and
    every balance is worked out again. The existing balances must already be right,
    and nothing can be entered into a month that has been closed.
    """
    root = Path(root)
    path = root / LEDGER
    with open(path, newline="", encoding="utf-8") as f:
        raw = list(csv.reader(f))
    if not raw or raw[0] != LEDGER_COLS:
        raise ValueError("%s does not have the expected header" % LEDGER)
    rows = [dict(zip(LEDGER_COLS, r)) for r in raw[1:]]
    balance = ZERO
    for r in rows:
        balance += Decimal(r["amount"])
        if Decimal(r["balance"]) != balance:
            raise ValueError("The balance on row %s is wrong, so nothing was entered. Run check first." % r["id"])
    closed = ""
    recs = root / "financials" / "reconciliations.csv"
    if recs.is_file():
        with open(recs, newline="", encoding="utf-8") as f:
            closed = max([r["month"] for r in csv.DictReader(f)] or [""])
    ids = []
    for new in new_rows:
        d = parse_date(new["date"])
        if d is None or parse_money(new["amount"]) is None:
            raise ValueError("A new row needs a date written YYYY-MM-DD and an amount with two decimals.")
        if new["date"][:7] <= closed:
            raise ValueError("%s is closed, so a row dated %s cannot be entered. Correct it with a reversing row instead." % (closed, new["date"]))
        used = [int(r["id"][5:]) for r in rows if r["id"].startswith("%d-" % d.year)]
        row = {c: new.get(c, "") for c in LEDGER_COLS}
        row["id"] = "%d-%03d" % (d.year, max(used or [0]) + 1)
        if row["receipt"] == "auto":
            row["receipt"] = "receipts/%d/%s.pdf" % (d.year, row["id"])
        at = len(rows)
        while at > 0 and rows[at - 1]["date"] > new["date"]:
            at -= 1
        rows.insert(at, row)
        ids.append(row["id"])
    for row in rows:
        if row["ref"].startswith("@"):
            row["ref"] = ids[int(row["ref"][1:])]
    balance = ZERO
    for r in rows:
        balance += Decimal(r["amount"])
        r["balance"] = str(balance)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(LEDGER_COLS)
        w.writerows([[r[c] for c in LEDGER_COLS] for r in rows])
    return ids


# ---------- the pages ----------

def money(value):
    text = "${:,.2f}".format(abs(value))
    return "−" + text if value < 0 else text


def esc(text):
    return html.escape(str(text), quote=True)


def long_date(d):
    return "%s %d, %d" % (MONTHS[d.month - 1], d.day, d.year)


HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Mercy Works Outreach</title>
  <meta name="description" content="{description}">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="manifest" href="/site.webmanifest">
  <meta name="theme-color" content="#2A5599">
  <meta property="og:title" content="{title} — Mercy Works Outreach">
  <meta property="og:image" content="https://mercyworksoutreach.org/open-graph-share-image-1200x630.png">
  <link rel="canonical" href="https://mercyworksoutreach.org/{canonical}">
  <link rel="stylesheet" href="../style.css">
</head>
<body>
  <!-- This page is written by tools/ledger.py from the CSV files in the repo.
       Do not edit it by hand: change the CSV, then run python3 tools/ledger.py build -->
  <div class="page{page_class}">

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

LEAD = "Every dollar Mercy Works Outreach has received and spent, with the receipt and bank statement behind it."


def render_summary(books, year, is_index):
    """The Financial Ledger page: one year's totals, with a link to every transaction."""
    years = sorted(books.years, reverse=True)
    latest = years[0]
    t = books.totals(year)
    o = []
    w = o.append

    w('      <h1 class="title">Financial Ledger</h1>')
    w('      <p class="fin-lead">%s</p>' % LEAD)
    closed = [r for r in books.recs if r.get("_ym", (0, 0))[0] == year and "_ledger" in r]
    if closed:
        through = date.fromordinal(month_end(*closed[-1]["_ym"]))
        w('      <p class="fin-status">Checked against the bank statement through %s.</p>' % long_date(through))
    if len(years) > 1:
        links = ['<strong>%d</strong>' % y if y == year else '<a href="%s">%d</a>' % ("./" if y == latest else "%d.html" % y, y) for y in years]
        w('      <p class="fin-years">Years: %s</p>' % " &middot; ".join(links))

    share = "n/a" if t["share"] is None else ("%.1f" % t["share"]).replace(".0", "") + "%"
    w('')
    w('      <h2 id="summary">%d at a glance</h2>' % year)
    w('      <dl class="stats">')
    for label, value in (("Received", money(t["received"])), ("Spent", money(t["spent"])),
                         ("Cash in the bank", money(t["cash"])), ("Share spent on programs", share),
                         ("Paid in salaries", money(ZERO)), ("Spent on fundraising", money(t["by_fn"]["Fundraising"]))):
        w('        <div><dt>%s</dt><dd>%s</dd></div>' % (label, value))
    w('      </dl>')
    if t["in_transit"] != 0:
        w('      <p class="note">Besides the cash in the bank, %s given online is on its way to the bank account.</p>' % money(t["in_transit"]))

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

    n = len(books.rows)
    w('')
    w('      <h2 id="ledger">Every transaction</h2>')
    w('      <p>The general ledger lists every transaction since Mercy Works Outreach began, each expense with its receipt.</p>')
    w('      <ul class="rows">')
    w('        <li><a href="ledger.html">General Ledger</a> <span class="meta">%d %s</span></li>' % (n, "transaction" if n == 1 else "transactions"))
    w('      </ul>')

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
        w('      <p>No month has been closed yet. Each month, the ledger will be compared here with the bank statement, alongside the date the president reviewed it and a copy of the statement.</p>')

    n_goods = len(t["goods"])
    w('')
    w('      <h2 id="donated-goods">Donated goods</h2>')
    w('      <p>Goods given to us, such as clothing or blankets, are not cash, so they are kept out of the general ledger and listed on their own. In %d so far: %d %s of goods, with an estimated value of %s.</p>' % (year, n_goods, "gift" if n_goods == 1 else "gifts", money(t["goods_value"])))
    w('      <ul class="rows">')
    w('        <li><a href="donated-goods.html">Donated Goods</a> <span class="meta">%d since we began</span></li>' % len(books.goods))
    w('        <li><a href="../inventory/">Inventory</a> <span class="meta">On hand</span></li>')
    w('      </ul>')

    w('')
    w('      <h2 id="downloads">Downloads</h2>')
    w('      <ul class="rows">')
    w('        <li><a href="general-ledger.csv">General Ledger</a> <span class="meta">CSV</span></li>')
    w('        <li><a href="reconciliations.csv">Monthly Bank Checks</a> <span class="meta">CSV</span></li>')
    w('        <li><a href="donated-goods.csv">Donated Goods Log</a> <span class="meta">CSV</span></li>')
    w('      </ul>')

    title = "Financial Ledger" if is_index else "Financial Ledger %d" % year
    canonical = "financials/" if year == latest else "financials/%d.html" % year
    return HEAD.format(title=title, description=LEAD, canonical=canonical, page_class="") + "\n".join(o) + "\n" + FOOT


LEDGER_SORTS = [("new", "Newest first"), ("old", "Oldest first"), ("big", "Largest amount"),
                ("small", "Smallest amount"), ("cat", "Category, A to Z"), ("who", "Counterparty, A to Z")]
LEDGER_KINDS = [("in", "Money received"), ("out", "Money spent"), ("transfer", "Transfers")]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def chips(o, label, name, options):
    """One row of choices on the General Ledger page. The first option is the one chosen at the start."""
    o.append('        <div class="choices" role="radiogroup" aria-labelledby="by-%s">' % name)
    o.append('          <span class="choices-label" id="by-%s">%s</span>' % (name, esc(label)))
    for i, (value, text) in enumerate(options):
        o.append('          <label class="chip"><input type="radio" name="%s" value="%s"%s> %s</label>'
                 % (name, esc(value), " checked" if i == 0 else "", esc(text)))
    o.append('        </div>')


def render_ledger(books):
    """The General Ledger page: every transaction since inception, newest first.

    A visitor can sort and filter it. There is no JavaScript: the choices are radio
    buttons, and CSS (in style.css, plus one small <style> block written here for the
    categories and years) reorders and hides rows. The page itself is always written
    newest first, which is what a browser shows if it cannot do the rest.
    """
    rows = books.rows
    months = month_groups(rows)
    place = {r["id"]: i for i, r in enumerate(rows)}          # date order, as in the file
    newest_first = lambda r: -place[r["id"]]

    # Where each row goes under each way of sorting. Ties keep the newer row first.
    oldest = {}
    n = 0
    for ym in reversed(months):
        n += 1
        oldest[ym] = n
        for r in rows:
            if (r["d"].year, r["d"].month) == ym:
                n += 1
                oldest[r["id"]] = n
    def rank(key):
        return {r["id"]: i for i, r in enumerate(sorted(rows, key=lambda r: (key(r), newest_first(r))), start=1)}
    by_amount = rank(lambda r: -abs(r["amt"]))
    by_small = rank(lambda r: abs(r["amt"]))
    by_category = rank(lambda r: r["category"].lower())
    by_counterparty = rank(lambda r: r["counterparty"].lower())

    kinds = [(k, text) for k, text in LEDGER_KINDS if any(books.kind(r) == k for r in rows)]
    used = {r["category"] for r in rows}
    categories = [c for c in books.categories if c in used]
    years = sorted({r["d"].year for r in rows}, reverse=True)

    o = []
    w = o.append
    w('      <h1 class="title">General Ledger</h1>')
    w('      <p class="fin-lead">Every transaction since Mercy Works Outreach began, newest first.</p>')
    w('      <p class="fin-status"><a href="./">Back to the summary</a> &middot; <a href="general-ledger.csv">Download as CSV</a></p>')
    w('')
    if rows:
        w('      <form class="ledger-controls" aria-label="Sort and filter the ledger">')
        chips(o, "Sort by", "sort", LEDGER_SORTS)
        if len(kinds) > 1:
            chips(o, "Show", "show", [("all", "Everything")] + kinds)
        if len(categories) > 1:
            chips(o, "Category", "cat", [("all", "All categories")] + [(slug(c), c) for c in categories])
        if len(years) > 1:
            chips(o, "Year", "year", [("all", "All years")] + [(str(y), str(y)) for y in years])
        w('        <p class="choices-reset"><button type="reset">Back to everything, newest first</button></p>')
        w('      </form>')
        w('')
    w('      <table class="fin-table ledger stack" role="table">')
    w('        <thead role="rowgroup"><tr role="row"><th role="columnheader" scope="col">Date</th><th role="columnheader" scope="col">Description</th><th role="columnheader" scope="col">Category</th><th role="columnheader" scope="col">Counterparty</th><th role="columnheader" scope="col" class="num">Amount</th><th role="columnheader" scope="col" class="num bal">Balance</th><th role="columnheader" scope="col">Receipt</th></tr></thead>')
    for ym in months:
        w('        <tbody role="rowgroup">')
        w('          <tr role="row" class="group" style="--o:%d"><th role="rowheader" scope="rowgroup" colspan="7" aria-colspan="7">%s %d</th></tr>' % (oldest[ym], MONTHS[ym[1] - 1], ym[0]))
        for r in reversed(rows):
            if (r["d"].year, r["d"].month) != ym:
                continue
            note = ""
            if r["method"] == "paid-directly":
                note = '<span class="paid-note">Paid directly by donor</span>'
            elif r["method"] == "zeffy" and books.kind(r) != "transfer":
                note = '<span class="paid-note">Given online</span>'
            if r["receipt"] and r["id"] in books.pending_receipts:
                receipt = '<span class="pending">Pending</span>'
            elif r["receipt"]:
                receipt = '<a href="%s" target="_blank" rel="noopener">Receipt<span class="visually-hidden"> for %s</span></a>' % (esc(r["receipt"]), esc(r["id"]))
            else:
                receipt = '<span class="none">&ndash;</span>'
            w('          <tr role="row" data-kind="%s" data-cat="%s" data-year="%d" style="--o:%d;--a:%d;--s:%d;--c:%d;--p:%d">'
              % (esc(books.kind(r)), slug(r["category"]), r["d"].year, oldest[r["id"]],
                 by_amount[r["id"]], by_small[r["id"]], by_category[r["id"]], by_counterparty[r["id"]]))
            w('            <td role="cell" id="r%s" data-label="Date" class="date"><time datetime="%s">%s %d, %d</time> <span class="rowid">%s</span></td>' % (esc(r["id"]), esc(r["date"]), MONTHS[r["d"].month - 1][:3], r["d"].day, r["d"].year, esc(r["id"])))
            w('            <td role="cell" class="desc">%s%s</td>' % (esc(r["description"]), note))
            w('            <td role="cell" data-label="Category">%s</td>' % esc(r["category"]))
            w('            <td role="cell" data-label="Counterparty">%s</td>' % esc(r["counterparty"]))
            w('            <td role="cell" data-label="Amount" class="num">%s</td>' % money(r["amt"]))
            w('            <td role="cell" data-label="Balance" class="num bal">%s</td>' % money(r["bal"]))
            w('            <td role="cell" data-label="Receipt">%s</td>' % receipt)
            w('          </tr>')
        w('        </tbody>')
    w('      </table>')
    if not rows:
        w('      <p class="note">No transactions have been recorded yet.</p>')
    else:
        w('      <p class="note ledger-help"><strong>Sorting and filtering.</strong> The balance column is the balance after each transaction, in date order, so it is hidden when the ledger is sorted another way. For totals of your own, <a href="general-ledger.csv">download the CSV</a>.</p>')
    if any(r["id"] in books.pending_receipts for r in rows):
        w('      <p class="note"><strong>Receipts marked Pending.</strong> These receipts are being prepared for publication, with card numbers and personal details removed. Each will be linked here.</p>')
    if any(r["method"] == "paid-directly" for r in rows):
        w('      <p class="note"><strong>Paid directly by donor.</strong> A donor paid this bill with their own money and did not ask for it back. The gift and the expense are both recorded, so the balance rises and falls by the same amount.</p>')
    if any(r["method"] == "zeffy" for r in rows):
        w('      <p class="note"><strong>Given online.</strong> Online gifts are collected by Zeffy, our donation platform, and paid out to the bank account later. A gift is recorded on the day it is given. Until the payout arrives it is part of the balance but not yet cash in the bank.</p>')

    # The rules that depend on what is in the ledger: one per category and one per year.
    hide = '.fin:has([name="%s"][value="%s"]:checked) .ledger tr[data-%s]:not([data-%s="%s"]) { display: none; }'
    rules = [hide % ("cat", slug(c), "cat", "cat", slug(c)) for c in categories if len(categories) > 1]
    rules += [hide % ("year", y, "year", "year", y) for y in years if len(years) > 1]
    style = ""
    if rules:
        style = "  <style>\n    /* Written by tools/ledger.py: the category and year filters. The rest is in style.css. */\n    @supports selector(:has(*)) {\n      %s\n    }\n  </style>\n" % "\n      ".join(rules)
    description = "Every transaction of Mercy Works Outreach since it began, each expense with its receipt."
    head = HEAD.format(title="General Ledger", description=description, canonical="financials/ledger.html", page_class=" page-wide")
    return head.replace("</head>", style + "</head>") + "\n".join(o) + "\n" + FOOT


def month_groups(rows):
    """(year, month) pairs that have rows, newest first."""
    return sorted({(r["d"].year, r["d"].month) for r in rows}, reverse=True)


def date_cell(r):
    return '<td data-label="Date" class="date"><time datetime="%s">%s %d</time> <span class="rowid">%s</span></td>' % (
        esc(r["date"]), MONTHS[r["d"].month - 1][:3], r["d"].day, esc(r["id"]))


def render_goods(books):
    """The Donated Goods page: every gift of goods since inception, newest month first."""
    rows = books.goods
    o = []
    w = o.append
    w('      <h1 class="title">Donated Goods</h1>')
    w('      <p class="fin-lead">Every gift of goods to Mercy Works Outreach, newest month first.</p>')
    w('      <p class="fin-status"><a href="./">Back to the summary</a> &middot; <a href="donated-goods.csv">Download as CSV</a> &middot; <a href="../inventory/">Inventory</a></p>')
    w('')
    w('      <table class="fin-table ledger stack">')
    w('        <thead><tr><th scope="col">Date</th><th scope="col">Goods</th><th scope="col" class="num">Quantity</th><th scope="col" class="num">Estimated value</th><th scope="col">Valued at</th><th scope="col">From</th><th scope="col">Document</th></tr></thead>')
    for ym in month_groups(rows):
        w('        <tbody>')
        w('          <tr class="group"><th scope="rowgroup" colspan="7">%s %d</th></tr>' % (MONTHS[ym[1] - 1], ym[0]))
        for r in rows:
            if (r["d"].year, r["d"].month) != ym:
                continue
            if r["document"]:
                doc = '<a href="%s" target="_blank" rel="noopener">Invoice<span class="visually-hidden"> for %s</span></a>' % (esc(r["document"]), esc(r["id"]))
            else:
                doc = '<span class="none">&ndash;</span>'
            w('          <tr id="g%s">' % esc(r["id"]))
            w('            ' + date_cell(r))
            w('            <td class="desc">%s</td>' % esc(r["description"]))
            w('            <td data-label="Quantity" class="num">%s</td>' % "{:,}".format(int(r["quantity"])))
            w('            <td data-label="Estimated value" class="num">%s</td>' % money(r["value"]))
            w('            <td data-label="Valued at">%s</td>' % esc(r["valuation_basis"]))
            w('            <td data-label="From">%s</td>' % esc(r["donor_type"]))
            w('            <td data-label="Document">%s</td>' % doc)
            w('          </tr>')
        w('        </tbody>')
    w('      </table>')
    if not rows:
        w('      <p class="note">No goods have been given yet.</p>')
    w('      <p class="note"><strong>Not cash.</strong> Donated goods are kept out of the general ledger. What becomes of them is shown in the <a href="../inventory/">inventory</a>.</p>')
    description = "Every gift of goods to Mercy Works Outreach since it began, with its estimated value."
    return HEAD.format(title="Donated Goods", description=description, canonical="financials/donated-goods.html", page_class=" page-wide") + "\n".join(o) + "\n" + FOOT


def render_inventory(books):
    """The Inventory page: what is on hand, item by item."""
    o = []
    w = o.append
    w('      <h1 class="title">Inventory</h1>')
    w('      <p class="fin-lead">What Mercy Works Outreach has on hand to give out, and what has already gone out.</p>')
    if books.stock:
        w('      <p class="fin-status">As of %s.</p>' % long_date(books.stock[-1]["d"]))
    adjusted = any(m["adjustment"] for m in books.moved.values())
    w('')
    w('      <table class="fin-table totals">')
    w('        <thead><tr><th scope="col">Item</th><th scope="col" class="num">Received</th><th scope="col" class="num">Given out</th>%s<th scope="col" class="num">On hand</th></tr></thead>' % ('<th scope="col" class="num">Adjusted</th>' if adjusted else ''))
    w('        <tbody>')
    for item, (unit, _category) in books.items.items():
        m = books.moved.get(item, {"received": 0, "distributed": 0, "adjustment": 0})
        adj = '<td class="num">%s</td>' % signed(m["adjustment"]) if adjusted else ''
        w('          <tr><td>%s <span class="rowid">%s</span></td><td class="num">%s</td><td class="num">%s</td>%s<td class="num"><strong>%s</strong></td></tr>' % (
            esc(item), esc(unit), "{:,}".format(m["received"]), "{:,}".format(-m["distributed"]), adj, "{:,}".format(books.on_hand.get(item, 0))))
    w('        </tbody>')
    w('      </table>')
    if not books.items:
        w('      <p class="note">Nothing is in stock yet.</p>')

    n = len(books.stock)
    w('')
    w('      <h2 id="log">Every movement</h2>')
    w('      <p>The stock log lists everything that has come in and gone out. Goods come in as <a href="../financials/donated-goods.html">donated goods</a> or as purchases in the <a href="../financials/ledger.html">general ledger</a>, and go out at each outreach.</p>')
    w('      <ul class="rows">')
    w('        <li><a href="log.html">Stock Log</a> <span class="meta">%d %s</span></li>' % (n, "entry" if n == 1 else "entries"))
    w('      </ul>')
    w('')
    w('      <h2 id="downloads">Downloads</h2>')
    w('      <ul class="rows">')
    w('        <li><a href="stock-log.csv">Stock Log</a> <span class="meta">CSV</span></li>')
    w('      </ul>')
    description = "What Mercy Works Outreach has on hand to give out, and what has already gone out."
    return HEAD.format(title="Inventory", description=description, canonical="inventory/", page_class="") + "\n".join(o) + "\n" + FOOT


def signed(n):
    return "0" if n == 0 else ("+" if n > 0 else "\u2212") + "{:,}".format(abs(n))


def render_stock_log(books):
    """The Stock Log page: every movement of stock, newest month first."""
    rows = books.stock
    ledger_ids = {r["id"] for r in books.rows}
    o = []
    w = o.append
    w('      <h1 class="title">Stock Log</h1>')
    w('      <p class="fin-lead">Everything that has come into stock and gone out, newest month first.</p>')
    w('      <p class="fin-status"><a href="./">Back to the inventory</a> &middot; <a href="stock-log.csv">Download as CSV</a></p>')
    w('')
    w('      <table class="fin-table ledger stack">')
    w('        <thead><tr><th scope="col">Date</th><th scope="col">Item</th><th scope="col">Movement</th><th scope="col" class="num">Quantity</th><th scope="col" class="num">On hand</th><th scope="col">Source or destination</th></tr></thead>')
    for ym in month_groups(rows):
        w('        <tbody>')
        w('          <tr class="group"><th scope="rowgroup" colspan="6">%s %d</th></tr>' % (MONTHS[ym[1] - 1], ym[0]))
        for r in rows:
            if (r["d"].year, r["d"].month) != ym:
                continue
            if r["type"] == "received" and r["ref"] in books.goods_by_id:
                where = '<a href="../financials/donated-goods.html#g%s">Donated goods</a>' % esc(r["ref"])
            elif r["type"] == "received" and r["ref"] in ledger_ids:
                where = '<a href="../financials/ledger.html#r%s">Purchase</a>' % esc(r["ref"])
            elif r["type"] == "distributed":
                where = "Outreach: %s" % esc(books.outreach[r["date"]]["area"])
            else:
                where = ""
            note = '<span class="paid-note">%s</span>' % esc(r["note"]) if r["note"] else ""
            w('          <tr id="s%s">' % esc(r["id"]))
            w('            ' + date_cell(r))
            w('            <td class="desc">%s</td>' % esc(r["item"]))
            w('            <td data-label="Movement">%s</td>' % STOCK_TYPES[r["type"]])
            w('            <td data-label="Quantity" class="num">%s</td>' % signed(r["qty"]))
            w('            <td data-label="On hand" class="num">%s</td>' % "{:,}".format(int(r["on_hand"])))
            w('            <td data-label="Source or destination">%s%s</td>' % (where or ('<span class="none">&ndash;</span>' if not note else ""), note))
            w('          </tr>')
        w('        </tbody>')
    w('      </table>')
    if not rows:
        w('      <p class="note">Nothing has moved yet.</p>')
    description = "Every movement of Mercy Works Outreach stock: what came in, what went out, and what is on hand."
    return HEAD.format(title="Stock Log", description=description, canonical="inventory/log.html", page_class=" page-wide") + "\n".join(o) + "\n" + FOOT


def build(root, receipts_pending=False):
    books = run_check(root)
    blocking = [p for p in books.problems
                if p.code != "old-page" and not (receipts_pending and p.code == "receipt-missing")]
    if not blocking and not books.years:
        books.problem(1, LEDGER, "The ledger has no rows, so there is nothing to build.", "Enter the first transaction.")
        blocking = books.problems[-1:]
    if blocking:
        return books, blocking, []
    pages = {"financials/index.html": render_summary(books, max(books.years), True),
             "financials/ledger.html": render_ledger(books),
             "financials/donated-goods.html": render_goods(books),
             "inventory/index.html": render_inventory(books),
             "inventory/log.html": render_stock_log(books)}
    for year in books.years:
        pages["financials/%d.html" % year] = render_summary(books, year, False)
    before = len(books.problems)
    for name, text in pages.items():
        books.scan_text(name, text)
    if len(books.problems) > before:
        return books, books.problems[before:], []
    for name, text in pages.items():
        (books.root / name).write_text(text, encoding="utf-8")
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
    print("check passed: %d ledger rows (%s), %d donated-goods lines, %d stock movements." % (
        len(books.rows), ", ".join("%d in %d" % (len(books.year_rows(y)), y) for y in books.years), len(books.goods), len(books.stock)))
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
    print("build wrote: " + ", ".join(written))
    return 0


def cmd_summary(root, year):
    books = run_check(root)
    if not books.years:
        print_report(books, books.problems)
        return 1
    year = year or max(books.years)
    if year not in books.years:
        print("The ledger has no rows dated %d." % year)
        return 1
    t = books.totals(year)
    print("Mercy Works Outreach, %d year to date (cash basis)\n" % year)
    width = max(len(c) for c in books.categories) + 2
    for c, (kind, fn) in books.categories.items():
        print("  %-*s %12s   %s" % (width, c, money(t["by_cat"][c]).replace("−", "-"), "money in" if kind == "in" else fn))
    print()
    print("  Cash received (all money in, including paid-directly gifts): %s" % money(t["received"]))
    print("  Donated goods: %d gifts, estimated value %s" % (len(t["goods"]), money(t["goods_value"])))
    print("  Gross receipts (cash received plus donated goods): %s" % money(t["received"] + t["goods_value"]))
    print("  Spent: %s  (Program %s, Management and general %s, Fundraising %s)" % tuple(money(v) for v in (t["spent"], t["by_fn"]["Program"], t["by_fn"]["Management and general"], t["by_fn"]["Fundraising"])))
    print("  Share spent on programs: %s" % ("n/a" if t["share"] is None else "%.1f%%" % t["share"]))
    print("  Cash in the bank: %s" % money(t["cash"]))
    print("  Online gifts not yet paid out by Zeffy (payout receivable): %s" % money(t["in_transit"]))
    print("  Contributions year to date, cash and goods: %s  (Attorney General registration at $25,000)" % money(t["by_cat"].get("Contributions", ZERO) + t["goods_value"]))
    print("  Form 990-N: gross receipts must normally be $50,000 or less; now %s" % money(t["received"] + t["goods_value"]))
    if books.on_hand:
        print("  On hand: " + "; ".join("%s %d" % (k, v) for k, v in books.on_hand.items()))
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
    households, total = {}, ZERO
    with open(path, newline="", encoding="utf-8") as f:
        for d in csv.DictReader(f):
            amount = parse_money(d.get("amount", ""))
            if amount is None:
                print("Skipped a line with no valid amount: ledger_id %s" % d.get("ledger_id", "?"))
                continue
            key = d.get("household_key") or d.get("donor_name") or "unknown"
            households[key] = households.get(key, ZERO) + amount
            total += amount
    books = run_check(root)
    interest = sum((books.totals(y)["by_cat"].get("Interest", ZERO) for y in books.years), ZERO)
    total += interest
    if total <= 0:
        print("No support has been recorded yet.")
        return 0
    cap = total * 2 / 100
    public = sum((min(v, cap) for v in households.values()), ZERO)
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
