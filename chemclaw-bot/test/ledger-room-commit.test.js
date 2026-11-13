import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createGroupLedgerCommitter } from '../src/host/ledger-room-commit.js'
import { publishInitialGroupBook } from '../src/host/ledger-import.js'
import { readLedger } from '../src/host/ledger-foundation.js'
import { inspectGroupLedgerRecovery } from '../src/host/ledger-recovery.js'
import { GROUP_LINE_READ, TEXT_KEPT } from '../src/host/constants.js'
import { headOf } from '../src/host/text.js'

const row = (seq, text = 'message ' + seq) => ({ seq, who: 'ChemClaw', botId: 'chief', text })
const preview = record => typeof record.text === 'string' && record.text.length > TEXT_KEPT
  ? { ...record, text: headOf(record.text, TEXT_KEPT), length: record.text.length } : { ...record }

async function fixture(t, rows = [], id = 'r1') {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-room-commit-'))
  t.after(() => rm(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 30 }))
  const room = { id, seq: rows.length, log: rows.slice(-60).map(preview), seen: { chief: 0 } }
  await publishInitialGroupBook(home, 'group-' + id, rows)
  const stateFile = join(home, 'state.json')
  const persist = () => writeFile(stateFile, JSON.stringify({ rooms: { [id]: room } }))
  await persist()
  return { home, room, stateFile, persist }
}

const create = ({ home, persist, assertWriter = () => true, beforeWrite } = {}) =>
  createGroupLedgerCommitter({ home, assertWriter, saveState: persist, beforeWrite })

test('group line is durable before visible state mutation and before the required state save', async t => {
  const { home, room, stateFile } = await fixture(t)
  let saved = 0
  const writer = create({
    home,
    beforeWrite: async () => {
      assert.equal(room.seq, 0)
      assert.deepEqual(room.log, [])
    },
    persist: async () => {
      const onDisk = await readLedger(home, 'group-r1')
      assert.equal(onDisk.records.length, 1, 'Ledger must be fsynced before state.json save')
      assert.equal(room.seq, 1)
      assert.equal(room.log.length, 1)
      await writeFile(stateFile, JSON.stringify({ rooms: { r1: room } }))
      saved++
    },
  })
  const result = await writer.commit(room, { who: 'ChemClaw', botId: 'chief', text: 'first result' })
  assert.deepEqual(result.record, row(1, 'first result'))
  assert.deepEqual(result.preview, row(1, 'first result'))
  assert.equal(saved, 1)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [row(1, 'first result')])
  assert.equal(JSON.parse(await readFile(stateFile, 'utf8')).rooms.r1.seq, 1)
})

test('concurrent group commits preserve order, unique sequence and state cache', async t => {
  const { home, room, persist } = await fixture(t)
  const writer = create({ home, persist })
  const results = await Promise.all([
    writer.commit(room, { who: 'ChemClaw', botId: 'chief', text: 'first' }),
    writer.commit(room, { who: 'User', text: 'second' }),
    writer.commit(room, { who: 'Analyst', botId: 'a1', text: 'third' }),
  ])
  assert.deepEqual(results.map(v => v.seq), [1, 2, 3])
  assert.deepEqual(room.log.map(v => v.seq), [1, 2, 3])
  assert.equal(room.seq, 3)
  assert.deepEqual((await readLedger(home, 'group-r1')).records.map(v => v.seq), [1, 2, 3])
  await writer.flush()
})

test('large UTF-8 texts remain whole in Ledger, short in state, and readable through a sidecar', async t => {
  const { home, room, persist } = await fixture(t)
  const full = '化工📈能源'.repeat(5_000)
  const writer = create({ home, persist })
  await writer.commit(room, { who: 'ChemClaw', botId: 'chief', text: full })
  const kept = room.log[0]
  assert.equal(kept.length, full.length)
  assert.equal(kept.text, headOf(full, TEXT_KEPT))
  const sidecar = await readFile(join(home, 'group-lines', 'r1', '1.txt'), 'utf8')
  assert.equal(sidecar, headOf(full, GROUP_LINE_READ))
  assert.equal((await readLedger(home, 'group-r1')).records[0].text, full)
  assert.equal((await inspectGroupLedgerRecovery(home, room)).status, 'aligned')
})

