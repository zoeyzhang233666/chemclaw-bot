import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, readFile, rm, unlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createDurableGroupLedger } from '../src/host/ledger-append.js'
import { publishInitialGroupBook } from '../src/host/ledger-import.js'
import { readLedger } from '../src/host/ledger-foundation.js'

async function fixture(t, records = []) {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-ledger-fast-'))
  t.after(() => rm(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 20 }))
  await publishInitialGroupBook(home, 'group-r1', records)
  return home
}
const row = (seq, text = 'msg ' + seq) => ({ seq, who: 'ChemClaw', text })

test('a long series of normal appends scans the entire book just once per writer', async t => {
  const home = await fixture(t)
  let fullReads = 0
  const writer = createDurableGroupLedger({
    home, assertWriter: () => true,
    loadBook: async (location, book) => { fullReads++; return readLedger(location, book) },
  })
  for (let seq = 1; seq <= 35; seq++) {
    assert.deepEqual(await writer.append('group-r1', row(seq)), { seq, reused: false })
  }
  await writer.flush('group-r1')
  assert.equal(fullReads, 1, 'normal append must not repeatedly parse the full JSONL book')
  assert.deepEqual((await readLedger(home, 'group-r1')).records.map(v => v.seq),
    Array.from({ length: 35 }, (_, i) => i + 1))
})

test('an imported long history is validated once, then only its tail is checked', async t => {
  const old = Array.from({ length: 500 }, (_, i) => row(i + 1, '历史消息 ' + i))
  const home = await fixture(t, old)
  let fullReads = 0
  const writer = createDurableGroupLedger({
    home, assertWriter: () => true,
    loadBook: async (location, book) => { fullReads++; return readLedger(location, book) },
  })
  await writer.append('group-r1', row(501, '新增 501'))
  await writer.append('group-r1', row(502, '新增 502'))
  await writer.append('group-r1', row(503, '新增 503'))
  assert.equal(fullReads, 1)
  const records = (await readLedger(home, 'group-r1')).records
  assert.equal(records.length, 503)
  assert.equal(records.at(-1).text, '新增 503')
  assert.deepEqual(records.slice(0, 500), old)
})

test('a same-size external rewrite after a successful append poisons the cached book', async t => {
  const home = await fixture(t)
  const writer = createDurableGroupLedger({ home, assertWriter: () => true })
  await writer.append('group-r1', row(1, 'AAAA'))
  const path = join(home, 'ledger', 'group-r1.jsonl')
  const replacement = JSON.stringify(row(1, 'BBBB')) + '\n'
  const old = await readFile(path, 'utf8')
  assert.equal(Buffer.byteLength(old), Buffer.byteLength(replacement))
  await writeFile(path, replacement)
  await assert.rejects(writer.append('group-r1', row(2)), /changed between verification|last record changed/)
  await assert.rejects(writer.flush(), /changed between verification|last record changed/)
  assert.equal(await readFile(path, 'utf8'), replacement)
})

test('an external append and deleted canonical book are never accepted from the cache', async t => {
  const home = await fixture(t)
  const path = join(home, 'ledger', 'group-r1.jsonl')
  const writer = createDurableGroupLedger({ home, assertWriter: () => true })
  await writer.append('group-r1', row(1))
  await writeFile(path, JSON.stringify(row(1)) + '\n' + JSON.stringify(row(2, 'outsider')) + '\n')
  await assert.rejects(writer.append('group-r1', row(2)), /changed between verification/)
  assert.deepEqual((await readLedger(home, 'group-r1')).records.map(v => v.text), ['msg 1', 'outsider'])
  const recovered = createDurableGroupLedger({ home, assertWriter: () => true })
  await recovered.append('group-r1', row(3))
  await unlink(path)
  await assert.rejects(recovered.append('group-r1', row(4)), { code: 'ENOENT' })
  assert.equal(await readLedger(home, 'group-r1'), undefined)
})

test('cached UTF-8 byte offsets remain exact across many Chinese and emoji messages', async t => {
  const home = await fixture(t, [row(1, '初始化工新闻')])
  const writer = createDurableGroupLedger({ home, assertWriter: () => true })
  for (let seq = 2; seq <= 14; seq++) {
    await writer.append('group-r1', row(seq, '中化📈能源报价—' + seq))
  }
  const contents = await readFile(join(home, 'ledger', 'group-r1.jsonl'), 'utf8')
  assert.equal(contents.endsWith('\n'), true)
  assert.deepEqual((await readLedger(home, 'group-r1')).records.map(v => v.seq),
    Array.from({ length: 14 }, (_, i) => i + 1))
})

test('idempotent replay may do a full read, but normal appends resume bounded validation', async t => {
  const home = await fixture(t)
  let fullReads = 0
  const writer = createDurableGroupLedger({
    home, assertWriter: () => true,
    loadBook: async (location, book) => { fullReads++; return readLedger(location, book) },
  })
  await writer.append('group-r1', row(1))
  await writer.append('group-r1', row(2))
  assert.deepEqual(await writer.append('group-r1', row(1)), { seq: 1, reused: true })
  await writer.append('group-r1', row(3))
  assert.equal(fullReads, 2, 'one initial scan and one explicit replay verification')
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [row(1), row(2), row(3)])
})

test('queued message bytes are captured before the caller changes the object', async t => {
  const home = await fixture(t)
  let release
  const gate = new Promise(resolve => { release = resolve })
  const writer = createDurableGroupLedger({
    home, assertWriter: () => true,
    beforeWrite: async (_book, record) => {
      if (record.seq === 1) await gate
      if (record.seq === 2) record.text = 'mutation inside beforeWrite'
    },
  })
  const first = writer.append('group-r1', row(1))
  const secondInput = row(2, 'original queued text')
  const second = writer.append('group-r1', secondInput)
  secondInput.seq = 999
  secondInput.text = 'modified by caller after append()'
  release()
  await Promise.all([first, second])
  const records = (await readLedger(home, 'group-r1')).records
  assert.deepEqual(records, [row(1), row(2, 'original queued text')])
})

test('invalid queued records poison the book instead of being ignored by the fast path', async t => {
  const home = await fixture(t)
  const writer = createDurableGroupLedger({ home, assertWriter: () => true })
  await assert.rejects(writer.append('group-r1', { text: 'no sequence' }), /positive integer seq/)
  await assert.rejects(writer.append('group-r1', row(1)), /positive integer seq/)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
})
