import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createDurableGroupLedger } from '../src/host/ledger-append.js'
import { publishInitialGroupBook } from '../src/host/ledger-import.js'
import {
  inspectGroupLedgerRecovery, planGroupLedgerRecovery,
} from '../src/host/ledger-recovery.js'

async function fixture(t) {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-recovery-'))
  t.after(() => rm(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 20 }))
  return home
}
const row = (seq, text = 'message ' + seq) => ({ seq, who: 'ChemClaw', botId: 'chief', text })
const snapshot = (records, tail = '') => ({
  records, incompleteTail: tail,
})

test('fsynced ledger outlives an unsaved state.json without replaying its message', async t => {
  const home = await fixture(t)
  const room = { id: 'r1', seq: 1, log: [row(1)], seen: { chief: 1 }, sessions: { chief: 'session-1' } }
  const state = JSON.stringify({ version: 1, rooms: { r1: room } })
  await writeFile(join(home, 'state.json'), state)
  await publishInitialGroupBook(home, 'group-r1', [row(1)])
  const writer = createDurableGroupLedger({ home, assertWriter: () => true })
  await writer.append('group-r1', row(2, 'fsynced before state save failed'))
  await writer.flush()
  // Simulated crash: there is deliberately no state.json save after append.
  const before = JSON.stringify(room)
  const result = await inspectGroupLedgerRecovery(home, room)
  assert.equal(result.status, 'ledger-ahead')
  assert.deepEqual([result.stateSeq, result.ledgerSeq], [1, 2])
  assert.deepEqual(result.unconfirmedRecords, [row(2, 'fsynced before state save failed')])
  assert.equal(result.mustNotRedispatch, true)
  assert.equal(result.requiresDeliveryReview, true)
  assert.deepEqual(result.previewLog, [row(1), row(2, 'fsynced before state save failed')])
  assert.equal(JSON.stringify(room), before)
  assert.equal(await readFile(join(home, 'state.json'), 'utf8'), state)
  assert.deepEqual(room.seen, { chief: 1 })
  assert.deepEqual(room.sessions, { chief: 'session-1' })
})

test('re-inspection is read-only, idempotent, and does not consider receipts complete', async t => {
  const home = await fixture(t)
  const room = { id: 'r1', seq: 1, log: [row(1)] }
  await publishInitialGroupBook(home, 'group-r1', [row(1), row(2)])
  const first = await inspectGroupLedgerRecovery(home, room)
  const second = await inspectGroupLedgerRecovery(home, room)
  assert.deepEqual(first, second)
  assert.equal(second.status, 'ledger-ahead')
  assert.equal(second.mustNotRedispatch, true)
  assert.deepEqual(room.log, [row(1)])
})

test('a saved state that matches the ledger is aligned without duplicate deliveries', async t => {
  const home = await fixture(t)
  const room = { id: 'r1', seq: 2, log: [row(1), row(2)], seen: { chief: 1 } }
  await publishInitialGroupBook(home, 'group-r1', [row(1), row(2)])
  const result = await inspectGroupLedgerRecovery(home, room)
  assert.equal(result.status, 'aligned')
  assert.deepEqual(result.unconfirmedRecords, [])
  assert.deepEqual(result.previewLog, [])
  assert.equal(result.mustNotRedispatch, true)
})

test('state ahead of the ledger is blocked without dropping saved messages', async t => {
  const home = await fixture(t)
  const room = { id: 'r1', seq: 2, log: [row(1), row(2)] }
  await publishInitialGroupBook(home, 'group-r1', [row(1)])
  const before = structuredClone(room)
  const result = await inspectGroupLedgerRecovery(home, room)
  assert.equal(result.status, 'blocked')
  assert.match(result.reason, /state.json is ahead/)
  assert.deepEqual(result.unconfirmedRecords, [])
  assert.deepEqual(room, before)
})

test('conflicting text or speaker metadata blocks apparent sequence agreement', () => {
  const ledger = snapshot([row(1), row(2)])
  const textConflict = planGroupLedgerRecovery({
    room: { id: 'r1', seq: 1, log: [row(1, 'different')] }, ledger,
  })
  assert.equal(textConflict.status, 'blocked')
  const wrongSpeaker = planGroupLedgerRecovery({
    room: { id: 'r1', seq: 1, log: [{ ...row(1), who: 'Other' }] }, ledger,
  })
  assert.equal(wrongSpeaker.status, 'blocked')
  assert.match(wrongSpeaker.reason, /inconsistent/)
})

