// Regression coverage for upstream DS-Bot #1317's old-group -> Ledger boundary.
// ChemClaw must preserve every historical source and leave private delegation alone.
// This suite DOES NOT enable the live groups.js Ledger cutover.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { planLegacyGroupImport, seedLegacyGroupLedger } from '../src/host/ledger-import.js'
import { readLedger } from '../src/host/ledger-foundation.js'

async function fixture(t) {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-upstream-ledger-upgrade-'))
  t.after(() => rm(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 30 }))
  return home
}

const line = (seq, text = '原始消息 #' + seq) => ({
  seq, who: seq % 2 ? 'User' : 'ChemClaw', text,
})

async function preserveOldState(home, room, otherRoom) {
  const state = {
    version: 1, mainBotIds: ['chief'],
    bots: { chief: { id: 'chief', name: 'ChemClaw', sessionId: 'chief-session' } },
    rooms: { [room.id]: room, [otherRoom.id]: otherRoom },
    works: { 'private-task': { from: 'chief', to: 'analyst', status: 'working' } },
    exchanges: [{ from: 'chief', to: 'analyst', text: '已有私聊任务' }],
    questions: { 'chief-session': { waiting: true } },
  }
  const bytes = JSON.stringify(state)
  await writeFile(join(home, 'state.json'), bytes)
  return bytes
}

test('upstream #1317 boundary: import 95 old group lines, overlap, two long-text sources without touching saved sessions or other rooms', async t => {
  const home = await fixture(t)
  const old = Array.from({ length: 95 }, (_, index) => line(index + 1))
  const archivedLong = '聚氨酯行业历史全文：' + '聚醚多元醇'.repeat(6200)
  const sidecarLong = '钛白粉现货市场长报告：' + '采购风险预警'.repeat(9800)
  old[29] = line(30, archivedLong)  // Old group-logs retains this entire line.
  old[84] = line(85, sidecarLong)   // Newer long text has only a sidecar.
  const room = {
    id: 'r1', name: '化工专家团', seq: 95, members: ['chief', 'analyst'],
    sessions: { chief: 'group-chief-session', analyst: 'group-analyst-session' },
    seen: { chief: 80 },
    log: old.slice(-60).map(record => record.seq === 85
      ? { ...record, text: record.text.slice(0, 2000), length: record.text.length }
      : { ...record }),
  }
  const otherRoom = { id: 'r2', name: '未迁移群', seq: 1, log: [line(1, '独立群聊')] }
  const originalState = await preserveOldState(home, room, otherRoom)
  const originalArchive = old.slice(0, 70).map(record => JSON.stringify(record) + '\n').join('')
  await mkdir(join(home, 'group-logs'), { recursive: true })
  await writeFile(join(home, 'group-logs', 'r1.jsonl'), originalArchive)
  await mkdir(join(home, 'group-lines', 'r1'), { recursive: true })
  await writeFile(join(home, 'group-lines', 'r1', '85.txt'), sidecarLong)
  const originalSession = '{"session":"group-chief-session","keep":"old user work"}\n'
  await writeFile(join(home, 'existing-session-fixture.jsonl'), originalSession)

  const inspected = await planLegacyGroupImport({ home, room })
  assert.equal(inspected.ready, true, inspected.warnings.join('; '))
  assert.deepEqual(inspected.rows.map(record => record.seq), Array.from({ length: 95 }, (_, index) => index + 1))
  assert.equal(inspected.rows[29].text, archivedLong)
  assert.equal(inspected.rows[84].text, sidecarLong)
  assert.equal(await readLedger(home, 'group-r1'), undefined, 'preflight must be read-only')

  const published = await seedLegacyGroupLedger({ home, room })
  assert.equal(published.rows, 95)
  assert.equal(published.reused, false)
  const book = await readLedger(home, 'group-r1')
  assert.equal(book.records.length, 95)
  assert.equal(book.records[29].text, archivedLong)
  assert.equal(book.records[84].text, sidecarLong)
  assert.equal(await readLedger(home, 'group-r2'), undefined, 'an unrelated room must remain unmigrated')
  assert.equal((await seedLegacyGroupLedger({ home, room })).reused, true, 'repeated import must not rewrite the book')
  assert.equal(await readFile(join(home, 'state.json'), 'utf8'), originalState)
  assert.equal(await readFile(join(home, 'group-logs', 'r1.jsonl'), 'utf8'), originalArchive)
  assert.equal(await readFile(join(home, 'group-lines', 'r1', '85.txt'), 'utf8'), sidecarLong)
  assert.equal(await readFile(join(home, 'existing-session-fixture.jsonl'), 'utf8'), originalSession)
})

test('upstream #1317 boundary: historical gap, torn archive tail and missing long text block migration without changing original bytes', async t => {
  const home = await fixture(t)
  const older = [
    ...Array.from({ length: 49 }, (_, index) => line(index + 1)),
    ...Array.from({ length: 16 }, (_, index) => line(index + 51)),
  ]
  const room = {
    id: 'r1', name: '不能盲目补齐的旧群', seq: 70,
    log: [...Array.from({ length: 9 }, (_, index) => line(index + 61)),
      { ...line(70, '只有开头'), length: 9000 }],
  }
  const originalState = await preserveOldState(home, room, { id: 'r2', seq: 0, log: [] })
  await mkdir(join(home, 'group-logs'), { recursive: true })
  const originalArchive = older.map(record => JSON.stringify(record) + '\n').join('') + '{"seq":71'
  await writeFile(join(home, 'group-logs', 'r1.jsonl'), originalArchive)

  const inspected = await planLegacyGroupImport({ home, room })
  assert.equal(inspected.ready, false)
  const warnings = inspected.warnings.join('; ')
  assert.match(warnings, /missing messages between sequences 49 and 51/)
  assert.match(warnings, /interrupted JSONL/)
  assert.match(warnings, /incomplete/)
  await assert.rejects(seedLegacyGroupLedger({ home, room }), /import is incomplete/)
  assert.equal(await readLedger(home, 'group-r1'), undefined)
  assert.equal(await readFile(join(home, 'state.json'), 'utf8'), originalState)
  assert.equal(await readFile(join(home, 'group-logs', 'r1.jsonl'), 'utf8'), originalArchive)
})
