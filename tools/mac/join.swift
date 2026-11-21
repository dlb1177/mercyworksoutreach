// Join PDFs, or chosen pages of them, into one clean PDF.
//
// Build:  swiftc -O -o /tmp/join tools/mac/join.swift
// Use:    TITLE="..." /tmp/join <out.pdf> <in.pdf>[:FIRST-LAST] ...
//
// "a.pdf" takes every page; "a.pdf:1" takes page 1; "a.pdf:2-4" takes pages 2 to 4.
// Pages are redrawn into a fresh file, so the inputs' metadata is not carried
// over. Redact first (redact.swift), then join.

import Foundation
import PDFKit
import CoreGraphics

let args = CommandLine.arguments
let env = ProcessInfo.processInfo.environment
var media = CGRect(x: 0, y: 0, width: 612, height: 792)
let info: [CFString: Any] = [kCGPDFContextTitle: env["TITLE"] ?? "Mercy Works Outreach",
                             kCGPDFContextAuthor: "Mercy Works Outreach"]
guard let ctx = CGContext(URL(fileURLWithPath: args[1]) as CFURL, mediaBox: &media, info as CFDictionary) else { fatalError("cannot write \(args[1])") }
var total = 0
for spec in args[2...] {
    var path = spec, first = 1, last = Int.max
    if let r = spec.range(of: #":\d+(-\d+)?$"#, options: .regularExpression) {
        path = String(spec[..<r.lowerBound])
        let nums = spec[r].dropFirst().split(separator: "-").map { Int($0)! }
        first = nums[0]; last = nums.count > 1 ? nums[1] : nums[0]
    }
    guard let doc = PDFDocument(url: URL(fileURLWithPath: path)) else { fatalError("cannot open \(path)") }
    for i in (first - 1)..<min(last, doc.pageCount) {
        let page = doc.page(at: i)!
        var box = page.bounds(for: .mediaBox)
        ctx.beginPage(mediaBox: &box)
        page.draw(with: .mediaBox, to: ctx)
        ctx.endPage()
        total += 1
    }
}
ctx.closePDF()
print("wrote \(args[1]): \(total) pages")
