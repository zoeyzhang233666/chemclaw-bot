import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { decodeLedger, ledgerFilename, previewLegacyRoom, readLedger, writeInitialLedger } from '../src/host/ledger-foundation.js'

async function temporary(t) {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-ledger-legacy-'))
  t.after(() => rm(home, { recursive: true, force: true }))
  return home
}

test('a dry-run preview preserves existing legacy state and long-line files', async t => {
  const home = await temporary(t)
  const state = { rooms: { r1: {
    id: 'r1', seq: 2, log: [
      { seq: 1, who: 'Chief', text: 'Hello' },
      { seq: 2, who: 'Writer', text: 'This is short', length: 40 },
    ],
  } } }
  const json = JSON.stringify(state)
  await writeFile(join(home, 'state.json'), json)
  await mkdir(join(home, 'group-lines', 'r1'), { recursive: true })
  await writeFile(join(home, 'group-lines', 'r1', '2.txt'), 'This is short and there is more')
  const result = await previewLegacyRoom({ home, room: state.rooms.r1 })
  assert.equal(result.book, 'group-r1')
  assert.equal(result.rows[0].text, 'Hello')
  assert.equal(result.rows[1].text, 'This is short and there is more')
  assert.equal(result.rows[1].legacyIncomplete, true)
  assert.ok(result.warnings.some(message => message.includes('incomplete')))
  assert.equal(await readFile(join(home, 'state.json'), 'utf8'), json)
  assert.equal(await readFile(join(home, 'group-lines', 'r1', '2.txt'), 'utf8'), 'This is short and there is more')
  assert.equal(await readLedger(home, 'group-r1'), undefined)
})

test('missing long text is reported instead of falsely claiming full recovery', async t => {
  const home = await temporary(t)
  const result = await previewLegacyRoom({
    home, room: { id: 'old', seq: 10, log: [{ seq: 9, text: 'start', length: 60 }] },
  })
  assert.equal(result.rows[0].legacyIncomplete, true)
  assert.equal(result.rows[0].text, 'start')
  assert.ok(result.warnings.some(w => w.includes('Missing legacy long-text')))
  assert.ok(result.warnings.some(w => w.includes('older/missing history')))
  assert.ok(result.warnings.some(w => w.includes('older history')))
})

test('explicit archived rows and latest state rows are ordered and deduplicated', async t => {
  const home = await temporary(t)
  const first = { seq: 1, who: 'User', text: 'first' }
  const second = { seq: 2, who: 'Chief', text: 'second' }
  const result = await previewLegacyRoom({
    home,
    room: { id: 'r1', seq: 3, log: [second, { seq: 3, who: 'Writer', text: 'third' }] },
    archivedRows: [first, second],
  })
  assert.deepEqual(result.rows.map(row => row.seq), [1, 2, 3])
  assert.deepEqual(result.rows.map(row => row.text), ['first', 'second', 'third'])
  assert.deepEqual(result.warnings, [])
})

test('conflicting sequence numbers are refused rather than silently dropping history', async t => {
  const home = await temporary(t)
  await assert.rejects(previewLegacyRoom({
    home, room: { id: 'r1', log: [{ seq: 2, text: 'one' }, { seq: 2, text: 'different' }] },
  }), /Conflicting legacy group sequence/)
})

test('legacy identifiers cannot escape the data directory', async t => {
  const home = await temporary(t)
  await assert.rejects(previewLegacyRoom({ home, room: { id: '../elsewhere', log: [] } }), /Invalid legacy group id/)
  assert.match(ledgerFilename('../outside'), /^[a-f0-9]{64}\.jsonl$/)
  assert.equal(ledgerFilename('group-r1'), 'group-r1.jsonl')
})

test('a book is initialized at most once and legacy source files remain untouched', async t => {
  const home = await temporary(t)
  const state = '{"rooms":{"r1":{"id":"r1"}}}'
  await writeFile(join(home, 'state.json'), state)
  const rows = [{ seq: 1, who: 'User', text: 'hello' }, { seq: 2, who: 'Chief', text: 'answer' }]
  await writeInitialLedger(home, 'group-r1', rows)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, rows)
  await assert.rejects(writeInitialLedger(home, 'group-r1', [{ seq: 999 }]), { code: 'EEXIST' })
  assert.deepEqual((await readLedger(home, 'group-r1')).records, rows)
  assert.equal(await readFile(join(home, 'state.json'), 'utf8'), state)
})

test('an interrupted unterminated row is never treated as committed', async t => {
  const home = await temporary(t)
  await mkdir(join(home, 'ledger'), { recursive: true })
  await writeFile(join(home, 'ledger', 'group-r1.jsonl'), '{"seq":1,"text":"saved"}\n{"seq":2,"text":"interrup')
  const result = await readLedger(home, 'group-r1')
  assert.deepEqual(result.records, [{ seq: 1, text: 'saved' }])
  assert.equal(result.incompleteTail, '{"seq":2,"text":"interrup')
})

test('corrupt completed rows fail visibly instead of silently skipping records', async () => {
  assert.throws(() => decodeLedger('{"seq":1}\nnot-json\n{"seq":3}\n'), /corrupt complete line at 2/)
  assert.throws(() => decodeLedger('42\n'), /non-object record at 1/)
  assert.deepEqual(decodeLedger(''), { records: [], incompleteTail: '' })
})

test('no write happens if a candidate record is malformed', async t => {
  const home = await temporary(t)
  await assert.rejects(writeInitialLedger(home, 'group-r1', [null]), /Ledger record must be an object/)
  assert.equal(await readLedger(home, 'group-r1'), undefined)
})

test('legacy logs without per-row sequence retain the offset stored by the room', async t => {
  const home = await temporary(t)
  const room = { id: 'r1', seq: 102, log: [{ text: 'one' }, { text: 'two' }] }
  const preview = await previewLegacyRoom({ home, room })
  assert.deepEqual(preview.rows.map(row => row.seq), [101, 102])
  assert.ok(preview.warnings.some(warning => warning.includes('older history')))
})
