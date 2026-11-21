#!/usr/bin/env python3
"""Mercy Works Outreach: bring a Zeffy export into the books.

Zeffy is the online donation platform. Its export (Payments > Export, an .xlsx
file) lists every payment. This script reads an export, finds what is new since
the last one, and enters it. It uses only the Python 3 standard library.

    python3 tools/zeffy.py import <export.xlsx>   enter what is new, then file the export
    python3 tools/zeffy.py status                 what Zeffy still owes, and anything open
    python3 tools/zeffy.py payout YYYY-MM-DD [--posted YYYY-MM-DD]
                                                  a payout has reached the bank: clear it
    python3 tools/zeffy.py match "<key>" <ledger ids>
                                                  say which ledger rows a hand-entered
                                                  Zeffy payment is already recorded as

How a gift moves through the books
  1. Given online. The export shows it with a payout date ("Upcoming" at first).
     import enters it in the general ledger on the day it was given, as a
     Contributions row with method zeffy. From then on it is a payout receivable:
     part of the balance, not yet cash in the bank.
  2. Paid out. A later export shows the real payout date. import records it and
     says which payout to look for on the bank statement.
  3. Cleared. When the bank statement shows the deposit, payout enters a pair of
     Transfers rows (out of Zeffy, into the bank). The receivable goes down and the
     cash in the bank goes up by the same amount.

Payments entered into Zeffy by hand (a cheque, cash, a gift in kind) have no payout
date. They never pass through Zeffy, so they are not entered from the export: they
reach the books the usual way, from the deposit slip or the receipt. import only
checks that each one is matched to ledger rows, and says so if one is not.

What is public and what is private
  The ledger row says only "Donor" (a director) or "Individual donor", the date and
  the amount. Names, email addresses and home addresses go to Books/donors.csv and
  Books/zeffy-log.csv, which are never committed. The export itself is filed in
  Books/zeffy/. Nothing private is printed into a public file.
"""

import csv
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger  # noqa: E402

LOG = "Books/zeffy-log.csv"
LOG_COLS = ["key", "payment_date", "payment_time", "amount", "payment_method", "status",
            "payout_date", "refund_amount", "first_name", "last_name", "email",
            "kind", "ledger_ids", "cleared_ids", "first_seen"]
DONORS = "Books/donors.csv"
DONOR_COLS = ["ledger_id", "date", "donor_name", "household_key", "email", "mailing_address",
              "amount", "type", "public_name_ok", "acknowledged_on"]
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NEEDED = ["Payment Date (America/Chicago)", "Payment Time (America/Chicago)", "Total Amount",
          "Payment Method", "Payment Status", "Payout Date", "First Name", "Last Name", "Email"]


# ---------- reading the export ----------

