import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createDurableGroupLedger } from '../src/host/ledger-append.js'
import { publishInitialGroupBook } from '../src/host/ledger-import.js'
import { readLedger } from '../src/host/ledger-foundation.js'

async function emptyBook(t, book = 'group-r1') {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-ledger-append-'))
  t.after(() => rm(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 20 }))
  await publishInitialGroupBook(home, book, [])
  return home
}

const row = (seq, text = 'message ' + seq) => ({ seq, who: 'Chief', text })

test('ordered, concurrent appends only resolve after all earlier records are durable', async t => {
  const home = await emptyBook(t)
  const ledger = createDurableGroupLedger({ home, assertWriter: () => true })
  const results = await Promise.all([
    ledger.append('group-r1', row(1)),
    ledger.append('group-r1', row(2)),
    ledger.append('group-r1', row(3)),
  ])
  assert.deepEqual(results.map(r => r.seq), [1, 2, 3])
  assert.deepEqual(results.map(r => r.reused), [false, false, false])
  await ledger.flush()
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [row(1), row(2), row(3)])
})

test('append succeeds only with a verified exclusive writer and is sticky on refusal', async t => {
  const home = await emptyBook(t)
  let holds = false
  const ledger = createDurableGroupLedger({ home, assertWriter: async () => holds })
  await assert.rejects(ledger.append('group-r1', row(1)), /Exclusive writer lock/)
  holds = true
  await assert.rejects(ledger.append('group-r1', row(1)), /Exclusive writer lock/)
  await assert.rejects(ledger.written('group-r1'), /Exclusive writer lock/)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
  const afterInspection = createDurableGroupLedger({ home, assertWriter: () => true })
  assert.deepEqual(await afterInspection.append('group-r1', row(1)), { seq: 1, reused: false })
})

test('the same durable row is idempotent, but conflicting replay poisons the book', async t => {
  const home = await emptyBook(t)
  const ledger = createDurableGroupLedger({ home, assertWriter: () => true })
  await ledger.append('group-r1', row(1))
  assert.deepEqual(await ledger.append('group-r1', row(1)), { seq: 1, reused: true })
  await assert.rejects(ledger.append('group-r1', row(1, 'different')), /different record/)
  await assert.rejects(ledger.append('group-r1', row(2)), /different record/)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [row(1)])
})

test('an interrupted final JSONL line blocks new writes without erasing the original', async t => {
  const home = await emptyBook(t)
  const path = join(home, 'ledger', 'group-r1.jsonl')
  const tail = JSON.stringify(row(1)) + '\n{"seq":2,"who":"Chief","text":"partial'
  await writeFile(path, tail)
  const ledger = createDurableGroupLedger({ home, assertWriter: () => true })
  await assert.rejects(ledger.append('group-r1', row(2)), /truncated final line/)
  assert.equal(await readFile(path, 'utf8'), tail)
  await assert.rejects(ledger.flush(), /truncated final line/)
})

test('missing book must be initialized separately before any append', async t => {
  const home = await emptyBook(t)
  const ledger = createDurableGroupLedger({ home, assertWriter: () => true })
  await assert.rejects(ledger.append('group-absent', row(1)), /not initialized/)
  assert.equal(await readLedger(home, 'group-absent'), undefined)
})

test('skipped sequences and invalid records are refused without writes', async t => {
  const home = await emptyBook(t)
  const ledger = createDurableGroupLedger({ home, assertWriter: () => true })
  await assert.rejects(ledger.append('group-r1', row(2)), /cannot skip/)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
  const next = createDurableGroupLedger({ home, assertWriter: () => true })
  await assert.rejects(next.append('group-r1', { text: 'no seq' }), /positive integer seq/)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
})

test('simulated disk-write failure is not swallowed or retried automatically', async t => {
  const home = await emptyBook(t)
  let calls = 0
  const ledger = createDurableGroupLedger({
    home,
    assertWriter: () => true,
    beforeWrite: () => { calls++; throw new Error('ENOSPC simulated') },
  })
  await assert.rejects(ledger.append('group-r1', row(1)), /ENOSPC simulated/)
  await assert.rejects(ledger.append('group-r1', row(2)), /ENOSPC simulated/)
  assert.equal(calls, 1)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
  await assert.rejects(ledger.flush('group-r1'), /ENOSPC simulated/)
})

test('a failure on one book does not stop another independent group book', async t => {
  const home = await emptyBook(t)
  await publishInitialGroupBook(home, 'group-r2', [])
  const ledger = createDurableGroupLedger({
    home,
    assertWriter: book => book === 'group-r2',
  })
  await assert.rejects(ledger.append('group-r1', row(1)), /Exclusive writer lock/)
  assert.deepEqual(await ledger.append('group-r2', row(1)), { seq: 1, reused: false })
  assert.deepEqual((await readLedger(home, 'group-r2')).records, [row(1)])
  await assert.rejects(ledger.flush(), /Exclusive writer lock/)
})

test('a new writer after restart sees all durable records and checks the next seq', async t => {
  const home = await emptyBook(t)
  const first = createDurableGroupLedger({ home, assertWriter: () => true })
  await first.append('group-r1', row(1))
  await first.flush()
  const restarted = createDurableGroupLedger({ home, assertWriter: () => true })
  assert.deepEqual(await restarted.append('group-r1', row(1)), { seq: 1, reused: true })
  await restarted.append('group-r1', row(2))
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [row(1), row(2)])
})

test('invalid ledger book paths and a missing lock checker are refused', async t => {
  const home = await emptyBook(t)
  assert.throws(() => createDurableGroupLedger({ home }), /explicit exclusive-writer check/)
  const ledger = createDurableGroupLedger({ home, assertWriter: () => true })
  await assert.rejects(ledger.append('pair-r1-r2', row(1)), /Only a safe group ledger/)
  await assert.rejects(ledger.append('group-../escape', row(1)), /Only a safe group ledger/)
  await assert.rejects(ledger.append('group-r1', row(0)), /positive integer seq/)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
})

test('existing non-consecutive book blocks new writes even when its tail is valid JSONL', async t => {
  const home = await emptyBook(t)
  const path = join(home, 'ledger', 'group-r1.jsonl')
  const old = JSON.stringify(row(1)) + '\n' + JSON.stringify(row(3)) + '\n'
  await writeFile(path, old)
  const ledger = createDurableGroupLedger({ home, assertWriter: () => true })
  await assert.rejects(ledger.append('group-r1', row(4)), /not consecutive/)
  assert.equal(await readFile(path, 'utf8'), old)
})
