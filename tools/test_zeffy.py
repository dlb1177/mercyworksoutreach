"""Tests for tools/zeffy.py and for entering rows with ledger.add_rows.

Run from the repo root:  python3 -m unittest tools/test_zeffy.py

Each test copies the made-up clean ledger in tools/fixtures/clean/ to a temp
folder and writes a small made-up Zeffy feed there.
"""

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger  # noqa: E402
import zeffy   # noqa: E402

TRACKED = ["financials/general-ledger.csv", "financials/zeffy-log.csv"]


def when(day, clock="12:00"):
    """Unix time of a day and time in the organization's time zone."""
    return int(datetime.strptime(day + " " + clock, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(zeffy.TIMEZONE)).timestamp())


def payment(pid, day, dollars, clock="12:00", type="online", method="card", status="succeeded",
            refunded=0, disputed=False, giver="individual", payout=""):
    return {"id": "pay-%s-0000" % pid, "created": when(day, clock), "amount_cents": int(round(dollars * 100)), "currency": "usd",
            "type": type, "method": method, "status": status, "refunded_cents": int(round(refunded * 100)),
            "disputed": disputed, "from": giver, "payout_date": payout}


class ZeffyTests(unittest.TestCase):

    def setUp(self):
        self._insiders = ledger.INSIDERS
        ledger.INSIDERS = ["Pat Insider"]
        self.root = Path(tempfile.mkdtemp(prefix="zeffy-test-"))
        self.out = Path(tempfile.mkdtemp(prefix="zeffy-feed-"))
        shutil.copytree(HERE / "fixtures" / "clean", self.root, dirs_exist_ok=True)
        (self.root / "gitignore.txt").rename(self.root / ".gitignore")
        (self.root / "Books").mkdir()
        (self.root / "books_donors.csv").rename(self.root / "Books" / "donors.csv")

    def tearDown(self):
        ledger.INSIDERS = self._insiders
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.out, ignore_errors=True)

    def check(self):
        books = ledger.run_check(self.root, tracked=TRACKED)
        self.assertEqual([], [str(p) for p in books.problems])
        return books

    def rows(self):
        with open(self.root / ledger.LEDGER, newline="") as f:
            return list(csv.DictReader(f))

    def log(self):
        return zeffy.read_log(self.root)

    def feed(self, payments, raw=None):
        path = self.out / "feed.json"
        path.write_text(json.dumps(raw if raw is not None else {"payments": payments}))
        return path

    def sync(self, payments, today="2030-03-06"):
        res = zeffy.sync(self.root, self.feed(payments), today=today)
        return res, "\n".join(res.lines + ["ATTENTION: " + a for a in res.attention])

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

    # ---- the hourly sync ----

    def test_sync_enters_new_online_gifts_once(self):
        gifts = [payment("a", "2030-03-04", 250, clock="17:47"), payment("b", "2030-03-03", 40.5, giver="director")]
        res, report = self.sync(gifts)
        self.assertIn("entered as 2030-011 (Donor)", report)
        self.assertIn("entered as 2030-012 (Individual donor)", report)
        self.assertEqual(["2030-011", "2030-012"], res.entered)
        rows = self.rows()
        self.assertEqual([("2030-03-03", "Contributions", "Donor", "Gift given online", "40.50", "zeffy"),
                          ("2030-03-04", "Contributions", "Individual donor", "Gift given online", "250.00", "zeffy")],
                         [(r["date"], r["category"], r["counterparty"], r["description"], r["amount"], r["method"]) for r in rows[-2:]])
        t = self.check().totals(2030)
        self.assertEqual(("1415.55", "430.05", "290.50"), (str(t["received"]), str(t["cash"]), str(t["in_transit"])))
        # Zeffy's own payment id is never kept, only its fingerprint
        public = (self.root / zeffy.LOG).read_text() + (self.root / ledger.LEDGER).read_text()
        self.assertNotIn("pay-a", public)
        self.assertRegex(self.log()[0]["fingerprint"], r"^[a-p]{20}$")

        # the same payments an hour later are not entered again, and nothing is rewritten
        res, report = self.sync(gifts, today="2030-03-08")
        self.assertFalse(res.changed)
        self.assertIn("Nothing new from Zeffy.", report)
        self.assertEqual(12, len(self.rows()))

    def test_the_date_is_the_local_day_not_the_utc_day(self):
        self.sync([payment("a", "2030-03-04", 10, clock="23:30")])      # already March 5 in UTC
        self.assertEqual("2030-03-04", self.rows()[-1]["date"])

    def test_a_processing_payment_waits_until_it_succeeds(self):
        res, report = self.sync([payment("a", "2030-03-04", 75, status="pending")])
        self.assertIn("Still processing", report)
        self.assertFalse(res.changed)
        self.assertEqual([], self.log())
        res, report = self.sync([payment("a", "2030-03-04", 75)], today="2030-03-07")
        self.assertIn("entered as 2030-011", report)

    def test_payout_is_noted_by_sync_and_cleared_by_a_person(self):
        self.sync([payment("a", "2030-03-04", 250), payment("b", "2030-03-05", 30)])
        with self.assertRaises(ValueError):
            zeffy.payout(self.root, "2030-03-10")          # Zeffy has not said it paid out yet
        res, report = self.sync([payment("a", "2030-03-04", 250, payout="2030-03-10"), payment("b", "2030-03-05", 30, payout="2030-03-10"),
                                 payment("c", "2030-03-09", 15)], today="2030-03-12")
        self.assertEqual(2, report.count("Paid out by Zeffy on 2030-03-10"))
        self.assertEqual(13, len(self.rows()))             # sync never enters the transfer itself
        status = "\n".join(zeffy.status(self.root))
        self.assertIn("Paid out by Zeffy on 2030-03-10: 2 gifts, $280.00", status)
        self.assertIn("Not paid out yet: 1 gift, $15.00", status)
        with self.assertRaises(ValueError):
            zeffy.payout(self.root, "2030-03-10", posted="2030-03-11", amount="270.00")   # the deposit does not agree
        report = "\n".join(zeffy.payout(self.root, "2030-03-10", posted="2030-03-11", amount="280.00"))
        self.assertIn("Cleared the payout of $280.00", report)
        rows = self.rows()
        self.assertEqual([("Transfers", "Zeffy", "-280.00", "zeffy", ""), ("Transfers", "Sunrise Banks", "280.00", "bank", rows[-2]["id"])],
                         [(r["category"], r["counterparty"], r["amount"], r["method"], r["ref"]) for r in rows[-2:]])
        t = self.check().totals(2030)
        self.assertEqual(("1420.05", "710.05", "15.00"), (str(t["received"]), str(t["cash"]), str(t["in_transit"])))
        with self.assertRaises(ValueError):
            zeffy.payout(self.root, "2030-03-10")          # already cleared
        self.assertNotIn("ATTENTION", "\n".join(zeffy.status(self.root)))

    def test_sync_refuses_when_the_log_is_behind_the_ledger(self):
        """If the ledger has online gifts the log does not know, a gift could be entered twice."""
        gifts = [payment("a", "2030-03-04", 250)]
        self.sync(gifts)
        (self.root / zeffy.LOG).unlink()
        with self.assertRaises(ValueError):
            zeffy.sync(self.root, self.feed(gifts), today="2030-03-08")
        with self.assertRaises(ValueError):
            zeffy.payout(self.root, "2030-03-10")
        self.assertEqual(11, len(self.rows()))

    def test_hand_entered_payments_are_tied_to_the_ledger_not_entered(self):
        by_hand = [payment("a", "2030-01-06", 100, type="manual", method="cheque"),
                   payment("b", "2030-03-03", 77, type="manual", method="cash")]
        res, report = self.sync(by_hand)
        self.assertIn("already in the ledger as 2030-001", report)
        self.assertEqual(1, len(res.attention))
        self.assertIn("not yet in the ledger", report)
        self.assertEqual(10, len(self.rows()))
        # an hour later it is not flagged again
        res, _ = self.sync(by_hand, today="2030-03-07")
        self.assertEqual(([], False), (res.attention, res.changed))
        # once the deposit is in the ledger, the next run ties them together by itself
        ledger.add_rows(self.root, [{"date": "2030-03-05", "category": "Contributions", "counterparty": "Individual donor",
                                     "description": "Gift in cash, deposited", "amount": "77.00", "method": "bank"}])
        res, report = self.sync(by_hand, today="2030-03-08")
        self.assertIn("already in the ledger as 2030-011", report)
        self.assertNotIn("ATTENTION", "\n".join(zeffy.status(self.root)))
        self.assertEqual(11, len(self.rows()))

    def test_match_ties_a_payment_to_several_rows(self):
        self.sync([payment("a", "2030-01-20", 55, type="manual", method="inKind")])
        fp = self.log()[0]["fingerprint"]
        with self.assertRaises(ValueError):
            zeffy.match(self.root, fp[:8], ["2030-099"])
        self.assertIn("Tied", "\n".join(zeffy.match(self.root, fp[:8], ["2030-001", "2030-003"])))
        self.assertEqual(("2030-001 2030-003", ""), (self.log()[0]["ledger_ids"], self.log()[0]["waiting_on"]))

    def test_refunds_failures_and_organizations_are_left_for_a_person(self):
        odd = [payment("a", "2030-03-04", 250, status="failed"),
               payment("b", "2030-03-04", 60, refunded=60),
               payment("c", "2030-03-04", 500, giver="organization"),
               payment("d", "2030-03-04", 45, disputed=True),
               payment("e", "2030-02-27", 20)]                       # February is closed
        res, report = self.sync(odd)
        self.assertEqual(5, len(res.attention))
        self.assertEqual(10, len(self.rows()))
        self.check()
        res, _ = self.sync(odd, today="2030-03-07")                  # flagged once, not every hour
        self.assertEqual(([], False), (res.attention, res.changed))
        # the organization's gift is entered once a person has chosen its label
        fp = [e for e in self.log() if e["waiting_on"] == "label"][0]["fingerprint"]
        with self.assertRaises(ValueError):
            zeffy.enter(self.root, fp, "Sample Foundation")
        self.assertIn("(Foundation)", "\n".join(zeffy.enter(self.root, fp, "Foundation")))
        self.assertEqual(("Foundation", "500.00", "zeffy"), tuple(self.rows()[-1][c] for c in ("counterparty", "amount", "method")))
        self.check()

    def test_a_refund_after_entry_is_flagged_once_and_not_changed(self):
        self.sync([payment("a", "2030-03-04", 250)])
        res, report = self.sync([payment("a", "2030-03-04", 250, refunded=250)], today="2030-03-09")
        self.assertIn("needs a correcting entry by a person", report)
        self.assertEqual(11, len(self.rows()))
        res, _ = self.sync([payment("a", "2030-03-04", 250, refunded=250)], today="2030-03-10")
        self.assertEqual([], res.attention)
        with self.assertRaises(ValueError):
            zeffy.payout(self.root, "2030-03-10")

    def test_a_feed_with_private_details_is_refused(self):
        with_name = dict(payment("a", "2030-03-04", 250), first_name="Nora")
        with_email = dict(payment("b", "2030-03-04", 250), method="nora@quill.example")
        euros = dict(payment("c", "2030-03-04", 250), currency="eur")
        for bad in (with_name, with_email, euros):
            with self.assertRaises(ValueError):
                zeffy.sync(self.root, self.feed([bad]))
        with self.assertRaises(ValueError):
            zeffy.sync(self.root, self.feed(None, raw={"payments": [], "donors": ["Nora Quill"]}))
        with self.assertRaises(ValueError):
            zeffy.sync(self.root, self.out / "missing.json")
        self.assertEqual(10, len(self.rows()))
        self.assertFalse((self.root / zeffy.LOG).exists())

    # ---- the whole hourly run ----

    def git(self, *args):
        done = subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@test.invalid"] + list(args),
                              capture_output=True, text=True)
        self.assertEqual(0, done.returncode, done.stderr)
        return done.stdout

    def repo(self):
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "start")

    def test_hourly_run_builds_the_pages_and_changes_only_what_it_may(self):
        self.repo()
        lines, result = zeffy.hourly(self.root, self.feed([]), today="2030-03-06", run_tests=False, check_push=False)
        self.assertEqual(("nothing-new", ""), (result, self.git("status", "--porcelain")))
        self.assertIn("Read 0 payments from Zeffy.", lines)
        self.assertFalse((self.out / "feed.json").exists())          # the feed is deleted whatever happens
        lines, result = zeffy.hourly(self.root, self.feed([payment("a", "2030-03-04", 250)]), today="2030-03-06", run_tests=False, check_push=False)
        self.assertEqual("ready", result)
        self.assertIn("COMMIT MESSAGE: Zeffy sync: 1 online gift entered (2030-011)", lines)
        changed = zeffy.changed_files(self.root)
        self.assertIn("financials/general-ledger.csv", changed)
        self.assertIn("financials/zeffy-log.csv", changed)
        self.assertIn("financials/ledger.html", changed)
        self.assertEqual([], [f for f in changed if not zeffy.HOURLY_MAY_CHANGE.match(f)])
        self.assertIn("250.00", (self.root / "financials" / "ledger.html").read_text())

    def test_hourly_run_stops_and_puts_everything_back(self):
        self.repo()
        # a working copy that already has changes
        (self.root / "index.html").write_text("stray")
        lines, result = zeffy.hourly(self.root, self.feed([payment("a", "2030-03-04", 250)]), today="2030-03-06", run_tests=False, check_push=False)
        self.assertEqual("stopped", result)
        (self.root / "index.html").unlink()
        self.assertFalse((self.out / "feed.json").exists())
        # a session that may not push: the practice push fails (this test repo has nowhere to push to)
        lines, result = zeffy.hourly(self.root, self.feed([payment("a", "2030-03-04", 250)]), today="2030-03-06", run_tests=False)
        self.assertEqual(("stopped", ""), (result, self.git("status", "--porcelain")))
        self.assertIn("cannot push to main", "\n".join(lines))
        # a feed the script refuses
        lines, result = zeffy.hourly(self.root, self.feed([dict(payment("a", "2030-03-04", 250), email="x")]), today="2030-03-06", run_tests=False, check_push=False)
        self.assertEqual(("stopped", ""), (result, self.git("status", "--porcelain")))
        # books that do not pass the check after the sync: everything is put back
        ledger.INSIDERS = ["Individual donor"]
        lines, result = zeffy.hourly(self.root, self.feed([payment("a", "2030-03-04", 250)]), today="2030-03-06", run_tests=False, check_push=False)
        self.assertEqual(("stopped", ""), (result, self.git("status", "--porcelain")))
        self.assertEqual(10, len(self.rows()))


if __name__ == "__main__":
    unittest.main()
