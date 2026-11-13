import assert from 'node:assert/strict'
import fs from 'node:fs'
import { syncBuiltinESMExports } from 'node:module'
import { test } from 'node:test'
import { mkdtemp, readFile, rm, unlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { install } from '../src/host/store.js'
import { createDurableGroupLedger } from '../src/host/ledger-append.js'
import { publishInitialGroupBook } from '../src/host/ledger-import.js'
import { readLedger } from '../src/host/ledger-foundation.js'

async function freshHome(t) {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-ledger-lock-'))
  t.after(() => rm(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 25 }))
  return home
}

function setupStore(home) {
  const effects = []
  const rt = {
    home, statePath: join(home, 'state.json'),
    ctx: { effect(installEffect) {
      const cleanup = installEffect()
      if (typeof cleanup === 'function') effects.push(cleanup)
    } },
    autoRoomName: () => 'Team',
    retitleRoom: async () => {},
    warn: () => {},
  }
  install(rt)
  return {
    rt,
    dispose: async () => { await Promise.all(effects.splice(0).map(dispose => dispose())) },
  }
}

const row = (seq, text = 'message') => ({ seq, who: 'Writer', text })

test('only the first Host owns the strict Ledger writer lock; the reader can take over after release', async t => {
  const home = await freshHome(t)
  const first = setupStore(home)
  const second = setupStore(home)
  t.after(async () => { await second.dispose(); await first.dispose() })
  await first.rt.load()
  // Both mock Hosts run in this Node test process, while real Desktop/Web hosts
  // have different PIDs. Simulate that different PID in the lock record without
  // changing the owner's token, so ownership and takeover behave like two OS processes.
  const lockPath = join(home, 'state.lock')
  const owned = JSON.parse(await readFile(lockPath, 'utf8'))
  await writeFile(lockPath, JSON.stringify({ ...owned, pid: process.ppid }))
  await second.rt.load()
  assert.equal(await first.rt.assertLedgerWriter(), true)
  assert.equal(await second.rt.assertLedgerWriter(), false)
  await publishInitialGroupBook(home, 'group-r1', [])
  const readOnlyWriter = createDurableGroupLedger({ home, assertWriter: () => second.rt.assertLedgerWriter() })
  await assert.rejects(readOnlyWriter.append('group-r1', row(1)), /Exclusive writer lock/)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
  await first.dispose()
  await second.rt.refresh()
  assert.equal(await second.rt.assertLedgerWriter(), true)
  const writer = createDurableGroupLedger({ home, assertWriter: () => second.rt.assertLedgerWriter() })
  await writer.append('group-r1', row(1))
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [row(1)])
})

test('an unavailable state lock cannot grant Ledger write permission through the legacy fallback', async t => {
  const home = await freshHome(t)
  const instance = setupStore(home)
  t.after(() => instance.dispose())
  const original = fs.mkdirSync
  fs.mkdirSync = (path, ...args) => {
    if (path === home) throw Object.assign(new Error('simulated inaccessible home lock'), { code: 'EACCES' })
    return original(path, ...args)
  }
  syncBuiltinESMExports()
  try { await instance.rt.load() }
  finally {
    fs.mkdirSync = original
    syncBuiltinESMExports()
  }
  // Older state.json saves intentionally have a compatibility fallback; a
  // Ledger needs the stronger signal regardless of readOnly()'s presentation.
  assert.equal(instance.rt.readOnly(), undefined)
  assert.equal(await instance.rt.assertLedgerWriter(), false)
  await publishInitialGroupBook(home, 'group-r1', [])
  const writer = createDurableGroupLedger({ home, assertWriter: () => instance.rt.assertLedgerWriter() })
  await assert.rejects(writer.append('group-r1', row(1)), /Exclusive writer lock/)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
})

test('a Ledger book deleted during append cannot be silently recreated', async t => {
  const home = await freshHome(t)
  const path = join(home, 'ledger', 'group-r1.jsonl')
  await publishInitialGroupBook(home, 'group-r1', [])
  const writer = createDurableGroupLedger({
    home, assertWriter: () => true,
    beforeWrite: () => unlink(path),
  })
  await assert.rejects(writer.append('group-r1', row(1)), { code: 'ENOENT' })
  assert.equal(await readLedger(home, 'group-r1'), undefined)
  await assert.rejects(writer.append('group-r1', row(2)), { code: 'ENOENT' })
})

test('a Ledger book replaced between verification and append fails closed', async t => {
  const home = await freshHome(t)
  const path = join(home, 'ledger', 'group-r1.jsonl')
  await publishInitialGroupBook(home, 'group-r1', [])
  const external = JSON.stringify(row(1, 'external')) + '\n'
  const writer = createDurableGroupLedger({
    home, assertWriter: () => true,
    beforeWrite: () => writeFile(path, external),
  })
  await assert.rejects(writer.append('group-r1', row(1)), /changed between verification and append/)
  assert.equal(await readFile(path, 'utf8'), external)
  await assert.rejects(writer.flush(), /changed between verification and append/)
})

test('a Ledger writer that loses the lock between checks writes nothing', async t => {
  const home = await freshHome(t)
  await publishInitialGroupBook(home, 'group-r1', [])
  let checks = 0
  const writer = createDurableGroupLedger({
    home, assertWriter: () => ++checks === 1,
  })
  await assert.rejects(writer.append('group-r1', row(1)), /Exclusive writer lock lost/)
  assert.equal(checks, 2)
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [])
})

test('appending to an existing book preserves its previous records and UTF-8 byte lengths', async t => {
  const home = await freshHome(t)
  const original = row(1, '化工' + '测试'.repeat(120))
  await publishInitialGroupBook(home, 'group-r1', [original])
  const writer = createDurableGroupLedger({ home, assertWriter: () => true })
  await writer.append('group-r1', row(2, '中英文 UTF-8 abc'))
  assert.deepEqual((await readLedger(home, 'group-r1')).records, [original, row(2, '中英文 UTF-8 abc')])
})