test('old reading sidecars are never deleted when room.log rolls over its sixty-row window', async t => {
  const initial = Array.from({ length: 60 }, (_, i) => row(i + 1, 'text ' + (i + 1)))
  const { home, room, persist } = await fixture(t, initial)
  const oldFile = join(home, 'group-lines', 'r1', '1.txt')
  await writeFile(oldFile, 'legacy previous reader sidecar')
  const writer = create({ home, persist })
  await writer.commit(room, { who: 'User', text: 'new message' })
  assert.equal(room.seq, 61)
  assert.equal(room.log.length, 60)
  assert.equal(room.log[0].seq, 2)
  assert.equal(room.log.at(-1).seq, 61)
  assert.equal(await readFile(oldFile, 'utf8'), 'legacy previous reader sidecar')
  assert.equal((await readLedger(home, 'group-r1')).records.length, 61)
})

test('the adapter refuses missing import; it cannot create a new book by accident', async t => {
  const { home, room, persist } = await fixture(t)
  await rm(join(home, 'ledger', 'group-r1.jsonl'))
  const writer = create({ home, persist })
  await assert.rejects(writer.commit(room, { who: 'User', text: 'unimported' }), /not-migrated/)
  assert.equal(room.seq, 0)
  assert.deepEqual(room.log, [])
  assert.equal(await readLedger(home, 'group-r1'), undefined)
})

test('Ledger ahead of state after a crash blocks all further commits, with no replay', async t => {
  const { home, room, persist, stateFile } = await fixture(t, [row(1)])
  const before = await readFile(stateFile, 'utf8')
  await writeFile(join(home, 'ledger', 'group-r1.jsonl'),
    JSON.stringify(row(1)) + '\n' + JSON.stringify(row(2, 'written but not saved')) + '\n')
  const writer = create({ home, persist })
  await assert.rejects(writer.commit(room, { who: 'User', text: 'new attempt' }), /ledger-ahead/)
  assert.equal(room.seq, 1)
  assert.deepEqual(room.log, [row(1)])
  assert.equal(await readFile(stateFile, 'utf8'), before)
  assert.equal((await readLedger(home, 'group-r1')).records.length, 2)
})

test('saving state.json after an fsynced append can fail; the book stays ahead and is never dispatched', async t => {
  const { home, room, stateFile } = await fixture(t)
  const before = await readFile(stateFile, 'utf8')
  let calls = 0
  const writer = create({
    home,
    persist: async () => { calls++; throw new Error('EACCES simulated state save') },
  })
  await assert.rejects(writer.commit(room, { who: 'User', text: 'persisted only in ledger' }), /EACCES simulated/)
  assert.equal(calls, 1)
  assert.equal(room.seq, 1, 'memory may be ahead but must never be treated as saved')
  assert.equal((await readLedger(home, 'group-r1')).records.length, 1)
  assert.equal(await readFile(stateFile, 'utf8'), before)
  await assert.rejects(writer.commit(room, { who: 'User', text: 'must not continue' }), /EACCES simulated/)
  assert.equal((await readLedger(home, 'group-r1')).records.length, 1)
  const restartedState = JSON.parse(await readFile(stateFile, 'utf8')).rooms.r1
  const recovered = await inspectGroupLedgerRecovery(home, restartedState)
  assert.equal(recovered.status, 'ledger-ahead')
  assert.equal(recovered.mustNotRedispatch, true)
  const newWriter = create({ home, persist: () => Promise.resolve() })
  await assert.rejects(newWriter.commit(restartedState, { who: 'User', text: 'no unsafe continuation' }), /ledger-ahead/)
})

test('a failed ledger append never mutates state or calls the state saver', async t => {
  const { home, room, persist } = await fixture(t)
  let saved = 0
  const writer = create({
    home, beforeWrite: () => { throw new Error('ENOSPC simulated') },
    persist: async () => { saved++; await persist() },
  })
  await assert.rejects(writer.commit(room, { who: 'User', text: 'not written' }), /ENOSPC simulated/)
  assert.equal(saved, 0)
  assert.equal(room.seq, 0)
  assert.deepEqual(room.log, [])
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
  await assert.rejects(writer.flush(), /ENOSPC simulated/)
})

