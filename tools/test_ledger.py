"""Tests for tools/ledger.py.

Run from the repo root:  python3 -m unittest tools/test_ledger.py

tools/fixtures/clean/ is a small made-up ledger (all in 2030) that passes every rule.
Each folder in tools/fixtures/broken/ holds only the files that differ from the
clean year (and remove.txt lists files to delete), and breaks exactly one rule.
The folder name starts with the number of the rule it breaks.
"""

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger  # noqa: E402

FIXTURES = HERE / "fixtures"
CLEAN_TRACKED = ["financials/general-ledger.csv", "tools/ledger.py"]


class LedgerTests(unittest.TestCase):

    def setUp(self):
        self._insiders = ledger.INSIDERS
        ledger.INSIDERS = ["Pat Insider"]
        self._tmp = []

    def tearDown(self):
        ledger.INSIDERS = self._insiders
        for d in self._tmp:
            shutil.rmtree(d, ignore_errors=True)

    def repo(self, broken=None):
        """Copy the clean year to a temp folder, then lay one broken fixture over it."""
        root = Path(tempfile.mkdtemp(prefix="ledger-test-"))
        self._tmp.append(root)
        shutil.copytree(FIXTURES / "clean", root, dirs_exist_ok=True)
        if broken:
            src = FIXTURES / "broken" / broken
            self.assertTrue(src.is_dir(), "no such fixture: %s" % broken)
            shutil.copytree(src, root, dirs_exist_ok=True)
            remove = root / "remove.txt"
            if remove.is_file():
                for line in remove.read_text().split():
                    (root / line).unlink()
                remove.unlink()
        (root / "gitignore.txt").rename(root / ".gitignore")
        (root / "Books").mkdir()
        (root / "books_donors.csv").rename(root / "Books" / "donors.csv")
        return root

    def rules(self, broken=None, tracked=CLEAN_TRACKED):
        books = ledger.run_check(self.repo(broken), tracked=list(tracked))
        return sorted({p.rule for p in books.problems}), books

    # ---- the clean year ----

    def test_clean_year_passes(self):
        rules, books = self.rules()
        self.assertEqual([], [str(p) for p in books.problems])
        self.assertEqual([], books.warnings)
        t = books.totals(2030)
        self.assertEqual("1125.05", str(t["received"]))
        self.assertEqual("695.00", str(t["spent"]))
        self.assertEqual("430.05", str(t["cash"]))
        self.assertEqual("95.00", str(t["by_fn"]["Program"]))
        self.assertEqual("600.00", str(t["by_fn"]["Management and general"]))
        self.assertEqual("0.00", str(t["by_fn"]["Fundraising"]))
        self.assertEqual("96.00", str(t["goods_value"]))
        self.assertEqual({"Blanket": 5, "Winter coat": 7}, books.on_hand)
        self.assertEqual({"received": 10, "distributed": -4, "packed": 0, "adjustment": -1}, books.moved["Blanket"])

    # ---- one or more broken fixtures for each rule ----

    def test_every_broken_fixture_breaks_only_its_own_rule(self):
        names = sorted(p.name for p in (FIXTURES / "broken").iterdir() if p.is_dir())
        self.assertEqual(list(range(1, 14)), sorted({int(n[:2]) for n in names} | {11}),
                         "every rule from 1 to 13 needs a broken fixture")
        for name in names:
            with self.subTest(fixture=name):
                rules, books = self.rules(name)
                self.assertEqual([int(name[:2])], rules, "\n".join(str(p) for p in books.problems))

    def test_rule_11_tracked_private_file(self):
        rules, books = self.rules(tracked=CLEAN_TRACKED + ["Books/donors.csv"])
        self.assertEqual([11], rules)
        rules, _ = self.rules(tracked=CLEAN_TRACKED + ["Document_Inbox/statement.pdf", "Formation_Docs/x.pdf"])
        self.assertEqual([11], rules)

    def test_problems_name_the_file_the_row_and_a_fix(self):
        _, books = self.rules("05-balance")
        text = str(books.problems[0])
        self.assertIn("financials/general-ledger.csv row 2030-007", text)
        self.assertIn("[rule 5]", text)
        self.assertIn("Fix:", text)

    def test_missing_books_folder_warns_instead_of_failing(self):
        root = self.repo()
        shutil.rmtree(root / "Books")
        books = ledger.run_check(root, tracked=CLEAN_TRACKED)
        self.assertEqual([], books.problems)
        self.assertEqual(1, len(books.warnings))

    def test_warnings_do_not_fail(self):
        root = self.repo()
        path = root / "financials" / "general-ledger.csv"
        path.write_text(path.read_text() +
                        "2030-011,2030-03-05,Contributions,Individual donor,Large gift,45000.00,bank,45430.05,,,\n"
                        "2030-012,2030-03-06,Fundraising,Print Shop,Appeal letters,-10.00,bank,45420.05,receipts/2030/2030-012.pdf,,\n")
        (root / "financials" / "receipts" / "2030" / "2030-012.pdf").write_text("fixture\n")
        books = ledger.run_check(root, tracked=CLEAN_TRACKED)
        self.assertEqual([], [str(p) for p in books.problems])
        self.assertEqual(3, len(books.warnings))  # contributions, gross receipts, fundraising

    def test_one_ledger_runs_across_years(self):
        root = self.repo()
        path = root / "financials" / "general-ledger.csv"
        path.write_text(path.read_text() +
                        "2031-001,2031-01-04,Contributions,Donor,Gift by check,50.00,bank,480.05,,,\n"
                        "2031-002,2031-01-09,Food,Corner Grocery,Sandwich supplies,-20.00,bank,460.05,receipts/2031/2031-002.pdf,,\n")
        (root / "financials" / "receipts" / "2031").mkdir()
        (root / "financials" / "receipts" / "2031" / "2031-002.pdf").write_text("fixture\n")
        books = ledger.run_check(root, tracked=CLEAN_TRACKED)
        self.assertEqual([], [str(p) for p in books.problems])
        self.assertEqual([2030, 2031], books.years)
        self.assertEqual("430.05", str(books.totals(2030)["cash"]))
        t = books.totals(2031)
        self.assertEqual(("50.00", "20.00", "460.05"), (str(t["received"]), str(t["spent"]), str(t["cash"])))

    def test_a_paid_directly_pair_moves_the_balance_up_and_back(self):
        _, books = self.rules()
        gift, expense = books.rows[2], books.rows[3]
        self.assertEqual(("paid-directly", "85.00"), (gift["method"], gift["balance"]))
        self.assertEqual(("paid-directly", "60.00"), (expense["method"], expense["balance"]))

    # ---- build ----

    def test_build_writes_pages_only_when_check_passes(self):
        root = self.repo("05-balance")
        books = ledger.Books(root, CLEAN_TRACKED)
        ledger.run_check = lambda r, tracked=None: ledger.Books(r, CLEAN_TRACKED).run()
        try:
            _, blocking, written = ledger.build(root)
            self.assertTrue(blocking)
            self.assertEqual([], written)
            self.assertFalse((root / "financials" / "index.html").exists())

            root = self.repo()
            _, blocking, written = ledger.build(root)
            self.assertEqual([], [str(p) for p in blocking])
            self.assertEqual(["financials/2030.html", "financials/donated-goods.html", "financials/index.html",
                              "financials/ledger.html", "inventory/index.html", "inventory/log.html"], written)
            page = (root / "financials" / "index.html").read_text()
            for expected in ("$1,125.05", "$695.00", "$430.05", "13.7%", "statements/2030-02.pdf",
                             'href="ledger.html"', "10 transactions", 'href="general-ledger.csv"',
                             'href="donated-goods.html"', "$96.00", 'href="../inventory/"'):
                self.assertIn(expected, page)
            for gone in ("<script", "github", "How to read", "categories.csv", "2030-002"):
                self.assertNotIn(gone, page)
            page = (root / "financials" / "ledger.html").read_text()
            for expected in ("Paid directly by donor", "receipts/2030/2030-002.pdf", "February 2030",
                             "\u2212$600.00", "$85.00"):
                self.assertIn(expected, page)
            self.assertNotIn("<script", page)
            # newest first, with the choices to sort and filter and the rules that go with them
            self.assertLess(page.index('id="r2030-010"'), page.index('id="r2030-001"'))
            for expected in ('name="sort" value="new" checked', 'name="show" value="out"', 'name="cat" value="food"',
                             '.fin:has([name="cat"][value="food"]:checked) .sortable tr[data-cat]:not([data-cat="food"])',
                             'data-kind="out" data-cat="food" data-year="2030"', 'type="reset"'):
                self.assertIn(expected, page)
            self.assertNotIn('name="year"', page)       # one year, so no choice of year
            places = [int(n) for n in re.findall(r'data-year="2030" style="--o:(\d+);', page)]
            self.assertEqual(10, len(places))
            self.assertEqual(sorted(places, reverse=True), places)     # the page's order is the reverse of oldest first
            page = (root / "financials" / "donated-goods.html").read_text()
            for expected in ("Winter coats, used", "$96.00", "donated-goods/G2030-001.pdf", "Individual donor"):
                self.assertIn(expected, page)
            page = (root / "inventory" / "index.html").read_text()
            self.assertIn("<td>Blanket <span", page)
            self.assertIn("<strong>5</strong>", page)
            self.assertIn("<strong>7</strong>", page)
            page = (root / "inventory" / "log.html").read_text()
            for expected in ("Outreach: North Loop", "donated-goods.html#gG2030-001", "ledger.html#r2030-004",
                             "One blanket found damaged", "\u22125", "+12"):
                self.assertIn(expected, page)
            # the pages it wrote pass the privacy scan too
            again = ledger.run_check(root)
            self.assertEqual([], [str(p) for p in again.problems])
        finally:
            ledger.run_check = lambda r, tracked=None: ledger.Books(r, tracked).run()

    def test_goods_packed_into_packages_leave_the_pages_but_not_the_log(self):
        root = self.repo()
        items = root / "inventory" / "items.csv"
        items.write_text(items.read_text() + "Socks,pairs,Clothing and blankets\nComfort pack,packs,Clothing and blankets\n")
        log = root / "inventory" / "stock-log.csv"
        log.write_text(log.read_text() +
                       "S2030-006,2030-03-02,Socks,received,5,5,2030-004,\n"
                       "S2030-007,2030-03-03,Comfort pack,packed,5,5,,One pair of socks and one coat in each\n"
                       "S2030-008,2030-03-03,Socks,packed,-5,0,S2030-007,\n"
                       "S2030-009,2030-03-03,Winter coat,packed,-5,2,S2030-007,\n")
        ledger.run_check = lambda r, tracked=None: ledger.Books(r, CLEAN_TRACKED).run()
        try:
            books, blocking, written = ledger.build(root)
            self.assertEqual([], [str(p) for p in blocking])
            self.assertEqual({"Blanket": 5, "Winter coat": 2, "Socks": 0, "Comfort pack": 5}, books.on_hand)
            page = (root / "inventory" / "index.html").read_text()
            self.assertIn("<td>Comfort pack <span", page)
            self.assertIn(">Added</th>", page)
            self.assertNotIn("Socks", page)                     # all of it went into packs
            self.assertIn("<td>Winter coat <span", page)        # some is still loose, and some was given out
            self.assertIn("7 entries", page)                    # the two rows for socks are not counted
            page = (root / "inventory" / "log.html").read_text()
            self.assertNotIn("Socks", page)
            self.assertNotIn("One pair of socks", page)
            for expected in ("Packed", "Packed into: Comfort pack", "\u22125", "+5",
                             '<a href="../financials/donated-goods.html">Donated goods</a> and <a href="../financials/ledger.html">purchases</a>'):
                self.assertIn(expected, page)
            self.assertIn("Socks", log.read_text())              # the file keeps every row
        finally:
            ledger.run_check = lambda r, tracked=None: ledger.Books(r, tracked).run()

    def test_receipts_pending_builds_but_check_still_fails(self):
        root = self.repo("07-receipt-missing")
        ledger.run_check = lambda r, tracked=None: ledger.Books(r, CLEAN_TRACKED).run()
        try:
            _, blocking, written = ledger.build(root)
            self.assertTrue(blocking)
            self.assertEqual([], written)
            books, blocking, written = ledger.build(root, receipts_pending=True)
            self.assertEqual([], blocking)
            self.assertEqual([7], sorted({p.rule for p in books.problems}))
            page = (root / "financials" / "ledger.html").read_text()
            self.assertIn('<span class="pending">Pending</span>', page)
            self.assertNotIn("receipts/2030/2030-002.pdf", page)
        finally:
            ledger.run_check = lambda r, tracked=None: ledger.Books(r, tracked).run()


if __name__ == "__main__":
    unittest.main()
