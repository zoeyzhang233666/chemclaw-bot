import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { publishInitialGroupBook } from '../src/host/ledger-import.js'
import { readLedger } from '../src/host/ledger-foundation.js'
import { createGroupDeliveryJournal, inspectGroupDeliveries } from '../src/host/ledger-delivery.js'

const groupRow = (seq, text = 'message ' + seq) => ({ seq, who: 'User', text })
const params = (deliveryId = 'call-1', roomSeq = 1, recipientId = 'analyst') =>
  ({ roomId: 'r1', roomSeq, deliveryId, recipientId })

async function fixture(t, rows = [groupRow(1)]) {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-delivery-journal-'))
  t.after(() => rm(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 30 }))
  await publishInitialGroupBook(home, 'group-r1', rows)
  const originalState = JSON.stringify({ rooms: { r1: { id: 'r1', seq: rows.length, log: rows } } })
  await writeFile(join(home, 'state.json'), originalState)
  return { home, originalState }
}

const journalPath = home => join(home, 'delivery-receipts', 'ledger', 'group-r1.jsonl')

test('a durable attempt before DSH call survives restart as unknown and is never auto-replayed', async t => {
  const { home, originalState } = await fixture(t)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await writer.initialize('r1')
  await writer.begin(params())
  // The process exits here, before send or an API receipt.
  const afterRestart = await inspectGroupDeliveries(home, 'r1')
  assert.equal(afterRestart.status, 'ready')
  assert.deepEqual(afterRestart.entries, [
    { deliveryId: 'call-1', roomSeq: 1, recipientId: 'analyst', status: 'unknown' },
  ])
  assert.equal(afterRestart.mustNotRedispatch, true)
  const restarted = createGroupDeliveryJournal({ home, assertWriter: () => true })
  let sent = 0
  await assert.rejects(restarted.dispatchOnce({
    ...params(), send: async () => { sent++ },
  }), /already attempted/)
  assert.equal(sent, 0)
  assert.equal(await readFile(join(home, 'state.json'), 'utf8'), originalState)
})

test('the API-returned receipt is fsynced after the callback returns', async t => {
  const { home } = await fixture(t)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await writer.initialize('r1')
  let sent = 0
  const result = await writer.dispatchOnce({
    ...params(),
    send: async () => {
      sent++
      const previous = await writer.inspect('r1')
      assert.equal(previous.entries[0].status, 'unknown')
      assert.match(await readFile(journalPath(home), 'utf8'), /"stage":"attempt"/)
      return { accepted: true }
    },
  })
  assert.deepEqual(result, { accepted: true })
  assert.equal(sent, 1)
  const after = await writer.inspect('r1')
  assert.equal(after.entries[0].status, 'api-returned')
  assert.equal(after.mustNotRedispatch, true)
  assert.equal((await readLedger(join(home, 'delivery-receipts'), 'group-r1')).records.length, 2)
  assert.equal((await readLedger(home, 'group-r1')).records.length, 1)
})

test('a failed external call leaves an unknown attempt; repeat calls cannot execute', async t => {
  const { home } = await fixture(t)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await writer.initialize('r1')
  let sends = 0
  await assert.rejects(writer.dispatchOnce({
    ...params(), send: async () => { sends++; throw new Error('DSH bridge disconnected') },
  }), /DSH bridge disconnected/)
  assert.equal((await writer.inspect('r1')).entries[0].status, 'unknown')
  await assert.rejects(writer.dispatchOnce({
    ...params(), send: async () => { sends++ },
  }), /already attempted/)
  assert.equal(sends, 1)
})

test('losing the writer lock after API returned cannot claim a durable receipt', async t => {
  const { home } = await fixture(t)
  let hasLock = true
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => hasLock })
  await writer.initialize('r1')
  await assert.rejects(writer.dispatchOnce({
    ...params(), send: async () => { hasLock = false; return { done: true } },
  }), /Exclusive writer lock/)
  const after = await inspectGroupDeliveries(home, 'r1')
  assert.equal(after.status, 'ready')
  assert.equal(after.entries[0].status, 'unknown')
  assert.equal(after.mustNotRedispatch, true)
})

