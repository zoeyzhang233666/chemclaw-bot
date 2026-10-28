import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { profileKey, resolveProfile } from '../../scripts/launch-profiles.mjs'

test('profile keys isolate pr and integration away from baseline', () => {
  assert.equal(profileKey({ kind: 'main' }), 'baseline')
  assert.equal(profileKey({ kind: 'integration' }), 'integration')
  assert.equal(profileKey({ kind: 'pr', number: 64 }), 'pr-64')
  assert.equal(profileKey({ profile: 'custom' }), 'custom')
})

test('isolated profiles do not copy credentials unless requested', t => {
  const origin = mkdtempSync(join(tmpdir(), 'chemclaw-profile-'))
  t.after(() => rmSync(origin, { recursive: true, force: true }))
  mkdirSync(join(origin, '.chemclaw-dev', 'data', 'chemclaw'), { recursive: true })
  writeFileSync(join(origin, '.chemclaw-dev', 'data', '.credentials.yaml'), 'secret: 1\n')
  writeFileSync(join(origin, '.chemclaw-dev', 'data', 'chemclaw', 'secrets.json'), '{"k":1}')
  writeFileSync(join(origin, '.chemclaw-dev', 'data', 'chemclaw', 'state.json'), '{"bots":[]}')

  const blocked = resolveProfile(origin, { kind: 'pr', number: 64 }, { copyCredentials: false })
  assert.equal(blocked.isolated, true)
  assert.equal(blocked.copiedCredentials, false)
  assert.equal(existsSync(join(blocked.data, '.credentials.yaml')), false)
  assert.equal(existsSync(join(blocked.data, 'chemclaw', 'secrets.json')), false)
  assert.equal(existsSync(join(blocked.data, 'chemclaw', 'state.json')), false)
  assert.match(readFileSync(join(blocked.home, 'PROFILE.txt'), 'utf8'), /not copied/i)

  const allowed = resolveProfile(origin, { kind: 'integration' }, { copyCredentials: true })
  assert.equal(allowed.copiedCredentials, true)
  assert.equal(readFileSync(join(allowed.data, '.credentials.yaml'), 'utf8'), 'secret: 1\n')
  assert.equal(existsSync(join(allowed.data, 'chemclaw', 'state.json')), false)
})
