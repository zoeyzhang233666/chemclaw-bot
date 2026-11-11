import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('macOS paper icon preserves the existing ChemClaw cloud silhouette', () => {
  const shared = read('../assets/icon.svg')
  const mac = read('../assets/icon-mac.svg')
  const outline = shared.match(/<path d="([^"]+)"/)?.[1]
  assert.ok(outline, 'shared icon must contain a cloud path')
  assert.ok(mac.includes('d="' + outline + '"'), 'mac icon must reuse the exact cloud geometry')
  assert.match(mac, /viewBox="0 0 1024 1024"/)
  assert.match(mac, /clipPath id="tileClip"/)
})

test('macOS icon packaging does not change Windows and Linux icons', () => {
  const config = read('../electron-builder.yml')
  assert.match(config, /win:[\s\S]*?icon: assets\/icon\.ico\s+nsis:/)
  assert.match(config, /mac:[\s\S]*?icon: assets\/icon-mac\.png\s+category: public\.app-category\.productivity/)
  assert.match(config, /linux:[\s\S]*?icon: assets\/icon\.png\s+category: Utility/)
})

test('packaging commands generate the macOS icon before electron-builder', () => {
  const scripts = JSON.parse(read('../package.json')).scripts
  for (const name of ['pack', 'dist', 'dist:mac-preview']) {
    assert.ok(scripts[name].startsWith('node scripts/build-mac-icon.mjs && '), name)
  }
  const generator = read('../scripts/build-mac-icon.mjs')
  assert.match(generator, /process\.platform === 'darwin'/)
})
