import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { nativeOpenFixture } from '../scripts/native-open-fixture.mjs'

test('the isolated native handler records literal paths without shell interpretation', t => {
  const work = mkdtempSync(join(tmpdir(), 'chemclaw-native-open-'))
  t.after(() => rmSync(work, { recursive: true, force: true, maxRetries: 5 }))
  const fixture = nativeOpenFixture(work)
  const path = join(work, '中文 file; literal.xlsx')
  const result = spawnSync(process.execPath, [fixture.entry, path], { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  assert.deepEqual(fixture.received(), [path])
})

test('Linux xdg-open delegates a directory to the isolated desktop handler', { skip: process.platform !== 'linux' }, t => {
  const work = mkdtempSync(join(tmpdir(), 'chemclaw-native-xdg-'))
  t.after(() => rmSync(work, { recursive: true, force: true, maxRetries: 5 }))
  const fixture = nativeOpenFixture(work)
  const path = join(work, '中文 directory')
  mkdirSync(path)
  const result = spawnSync('xdg-open', [path], {
    env: { ...process.env, ...fixture.env, DISPLAY: process.env.DISPLAY || ':99' },
    encoding: 'utf8', timeout: 10_000,
  })
  assert.equal(result.status, 0, result.error?.message ?? result.stderr)
  assert.deepEqual(fixture.received(), [path])
})
