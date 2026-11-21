#!/usr/bin/env python3
"""Mercy Works Outreach: keep the books in step with Zeffy.

Zeffy is the online donation platform and the organization's record of who gave.
Once an hour a scheduled session reads Zeffy, writes down a few facts about each
payment that are not private (the "feed"), and hands them to this script. The
script enters what is new. It uses only the Python 3 standard library.

    python3 tools/zeffy.py hourly <feed.json>    the whole hourly run: a practice push, tests,
                                                 sync, check, build, a last look at what
                                                 changed; it deletes the feed when done
    python3 tools/zeffy.py sync <feed.json>      only enter what is new in the feed
    python3 tools/zeffy.py status                what Zeffy still owes, and anything open
    python3 tools/zeffy.py payout YYYY-MM-DD [--posted YYYY-MM-DD] [--amount 0.00]
                                                 a payout has reached the bank: clear it
    python3 tools/zeffy.py match <fingerprint> <ledger ids>
                                                 say which ledger rows a payment is recorded as
    python3 tools/zeffy.py enter <fingerprint> "<label>"
                                                 enter a waiting online gift under a public label

How a gift moves through the books
  1. Given online. sync enters it in the general ledger on the day it was given,
     as a Contributions row with method zeffy. From then on it is a payout
     receivable: part of the balance, not yet cash in the bank.
  2. Paid out. A later feed carries the payout date. sync records it and says
     which payout to look for on the bank statement.
  3. Cleared. When the bank statement shows the deposit, payout enters a pair of
     Transfers rows (out of Zeffy, into the bank). The receivable goes down and the
     cash in the bank goes up by the same amount. This step is done by a person at
     the monthly close, never by the hourly run, so the date is the bank's date.

Payments entered into Zeffy by hand (a cheque, cash, a gift in kind) never pass
through Zeffy, so they are not entered from the feed: they reach the books the
usual way, from the deposit slip or the receipt. sync ties each one to its ledger
row when the amount and date make that unambiguous, and says so if it cannot.

Left for a person, and reported once with "ATTENTION": refunds, failed and
disputed payments, gifts from an organization (which need a public label), and
anything dated in a closed month.

The feed
  A JSON file written outside the repo; hourly deletes it when it finishes:
    {"payments": [{"id": "...", "created": 1795218477, "amount_cents": 25000,
                   "currency": "usd", "type": "online", "method": "card",
                   "status": "succeeded", "refunded_cents": 0, "disputed": false,
                   "from": "individual", "payout_date": ""}]}
  id            Zeffy's own payment id. It is used only to make the fingerprint.
  created       the payment's Unix time, copied as it is. The script works out the
                date in the organization's time zone.
  type          online, manual or imported, as Zeffy gives it.
  status        succeeded, failed or pending, as Zeffy gives it.
  from          director, individual or organization. The session compares the
                giver's name with the directors and writes only this word.
  payout_date   the day Zeffy paid the gift out (YYYY-MM-DD), or "" if not yet.
  Any other field, and anything that looks like an email address, is refused, so
  a name or an address cannot reach the books by mistake.

What is public and what is private
  Everything this script keeps is public. The ledger row says only "Donor" (a
  director) or "Individual donor", the date and the amount. financials/zeffy-log.csv
  is how sync knows what it has already entered: one line per payment with a
  fingerprint, the date, the amount, how it was paid, and where it stands. The
  fingerprint is a one-way scramble of Zeffy's payment id; it cannot be turned back
  into the id. Names, email addresses and home addresses stay in Zeffy and are
  never written here.
"""

import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger  # noqa: E402

LOG = "financials/zeffy-log.csv"
LOG_COLS = ["fingerprint", "date", "amount", "kind", "method", "status", "refund", "payout_date",
            "ledger_ids", "cleared_ids", "waiting_on", "first_seen"]
TIMEZONE = "America/Chicago"
FEED_KEYS = {"id", "created", "amount_cents", "currency", "type", "method", "status",
             "refunded_cents", "disputed", "from", "payout_date"}
TYPES = ("online", "manual", "imported")
STATUSES = ("succeeded", "failed", "pending")
GIVERS = ("director", "individual", "organization")
LABELS = [g for g in ledger.GENERIC_DONORS if g != "Director"]
ZERO = Decimal("0.00")
# The only files an hourly run may change. Anything else stops the run.
HOURLY_MAY_CHANGE = re.compile(r"^(financials/general-ledger\.csv|financials/zeffy-log\.csv|financials/[^/]+\.html|inventory/[^/]+\.html)$")


