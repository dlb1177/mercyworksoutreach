// Render each page of a PDF to a PNG, to look over a redacted copy before publishing.
//
// Build:  swiftc -O -o /tmp/pages tools/mac/pages.swift
// Use:    /tmp/pages <in.pdf> <existing output folder>   ->  p1.png, p2.png, ...

import Foundation
import PDFKit

let doc = PDFDocument(url: URL(fileURLWithPath: CommandLine.arguments[1]))!
for i in 0..<doc.pageCount {
    let img = doc.page(at: i)!.thumbnail(of: NSSize(width: 1100, height: 1424), for: .mediaBox)
    let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
    try! rep.representation(using: .png, properties: [:])!
        .write(to: URL(fileURLWithPath: CommandLine.arguments[2] + "/p\(i + 1).png"))
}
