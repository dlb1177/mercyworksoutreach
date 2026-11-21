// Fill every field of a PDF form with sample text, to check that the fields work
// and line up. Used by make-distribution-form.py.
//
// Build:  swiftc -O -o /tmp/fill-sample tools/mac/fill-sample.swift
// Use:    /tmp/fill-sample <form.pdf> <out.pdf>

import Foundation
import PDFKit

let args = CommandLine.arguments
guard let doc = PDFDocument(url: URL(fileURLWithPath: args[1])), let page = doc.page(at: 0) else { fatalError("cannot open \(args[1])") }
let widgets = page.annotations.filter { $0.type == "Widget" }
for a in widgets {
    let name = a.fieldName ?? ""
    if a.isMultiline { a.widgetStringValue = "Sample notes on a first line.\nAnd a second line." }
    else if name.hasPrefix("quantity") { a.widgetStringValue = "25" }
    else if name.hasPrefix("item") { a.widgetStringValue = "Winter sets" }
    else { a.widgetStringValue = "Sample text" }
}
if !doc.write(to: URL(fileURLWithPath: args[2])) { fatalError("cannot write \(args[2])") }
print("the form has \(widgets.count) fillable text fields: " + widgets.prefix(6).map { $0.fieldName ?? "?" }.joined(separator: ", ") + ", ...")