# ---------- the feed ----------

def fingerprint(payment_id):
    """A one-way scramble of Zeffy's payment id, in letters only.

    Letters only, so the privacy scan never mistakes it for an account number.
    """
    digest = hashlib.sha256(("zeffy-payment:" + payment_id.strip().lower()).encode("utf-8")).hexdigest()[:20]
    return digest.translate(str.maketrans("0123456789abcdef", "ghijklmnopabcdef"))


def cents(n):
    return str((Decimal(n) / 100).quantize(Decimal("0.01")))


def read_feed(path):
    """The feed's payments, checked and tidied. Refuses anything it does not expect."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError("Cannot read the feed %s: %s" % (path, e))
    if not isinstance(data, dict) or not isinstance(data.get("payments"), list) or set(data) - {"payments"}:
        raise ValueError('The feed must be {"payments": [...]} and nothing else.')
    out, seen = [], set()
    for n, p in enumerate(data["payments"], start=1):
        where = "Payment %d in the feed" % n
        if not isinstance(p, dict):
            raise ValueError("%s is not an object." % where)
        extra = sorted(set(p) - FEED_KEYS)
        if extra:
            raise ValueError("%s has fields the books must never see (%s). Nothing was entered. "
                             "The feed carries only: %s." % (where, ", ".join(extra), ", ".join(sorted(FEED_KEYS))))
        missing = sorted(FEED_KEYS - set(p))
        if missing:
            raise ValueError("%s is missing: %s." % (where, ", ".join(missing)))
        if any(isinstance(v, str) and "@" in v for v in p.values()):
            raise ValueError("%s contains what looks like an email address. Nothing was entered." % where)
        if not isinstance(p["id"], str) or not re.match(r"^[A-Za-z0-9_-]{8,80}$", p["id"]):
            raise ValueError("%s: the id is not a Zeffy payment id." % where)
        for key in ("created", "amount_cents", "refunded_cents"):
            if not isinstance(p[key], int) or isinstance(p[key], bool) or p[key] < 0:
                raise ValueError("%s: %s must be a whole number, zero or more." % (where, key))
        if str(p["currency"]).lower() != "usd":
            raise ValueError("%s is not in US dollars. Nothing was entered." % where)
        if p["type"] not in TYPES or p["status"] not in STATUSES or p["from"] not in GIVERS:
            raise ValueError("%s: type must be one of %s, status one of %s, and from one of %s."
                             % (where, ", ".join(TYPES), ", ".join(STATUSES), ", ".join(GIVERS)))
        if not isinstance(p["method"], str) or not re.match(r"^[A-Za-z]{1,30}$", p["method"]):
            raise ValueError("%s: method must be one word, such as card or cheque." % where)
        if not isinstance(p["disputed"], bool):
            raise ValueError("%s: disputed must be true or false." % where)
        if p["payout_date"] != "" and ledger.parse_date(p["payout_date"]) is None:
            raise ValueError('%s: payout_date must be YYYY-MM-DD or "".' % where)
        if p["refunded_cents"] > p["amount_cents"]:
            raise ValueError("%s: more was refunded than was given." % where)
        fp = fingerprint(p["id"])
        if fp in seen:
            raise ValueError("%s appears twice in the feed." % where)
        seen.add(fp)
        out.append({
            "fingerprint": fp,
            "created": p["created"],
            "date": datetime.fromtimestamp(p["created"], ZoneInfo(TIMEZONE)).date().isoformat(),
            "amount": cents(p["amount_cents"]),
            "kind": "online" if p["type"] == "online" else "manual",
            "method": p["method"],
            "status": "disputed" if p["disputed"] else p["status"],
            "refund": cents(p["refunded_cents"]),
            "from": p["from"],
            "payout_date": p["payout_date"],
        })
    out.sort(key=lambda p: (p["created"], p["fingerprint"]))
    return out


# ---------- the log ----------

def read_log(root):
    path = Path(root) / LOG
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != LOG_COLS:
            raise ValueError("%s does not have the expected header." % LOG)
        return [{c: r.get(c, "") or "" for c in LOG_COLS} for r in reader]


def write_log(root, log):
    path = Path(root) / LOG
    log.sort(key=lambda e: (e["date"], e["first_seen"], e["fingerprint"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(LOG_COLS)
        w.writerows([[e[c] for c in LOG_COLS] for e in log])


def ledger_rows(root):
    with open(Path(root) / ledger.LEDGER, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def closed_month(root):
    recs = Path(root) / "financials" / "reconciliations.csv"
    if not recs.is_file():
        return ""
    with open(recs, newline="", encoding="utf-8") as f:
        return max([r["month"] for r in csv.DictReader(f)] or [""])


def require_log(root, log):
    """Stop if the ledger has online gifts the log does not know about.

    The log is how sync knows what it has already entered. If the two disagree,
    entering anything could put a gift in the books twice.
    """
    logged = {i for e in log for i in (e["ledger_ids"] + " " + e["cleared_ids"]).split()}
    unknown = [r["id"] for r in ledger_rows(root) if r["method"] == "zeffy" and r["id"] not in logged]
    if unknown:
        raise ValueError("The ledger has Zeffy rows (%s) that %s does not know about, so nothing was entered. "
                         "Find out how they were entered, then tie each to its payment with: "
                         "python3 tools/zeffy.py match <fingerprint> <ledger ids>" % (", ".join(unknown), LOG))


def open_amount(e):
    """How much of this payment the ledger should still show as owed by Zeffy."""
    if e["kind"] != "online" or not e["ledger_ids"] or e["cleared_ids"]:
        return ZERO
    if e["waiting_on"] == "person":
        return Decimal(e["amount"])            # the correcting entry has not been made yet
    if e["status"] != "succeeded":
        return ZERO
    return Decimal(e["amount"]) - Decimal(e["refund"] or "0")


def what(e):
    return "$%s payment on %s (%s)" % (e["amount"], e["date"], e["method"])


def find(log, text):
    """The one log entry whose fingerprint starts with text."""
    hits = [e for e in log if e["fingerprint"].startswith(text)] if len(text) >= 6 else []
    if len(hits) != 1:
        raise ValueError('"%s" does not pick out one payment in %s. Use the fingerprint shown by: python3 tools/zeffy.py status' % (text, LOG))
    return hits[0]


# ---------- sync ----------

class Result:
    def __init__(self):
        self.lines, self.attention, self.entered, self.changed, self.seen = [], [], [], False, 0


def sync(root, feed, today=None):
    """Enter what is new in the feed. Returns a Result."""
    root = Path(root)
    today = today or date.today().isoformat()
    payments = read_feed(feed)
    log = read_log(root)
    before = [dict(e) for e in log]
    require_log(root, log)
    known = {e["fingerprint"]: e for e in log}
    res = Result()
    res.seen = len(payments)
    closed = closed_month(root)
    matched = {i for e in log for i in e["ledger_ids"].split()}
    to_enter = []

    def wait(e, reason, message):
        if e["waiting_on"] != reason:
            e["waiting_on"] = reason
            res.attention.append(message)

    for p in payments:
        e = known.get(p["fingerprint"])
        if e is None:
            if p["amount"] == "0.00":
                continue
            if p["status"] == "pending":
                res.lines.append("Still processing at Zeffy, not entered yet: a %s." % what(p))
                continue
            e = {c: p.get(c, "") for c in LOG_COLS}
            e.update(ledger_ids="", cleared_ids="", waiting_on="", first_seen=today, payout_date="")
            log.append(e)
            known[e["fingerprint"]] = e
            if p["status"] != "succeeded":
                res.attention.append("Not entered: a %s shows as %s at Zeffy. Nothing needs doing unless the donor expected it to go through." % (what(p), p["status"]))
        else:
            if (p["amount"], p["date"]) != (e["amount"], e["date"]):
                wait(e, "person", "The %s (ledger %s) now shows as $%s on %s in Zeffy. It needs a person to look."
                     % (what(e), e["ledger_ids"] or "not entered", p["amount"], p["date"]))
            elif (p["status"], p["refund"]) != (e["status"], e["refund"]):
                e["status"], e["refund"] = p["status"], p["refund"]
                if e["ledger_ids"] and e["kind"] == "online" and (p["status"] != "succeeded" or Decimal(p["refund"]) != 0):
                    wait(e, "person", "The %s (ledger %s) now shows status %s and $%s refunded. It needs a correcting entry by a person."
                         % (what(e), e["ledger_ids"], p["status"], p["refund"]))
            e["method"] = p["method"]

        if p["payout_date"] and p["payout_date"] != e["payout_date"]:
            e["payout_date"] = p["payout_date"]
            if e["kind"] == "online" and e["ledger_ids"]:
                res.lines.append("Paid out by Zeffy on %s: the %s (ledger %s)." % (p["payout_date"], what(e), e["ledger_ids"]))

        if e["ledger_ids"] or e["waiting_on"] in ("person", "label") or e["status"] != "succeeded":
            continue
        if e["kind"] == "manual":
            # Entered into Zeffy by hand, so it never passes through Zeffy. Is it already in the ledger?
            close = [r for r in ledger_rows(root)
                     if r["category"] in ledger.GIFT_CATEGORIES and r["method"] != "zeffy" and r["amount"] == e["amount"]
                     and r["id"] not in matched and abs((date.fromisoformat(r["date"]) - date.fromisoformat(e["date"])).days) <= 5]
            if len(close) == 1:
                e["ledger_ids"], e["waiting_on"] = close[0]["id"], ""
                matched.add(close[0]["id"])
                res.lines.append("Entered in Zeffy by hand, already in the ledger as %s: the %s." % (close[0]["id"], what(e)))
            else:
                wait(e, "deposit", "Entered in Zeffy by hand and not yet in the ledger: a %s. It reaches the books from the deposit slip or receipt. "
                     "If it is already recorded, run: python3 tools/zeffy.py match %s <ledger ids>" % (what(e), e["fingerprint"][:8]))
            continue
        if Decimal(e["refund"]) != 0:
            wait(e, "person", "Not entered: a %s with $%s refunded before it reached the books. It needs a person to enter what was kept." % (what(e), e["refund"]))
        elif p["from"] == "organization":
            wait(e, "label", 'Not entered: a %s from an organization. Choose its public label, then run: python3 tools/zeffy.py enter %s "Foundation"'
                 % (what(e), e["fingerprint"][:8]))
        elif e["date"][:7] <= closed:
            wait(e, "person", "Not entered: a %s is dated in %s, which is closed. It needs a person." % (what(e), e["date"][:7]))
        else:
            to_enter.append((e, "Donor" if p["from"] == "director" else "Individual donor"))

    if to_enter:
        ids = ledger.add_rows(root, [{"date": e["date"], "category": "Contributions", "counterparty": label,
                                      "description": "Gift given online", "amount": e["amount"], "method": "zeffy"} for e, label in to_enter])
        for (e, label), lid in zip(to_enter, ids):
            e["ledger_ids"] = lid
            res.entered.append(lid)
            res.lines.append("New: online gift of $%s on %s, entered as %s (%s)." % (e["amount"], e["date"], lid, label))
    if log != before:
        write_log(root, log)
    res.changed = bool(to_enter) or log != before
    if not res.changed:
        res.lines.append("Nothing new from Zeffy.")
    return res


# ---------- status, payout, match, enter ----------

def count(group):
    return "1 gift" if len(group) == 1 else "%d gifts" % len(group)


def status(root):
    root = Path(root)
    log = read_log(root)
    owed = sum((Decimal(r["amount"]) for r in ledger_rows(root) if r["method"] == "zeffy"), ZERO)
    open_ = [e for e in log if open_amount(e) != 0]
    logged = sum((open_amount(e) for e in open_), ZERO)
    lines = ["Payout receivable in the ledger (given through Zeffy, not yet cleared to the bank): $%s" % owed]
    if logged != owed:
        lines.append("ATTENTION: the Zeffy log says $%s is open, which does not match the ledger." % logged)
    upcoming = [e for e in open_ if not e["payout_date"]]
    if upcoming:
        lines.append("  Not paid out yet: %s, $%s" % (count(upcoming), sum(open_amount(e) for e in upcoming)))
    for day in sorted({e["payout_date"] for e in open_ if e["payout_date"]}):
        group = [e for e in open_ if e["payout_date"] == day]
        lines.append("  Paid out by Zeffy on %s: %s, $%s. When that deposit is on the bank statement, run: python3 tools/zeffy.py payout %s"
                     % (day, count(group), sum(open_amount(e) for e in group), day))
    waiting = {"deposit": "entered in Zeffy by hand, not yet in the ledger",
               "label": "from an organization, needs a public label",
               "person": "needs a person to look"}
    for e in log:
        if e["waiting_on"]:
            lines.append("ATTENTION: %s: a %s (status %s, refunded $%s, ledger %s). Fingerprint %s"
                         % (waiting.get(e["waiting_on"], e["waiting_on"]), what(e), e["status"], e["refund"], e["ledger_ids"] or "none", e["fingerprint"][:8]))
    return lines


def payout(root, day, posted=None, amount=None):
    """A Zeffy payout has reached the bank: move it from the receivable to the bank."""
    root = Path(root)
    posted = posted or day
    log = read_log(root)
    require_log(root, log)
    group = [e for e in log if e["payout_date"] == day and open_amount(e) != 0]
    if not group:
        raise ValueError("The Zeffy log has no uncleared gifts with payout date %s." % day)
    held = [e for e in group if e["waiting_on"]]
    if held:
        raise ValueError("A gift in this payout is waiting on a person (%s). Settle it first; see: python3 tools/zeffy.py status" % what(held[0]))
    total = sum(open_amount(e) for e in group)
    if amount is not None and Decimal(amount) != total:
        raise ValueError("The books expect a payout of $%s for %s, but the deposit is $%s. Nothing was entered. Find the difference first." % (total, day, amount))
    n = len(group)
    ids = ledger.add_rows(root, [
        {"date": posted, "category": "Transfers", "counterparty": "Zeffy", "amount": str(-total), "method": "zeffy",
         "description": "Payout of %d online %s sent to the bank" % (n, "gift" if n == 1 else "gifts")},
        {"date": posted, "category": "Transfers", "counterparty": "Sunrise Banks", "amount": str(total), "method": "bank",
         "description": "Payout of %d online %s received from Zeffy" % (n, "gift" if n == 1 else "gifts"), "ref": "@0"},
    ])
    for e in group:
        e["cleared_ids"] = " ".join(ids)
    write_log(root, log)
    return ["Cleared the payout of $%s (%s, paid out %s, posted %s) as %s and %s." % (total, count(group), day, posted, ids[0], ids[1])] + status(root)


def match(root, text, ids):
    """Say which ledger rows a payment is recorded as. Nothing is waiting on it afterwards."""
    root = Path(root)
    log = read_log(root)
    e = find(log, text)
    have = {r["id"] for r in ledger_rows(root)}
    missing = [i for i in ids if i not in have]
    if missing:
        raise ValueError("Not in the ledger: " + ", ".join(missing))
    e["ledger_ids"], e["waiting_on"] = " ".join(ids), ""
    write_log(root, log)
    return ["Tied the %s to %s." % (what(e), e["ledger_ids"])]


def enter(root, text, label):
    """Enter an online gift that was waiting for a public label."""
    root = Path(root)
    log = read_log(root)
    require_log(root, log)
    e = find(log, text)
    if label not in LABELS:
        raise ValueError("The label must be one of: %s." % ", ".join(LABELS))
    if e["kind"] != "online" or e["ledger_ids"] or e["status"] != "succeeded" or Decimal(e["refund"]) != 0:
        raise ValueError("Only an online gift that succeeded, was not refunded and is not in the ledger yet can be entered this way.")
    lid = ledger.add_rows(root, [{"date": e["date"], "category": "Contributions", "counterparty": label,
                                  "description": "Gift given online", "amount": e["amount"], "method": "zeffy"}])[0]
    e["ledger_ids"], e["waiting_on"] = lid, ""
    write_log(root, log)
    return ["Entered the %s as %s (%s)." % (what(e), lid, label)]


# ---------- the hourly run ----------

def git(root, *args):
    return subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, text=True)


def changed_files(root):
    out = git(root, "status", "--porcelain", "--untracked-files=all")
    if out.returncode != 0:
        raise ValueError("Could not ask git what changed: %s" % out.stderr.strip())
    return [line[3:].split(" -> ")[-1].strip('"') for line in out.stdout.splitlines() if line.strip()]


def hourly(root, feed, today=None, run_tests=True, check_push=True):
    """The whole hourly run. Returns (lines, result) where result is nothing-new, ready or stopped.

    It never commits or pushes; the session does that, and only on "ready".
    On "stopped" every file is put back as it was. The feed is deleted whatever happens.
    """
    try:
        return hourly_run(Path(root), feed, today, run_tests, check_push)
    finally:
        Path(feed).unlink(missing_ok=True)


def hourly_run(root, feed, today, run_tests, check_push):
    lines = []

    def stop(why):
        # The run started from a clean working copy, so whatever differs now is its own doing.
        git(root, "checkout", "--", ".")
        for name in changed_files(root):
            (root / name).unlink(missing_ok=True)
        return lines + ["STOPPED: " + why, "Nothing was changed. Do not commit or push."], "stopped"

    try:
        if changed_files(root):
            return lines + ["STOPPED: the working copy already has changes, so the hourly run did not start.",
                            "Nothing was changed. Do not commit or push."], "stopped"
        if check_push:
            # A practice push that sends nothing. It fails if this session may not push to main,
            # so that is found out now and not on the day a gift arrives.
            practice = git(root, "push", "--dry-run", "origin", "HEAD:main")
            if practice.returncode != 0:
                return stop("this session cannot push to main, so a new gift could not be published.\n" + practice.stderr.strip()[-1000:])
        if run_tests:
            t = subprocess.run([sys.executable, "-m", "unittest", "tools/test_ledger.py", "tools/test_zeffy.py"],
                               cwd=str(root), capture_output=True, text=True)
            if t.returncode != 0:
                return stop("the tests did not pass.\n" + t.stderr[-2000:])
        res = sync(root, feed, today)
        lines += res.lines + ["ATTENTION: " + a for a in res.attention]
        health = "Read %d %s from Zeffy.%s" % (res.seen, "payment" if res.seen == 1 else "payments",
                                               " Push access to main confirmed." if check_push else "")
        if not res.changed:
            return lines + [health], "nothing-new"
        books, blocking, _ = ledger.build(root)
        if blocking:
            return stop("the books did not pass the check after the sync:\n" + "\n".join(str(p) for p in blocking))
        stray = [f for f in changed_files(root) if not HOURLY_MAY_CHANGE.match(f)]
        if stray:
            return stop("files changed that an hourly run must never touch: " + ", ".join(stray))
        lines += status(root) + [health]
        parts = []
        if res.entered:
            parts.append("%d online %s entered (%s)" % (len(res.entered), "gift" if len(res.entered) == 1 else "gifts", ", ".join(res.entered)))
        if any(l.startswith("Paid out") for l in res.lines):
            parts.append("payout recorded")
        if res.attention:
            parts.append("%d for a person" % len(res.attention))
        lines.append("COMMIT MESSAGE: Zeffy sync: " + ("; ".join(parts) or "log updated"))
        return lines, "ready"
    except ValueError as e:
        return stop(str(e))


def main(argv):
    root = Path(__file__).resolve().parent.parent
    cmd = argv[1] if len(argv) > 1 else ""

    def option(name):
        return argv[argv.index(name) + 1] if name in argv else None
    try:
        if cmd == "hourly" and len(argv) == 3:
            lines, result = hourly(root, Path(argv[2]))
            print("\n".join(lines))
            notify = result == "stopped" or any(l.startswith(("New:", "Paid out", "ATTENTION")) for l in lines)
            print("\nRESULT: %s\nNOTIFY: %s" % (result, "yes" if notify else "no"))
            return 1 if result == "stopped" else 0
        if cmd == "sync" and len(argv) == 3:
            res = sync(root, Path(argv[2]))
            lines = res.lines + ["ATTENTION: " + a for a in res.attention] + status(root)
        elif cmd == "status":
            lines = status(root)
        elif cmd == "payout" and len(argv) >= 3:
            lines = payout(root, argv[2], option("--posted"), option("--amount"))
        elif cmd == "match" and len(argv) >= 4:
            lines = match(root, argv[2], argv[3:])
        elif cmd == "enter" and len(argv) == 4:
            lines = enter(root, argv[2], argv[3])
        else:
            print(__doc__)
            return 2
    except (ValueError, KeyError) as e:
        print("Stopped: %s" % e)
        return 1
    print("\n".join(lines))
    if cmd != "status":
        print("\nNext: python3 tools/ledger.py check, then build, then commit and push.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