test('a mismatched receipt and an unrecorded API success cannot be acknowledged', async t => {
  const { home } = await fixture(t)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await writer.initialize('r1')
  await assert.rejects(writer.markApiReturned(params()), /missing or mismatched/)
  const afterFailure = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await afterFailure.begin(params())
  await assert.rejects(afterFailure.markApiReturned(params('call-1', 1, 'different')), /missing or mismatched/)
  assert.equal((await inspectGroupDeliveries(home, 'r1')).entries[0].status, 'unknown')
})

test('a delivery receipt is never allowed before its source group message is durable', async t => {
  const { home } = await fixture(t)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await writer.initialize('r1')
  await assert.rejects(writer.begin(params('call-missing', 2)), /must be durable/)
  assert.deepEqual((await inspectGroupDeliveries(home, 'r1')).entries, [])
})

test('two unrelated recipients get distinct, sequential receipt events', async t => {
  const { home } = await fixture(t)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await writer.initialize('r1')
  const [one, two] = await Promise.all([
    writer.begin(params('call-1', 1, 'analyst')),
    writer.begin(params('call-2', 1, 'trader')),
  ])
  assert.equal(one.status, 'attempt-recorded')
  assert.equal(two.status, 'attempt-recorded')
  const journal = await readLedger(join(home, 'delivery-receipts'), 'group-r1')
  assert.deepEqual(journal.records.map(e => e.seq), [1, 2])
  assert.deepEqual((await writer.inspect('r1')).entries.map(e => e.status), ['unknown', 'unknown'])
})

test('a second attempt for the same stable ID is blocked without calling external systems', async t => {
  const { home } = await fixture(t)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await writer.initialize('r1')
  const first = writer.begin(params())
  const second = writer.begin(params())
  const outcome = await Promise.allSettled([first, second])
  assert.equal(outcome[0].status, 'fulfilled')
  assert.equal(outcome[1].status, 'rejected')
  assert.match(String(outcome[1].reason), /already attempted/)
  assert.equal((await inspectGroupDeliveries(home, 'r1')).entries.length, 1)
})

test('an exact duplicate API receipt can be observed without appending another row', async t => {
  const { home } = await fixture(t)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await writer.initialize('r1')
  await writer.begin(params())
  assert.deepEqual(await writer.markApiReturned(params()), { status: 'api-returned', reused: false })
  assert.deepEqual(await writer.markApiReturned(params()), { status: 'api-returned', reused: true })
  assert.equal((await readLedger(join(home, 'delivery-receipts'), 'group-r1')).records.length, 2)
})

test('a torn receipt record blocks reading and future sends without deleting history', async t => {
  const { home } = await fixture(t)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await writer.initialize('r1')
  await writer.begin(params())
  const file = journalPath(home)
  const text = await readFile(file, 'utf8')
  await writeFile(file, text + '{"seq":2,"stage":"api-returned"')
  const verdict = await inspectGroupDeliveries(home, 'r1')
  assert.equal(verdict.status, 'blocked')
  assert.match(verdict.reason, /interrupted JSONL/)
  const restarted = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await assert.rejects(restarted.markApiReturned(params()), /interrupted JSONL/)
  assert.equal(await readFile(file, 'utf8'), text + '{"seq":2,"stage":"api-returned"')
})

test('an unknown receipt event referencing missing group history blocks read-only recovery', async t => {
  const { home } = await fixture(t)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await writer.initialize('r1')
  await writer.begin(params())
  const groupFile = join(home, 'ledger', 'group-r1.jsonl')
  await writeFile(groupFile, '')
  const result = await inspectGroupDeliveries(home, 'r1')
  assert.equal(result.status, 'blocked')
  assert.match(result.reason, /missing group message/)
})

test('unsafe IDs and a missing writer assertion are rejected before any delivery', async t => {
  const { home } = await fixture(t)
  assert.throws(() => createGroupDeliveryJournal({ home }), /exclusive-writer check/)
  const writer = createGroupDeliveryJournal({ home, assertWriter: () => true })
  await assert.rejects(writer.begin(params('../escape')), /Invalid delivery id/)
  await assert.rejects(writer.begin({ ...params(), roomId: '../escape' }), /Invalid room id/)
  await assert.rejects(writer.begin(params('call-1', 0)), /positive group message sequence/)
  assert.equal((await inspectGroupDeliveries(home, 'r1')).status, 'not-initialized')
})
