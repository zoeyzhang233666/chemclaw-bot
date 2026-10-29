import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { join, resolve } from 'node:path'
import { FileMatcher } from 'app-builder-lib/out/fileMatcher.js'
import { parse } from 'yaml'

// npm installs the peers that the DSH packages ask for, but electron-builder packs only the
// dependencies it finds through `dependencies` and `optionalDependencies`. A package that npm
// installed only as a peer would be left out of the installer, and the Host would not boot.
test('every package that the app runs on is a dependency, not only a peer', () => {
  const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'))
  const peerOnly = Object.entries(lock.packages)
    .filter(([path, entry]) => path !== '' && entry.peer && !entry.dev && !entry.devOptional)
    .map(([path, entry]) => `${path.replace(/^.*node_modules\//u, '')}@${entry.version}`)
  assert.deepEqual(peerOnly, [], `add these to "dependencies" in app/package.json: ${peerOnly.join(' ')}`)
})

test('sharp native modules and versioned libvips libraries are unpacked together', () => {
  const config = parse(readFileSync(new URL('../electron-builder.yml', import.meta.url), 'utf8'))
  const root = resolve('app-fixture')
  const filter = new FileMatcher(root, root, value => value, config.asarUnpack).createFilter()
  const stat = { isDirectory: () => false }
  for (const file of [
    '@img/sharp-linux-x64/lib/sharp-linux-x64-0.35.5.node',
    '@img/sharp-libvips-linux-x64/lib/libvips-cpp.so.8.18.7',
    '@img/sharp-linux-arm64/lib/sharp-linux-arm64.node',
    '@img/sharp-libvips-linux-arm64/lib/libvips-cpp.so.8.18.7',
    '@img/sharp-libvips-linuxmusl-x64/lib/libvips-cpp.so.8.18.7',
    '@img/sharp-libvips-darwin-arm64/lib/libvips-cpp.8.18.7.dylib',
    '@img/sharp-win32-x64/lib/libvips-42.dll',
    'pnpm/bin/pnpm.cjs',
  ]) assert.equal(filter(join(root, 'node_modules', file), stat), true, file)
  assert.equal(filter(join(root, 'node_modules/yaml/dist/index.js'), stat), false)
})

test('Linux packages select the official sharp WASM backend without shipping conflicting GLib', () => {
  const config = parse(readFileSync(new URL('../electron-builder.yml', import.meta.url), 'utf8'))
  const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'))
  assert.equal(lock.packages[''].dependencies['@img/sharp-wasm32'], lock.packages['node_modules/sharp'].version)
  const root = resolve('app-fixture')
  const stat = { isDirectory: () => false }
  const filter = new FileMatcher(root, root, value => value, ['**/*', ...config.linux.files]).createFilter()
  for (const file of [
    '@img/sharp-linux-x64/lib/sharp-linux-x64-0.35.5.node',
    '@img/sharp-linuxmusl-x64/lib/sharp-linuxmusl-x64-0.35.5.node',
    '@img/sharp-libvips-linux-x64/lib/libvips-cpp.so.8.18.7',
  ]) assert.equal(filter(join(root, 'node_modules', file), stat), false, file)
  const wasm = 'node_modules/@img/sharp-wasm32/lib/sharp-wasm32.wasm'
  assert.equal(filter(join(root, wasm), stat), true)
  const unpack = new FileMatcher(root, root, value => value, config.asarUnpack).createFilter()
  assert.equal(unpack(join(root, wasm), stat), true)
  assert.equal(config.win.files, undefined)
  assert.equal(config.mac.files, undefined)
})

// A release is tagged with the version of chemclaw-bot, and the installed apps compare their own
// version with the one in the release's latest.yml.
test('the app has the version of chemclaw-bot', () => {
  const version = file => JSON.parse(readFileSync(new URL(file, import.meta.url), 'utf8')).version
  assert.equal(version('../package.json'), version('../../chemclaw-bot/package.json'))
})

test('runtime build tools stay out of desktop packages while release archives remain included', () => {
  const config = parse(readFileSync(new URL('../electron-builder.yml', import.meta.url), 'utf8'))
  const root = resolve('app-fixture')
  const filter = new FileMatcher(root, root, value => value, ['**/*', ...config.files.filter(pattern => pattern.startsWith('!'))]).createFilter()
  const stat = { isDirectory: () => false }
  for (const file of ['uv-0.13.6/uv.exe', 'interpreters/python/bin/python3', 'cache/package.whl']) {
    assert.equal(filter(join(root, 'node_modules/chemclaw-bot/runtime/.build-tools', file), stat), false, file)
  }
  assert.equal(filter(join(root, 'node_modules/chemclaw-bot/runtime/bundled/linux-x64.tar.gz'), stat), true)
  assert.equal(filter(join(root, 'node_modules/chemclaw-bot/skills/builtin/delivery/SKILL.md'), stat), true)
})
