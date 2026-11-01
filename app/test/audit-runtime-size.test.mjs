import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { runtimeSizeReport, sizeOf } from '../scripts/audit-runtime-size.mjs'

test('size audit returns exact bytes, reads market manifest, and reports duplicated Python', t => {
  const app = mkdtempSync(join(tmpdir(), 'chemclaw-size-test-'))
  t.after(() => rmSync(app, { recursive: true, force: true }))
  const python = join(app, 'build', 'runtime', 'primary-runtime', 'dependencies', 'python')
  mkdirSync(python, { recursive: true })
  writeFileSync(join(python, 'python.exe'), Buffer.alloc(11))
  const market = join(app, 'node_modules', 'chemclaw-bot', 'runtime', 'bundled')
  mkdirSync(market, { recursive: true })
  writeFileSync(join(market, 'win32-x64.tar.gz'), Buffer.alloc(19))
  writeFileSync(join(market, 'win32-x64.json'), JSON.stringify({ python: '3.12', unpackedBytes: 123 }))
  assert.equal(sizeOf(python), 11)
  const result = runtimeSizeReport({ app, platform: 'win32', arch: 'x64' })
  assert.equal(result.officePythonBytes, 11)
  assert.equal(result.marketArchiveBytes, 19)
  assert.equal(result.marketUnpackedBytes, 123)
  assert.equal(result.duplicatePythonDistributions, true)
  assert.equal(result.officeNodeBytes, null)
})
test('missing market archive cannot be mistaken for an unpacked runtime', t => {
  const app = mkdtempSync(join(tmpdir(), 'chemclaw-size-test-'))
  t.after(() => rmSync(app, { recursive: true, force: true }))
  const r = runtimeSizeReport({ app, platform: 'win32', arch: 'x64' })
  assert.equal(r.duplicatePythonDistributions, false)
  assert.equal(r.marketUnpackedBytes, null)
  assert.equal(r.installer, null)
})
