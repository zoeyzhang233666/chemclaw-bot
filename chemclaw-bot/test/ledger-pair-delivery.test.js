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

test('pair #1358 merged replacement preserves old confirmed text until its own DSH receipt', async t => {
  const home = setup(t)
  const writer = createPairDeliveryJournal({ home, assertWriter: async () => true })
  await writer.seed('a', 'b')
  await writer.begin(message('merged-1'))
  await writer.delivered({ a: 'a', b: 'b', id: 'merged-1', sessionId: 'b-chat' })
  const changed = { ...message('merged-1'), text: 'Supplier check with revised date', merged: true }
  assert.equal((await writer.begin(changed)).seq, 3)
  const pending = await writer.inspect('a', 'b')
  assert.deepEqual(pending.delivered.map(row => row.text), ['Check supplier records'],
    'the earlier delivered version remains visible until the replacement is confirmed')
  assert.deepEqual(pending.uncertain.map(row => row.text), [changed.text])
  const resumed = createPairDeliveryJournal({ home, assertWriter: async () => true })
  await assert.rejects(resumed.begin(changed), /cannot merge an unknown or uncertain/)
  await resumed.delivered({ a: 'b', b: 'a', id: 'merged-1', sessionId: 'b-chat' })
  const confirmed = await resumed.inspect('a', 'b')
  assert.deepEqual(confirmed.delivered.map(row => row.text), [changed.text])
  assert.deepEqual(confirmed.uncertain, [])
  assert.deepEqual((await readLedger(home, 'pair-a-b')).records.map(row => [row.seq, row.event ?? 'message']),
    [[1, 'message'], [2, 'delivered'], [3, 'message'], [4, 'delivered']])
})

test('pair #1358 refuses merge spoofing and keeps an uncertain prior attempt untouched', async t => {
  const home = setup(t)
  const writer = createPairDeliveryJournal({ home, assertWriter: async () => true })
  await writer.seed('a', 'b')
  await writer.begin(message('same-1'))
  await assert.rejects(writer.begin({ ...message('same-1'), text: 'new text', merged: true }), /cannot merge/)
  await writer.delivered({ a: 'a', b: 'b', id: 'same-1', sessionId: 'b' })
  await assert.rejects(writer.begin({ ...message('same-1'), from: 'b', to: 'a', text: 'spoof', merged: true }), /cannot merge/)
  await assert.rejects(writer.begin({ ...message('same-1'), text: 'Check supplier records', merged: true }), /no changed/)
  assert.deepEqual((await writer.inspect('a', 'b')).delivered.map(row => row.text), ['Check supplier records'])
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

test('pair #1358 rejects ambiguous hyphenated pair identities instead of leaking another exchange', async t => {
  const home = setup(t)
  const writer = createPairDeliveryJournal({ home, assertWriter: async () => true })
  assert.equal(pairBook('a-b', 'c'), pairBook('a', 'b-c'), 'older DS-Bot-compatible pair names may collide')
  await writer.seed('a-b', 'c')
  await writer.begin({ a: 'a-b', b: 'c', id: 'unique-1', from: 'a-b', to: 'c', role: 'request', text: 'Private supplier report' })
  await writer.delivered({ a: 'a-b', b: 'c', id: 'unique-1', sessionId: 'c' })
  await assert.rejects(writer.inspect('a', 'b-c'), /different pair/)
  await assert.rejects(writer.seed('a', 'b-c'), /different pair/)
  assert.deepEqual((await writer.inspect('a-b', 'c')).delivered.map(row => row.text), ['Private supplier report'])
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
