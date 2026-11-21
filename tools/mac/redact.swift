// Redact a PDF before it is published on the site.
//
// Build:  swiftc -O -o /tmp/redact tools/mac/redact.swift
// Use:    TITLE="..." /tmp/redact <in.pdf> <out.pdf> <text to black out>...
//
// An argument written rect:PAGE:X,Y,WIDTH,HEIGHT blacks out a box instead of a string
// (page numbers start at 1; points measured from the bottom left of the page). Use it
// when text wraps across lines and cannot be found as one string. LOCATE=1 only prints
// where each string is, and writes nothing.
//
// Every page that contains one of the strings is flattened to an image with a
// black box drawn over each match, so the hidden text is gone, not just covered.
// Other pages are copied as they are. The result is a fresh PDF, so the
// original's metadata and form data are not carried over.
// The program stops with an error if any string is not found, if any string can
// still be found in the result, or (unless ALLOW_AT=1) if an "@" remains.

import Foundation
import PDFKit
import CoreGraphics

let args = CommandLine.arguments
let env = ProcessInfo.processInfo.environment
let inURL = URL(fileURLWithPath: args[1]), outURL = URL(fileURLWithPath: args[2])
var targets: [String] = []
var boxes: [Int: [CGRect]] = [:]
for a in args[3...] {
    if a.hasPrefix("rect:") {
        let parts = a.dropFirst(5).split(separator: ":")
        let n = parts[1].split(separator: ",").map { CGFloat(Double($0)!) }
        boxes[Int(parts[0])! - 1, default: []].append(CGRect(x: n[0], y: n[1], width: n[2], height: n[3]))
    } else {
        targets.append(a)
    }
}
guard let doc = PDFDocument(url: inURL) else { fatalError("cannot open \(args[1])") }

for t in targets {
    let sels = doc.findString(t, withOptions: [.literal])
    if sels.isEmpty {
        if env["LOCATE"] == "1" { print("not found: \(t)"); continue }
        fatalError("not found: \(t)")
    }
    for s in sels { for p in s.pages {
        let i = doc.index(for: p)
        boxes[i, default: []].append(s.bounds(for: p).insetBy(dx: -4, dy: -3))
        print("page \(i + 1): \(t)  at \(s.bounds(for: p))")
    } }
}
if env["LOCATE"] == "1" { exit(0) }

var media = CGRect(x: 0, y: 0, width: 612, height: 792)
let info: [CFString: Any] = [kCGPDFContextTitle: env["TITLE"] ?? "Mercy Works Outreach",
                             kCGPDFContextAuthor: "Mercy Works Outreach"]
guard let ctx = CGContext(outURL as CFURL, mediaBox: &media, info as CFDictionary) else { fatalError("cannot write \(args[2])") }
let scale: CGFloat = CGFloat(Double(env["DPI"] ?? "200")!) / 72.0
for i in 0..<doc.pageCount {
    let page = doc.page(at: i)!
    var box = page.bounds(for: .mediaBox)
    ctx.beginPage(mediaBox: &box)
    if let rects = boxes[i] {
        let w = Int(box.width * scale), h = Int(box.height * scale)
        let bm = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                           space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
        bm.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
        bm.fill(CGRect(x: 0, y: 0, width: w, height: h))
        bm.scaleBy(x: scale, y: scale)
        bm.translateBy(x: -box.minX, y: -box.minY)
        page.draw(with: .mediaBox, to: bm)
        bm.setFillColor(CGColor(red: 0, green: 0, blue: 0, alpha: 1))
        for r in rects { bm.fill(r) }
        ctx.draw(bm.makeImage()!, in: box)
    } else {
        page.draw(with: .mediaBox, to: ctx)
    }
    ctx.endPage()
}
ctx.closePDF()

// Check the result
let out = PDFDocument(url: outURL)!
let text = out.string ?? ""
for t in targets {
    if text.contains(t) || !out.findString(t, withOptions: [.literal]).isEmpty { fatalError("STILL PRESENT: \(t)") }
}
if env["ALLOW_AT"] != "1" && text.contains("@") { fatalError("an @ sign is still in the text") }
print("ok: \(out.pageCount) pages, none of the \(targets.count) strings remain")
