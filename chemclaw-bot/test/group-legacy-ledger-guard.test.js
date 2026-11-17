import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, mkdir, rm, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createLegacyGroupLedgerGuard } from '../src/host/group-legacy-ledger-guard.js'
import { ledgerFilename } from '../src/host/ledger-foundation.js'

async function fixture(t) {
  const home = await mkdtemp(join(tmpdir(), 'legacy-ledger-gate-'))
  t.after(() => rm(home, { recursive: true, force: true }))
  const guard = createLegacyGroupLedgerGuard({ home })
  const makeBook = async (roomId, content = '') => {
    const dir = join(home, 'ledger')
    await mkdir(dir, { recursive: true })
    const path = join(dir, ledgerFilename('group-' + roomId))
    await writeFile(path, content)
    return path
  }
  return { home, guard, makeBook }
}

test('a legacy room with no Ledger book remains writable', async t => {
  const { guard } = await fixture(t)
  assert.equal(guard.status('r1'), undefined)
  assert.doesNotThrow(() => guard.assertWritable('r1'))
})

test('a published Ledger blocks legacy writes even when it is an empty book', async t => {
  const { guard, makeBook } = await fixture(t)
  await makeBook('r1')
  assert.equal(guard.status('r1').code, 'LEDGER_MIGRATION_REQUIRED')
  assert.throws(() => guard.assertWritable('r1'), error => error.code === 'LEDGER_MIGRATION_REQUIRED')
})

test('the check is per-room and sees a Ledger published after the Host started', async t => {
  const { guard, makeBook } = await fixture(t)
  assert.equal(guard.status('r1'), undefined)
  await makeBook('r1', '{"seq":1}\n')
  assert.equal(guard.status('r1').code, 'LEDGER_MIGRATION_REQUIRED')
  assert.equal(guard.status('r2'), undefined)
  assert.doesNotThrow(() => guard.assertWritable('r2'))
})

test('invalid, incomplete and corrupt Ledger books never enable legacy fallback', async t => {
  const { guard, makeBook } = await fixture(t)
  assert.equal(guard.status('../r1').code, 'LEDGER_CHECK_FAILED')
  await makeBook('r1', '{"seq":1')
  assert.throws(() => guard.assertWritable('r1'), /Ledger book/)
})

test('a dangling Ledger symlink does not bypass legacy writer protection', async t => {
  if (process.platform === 'win32') return t.skip('Windows symlink permissions differ')
  const { home, guard } = await fixture(t)
  const dir = join(home, 'ledger')
  await mkdir(dir, { recursive: true })
  await symlink(join(home, 'nonexistent-ledger-target'), join(dir, ledgerFilename('group-r1')))
  assert.equal(guard.status('r1').code, 'LEDGER_MIGRATION_REQUIRED')
  assert.throws(() => guard.assertWritable('r1'), error => error.code === 'LEDGER_MIGRATION_REQUIRED')
})

test('a missing Ledger home rejects construction', () => {
  assert.throws(() => createLegacyGroupLedgerGuard({ home: '' }), /home is required/)
})
