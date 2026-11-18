// Normalize the macOS Launchpad icon without running (or downloading) Electron.
// CoreGraphics is available on macOS builders via Xcode command-line tools.
// The approved source asset is never rewritten. This script only creates a
// transparent 1024x1024 PNG containing the original 820px artwork.
import { spawnSync } from 'node:child_process'
import { mkdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const appDir = join(dirname(fileURLToPath(import.meta.url)), '..')
const original = join(appDir, 'assets', 'icon-mac.png')
const output = join(appDir, 'build', 'icon-mac-balanced.png')
const swiftSource = join(appDir, 'scripts', 'render-mac-icon.swift')
export const ICON_SIZE = 1024
export const ARTWORK_SIZE = 820
export const OFFSET = (ICON_SIZE - ARTWORK_SIZE) / 2

function checkRgbaPng(bytes, filename) {
  if (bytes.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a' ||
      bytes.readUInt32BE(16) !== ICON_SIZE ||
      bytes.readUInt32BE(20) !== ICON_SIZE ||
      bytes.readUInt8(25) !== 6) {
    throw new Error(filename + ' must be a 1024x1024 RGBA PNG')
  }
}

if (process.platform === 'darwin') {
  checkRgbaPng(readFileSync(original), 'Original approved macOS icon')
  mkdirSync(join(appDir, 'build'), { recursive: true })
  console.log('mac icon: generating transparent padded PNG with native CoreGraphics (no Electron runtime)')
  const result = spawnSync('/usr/bin/xcrun', ['swift', swiftSource, original, output], {
    stdio: 'inherit',
    timeout: 180_000,
  })
  if (result.error) throw result.error
  if (result.status !== 0) throw new Error('Mac icon renderer failed with exit code ' + result.status)
  checkRgbaPng(readFileSync(output), 'Generated balanced macOS icon')
} else {
  // Windows/Linux do not use this image and must not download an Electron binary.
  console.log('mac icon: skipped on ' + process.platform)
}
