import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { launchSource, missingPluginDependencies } from '../../scripts/launch-source.mjs'

test('an explicit source wins and forwarded launches keep the original data root without following another selection', t => {
  const dir = mkdtempSync(join(tmpdir(), 'chemclaw-launch-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const make = name => {
    const root = join(dir, name)
    for (const [folder, pkg] of [['app', 'chemclaw'], ['chemclaw-bot', 'chemclaw-bot']]) {
      mkdirSync(join(root, folder), { recursive: true })
      writeFileSync(join(root, folder, 'package.json'), JSON.stringify({ name: pkg }))
    }
    mkdirSync(join(root, 'scripts'))
    writeFileSync(join(root, 'scripts', 'launch-chemclaw.mjs'), '')
    return realpathSync(root)
  }
  const original = make('original')
  const preview = make('preview')
  mkdirSync(join(original, '.chemclaw-dev'))
  writeFileSync(join(original, '.chemclaw-dev', 'source.json'), JSON.stringify({ source: preview }))
  assert.equal(launchSource(original, [], {}).source, preview)
  const explicit = launchSource(original, ['--watch', '--source', original, '--sync-only'], {})
  assert.equal(explicit.source, original)
  assert.deepEqual(explicit.args, ['--watch', '--sync-only'])
  const forwarded = launchSource(preview, [], { CHEMCLAW_LAUNCH_HOME: original })
  assert.equal(forwarded.source, preview)
  assert.equal(forwarded.origin, original)
  assert.throws(() => launchSource(original, ['--source'], {}), /needs a ChemClaw/)
  writeFileSync(join(original, '.chemclaw-dev', 'source.json'), '{"source":"missing"}')
  assert.throws(() => launchSource(original, [], {}), /ENOENT/)
  assert.equal(launchSource(original, ['--source', preview], {}).source, preview)
})


test('dependency audit catches missing and stale bundles even when a previous stamp says ready', t => {
  const dir = mkdtempSync(join(tmpdir(), 'chemclaw-deps-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const name = '@changfenhuang/dsh-genui'
  const packageDir = join(dir, 'node_modules', '@changfenhuang', 'dsh-genui')
  const pluginDir = join(dir, 'node_modules', 'chemclaw-bot')
  mkdirSync(pluginDir, { recursive: true })
  writeFileSync(join(pluginDir, 'package.json'), JSON.stringify({ name: 'chemclaw-bot' }))
  const expected = { [name]: '0.15.0' }
  assert.deepEqual(missingPluginDependencies(dir, expected), [`${name}@0.15.0`])
  mkdirSync(packageDir, { recursive: true })
  const save = version => {
    // package.json is intentionally not exported, as with some third-party plugins.
    writeFileSync(join(packageDir, 'package.json'), JSON.stringify({ name, version, exports: { '.': './index.js' } }))
    writeFileSync(join(packageDir, 'index.js'), '')
  }
  save('0.14.0')
  assert.deepEqual(missingPluginDependencies(dir, expected), [`${name}@0.15.0`])
  save('0.15.0')
  assert.deepEqual(missingPluginDependencies(dir, expected), [])
  assert.deepEqual(missingPluginDependencies(dir, { ...expected, 'future-plugin': '1.0.0' }), ['future-plugin@1.0.0'])
})
