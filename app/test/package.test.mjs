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

test('a clean EXE installation graph includes each pinned ChemClaw plugin dependency', () => {
  const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'))
  const manifest = JSON.parse(readFileSync(new URL('../../chemclaw-bot/package.json', import.meta.url), 'utf8'))
  const packedPlugin = lock.packages['node_modules/chemclaw-bot']
  assert.ok(packedPlugin, 'App lockfile must include chemclaw-bot')
  for (const [name, version] of Object.entries(manifest.dependencies)) {
    assert.equal(packedPlugin.dependencies?.[name], version, `App lockfile has stale ChemClaw dependency ${name}`)
    const candidates = Object.entries(lock.packages).filter(([path, pkg]) =>
      path.endsWith(`node_modules/${name}`) && pkg.version === version)
    assert.ok(candidates.length, `App lockfile is missing ${name}@${version}`)
  }
})

test('GenUI stays a direct dependency of the desktop application and is locked for source preview', () => {
  const app = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'))
  const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'))
  const bot = JSON.parse(readFileSync(new URL('../../chemclaw-bot/package.json', import.meta.url), 'utf8'))
  const name = '@changfenhuang/dsh-genui'
  assert.equal(app.dependencies[name], bot.dependencies[name])
  assert.equal(lock.packages[''].dependencies[name], app.dependencies[name])
  assert.equal(lock.packages[`node_modules/${name}`]?.version, app.dependencies[name])
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

test('desktop and test harness lock the same DeepSeek Harness RC release', () => {
  const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
  const app = read('../package.json')
  const appLock = read('../package-lock.json')
  const harness = read('../../chemclaw-bot/dev/harness/package.json')
  const harnessLock = read('../../chemclaw-bot/dev/harness/package-lock.json')
  const pinned = app.dependencies['@deepseek-ai/dsh']
  assert.match(pinned, /^0\\.\\d+\\.\\d+-rc\\.\\d+$/u)

  for (const [name, version] of Object.entries(app.dependencies)) {
    if (!name.startsWith('@deepseek-ai/dsh')) continue
    assert.equal(version, pinned, `Desktop has a mismatched version for ${name}`)
    assert.equal(appLock.packages[''].dependencies[name], pinned, `Desktop root lock is stale for ${name}`)
    assert.equal(appLock.packages[`node_modules/${name}`]?.version, pinned, `Desktop installed lock is stale for ${name}`)
  }
  for (const [name, version] of Object.entries(app.overrides)) {
    if (name.startsWith('@deepseek-ai/dsh-')) assert.equal(version, pinned, `Override for ${name} is stale`)
  }
  for (const [name, version] of Object.entries(harness.dependencies)) {
    if (!name.startsWith('@deepseek-ai/dsh')) continue
    assert.equal(version, pinned, `Harness has a mismatched version for ${name}`)
    assert.equal(harnessLock.packages[''].dependencies[name], pinned, `Harness root lock is stale for ${name}`)
    assert.equal(harnessLock.packages[`node_modules/${name}`]?.version, pinned, `Harness installed lock is stale for ${name}`)
  }
})