test('a strict ownership failure refuses both Ledger and state writes', async t => {
  const { home, room } = await fixture(t)
  let saved = 0
  const writer = create({
    home, assertWriter: () => false,
    persist: () => { saved++ },
  })
  await assert.rejects(writer.commit(room, { who: 'User', text: 'no lock' }), /Exclusive writer lock/)
  assert.equal(saved, 0)
  assert.equal(room.seq, 0)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
})

test('a lock loss after Ledger fsync but before state save blocks the room', async t => {
  const { home, room } = await fixture(t)
  let checks = 0
  let saved = 0
  // commit() checks, append() checks twice, then commit() rechecks before save.
  const writer = create({
    home,
    assertWriter: () => ++checks <= 3,
    persist: () => { saved++ },
  })
  await assert.rejects(writer.commit(room, { who: 'User', text: 'safely fsynced' }), /lock lost before saving/)
  assert.equal(saved, 0)
  assert.equal(room.seq, 0)
  assert.equal((await readLedger(home, 'group-r1')).records.length, 1)
})

test('external legacy room mutation while fsync is in flight blocks state overwrite', async t => {
  const { home, room, persist } = await fixture(t)
  const writer = create({
    home, persist,
    beforeWrite: () => {
      room.seq = 7
      room.log = [row(7, 'legacy concurrent change')]
    },
  })
  await assert.rejects(writer.commit(room, { who: 'User', text: 'fsynced' }), /Legacy room state changed/)
  assert.equal(room.seq, 7)
  assert.deepEqual(room.log, [row(7, 'legacy concurrent change')])
  assert.equal((await readLedger(home, 'group-r1')).records.length, 1)
})

test('a sidecar collision is a blocking error and never overwrites older user data', async t => {
  const { home, room, persist } = await fixture(t)
  const dir = join(home, 'group-lines', 'r1')
  await import('node:fs/promises').then(fs => fs.mkdir(dir, { recursive: true }))
  const existing = join(dir, '1.txt')
  await writeFile(existing, 'unrelated legacy file')
  const writer = create({ home, persist })
  await assert.rejects(writer.commit(room, { who: 'User', text: 'x'.repeat(TEXT_KEPT + 500) }),
    /Conflicting existing long-text sidecar/)
  assert.equal(await readFile(existing, 'utf8'), 'unrelated legacy file')
  assert.equal(room.seq, 0)
  assert.equal((await readLedger(home, 'group-r1')).records.length, 1)
})

test('message payload is snapshotted before entering a queue while earlier work runs', async t => {
  const { home, room, persist } = await fixture(t)
  let release
  const blocked = new Promise(resolve => { release = resolve })
  const writer = create({
    home, persist,
    beforeWrite: async (_book, record) => { if (record.seq === 1) await blocked },
  })
  const first = writer.commit(room, { who: 'User', text: 'first' })
  const next = { who: 'User', text: 'original queued' }
  const second = writer.commit(room, next)
  next.text = 'caller changed payload'
  release()
  await Promise.all([first, second])
  assert.deepEqual((await readLedger(home, 'group-r1')).records.map(r => r.text), ['first', 'original queued'])
})

test('invalid unsequenced input poisons that group queue without touching its ledger', async t => {
  const { home, room, persist } = await fixture(t)
  const writer = create({ home, persist })
  await assert.rejects(writer.commit(room, { seq: 9000, who: 'User', text: 'wrong seq' }), /unsequenced message/)
  await assert.rejects(writer.commit(room, { who: 'User', text: 'later' }), /unsequenced message/)
  assert.equal(room.seq, 0)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
})

test('a corrupted or state-ahead room is never silently reconciled during commit', async t => {
  const { home, room, persist } = await fixture(t, [row(1)])
  room.seq = 2
  const writer = create({ home, persist })
  await assert.rejects(writer.commit(room, { who: 'User', text: 'bad state' }), /blocked/)
  assert.equal((await readLedger(home, 'group-r1')).records.length, 1)
})

test('the required state saver and safe group id cannot be omitted', async t => {
  const { home, room, persist } = await fixture(t)
  assert.throws(() => createGroupLedgerCommitter({ home, assertWriter: () => true }), /required state-save/)
  const writer = create({ home, persist })
  await assert.rejects(writer.commit({ ...room, id: '../escape' }, { who: 'User', text: 'no' }), /valid group room/)
})
