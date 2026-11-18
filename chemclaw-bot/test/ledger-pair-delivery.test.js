import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { ledgerFilename, readLedger } from '../src/host/ledger-foundation.js'
import { createPairDeliveryJournal, pairBook } from '../src/host/ledger-pair-delivery.js'

const setup = t => {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-pair-ledger-'))
  t.after(() => rmSync(home, { recursive: true, force: true }))
  return home
}
const message = (id = 'x-1') => ({
  a: 'a', b: 'b', id, from: 'a', to: 'b', role: 'request', text: 'Check supplier records',
})

test('pair #1358 imports legacy messages once and keeps them after a restart', async t => {
  const home = setup(t)
  const writer = createPairDeliveryJournal({ home, assertWriter: async () => true })
  const prior = { id: 'old-1', from: 'a', to: 'b', role: 'request', text: 'Earlier supplier reply', time: 1 }
  assert.deepEqual((await writer.seed('b', 'a', [prior])).imported, 1)
  const snapshot = readFileSync(join(home, 'ledger', ledgerFilename(pairBook('a', 'b'))), 'utf8')
  const restarted = createPairDeliveryJournal({ home, assertWriter: async () => true })
  assert.deepEqual(await restarted.seed('a', 'b', [prior]), { reused: true, imported: 1 })
  const view = await restarted.inspect('a', 'b')
  assert.deepEqual(view.delivered.map(row => row.id), ['old-1'])
  assert.equal(view.uncertain.length, 0)
  assert.equal(readFileSync(join(home, 'ledger', ledgerFilename('pair-a-b')), 'utf8'), snapshot)
})

test('pair #1358 writes a full attempt before a delivery can be confirmed', async t => {
  const home = setup(t)
  const writer = createPairDeliveryJournal({ home, assertWriter: async () => true })
  await writer.seed('a', 'b')
  const attempt = await writer.begin(message())
  assert.equal(attempt.seq, 1)
  const unknown = await writer.inspect('a', 'b')
  assert.equal(unknown.delivered.length, 0, 'an attempted send is not yet a confirmed delivery')
  assert.deepEqual(unknown.uncertain.map(row => row.id), ['x-1'])
  assert.deepEqual(await writer.delivered({ a: 'b', b: 'a', id: 'x-1', sessionId: 'b-chat' }), { reused: false })
  const confirmed = await readLedger(home, 'pair-a-b')
  assert.deepEqual(confirmed.records.map(row => [row.seq, row.event]), [[1, undefined], [2, 'delivered']])
  assert.deepEqual((await writer.inspect('a', 'b')).delivered.map(row => row.text), ['Check supplier records'])
  assert.deepEqual(await writer.delivered({ a: 'a', b: 'b', id: 'x-1', sessionId: 'b-chat' }), { reused: true })
})

test('pair #1358 never resends an attempt whose DSH outcome is uncertain', async t => {
  const home = setup(t)
  const initial = createPairDeliveryJournal({ home, assertWriter: async () => true })
  await initial.seed('a', 'b')
  await initial.begin(message())
  const restarted = createPairDeliveryJournal({ home, assertWriter: async () => true })
  await assert.rejects(restarted.begin(message()), /cannot replay/)
  assert.equal((await restarted.inspect('a', 'b')).uncertain.length, 1)
  assert.equal((await restarted.inspect('a', 'b')).delivered.length, 0)
})

test('pair #1358 refuses append without exclusive lock, without displaying a ghost message', async t => {
  const home = setup(t)
  let lock = true
  const writer = createPairDeliveryJournal({ home, assertWriter: async () => lock })
  await writer.seed('a', 'b')
  lock = false
  await assert.rejects(writer.begin(message()), /Exclusive writer lock/)
  assert.deepEqual((await writer.inspect('a', 'b')).rows, [])
  const restarted = createPairDeliveryJournal({ home, assertWriter: async () => true })
  await assert.rejects(restarted.delivered({ a: 'a', b: 'b', id: 'x-1', sessionId: 'b' }), /No recorded/)
})

test('pair #1358 rejects missing books, truncated tails, and cross-pair spoofing', async t => {
  const home = setup(t)
  const writer = createPairDeliveryJournal({ home, assertWriter: async () => true })
  await assert.rejects(writer.begin(message()), /Pair Ledger missing/)
  await writer.seed('a', 'b')
  await assert.rejects(writer.begin({ ...message(), from: 'c' }), /wrong sender/)
  await assert.rejects(writer.begin({ ...message(), id: '../escape' }), /Invalid pair Ledger/)
  await assert.rejects(writer.begin({ ...message(), text: null }), /Invalid pair Ledger/)
  assert.equal((await writer.inspect('a', 'b')).delivered.length, 0)
})
