import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { readLedger } from '../src/host/ledger-foundation.js'
import {
  legacyGroupLogFilename, planLegacyGroupImport, publishInitialGroupBook,
  readLegacyGroupLog, seedLegacyGroupLedger,
} from '../src/host/ledger-import.js'

async function fixture(t) {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-ledger-import-'))
  t.after(() => rm(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 20 }))
  return home
}

const row = (seq, text) => ({ seq, who: 'Chief', text })
async function archive(home, id, lines) {
  const dir = join(home, 'group-logs')
  await mkdir(dir, { recursive: true })
  const path = join(dir, legacyGroupLogFilename(id))
  await writeFile(path, lines)
  return path
}

test('imports exact old group-log + latest room.log once without touching old files', async t => {
  const home = await fixture(t)
  const history = [row(1, 'oldest'), row(2, 'early'), row(3, 'shared'), row(4, 'latest')]
  const path = await archive(home, 'r1', history.slice(0, 3).map(v => JSON.stringify(v) + '\n').join(''))
  const room = { id: 'r1', seq: 4, log: history.slice(2) }
  const oldState = JSON.stringify({ rooms: { r1: room } })
  await writeFile(join(home, 'state.json'), oldState)
  const planned = await planLegacyGroupImport({ home, room })
  assert.equal(planned.ready, true, planned.warnings.join('; '))
  assert.deepEqual(planned.rows.map(v => v.seq), [1, 2, 3, 4])
  const seeded = await seedLegacyGroupLedger({ home, room })
  assert.equal(seeded.rows, 4)
  assert.equal(seeded.reused, false)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, history)
  const repeated = await seedLegacyGroupLedger({ home, room })
  assert.equal(repeated.reused, true)
  assert.equal(await readFile(join(home, 'state.json'), 'utf8'), oldState)
  assert.equal((await readFile(path, 'utf8')).split('\n').filter(Boolean).length, 3)
})

test('a contiguous old state window can seed an empty/new archive safely', async t => {
  const home = await fixture(t)
  const room = { id: 'r1', seq: 2, log: [row(1, 'first'), row(2, 'last')] }
  const plan = await planLegacyGroupImport({ home, room })
  assert.equal(plan.legacyArchiveFound, false)
  assert.equal(plan.ready, true, plan.warnings.join('; '))
  await seedLegacyGroupLedger({ home, room })
  assert.deepEqual((await readLedger(home, 'group-r1')).records, room.log)
})

test('a truncated historical prefix blocks publication and preserves old state', async t => {
  const home = await fixture(t)
  const room = { id: 'r1', seq: 12, log: [row(12, 'tail')] }
  const state = JSON.stringify({ rooms: { r1: room } })
  await writeFile(join(home, 'state.json'), state)
  const plan = await planLegacyGroupImport({ home, room })
  assert.equal(plan.ready, false)
  assert.ok(plan.warnings.some(w => w.includes('older history')))
  await assert.rejects(seedLegacyGroupLedger({ home, room }), /import is incomplete/)
  assert.equal(await readLedger(home, 'group-r1'), undefined)
  assert.equal(await readFile(join(home, 'state.json'), 'utf8'), state)
})

test('a partial last line in the old group archive is never silently imported', async t => {
  const home = await fixture(t)
  await archive(home, 'r1', JSON.stringify(row(1, 'complete')) + '\n{"seq":2,"text":"interrup')
  const room = { id: 'r1', seq: 1, log: [row(1, 'complete')] }
  const plan = await planLegacyGroupImport({ home, room })
  assert.equal(plan.ready, false)
  assert.ok(plan.warnings.some(w => w.includes('interrupted JSONL')))
  await assert.rejects(seedLegacyGroupLedger({ home, room }), /import is incomplete/)
  assert.equal(await readLedger(home, 'group-r1'), undefined)
})

test('corrupt archive row with newline is a hard failure, not skipped', async t => {
  const home = await fixture(t)
  await archive(home, 'r1', JSON.stringify(row(1, 'okay')) + '\nbroken-json\n')
  await assert.rejects(planLegacyGroupImport({
    home, room: { id: 'r1', seq: 1, log: [row(1, 'okay')] },
  }), /corrupt complete line/)
})

