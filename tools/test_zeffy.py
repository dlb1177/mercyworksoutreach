"""Tests for tools/zeffy.py and for entering rows with ledger.add_rows.

Run from the repo root:  python3 -m unittest tools/test_zeffy.py

Each test copies the made-up clean ledger in tools/fixtures/clean/ to a temp
folder and writes a small made-up Zeffy export there.
"""

import csv
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger  # noqa: E402
import zeffy   # noqa: E402

TRACKED = ["financials/general-ledger.csv"]
HEADER = ["Payment Date (America/Chicago)", "Payment Time (America/Chicago)", "Total Amount", "DAF provider",
          "Payment Method", "Payment Status", "Payout Date", "Refund Amount", "Recurring Status", "Discount", "Fund",
          "First Name", "Last Name", "Email", "Company Name", "Address", "City", "Postal Code", "State", "Country"]


def payment(day, clock, amount, method="Card", payout="Upcoming", first="Nora", last="Quill",
            email="nora@quill.example", status="Succeeded", refund="", company=""):
    return [day, clock, amount, "", method, status, payout, refund, "", "", "", first, last, email, company,
            "1 Quill St", "Anytown", "55000", "MN", "US"]


def write_export(path, rows):
    """A minimal .xlsx laid out the way Zeffy's export is: one sheet, header row first."""
    def col(i):
        return chr(65 + i) if i < 26 else "A" + chr(65 + i - 26)
    xml = ['<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for n, row in enumerate([HEADER] + rows, start=1):
        cells = []
        for i, value in enumerate(row):
            if value == "":
                continue
            if n > 1 and i == 2:
                cells.append('<c r="%s%d"><v>%s</v></c>' % (col(i), n, value))
            else:
                cells.append('<c r="%s%d" t="str"><v>%s</v></c>' % (col(i), n, escape(value)))
        xml.append('<row r="%d">%s</row>' % (n, "".join(cells)))
    xml.append("</sheetData></worksheet>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", "".join(xml))
    return path


class ZeffyTests(unittest.TestCase):

    def setUp(self):
        self._insiders = ledger.INSIDERS
        ledger.INSIDERS = ["Pat Insider"]
        self.root = Path(tempfile.mkdtemp(prefix="zeffy-test-"))
        shutil.copytree(HERE / "fixtures" / "clean", self.root, dirs_exist_ok=True)
        (self.root / "gitignore.txt").rename(self.root / ".gitignore")
        (self.root / "Books").mkdir()
        (self.root / "books_donors.csv").rename(self.root / "Books" / "donors.csv")

    def tearDown(self):
        ledger.INSIDERS = self._insiders
        shutil.rmtree(self.root, ignore_errors=True)

    def check(self):
        books = ledger.run_check(self.root, tracked=TRACKED)
        self.assertEqual([], [str(p) for p in books.problems])
        return books

    def rows(self):
        with open(self.root / ledger.LEDGER, newline="") as f:
            return list(csv.DictReader(f))

    def export(self, rows, name="export.xlsx"):
        return write_export(self.root / name, rows)

    # ---- entering rows ----

    def test_add_rows_keeps_date_order_and_ids_and_reworks_balances(self):
        ids = ledger.add_rows(self.root, [{"date": "2030-03-01", "category": "Contributions", "counterparty": "Individual donor",
                                           "description": "Gift by check", "amount": "20.00", "method": "bank"}])
        self.assertEqual(["2030-011"], ids)
        rows = self.rows()
        self.assertEqual(["2030-008", "2030-011", "2030-009", "2030-010"], [r["id"] for r in rows[7:]])
        self.assertEqual(["430.05", "450.05", "480.05", "450.05"], [r["balance"] for r in rows[7:]])
        self.assertEqual("450.05", str(self.check().totals(2030)["cash"]))

    def test_add_rows_refuses_a_closed_month(self):
        with self.assertRaises(ValueError):
            ledger.add_rows(self.root, [{"date": "2030-02-20", "category": "Contributions", "counterparty": "Individual donor",
                                         "description": "Gift by check", "amount": "20.00", "method": "bank"}])
        self.assertEqual(10, len(self.rows()))

    # ---- the Zeffy export ----

    def test_import_enters_new_online_gifts_once(self):
        export = self.export([payment("03/04/2030", "5:47 PM", "250"), payment("03/03/2030", "9:05 AM", "40.5", first="Pat", last="Insider", email="pat@example.com")])
        report = "\n".join(zeffy.import_export(self.root, export, today="2030-03-06"))
        self.assertIn("entered as 2030-011 (Donor)", report)
        self.assertIn("entered as 2030-012 (Individual donor)", report)
        rows = self.rows()
        self.assertEqual([("2030-03-03", "Contributions", "Donor", "Gift given online", "40.50", "zeffy"),
                          ("2030-03-04", "Contributions", "Individual donor", "Gift given online", "250.00", "zeffy")],
                         [(r["date"], r["category"], r["counterparty"], r["description"], r["amount"], r["method"]) for r in rows[-2:]])
        books = self.check()
        t = books.totals(2030)
        self.assertEqual(("1415.55", "430.05", "290.50"), (str(t["received"]), str(t["cash"]), str(t["in_transit"])))
        # names, emails and addresses went to the private files only
        public = (self.root / ledger.LEDGER).read_text()
        for private in ("Nora", "Quill", "quill.example", "Anytown"):
            self.assertNotIn(private, public)
        donors = (self.root / "Books" / "donors.csv").read_text()
        self.assertIn("2030-012,2030-03-04,Nora Quill,quill-nora,nora@quill.example,\"1 Quill St, Anytown, MN 55000\",250.00,cash,no,", donors)
        self.assertFalse(export.exists())
        self.assertTrue((self.root / "Books" / "zeffy" / "export-2030-03-06.xlsx").is_file())

        # the same payments in a later export are not entered again
        again = self.export([payment("03/04/2030", "5:47 PM", "250"), payment("03/03/2030", "9:05 AM", "40.5", first="Pat", last="Insider", email="pat@example.com")])
        report = "\n".join(zeffy.import_export(self.root, again, today="2030-03-08"))
        self.assertIn("No new online gifts", report)
        self.assertEqual(12, len(self.rows()))

    def test_payout_clears_the_receivable_to_the_bank(self):
        zeffy.import_export(self.root, self.export([payment("03/04/2030", "5:47 PM", "250"), payment("03/05/2030", "8:00 AM", "30")]), today="2030-03-06")
        with self.assertRaises(ValueError):
            zeffy.payout(self.root, "2030-03-10")          # Zeffy has not said it paid out yet
        later = self.export([payment("03/04/2030", "5:47 PM", "250", payout="03/10/2030"), payment("03/05/2030", "8:00 AM", "30", payout="03/10/2030"),
                             payment("03/09/2030", "1:15 PM", "15")])
        report = "\n".join(zeffy.import_export(self.root, later, today="2030-03-12"))
        self.assertIn("Paid out by Zeffy on 2030-03-10: 2 gifts, $280.00", report)
        self.assertIn("Not paid out yet: 1 gift, $15.00", report)
        report = "\n".join(zeffy.payout(self.root, "2030-03-10", posted="2030-03-11"))
        self.assertIn("Cleared the payout of $280.00", report)
        rows = self.rows()
        self.assertEqual([("Transfers", "Zeffy", "-280.00", "zeffy", ""), ("Transfers", "Sunrise Banks", "280.00", "bank", rows[-2]["id"])],
                         [(r["category"], r["counterparty"], r["amount"], r["method"], r["ref"]) for r in rows[-2:]])
        t = self.check().totals(2030)
        self.assertEqual(("1420.05", "710.05", "15.00"), (str(t["received"]), str(t["cash"]), str(t["in_transit"])))
        with self.assertRaises(ValueError):
            zeffy.payout(self.root, "2030-03-10")          # already cleared

    def test_hand_entered_payments_are_matched_not_entered(self):
        export = self.export([payment("01/06/2030", "10:00 AM", "100", method="Cheque", payout=""),
                              payment("01/20/2030", "10:05 AM", "77", method="In kind", payout="")])
        report = "\n".join(zeffy.import_export(self.root, export, today="2030-03-06"))
        self.assertIn("already in the ledger as 2030-001", report)
        self.assertIn("not matched to the ledger", report)
        self.assertEqual(10, len(self.rows()))
        key = "2030-01-20 10:05|77.00|nora@quill.example"
        self.assertIn("Matched", "\n".join(zeffy.match(self.root, key, ["2030-003"])))
        self.assertNotIn("ATTENTION", "\n".join(zeffy.status(self.root)))

    def test_refunds_failures_and_organizations_are_left_for_a_person(self):
        export = self.export([payment("03/04/2030", "5:47 PM", "250", status="Failed"),
                              payment("03/04/2030", "6:00 PM", "60", refund="60"),
                              payment("03/04/2030", "6:30 PM", "500", company="Sample Foundation")])
        report = "\n".join(zeffy.import_export(self.root, export, today="2030-03-06"))
        self.assertEqual(3, report.count("ATTENTION: Not entered"))
        self.assertEqual(10, len(self.rows()))

    def test_something_that_is_not_a_zeffy_export_is_refused(self):
        with zipfile.ZipFile(self.root / "other.xlsx", "w") as z:
            z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="str"><v>Name</v></c></row></sheetData></worksheet>')
        with self.assertRaises(ValueError):
            zeffy.import_export(self.root, self.root / "other.xlsx", today="2030-03-06")


if __name__ == "__main__":
    unittest.main()