def read_xlsx(path):
    """Rows of the first sheet as dicts keyed by the header row."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
        sheets = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        table = []
        for row in ET.fromstring(z.read(sheets[0])).iter(NS + "row"):
            cells = {}
            for c in row.findall(NS + "c"):
                col = 0
                for ch in re.match(r"[A-Z]+", c.get("r")).group(0):
                    col = col * 26 + ord(ch) - 64
                v = c.find(NS + "v")
                if c.get("t") == "s" and v is not None:
                    value = shared[int(v.text)]
                elif c.get("t") == "inlineStr":
                    value = "".join(t.text or "" for t in c.iter(NS + "t"))
                else:
                    value = v.text if v is not None and v.text is not None else ""
                cells[col - 1] = value.strip()
            table.append(cells)
    if not table:
        raise ValueError("The export is empty.")
    header = [table[0].get(i, "") for i in range(max(table[0]) + 1)]
    missing = [h for h in NEEDED if h not in header]
    if missing:
        raise ValueError("This does not look like a Zeffy payments export. Missing columns: " + ", ".join(missing))
    return [{h: cells.get(i, "") for i, h in enumerate(header)} for cells in table[1:] if any(cells.values())]


def us_date(text):
    """11/20/2026 -> 2026-11-20. Returns "" for anything that is not a date."""
    try:
        return datetime.strptime(text.strip(), "%m/%d/%Y").date().isoformat()
    except ValueError:
        return ""


def payments(path):
    """The export's rows, tidied, each with a key that stays the same from one export to the next."""
    out, seen = [], {}
    for raw in read_xlsx(path):
        day = us_date(raw["Payment Date (America/Chicago)"])
        if not day:
            raise ValueError('Cannot read the payment date "%s".' % raw["Payment Date (America/Chicago)"])
        try:
            clock = datetime.strptime(raw["Payment Time (America/Chicago)"].strip().upper(), "%I:%M %p").strftime("%H:%M")
        except ValueError:
            clock = raw["Payment Time (America/Chicago)"].strip()
        amount = Decimal(raw["Total Amount"] or "0").quantize(Decimal("0.01"))
        refund = Decimal(raw.get("Refund Amount") or "0").quantize(Decimal("0.01"))
        key = "%s %s|%s|%s" % (day, clock, amount, raw["Email"].lower() or (raw["First Name"] + " " + raw["Last Name"]).lower())
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key += "#%d" % seen[key]
        payout = raw["Payout Date"].strip()
        out.append({
            "key": key, "payment_date": day, "payment_time": clock, "amount": str(amount),
            "payment_method": raw["Payment Method"], "status": raw["Payment Status"],
            "payout_date": us_date(payout) or payout, "refund_amount": str(refund),
            "first_name": raw["First Name"], "last_name": raw["Last Name"], "email": raw["Email"],
            "kind": "online" if payout else "manual",
            "company": raw.get("Company Name", ""),
            "address": ", ".join(x for x in (raw.get("Address", ""), raw.get("City", ""),
                                             (raw.get("State", "") + " " + raw.get("Postal Code", "")).strip()) if x),
        })
    out.sort(key=lambda p: (p["payment_date"], p["payment_time"]))
    return out


# ---------- the private files ----------

def read_csv(path, cols):
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [{c: r.get(c, "") or "" for c in cols} for r in csv.DictReader(f)]


