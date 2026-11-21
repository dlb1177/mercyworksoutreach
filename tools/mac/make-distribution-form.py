#!/usr/bin/env python3
"""Make the fillable Distribution Log form: documents/volunteer/distribution-log.pdf

    python3 tools/mac/make-distribution-form.py

The page is laid out here in points. Chromium prints it to PDF with the brand
fonts and logo, then add_fields() below appends a standard PDF form (AcroForm)
with one text field over each box, so it can be filled in Adobe Reader, Chrome,
Preview and phone PDF apps. On a Mac, fill-sample.swift then fills a copy to check it.

It needs a Chromium that can print to PDF. The path below is where Playwright put
one on Dylan's Mac; set the CHROME environment variable to use another. Everything
else is plain Python, so only the last checking step needs a Mac. The form is deliberately generic: it lists no stock items, so it
never needs to change when the inventory does.
"""
import os, re, shutil, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CHROME = Path(os.environ.get("CHROME") or Path.home() / "Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell")
OUT = ROOT / "documents/volunteer/distribution-log.pdf"
ROWS = 13

fields, boxes, labels = [], [], []

def field(name, x, top, w, h, label=None, multiline=False, tip=None):
    if label:
        labels.append((x, top - 13, label))
    boxes.append((x, top, w, h))
    fields.append({"name": name, "tip": tip or label, "x": x + 3, "top": top + 1, "w": w - 6, "h": h - 2, "multiline": multiline})


def add_fields(pdf, fields):
    """Append an incremental update that turns the flat page into a fillable form."""
    def body(n):
        return re.search(rb"(?:^|\n)%d 0 obj\s*(.*?)\s*endobj" % n, pdf, re.S).group(1)
    trailer = pdf[pdf.rfind(b"trailer"):]
    size = int(re.search(rb"/Size (\d+)", trailer).group(1))
    root = int(re.search(rb"/Root (\d+) 0 R", trailer).group(1))
    info = int(re.search(rb"/Info (\d+) 0 R", trailer).group(1))
    prev = int(re.search(rb"startxref\s+(\d+)", trailer).group(1))
    page = int(re.search(rb"/Kids \[\s*(\d+) 0 R", body(int(re.search(rb"/Pages (\d+) 0 R", body(root)).group(1)))).group(1))
    page_dict, catalog = body(page), body(root)
    assert b"/Annots" not in page_dict and b"/AcroForm" not in catalog
    height = float(re.search(rb"/MediaBox \[0 0 [\d.]+ ([\d.]+)\]", page_dict).group(1))

    font_n, form_n, first = size, size + 1, size + 2
    refs = b" ".join(b"%d 0 R" % (first + i) for i in range(len(fields)))
    da = b"(/Helv 11 Tf 0 g)"
    objects = {
        page: page_dict.replace(b"/Tabs /S", b"/Tabs /R")[:-2] + b"\n/Annots [" + refs + b"]>>",
        root: catalog[:-2] + b"\n/AcroForm %d 0 R>>" % form_n,
        font_n: b"<</Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding>>",
        form_n: b"<</Fields [" + refs + b"] /NeedAppearances true /DA " + da + b" /DR <</Font <</Helv %d 0 R>>>>>>" % font_n,
    }
    for i, f in enumerate(fields):
        y2 = height - f["top"]
        objects[first + i] = (b"<</Type /Annot /Subtype /Widget /FT /Tx /T (%s) /TU (%s) /Rect [%g %g %g %g] /P %d 0 R /F 4 /Ff %d /DA %s /MK <<>>>>"
                              % (f["name"].encode(), f["tip"].encode(), f["x"], y2 - f["h"], f["x"] + f["w"], y2, page, 4096 if f["multiline"] else 0, da))
    out = bytearray(pdf if pdf.endswith(b"\n") else pdf + b"\n")
    offsets = {}
    for n in sorted(objects):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objects[n] + b"\nendobj\n"
    start = len(out)
    out += b"xref\n"
    nums = sorted(objects)
    i = 0
    while i < len(nums):                      # one subsection for each run of consecutive object numbers
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out += b"%d %d\n" % (nums[i], j - i + 1)
        for n in nums[i:j + 1]:
            out += b"%010d 00000 n \n" % offsets[n]
        i = j + 1
    out += b"trailer\n<</Size %d\n/Root %d 0 R\n/Info %d 0 R\n/Prev %d>>\nstartxref\n%d\n%%%%EOF\n" % (first + len(fields), root, info, prev, start)
    return bytes(out)

field("date", 54, 143, 120, 24, "Date")
field("area", 186, 143, 372, 24, "Area or neighborhood")
field("volunteers", 54, 193, 120, 24, "Number of volunteers")
field("people_served", 186, 193, 150, 24, "People served \\(estimate\\)")
field("filled_out_by", 348, 193, 210, 24, "Filled out by")
TABLE_TOP = 290
for i in range(ROWS):
    top = TABLE_TOP + i * 26
    field("item_%d" % (i + 1), 54, top, 250, 22, tip="Item %d" % (i + 1))
    field("quantity_%d" % (i + 1), 312, top, 70, 22, tip="Quantity of item %d" % (i + 1))
    field("notes_%d" % (i + 1), 390, top, 168, 22, tip="Notes on item %d" % (i + 1))
