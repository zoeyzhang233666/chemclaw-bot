import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url))

test('approved original Scheme A macOS icon is a 1024px RGBA PNG', () => {
  const image = read('../assets/icon-mac.png')
  assert.ok(image.length > 100_000, 'preserve the original detailed paper texture')
  assert.equal(image.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
  assert.equal(image.readUInt32BE(16), 1024)
  assert.equal(image.readUInt32BE(20), 1024)
  assert.equal(image.readUInt8(25), 6, 'PNG must preserve transparency (RGBA)')
})

test('macOS uses its separate tile while Windows and Linux keep original icons', () => {
  const config = read('../electron-builder.yml').toString('utf8')
  assert.match(config, /win:[\s\S]*?icon: assets\/icon\.ico\s+nsis:/)
  assert.match(config, /mac:[\s\S]*?icon: build\/icon-mac-balanced\.png\s+category: public\.app-category\.productivity/)
  assert.match(config, /linux:[\s\S]*?icon: assets\/icon\.png\s+category: Utility/)
})

test('packaging does not regenerate the original approved raster', () => {
  const scripts = JSON.parse(read('../package.json').toString('utf8')).scripts
  for (const name of ['pack', 'dist', 'dist:mac-preview']) {
    assert.ok(scripts[name].includes('node scripts/prepare-mac-icon.mjs'), name)
    assert.ok(!scripts[name].includes('build-mac-icon'), name)
  }
})

test('Mac icon correction uses native macOS CoreGraphics, not Electron', () => {
  const script = read('../scripts/prepare-mac-icon.mjs').toString('utf8')
  const renderer = read('../scripts/render-mac-icon.swift').toString('utf8')
  assert.match(script, /ARTWORK_SIZE = 820/)
  assert.match(script, /OFFSET = \\(ICON_SIZE - ARTWORK_SIZE\\) \\/ 2/)
  assert.match(script, /spawnSync\\('\/usr\/bin\/xcrun', \\['swift', swiftSource, original, output\\]/)
  assert.match(script, /process\\.platform === 'darwin'/)
  assert.doesNotMatch(script, /createRequire\\(|import\\('electron'\\)|spawnSync\\(electron/)
  assert.doesNotMatch(script, /writeFileSync\\(original/)
  assert.match(renderer, /import CoreGraphics/)
  assert.match(renderer, /artworkSize = 820/)
  assert.match(renderer, /canvas\\.clear\\(/)
  assert.match(renderer, /canvas\\.draw\\(/)
  assert.match(renderer, /png\\.write\\(to: outputURL/)
})