def write_csv(path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        w.writerows([[r.get(c, "") for c in cols] for r in rows])


def ledger_rows(root):
    with open(Path(root) / ledger.LEDGER, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def public_label(p):
    """What the public ledger calls the donor. Never a name."""
    name = ("%s %s" % (p["first_name"], p["last_name"])).strip().lower()
    return "Donor" if any(name == n.lower() for n in ledger.INSIDERS) else "Individual donor"


def household(p, donors):
    name = ("%s %s" % (p["first_name"], p["last_name"])).strip()
    for d in donors:
        if d["household_key"] and ((p["email"] and d["email"].lower() == p["email"].lower()) or d["donor_name"].lower() == name.lower()):
            return d["household_key"]
    return re.sub(r"[^a-z0-9]+", "-", ("%s %s" % (p["last_name"], p["first_name"])).lower()).strip("-") or "unknown"


# ---------- import ----------

def import_export(root, export, today=None, archive=True):
    """Enter what is new in a Zeffy export. Returns the lines of a report."""
    root = Path(root)
    today = today or date.today().isoformat()
    log = read_csv(root / LOG, LOG_COLS)
    known = {r["key"]: r for r in log}
    donors = read_csv(root / DONORS, DONOR_COLS)
    report, attention, new_gifts = [], [], []
    matched = {i for r in log for i in r["ledger_ids"].split()}

    for p in payments(export):
        old = known.get(p["key"])
        what = "%s gift of $%s on %s" % (p["payment_method"].lower(), p["amount"], p["payment_date"])
        if old:
            if p["payout_date"] != old["payout_date"]:
                if old["kind"] == "online" and ledger.parse_date(p["payout_date"]):
                    report.append("Paid out by Zeffy on %s: the %s (ledger %s)." % (p["payout_date"], what, old["ledger_ids"]))
                old["payout_date"] = p["payout_date"]
            if p["refund_amount"] != (old["refund_amount"] or "0.00") or p["status"] != old["status"]:
                attention.append("The %s (ledger %s) now shows status %s and refund $%s. It needs a correcting entry by hand." % (what, old["ledger_ids"], p["status"], p["refund_amount"]))
                old["refund_amount"], old["status"] = p["refund_amount"], p["status"]
            continue
        if p["status"] != "Succeeded":
            attention.append("Not entered: a %s with status %s. It will be looked at again on the next export." % (what, p["status"]))
            continue
        if Decimal(p["refund_amount"]) != 0:
            attention.append("Not entered: a %s with a refund of $%s. Enter it by hand." % (what, p["refund_amount"]))
            continue
        entry = {c: p.get(c, "") for c in LOG_COLS}
        entry["first_seen"] = today
        if p["kind"] == "manual":
            # Entered into Zeffy by hand, so it never passes through Zeffy. Is it already in the ledger?
            close = [r for r in ledger_rows(root)
                     if r["category"] in ledger.GIFT_CATEGORIES and r["method"] != "zeffy" and r["amount"] == p["amount"]
                     and r["id"] not in matched and abs((date.fromisoformat(r["date"]) - date.fromisoformat(p["payment_date"])).days) <= 5]
            if len(close) == 1:
                entry["ledger_ids"] = close[0]["id"]
                matched.add(close[0]["id"])
                report.append("Entered in Zeffy by hand, already in the ledger as %s: the %s." % (close[0]["id"], what))
            else:
                attention.append('Entered in Zeffy by hand and not matched to the ledger: the %s. If it is already recorded, run: python3 tools/zeffy.py match "%s" <ledger ids>' % (what, p["key"]))
            log.append(entry)
            known[p["key"]] = entry
            continue
        if p["company"]:
            attention.append("Not entered: a %s from an organization. Decide its public label (Foundation, Church, Government) and enter it by hand." % what)
            continue
        new_gifts.append((p, entry))

    if new_gifts:
        ids = ledger.add_rows(root, [{"date": p["payment_date"], "category": "Contributions", "counterparty": public_label(p),
                                      "description": "Gift given online", "amount": p["amount"], "method": "zeffy"} for p, _ in new_gifts])
        for (p, entry), lid in zip(new_gifts, ids):
            entry["ledger_ids"] = lid
            log.append(entry)
            name = ("%s %s" % (p["first_name"], p["last_name"])).strip()
            donors.append({"ledger_id": lid, "date": p["payment_date"], "donor_name": name, "household_key": household(p, donors),
                           "email": p["email"], "mailing_address": p["address"], "amount": p["amount"], "type": "cash",
                           "public_name_ok": "no", "acknowledged_on": ""})
            report.append("New: online gift of $%s on %s, entered as %s (%s)." % (p["amount"], p["payment_date"], lid, public_label(p)))
        write_csv(root / DONORS, DONOR_COLS, donors)
    write_csv(root / LOG, LOG_COLS, log)

    if archive:
        folder = root / "Books" / "zeffy"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / ("export-%s.xlsx" % today)
        n = 2
        while target.exists():
            target = folder / ("export-%s-%d.xlsx" % (today, n))
            n += 1
        shutil.move(str(export), str(target))
        report.append("The export is filed at %s." % target.relative_to(root))
    if not new_gifts:
        report.append("No new online gifts in this export.")
    return report + ["ATTENTION: " + a for a in attention] + status(root)


# ---------- status, payout, match ----------

def count(group):
    return "1 gift" if len(group) == 1 else "%d gifts" % len(group)


def status(root):
    root = Path(root)
    log = read_csv(root / LOG, LOG_COLS)
    rows = ledger_rows(root)
    owed = sum((Decimal(r["amount"]) for r in rows if r["method"] == "zeffy"), Decimal("0.00"))
    online = [r for r in log if r["kind"] == "online" and r["ledger_ids"]]
    open_ = [r for r in online if not r["cleared_ids"]]
    lines = ["Payout receivable in the ledger (given through Zeffy, not yet cleared to the bank): $%s" % owed]
    if sum((Decimal(r["amount"]) for r in open_), Decimal("0.00")) != owed:
        lines.append("ATTENTION: the private Zeffy log says $%s is open, which does not match the ledger." % sum((Decimal(r["amount"]) for r in open_), Decimal("0.00")))
    upcoming = [r for r in open_ if not ledger.parse_date(r["payout_date"])]
    if upcoming:
        lines.append("  Not paid out yet: %s, $%s" % (count(upcoming), sum(Decimal(r["amount"]) for r in upcoming)))
    for day in sorted({r["payout_date"] for r in open_ if ledger.parse_date(r["payout_date"])}):
        group = [r for r in open_ if r["payout_date"] == day]
        lines.append("  Paid out by Zeffy on %s: %s, $%s. When that deposit is on the bank statement, run: python3 tools/zeffy.py payout %s"
                     % (day, count(group), sum(Decimal(r["amount"]) for r in group), day))
    for r in log:
        if r["kind"] == "manual" and not r["ledger_ids"]:
            lines.append('ATTENTION: hand-entered Zeffy payment not matched to the ledger: $%s on %s (%s). Key: "%s"' % (r["amount"], r["payment_date"], r["payment_method"], r["key"]))
    return lines


def payout(root, day, posted=None):
    """A Zeffy payout has reached the bank: move it from the receivable to the bank."""
    root = Path(root)
    posted = posted or day
    log = read_csv(root / LOG, LOG_COLS)
    group = [r for r in log if r["kind"] == "online" and r["payout_date"] == day and r["ledger_ids"] and not r["cleared_ids"]]
    if not group:
        raise ValueError("The Zeffy log has no uncleared gifts with payout date %s. Import a newer export first." % day)
    total = sum(Decimal(r["amount"]) for r in group)
    n = len(group)
    ids = ledger.add_rows(root, [
        {"date": posted, "category": "Transfers", "counterparty": "Zeffy", "amount": str(-total), "method": "zeffy",
         "description": "Payout of %d online %s sent to the bank" % (n, "gift" if n == 1 else "gifts")},
        {"date": posted, "category": "Transfers", "counterparty": "Sunrise Banks", "amount": str(total), "method": "bank",
         "description": "Payout of %d online %s received from Zeffy" % (n, "gift" if n == 1 else "gifts"), "ref": "@0"},
    ])
    for r in group:
        r["cleared_ids"] = " ".join(ids)
    write_csv(root / LOG, LOG_COLS, log)
    return ["Cleared the payout of $%s (%s, paid out %s, posted %s) as %s and %s." % (total, count(group), day, posted, ids[0], ids[1])] + status(root)


def match(root, key, ids):
    root = Path(root)
    log = read_csv(root / LOG, LOG_COLS)
    have = {r["id"] for r in ledger_rows(root)}
    for r in log:
        if r["key"] == key:
            if r["kind"] != "manual":
                raise ValueError("That payment went through Zeffy. Only hand-entered payments are matched this way.")
            missing = [i for i in ids if i not in have]
            if missing:
                raise ValueError("Not in the ledger: " + ", ".join(missing))
            r["ledger_ids"] = " ".join(ids)
            write_csv(root / LOG, LOG_COLS, log)
            return ["Matched the hand-entered payment of $%s on %s to %s." % (r["amount"], r["payment_date"], r["ledger_ids"])]
    raise ValueError("No payment in the Zeffy log has that key.")


def main(argv):
    root = Path(__file__).resolve().parent.parent
    cmd = argv[1] if len(argv) > 1 else ""
    try:
        if cmd == "import" and len(argv) == 3:
            lines = import_export(root, Path(argv[2]))
        elif cmd == "status":
            lines = status(root)
        elif cmd == "payout" and len(argv) >= 3:
            lines = payout(root, argv[2], argv[argv.index("--posted") + 1] if "--posted" in argv else None)
        elif cmd == "match" and len(argv) >= 4:
            lines = match(root, argv[2], argv[3:])
        else:
            print(__doc__)
            return 2
    except (ValueError, KeyError, zipfile.BadZipFile) as e:
        print("Stopped: %s" % e)
        return 1
    print("\n".join(lines))
    print("\nNext: python3 tools/ledger.py check, then build, then commit and push.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