test('a conflicting archived row and room row never silently drop either value', async t => {
  const home = await fixture(t)
  await archive(home, 'r1', JSON.stringify(row(1, 'archive says A')) + '\n')
  await assert.rejects(planLegacyGroupImport({
    home, room: { id: 'r1', seq: 1, log: [row(1, 'state says B')] },
  }), /Conflicting legacy group sequence/)
})

test('old archive files retain the historical 32-character hashed naming convention', async t => {
  const home = await fixture(t)
  const id = 'x'.repeat(130)
  assert.match(legacyGroupLogFilename(id), /^[a-f0-9]{32}\.jsonl$/)
  await archive(home, id, JSON.stringify(row(1, 'old')) + '\n')
  assert.deepEqual((await readLegacyGroupLog(home, id)).rows, [row(1, 'old')])
  assert.throws(() => legacyGroupLogFilename('../escape'), /Invalid legacy group id/)
})

test('atomic publication is no-clobber even for simultaneous identical writers', async t => {
  const home = await fixture(t)
  const rows = [row(1, 'one'), row(2, 'two')]
  const both = await Promise.all([
    publishInitialGroupBook(home, 'group-r1', rows),
    publishInitialGroupBook(home, 'group-r1', rows),
  ])
  assert.deepEqual(both.map(v => v.reused).sort(), [false, true])
  assert.deepEqual((await readLedger(home, 'group-r1')).records, rows)
  await assert.rejects(publishInitialGroupBook(home, 'group-r1', [row(1, 'different')]), /existing group ledger differs/)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, rows)
  assert.deepEqual((await readdir(join(home, 'ledger'))).filter(n => n.includes('.pending-')), [])
})

test('orphan temporary import from a simulated crash cannot masquerade as a book', async t => {
  const home = await fixture(t)
  await mkdir(join(home, 'ledger'), { recursive: true })
  const pending = join(home, 'ledger', 'group-r1.jsonl.pending-orphan')
  await writeFile(pending, JSON.stringify(row(1, 'uncommitted')) + '\n')
  assert.equal(await readLedger(home, 'group-r1'), undefined)
  await publishInitialGroupBook(home, 'group-r1', [row(1, 'real')])
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [row(1, 'real')])
  assert.match(await readFile(pending, 'utf8'), /uncommitted/)
})

test('the publisher rejects non-consecutive, malformed and out-of-scope records', async t => {
  const home = await fixture(t)
  await assert.rejects(publishInitialGroupBook(home, 'pair-r1-r2', [row(1, 'x')]), /Only a group book/)
  await assert.rejects(publishInitialGroupBook(home, 'group-r1', [row(2, 'not first')]), /consecutive sequences/)
  await assert.rejects(publishInitialGroupBook(home, 'group-r1', [row(1, 'ok'), row(3, 'gap')]), /consecutive sequences/)
  assert.equal(await readLedger(home, 'group-r1'), undefined)
})

test('missing long-text content blocks a publication even when old archive is present', async t => {
  const home = await fixture(t)
  const old = { seq: 1, who: 'Chief', text: 'short', length: 100 }
  await archive(home, 'r1', JSON.stringify(old) + '\n')
  const room = { id: 'r1', seq: 1, log: [old] }
  const plan = await planLegacyGroupImport({ home, room })
  assert.equal(plan.ready, false)
  assert.ok(plan.warnings.some(w => w.includes('incomplete')))
  await assert.rejects(seedLegacyGroupLedger({ home, room }), /import is incomplete/)
  assert.equal(await readLedger(home, 'group-r1'), undefined)
})

test('a genuinely empty legacy room can be initialized without invented history', async t => {
  const home = await fixture(t)
  const room = { id: 'r1', seq: 0, log: [] }
  const result = await seedLegacyGroupLedger({ home, room })
  assert.equal(result.rows, 0)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
})
