// macOS native image renderer. No Electron, npm image modules, or network downloads.
// The approved source PNG is NEVER modified. Only a padded derivative is written.
import AppKit
import CoreGraphics
import Foundation
import ImageIO

func fail(_ message: String) -> Never {
    fputs("mac icon: " + message + "\n", stderr)
    exit(1)
}

guard CommandLine.arguments.count == 3 else {
    fail("Usage: render-mac-icon.swift <original.png> <output.png>")
}

let sourceURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
let canvasSize = 1024
let artworkSize = 820
let padding = (canvasSize - artworkSize) / 2

guard let source = CGImageSourceCreateWithURL(sourceURL as CFURL, nil),
      let sourceImage = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
    fail("Cannot open original PNG: " + sourceURL.path)
}

guard sourceImage.width == canvasSize && sourceImage.height == canvasSize else {
    fail("Original icon must be 1024×1024 pixels")
}

guard let canvas = CGContext(
    data: nil,
    width: canvasSize,
    height: canvasSize,
    bitsPerComponent: 8,
    bytesPerRow: 0,
    space: CGColorSpaceCreateDeviceRGB(),
    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
) else {
    fail("Cannot allocate transparent RGBA bitmap")
}

canvas.clear(CGRect(x: 0, y: 0, width: canvasSize, height: canvasSize))
canvas.interpolationQuality = .high
canvas.setShouldAntialias(true)
canvas.draw(
    sourceImage,
    in: CGRect(x: padding, y: padding, width: artworkSize, height: artworkSize)
)

guard let outputImage = canvas.makeImage() else {
    fail("Cannot render scaled icon")
}

let bitmap = NSBitmapImageRep(cgImage: outputImage)
guard let png = bitmap.representation(using: .png, properties: [:]) else {
    fail("Cannot encode transparent PNG")
}
do {
    try png.write(to: outputURL, options: .atomic)
} catch {
    fail("Cannot write derived PNG: " + String(describing: error))
}

print("mac icon: rendered approved Scheme A artwork at \(artworkSize)px inside a transparent \(canvasSize)px canvas")
