import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { setTimeout as delay } from 'node:timers/promises'
import { test } from 'node:test'
import { install } from '../src/host/resume.js'

const pending = { turns: { s: { botId: 'b', since: 1 } }, queued: {} }
const waitFor = async check => {
  const until = Date.now() + 3000
  while (!check() && Date.now() < until) await delay(10)
  assert.ok(check(), 'recovery did not settle')
}

function start(t, saved = pending, options = {}) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-resume-failure-'))
  const file = join(home, 'inflight.json')
  writeFileSync(file, typeof saved === 'string' ? saved : JSON.stringify(saved))
  const disposers = []
  const warnings = []
  const delivered = []
  const listeners = new Map()
  const rt = {
    home, ctx: { on(name, fn) { listeners.set(name, fn) }, effect(fn) { disposers.push(fn()) } },
    async load() {}, readOnly() {}, warn: (...args) => warnings.push(args),
    botOf: () => ({ id: 'b' }), chatOf: () => 's',
    resolveAgent: async () => ({ status: 'idle' }),
    deliver: async args => { delivered.push(args) },
    ...options,
  }
  install(rt)
  t.after(async () => { for (const dispose of disposers) await dispose(); rmSync(home, { recursive: true, force: true, maxRetries: 5 }) })
  return { rt, file, notes: () => JSON.parse(readFileSync(file, 'utf8')), warnings, delivered, listeners }
}

test('transient session read failure preserves pending work without delivering it', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const run = start(t, pending, { resolveAgent: async () => { throw new Error('mock read failure') } })
  t.mock.timers.tick(3000)
  await waitFor(() => run.warnings.length > 0)
  assert.deepEqual(run.notes().turns, pending.turns)
  assert.equal(run.delivered.length, 0)
})

test('failed recovery retains its original record as uncertain and does not retry it', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let attempts = 0
  const run = start(t, pending, { deliver: async () => { attempts += 1; throw new Error('mock send failed') } })
  t.mock.timers.tick(3000)
  await waitFor(() => run.warnings.length > 0)
  assert.equal(attempts, 1)
  assert.deepEqual(run.notes().recovery['turns:s'].record, pending.turns.s)
  assert.deepEqual(run.notes().turns, {})
  const next = start(t, run.notes(), { deliver: async () => { attempts += 1 } })
  t.mock.timers.tick(3000)
  await waitFor(() => next.warnings.length > 0)
  assert.equal(attempts, 1)
  assert.equal(next.notes().recovery['turns:s'].status, 'uncertain')
})

test('uncertainty is durable before any recovery delivery is attempted', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let checked = false
  const run = start(t, pending, { deliver: async () => {
    assert.equal(run.notes().recovery['turns:s'].status, 'uncertain')
    assert.deepEqual(run.notes().turns, {})
    checked = true
  } })
  t.mock.timers.tick(3000)
  await waitFor(() => checked && Object.keys(run.notes().recovery).length === 0)
})

test('corrupt recovery bytes survive new deliveries and recovery attempts', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const run = start(t, '{broken')
  await run.rt.deliver({ toId: 'b', text: 'mock new message' })
  t.mock.timers.tick(3000)
  await waitFor(() => run.warnings.length > 0)
  assert.equal(readFileSync(run.file, 'utf8'), '{broken')
})

test('new work before the recovery delay does not erase interrupted work', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const run = start(t)
  await run.rt.deliver({ toId: 'b', text: 'mock new message' })
  await waitFor(() => run.notes().queued.s?.length === 1)
  assert.deepEqual(run.notes().turns, pending.turns)
})

test('messages withdrawn before recovery are removed from the persisted interrupted queue', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const run = start(t, { turns: {}, queued: { s: [{ at: Date.now(), args: { toId: 'b', exchangeId: 'withdrawn' } }] } })
  run.listeners.get('agent/inbox/discarded')({ message: { source: { kind: 'bot', exchangeId: 'withdrawn' } } })
  await run.rt.deliver({ toId: 'b', exchangeId: 'new-message' })
  await waitFor(() => run.notes().queued.s?.length === 1 && run.notes().queued.s[0].args.exchangeId === 'new-message')
})

test('invalid recovery record shapes are preserved instead of crashing later deliveries', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  for (const saved of [{ turns: { s: null }, queued: {} }, { turns: {}, queued: { s: [null] } }]) {
    const raw = JSON.stringify(saved)
    const run = start(t, raw)
    await run.rt.deliver({ toId: 'b', text: 'mock delivery' })
    assert.equal(readFileSync(run.file, 'utf8'), raw)
  }
})

test('context-blocked work survives restart without resolving or replaying its turn and queue', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let resolved = 0
  const saved = { turns: { s: { botId: 'b', since: 1 } }, queued: { s: [{ at: Date.now(), args: { toId: 'b', exchangeId: 'kept' } }] } }
  const run = start(t, saved, {
    contextRecovery: { async settled() {}, blocked: () => true, notice() {} },
    resolveAgent: async () => { resolved += 1; return { status: 'idle' } },
  })
  t.mock.timers.tick(3000)
  await delay(30)
  assert.equal(resolved, 0)
  assert.equal(run.delivered.length, 0)
  assert.deepEqual(run.notes(), saved)
})
