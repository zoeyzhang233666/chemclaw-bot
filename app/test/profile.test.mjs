import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { after, before, describe, test } from 'node:test'
import { composeEntries } from '@deepseek-ai/dsh-app-boot'
import { BUNDLES, claimBundles, ensureOptionalGenuiRecovery, loadAppProfile } from '../src/profile.mjs'

// Packages of DSH's own Web front end and its browser runtime, which the window shows.
const DSH_WEB_FRONT_END = /^@deepseek-ai\/dsh-(client-ui-|web-app|web-frontend|client-modules|host-frontend-static|cordis-client-runner|client-hmr)/u

// Every row of an entry list, with the rows inside groups and agent presets.
function rows(entries) {
  return entries.flatMap((entry) => [
    entry,
    ...rows(Array.isArray(entry.config) ? entry.config : []),
    ...rows(Array.isArray(entry.config?.plugins) ? entry.config.plugins : []),
  ])
}

describe('the app profile', () => {
  let home
  let entries
  before(() => {
    home = mkdtempSync(join(tmpdir(), 'ds-bot-app-profile-'))
    process.env.DSH_HOME = home
    const profile = loadAppProfile()
    assert.deepEqual(profile.layers.map((layer) => layer.packageName), BUNDLES)
    assert.deepEqual(profile.skippedBundles, [])
    entries = composeEntries([...profile.layers.map((layer) => layer.patches), profile.patches])
  })
  after(() => { rmSync(home, { recursive: true, force: true }) })

  test('GenUI bundle is mounted by a fresh app profile, without replacing native charts', () => {
    const genui = rows(entries).find(entry => entry.id === 'genui')
    assert.equal(genui?.name, '@changfenhuang/dsh-genui')
    assert.equal(genui?.disabled, undefined)
    assert.equal(genui?.config?.renderUiTool, false)
    assert.equal(rows(entries).some(entry => entry.id === 'chemclaw'), true)
  })

  test('mounts DSH Web, which the window shows, and the Bot team', () => {
    const on = new Set(entries.filter((entry) => entry.disabled !== true).map((entry) => entry.id))
    for (const id of ['webserver', 'connection', 'chemclaw']) assert.ok(on.has(id), `${id} is mounted`)
    assert.ok(rows(entries).some((entry) => DSH_WEB_FRONT_END.test(entry.name ?? '')), 'the DSH Web front end is mounted')
  })

  test('acknowledges the pinned preview notice only in the independent app profile', () => {
    assert.equal(rows(entries).find(entry => entry.id === 'ui-settings-general')?.config?.welcomeNoticeVersion, '2026-09-28.1')
  })

  test('keeps deliverable routes available and bounds repository snapshots', () => {
    const changes = rows(entries).find(entry => entry.id === 'workspace-changes')
    assert.notEqual(changes?.disabled, true)
    assert.equal(changes?.config?.timeoutMs, 1000)
  })

  test('repairs the earlier disabled deliverables dependency on upgrade', () => {
    const file = join(home, 'profiles', 'chemclaw', 'cordis.patch.yml')
    writeFileSync(file, readFileSync(file, 'utf8').replace('- id: workspace-changes\n  config:\n    timeoutMs: 1000', '- id: workspace-changes\n  disabled: true'))
    const profile = loadAppProfile()
    const composed = composeEntries([...profile.layers.map(layer => layer.patches), profile.patches])
    const changes = rows(composed).find(entry => entry.id === 'workspace-changes')
    assert.notEqual(changes?.disabled, true)
    assert.equal(changes?.config?.timeoutMs, 1000)
  })

  test('upgrades an earlier preview acknowledgement without changing other preferences', () => {
    const file = join(home, 'profiles', 'chemclaw', 'cordis.patch.yml')
    writeFileSync(file, readFileSync(file, 'utf8').replace('2026-09-28.1', 'older-preview'))
    loadAppProfile()
    const patch = readFileSync(file, 'utf8')
    assert.match(patch, /welcomeNoticeVersion: "2026-09-28.1"/)
    assert.match(patch, /preference: zh/)
  })
})

describe('claimBundles', () => {
  let dir
  before(() => { dir = mkdtempSync(join(tmpdir(), 'ds-bot-app-bundles-')) })
  after(() => { rmSync(dir, { recursive: true, force: true }) })

  const write = (bundles) => {
    mkdirSync(dir, { recursive: true })
    writeFileSync(join(dir, 'package.json'), `${JSON.stringify({ name: 'dsh-profile-chemclaw', private: true, dependencies: { 'a-plugin': '1.0.0' }, dsh: { profile: { bundles } } }, undefined, 2)}\n`)
  }
  const read = () => JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8'))

  test('puts the app bundles first, keeps the user bundles and drops the retired ones', () => {
    write(['@deepseek-ai/dsh-base', 'deepseek-bot-engine', 'ds-bot', 'chemclaw-bot', 'a-plugin'])
    claimBundles(dir)
    assert.deepEqual(read().dsh.profile.bundles, [...BUNDLES, 'a-plugin'])
    assert.deepEqual(read().dependencies, { 'a-plugin': '1.0.0' })
  })

  test('leaves a profile that already lists them alone', () => {
    write([...BUNDLES, 'a-plugin'])
    const before = readFileSync(join(dir, 'package.json'), 'utf8')
    claimBundles(dir)
    assert.equal(readFileSync(join(dir, 'package.json'), 'utf8'), before)
  })
})


test('missing GenUI disables only the optional plugin and restores it when installed', t => {
  const dir = mkdtempSync(join(tmpdir(), 'chemclaw-genui-recovery-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const patch = join(dir, 'cordis.patch.yml')
  const original = '- id: chemclaw\n  config:\n    enabled: true\n'
  writeFileSync(patch, original)
  ensureOptionalGenuiRecovery(dir, false)
  let result = readFileSync(patch, 'utf8')
  assert.match(result, /- id: genui\n  disabled: true/u)
  assert.match(result, /- id: chemclaw/u)
  ensureOptionalGenuiRecovery(dir, false)
  assert.equal(readFileSync(patch, 'utf8'), result, 'repeated startup must not duplicate recovery overrides')
  ensureOptionalGenuiRecovery(dir, true)
  assert.equal(readFileSync(patch, 'utf8').trim(), original.trim())
})