NOTES_TOP = TABLE_TOP + ROWS * 26 + 24
field("other_notes", 54, NOTES_TOP, 504, 56, "Anything else worth noting", multiline=True)

font = lambda f: (ROOT / "fonts" / f).as_uri()
css = """
@font-face { font-family: "EB Garamond"; src: url("%s"); font-weight: 500; }
@font-face { font-family: "EB Garamond"; src: url("%s"); font-weight: 400; }
@font-face { font-family: "Source Sans 3"; src: url("%s"); font-weight: 400; }
@font-face { font-family: "Source Sans 3"; src: url("%s"); font-weight: 600; }
@page { size: 612pt 792pt; margin: 0; }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
html, body { margin: 0; padding: 0; }
.page { position: relative; width: 612pt; height: 792pt; overflow: hidden; font-family: "Source Sans 3", sans-serif; color: #1F2430; }
.page > * { position: absolute; margin: 0; }
.logo { left: 54pt; top: 38pt; width: 62pt; }
h1 { left: 132pt; top: 44pt; font-family: "EB Garamond", serif; font-weight: 500; font-size: 29pt; line-height: 1; color: #1D3F75; }
.sub { left: 133pt; top: 81pt; font-size: 10.5pt; color: #5B6472; }
.rule { left: 54pt; top: 112pt; width: 504pt; height: 1pt; background: #7FA3D6; }
.label { font-size: 7.5pt; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: #5B6472; line-height: 10pt; }
.box { background: #EEF3F9; border-bottom: 0.75pt solid #7FA3D6; border-radius: 2pt; }
h2 { left: 54pt; font-family: "EB Garamond", serif; font-weight: 500; font-size: 16pt; line-height: 1; color: #1D3F75; }
.help { left: 54pt; font-size: 9.5pt; color: #5B6472; line-height: 12pt; }
.num { font-size: 8pt; color: #5B6472; text-align: right; width: 14pt; line-height: 22pt; }
.privacy { left: 54pt; width: 504pt; font-size: 9pt; line-height: 12pt; color: #5B6472; }
.privacy strong { font-weight: 600; color: #1F2430; }
.foot { left: 54pt; width: 504pt; text-align: center; font-size: 8.5pt; color: #5B6472; border-top: 0.75pt solid rgba(127,163,214,0.5); padding-top: 6pt; }
""" % (font("EBGaramond-Medium.ttf"), font("EBGaramond-Regular.ttf"), font("SourceSans3-Regular.ttf"), font("SourceSans3-SemiBold.ttf"))

h = ['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Distribution Log</title><style>%s</style></head><body><div class="page">' % css]
h.append('<img class="logo" src="%s" alt="Mercy Works Outreach">' % (ROOT / "logo.svg").as_uri())
h.append('<h1>Distribution Log</h1>')
h.append('<p class="sub">One form for each outreach. Fill in what you can. Estimates are fine.</p>')
h.append('<div class="rule"></div>')
for x, top, text in labels:
    h.append('<p class="label" style="left:%spt; top:%spt">%s</p>' % (x, top, text.replace("\\", "")))
for x, top, w, hh in boxes:
    h.append('<div class="box" style="left:%spt; top:%spt; width:%spt; height:%spt"></div>' % (x, top, w, hh))
h.append('<h2 style="top:%spt">What we gave out</h2>' % (TABLE_TOP - 50))
h.append('<p class="help" style="top:%spt">List each kind of item and about how many were given out.</p>' % (TABLE_TOP - 30))
for x, text in ((54, "Item"), (312, "Quantity"), (390, "Notes (optional)")):
    h.append('<p class="label" style="left:%spt; top:%spt">%s</p>' % (x, TABLE_TOP - 13, text))
for i in range(ROWS):
    h.append('<p class="num" style="left:36pt; top:%spt">%d</p>' % (TABLE_TOP + i * 26, i + 1))
h.append('<p class="privacy" style="top:%spt"><strong>Please keep it general.</strong> Do not write the names of the people we served or the exact places they stay. When the form is filled in, send it to info@mercyworksoutreach.org.</p>' % (NOTES_TOP + 68))
h.append('<p class="foot" style="top:752pt">Mercy Works Outreach &middot; mercyworksoutreach.org</p>')
h.append('</div></body></html>')

work = Path(tempfile.mkdtemp(prefix="distribution-form-"))
(work / "form.html").write_text("\n".join(h), encoding="utf-8")
subprocess.run([str(CHROME), "--headless", "--no-pdf-header-footer", "--print-to-pdf=%s" % (work / "flat.pdf"), (work / "form.html").as_uri()],
               check=True, stderr=subprocess.DEVNULL)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(add_fields((work / "flat.pdf").read_bytes(), fields))
print("wrote %s: %d bytes, %d fields" % (OUT.relative_to(ROOT), OUT.stat().st_size, len(fields)))
if shutil.which("swiftc"):
    subprocess.run(["swiftc", "-O", "-o", str(work / "fill-sample"), str(Path(__file__).resolve().parent / "fill-sample.swift")], check=True, stderr=subprocess.DEVNULL)
    subprocess.run([str(work / "fill-sample"), str(OUT), str(work / "sample.pdf")], check=True)
    print("sample copy with every field filled, for checking: %s" % (work / "sample.pdf"))
else:
    print("No Swift compiler here, so the filled sample was not made. Open the form in a PDF reader and try the fields.")