test('long ledger text matches a saved truncated prefix and needs an explicit sidecar', async t => {
  const home = await fixture(t)
  const full = '化工'.repeat(1800)
  const first = row(1, full)
  const previous = { ...first, text: full.slice(0, 2000), length: full.length }
  const room = { id: 'r1', seq: 1, log: [previous], seen: { chief: 1 } }
  await publishInitialGroupBook(home, 'group-r1', [first, row(2, 'new')])
  const result = await inspectGroupLedgerRecovery(home, room)
  assert.equal(result.status, 'ledger-ahead')
  assert.equal(result.previewLog[0].length, full.length)
  assert.equal(result.previewLog[0].text, full.slice(0, 2000))
  assert.deepEqual(result.longTextSidecarsNeeded, [1])
  assert.deepEqual(result.unconfirmedRecords, [row(2, 'new')])
  assert.deepEqual(room.log, [previous])
})

test('long text with an incorrect saved length refuses the recovery preview', () => {
  const long = 'x'.repeat(3000)
  const result = planGroupLedgerRecovery({
    room: { id: 'r1', seq: 1, log: [{ ...row(1, long.slice(0, 2000)), length: 2001 }] },
    ledger: snapshot([row(1, long), row(2)]),
  })
  assert.equal(result.status, 'blocked')
})

test('retains only the latest 60 messages in the preview but detects all durable deltas', () => {
  const records = Array.from({ length: 70 }, (_, i) => row(i + 1))
  const room = { id: 'r1', seq: 65, log: records.slice(5, 65) }
  const result = planGroupLedgerRecovery({ room, ledger: snapshot(records) })
  assert.equal(result.status, 'ledger-ahead')
  assert.deepEqual(result.unconfirmedRecords.map(v => v.seq), [66, 67, 68, 69, 70])
  assert.equal(result.previewLog.length, 60)
  assert.equal(result.previewLog[0].seq, 11)
  assert.equal(result.previewLog.at(-1).seq, 70)
})

test('does not invent user group messages or Bot tasks when the saved room is empty', () => {
  const result = planGroupLedgerRecovery({
    room: { id: 'r1', seq: 0, log: [], members: ['b1', 'b2'] },
    ledger: snapshot([row(1, 'delivered before crash')]),
  })
  assert.equal(result.status, 'ledger-ahead')
  assert.deepEqual(result.unconfirmedRecords.map(v => v.seq), [1])
  assert.equal(result.mustNotRedispatch, true)
})

test('a torn JSONL tail, a gap, and incomplete original text all block recovery', () => {
  const room = { id: 'r1', seq: 1, log: [row(1)] }
  const torn = planGroupLedgerRecovery({ room, ledger: snapshot([row(1)], '{"seq":2') })
  assert.equal(torn.status, 'blocked')
  assert.match(torn.reason, /interrupted/)
  const gap = planGroupLedgerRecovery({ room, ledger: snapshot([row(1), row(3)]) })
  assert.equal(gap.status, 'blocked')
  assert.match(gap.reason, /gap/)
  const incomplete = planGroupLedgerRecovery({
    room: { id: 'r1', seq: 0, log: [] },
    ledger: snapshot([{ ...row(1, 'cut'), length: 400 }]),
  })
  assert.equal(incomplete.status, 'blocked')
  assert.match(incomplete.reason, /incomplete/)
})

test('non-migrated rooms remain untouched and are never assumed to have an empty book', async t => {
  const home = await fixture(t)
  const room = { id: 'r1', seq: 3, log: [row(1), row(2), row(3)] }
  const result = await inspectGroupLedgerRecovery(home, room)
  assert.equal(result.status, 'not-migrated')
  assert.equal(result.ledgerSeq, null)
  assert.equal(result.mustNotRedispatch, true)
  assert.deepEqual(room.log.map(v => v.seq), [1, 2, 3])
})

test('malformed saved room state and missing history are never silently repaired', () => {
  assert.throws(() => planGroupLedgerRecovery({
    room: { id: '../escape', seq: 0, log: [] }, ledger: snapshot([]),
  }), /Invalid group id/)
  assert.throws(() => planGroupLedgerRecovery({
    room: { id: 'r1', seq: -1, log: [] }, ledger: snapshot([]),
  }), /Invalid saved group/)
  const result = planGroupLedgerRecovery({
    room: { id: 'r1', seq: 3, log: [] },
    ledger: snapshot([row(1), row(2), row(3), row(4)]),
  })
  assert.equal(result.status, 'blocked')
  assert.match(result.reason, /nonzero sequence/)
})

test('a finished notice remains a notice in the recovery preview', () => {
  const notice = { seq: 1, who: 'ChemClaw', kind: 'notice', reason: 'paused', names: ['Analyst'], limit: 10 }
  const result = planGroupLedgerRecovery({
    room: { id: 'r1', seq: 0, log: [] },
    ledger: snapshot([notice]),
  })
  assert.equal(result.status, 'ledger-ahead')
  assert.deepEqual(result.previewLog, [notice])
  assert.equal(Object.hasOwn(result.previewLog[0], 'text'), false)
})
