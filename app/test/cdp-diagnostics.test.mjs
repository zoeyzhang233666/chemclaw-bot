import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { createCdpDiagnosticWriter } from '../src/cdp-diagnostics.mjs'

test('CDP diagnostics retain only allowlisted event names, bounded histories and no credentials', t => {
  const root = mkdtempSync(join(tmpdir(), 'chemclaw-cdp-log-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const path = join(root, 'cdp-frame-diagnostics.log')
  const write = createCdpDiagnosticWriter(path)
  write({
    method: 'Page.frameAttached',
    reason: 'duplicate-attach',
    recent: [{ method: 'Page.getFrameTree', outcome: 'accepted' }, {
      method: 'https://example.com/?token=SECRET123', outcome: 'SECRET123',
    }],
  })
  const content = readFileSync(path, 'utf8')
  const record = JSON.parse(content.trim())
  assert.equal(record.method, 'Page.frameAttached')
  assert.equal(record.reason, 'duplicate-attach')
  assert.deepEqual(record.recent.at(-1), { method: 'other', outcome: 'other' })
  assert.equal(content.includes('SECRET123'), false)
  assert.equal(content.includes('https://'), false)
})

test('CDP diagnostics rotate oversized history and never throw on disk errors', t => {
  const root = mkdtempSync(join(tmpdir(), 'chemclaw-cdp-log-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const path = join(root, 'cdp.log')
  writeFileSync(path, 'x'.repeat(100))
  const write = createCdpDiagnosticWriter(path, { maxBytes: 20 })
  write({ method: 'Page.frameAttached', reason: 'unknown-parent' })
  assert.equal(readFileSync(path, 'utf8').includes('x'.repeat(100)), false)
  // A directory is not a file: an error is reported rather than escaping the Host.
  const errors = []
  createCdpDiagnosticWriter(root, { onError: error => errors.push(error.code) })({
    method: 'Page.frameAttached', reason: 'duplicate-attach',
  })
  assert.ok(errors.length > 0)
})
