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

test('two concurrent deferred deliveries of one exchange send once and persist one queue note', async t => {
  let complete
  const pendingSend = new Promise(resolve => { complete = resolve })
  const sent = []
  const run = start(t, { turns: {}, queued: {} }, {
    deliver: async args => { sent.push(args); return pendingSend },
  })
  const args = { toId: 'b', sessionId: 's', exchangeId: 'same-exchange', role: 'request', deferred: true, text: 'reply once' }
  const first = run.rt.deliver(args)
  const duplicate = run.rt.deliver({ ...args })
  assert.equal(sent.length, 1, 'duplicate must join the in-flight send')
  await waitFor(() => run.notes().queued.s?.length === 1)
  assert.equal(run.notes().queued.s[0].args.exchangeId, 'same-exchange')
  complete('accepted')
  assert.deepEqual(await Promise.all([first, duplicate]), ['accepted', 'accepted'])
  assert.equal(sent.length, 1)
  assert.equal(run.rt.unreadOf('s').length, 1)
})

test('failed deferred delivery shares its failure, then a later retry can send again', async t => {
  let rejectFirst
  const blocked = new Promise((_, reject) => { rejectFirst = reject })
  let attempts = 0
  const run = start(t, { turns: {}, queued: {} }, {
    deliver: async () => { attempts += 1; if (attempts === 1) return blocked; return 'retried' },
  })
  const args = { toId: 'b', sessionId: 's', exchangeId: 'failed-once', role: 'request', deferred: true }
  const first = run.rt.deliver(args)
  const second = run.rt.deliver({ ...args })
  assert.equal(attempts, 1)
  rejectFirst(new Error('transient delivery error'))
  const settled = await Promise.allSettled([first, second])
  assert.deepEqual(settled.map(item => item.status), ['rejected', 'rejected'])
  assert.match(settled[0].reason.message, /transient delivery error/)
  assert.match(settled[1].reason.message, /transient delivery error/)
  await waitFor(() => run.notes().queued.s === undefined)
  assert.equal(await run.rt.deliver(args), 'retried')
  assert.equal(attempts, 2, 'a failed in-flight record must not block retries')
})

test('deferred deduplication is scoped to a Session and does not change ordinary deliveries', async t => {
  const calls = []
  let release
  const pendingSend = new Promise(resolve => { release = resolve })
  const run = start(t, { turns: {}, queued: {} }, {
    deliver: async args => { calls.push(args); return pendingSend },
  })
  const args = { toId: 'b', exchangeId: 'same-id', role: 'request', deferred: true }
  const a = run.rt.deliver({ ...args, sessionId: 's' })
  const b = run.rt.deliver({ ...args, sessionId: 'other-session' })
  assert.equal(calls.length, 2, 'different Sessions must not be coalesced')
  const normal = { ...args, deferred: false, sessionId: 's', exchangeId: 'normal' }
  const c = run.rt.deliver(normal)
  const d = run.rt.deliver({ ...normal })
  assert.equal(calls.length, 4, 'non-deferred deliveries are not coalesced')
  await waitFor(() => run.notes().queued.s?.length === 2)
  assert.deepEqual(run.notes().queued.s.map(item => item.args.exchangeId), ['same-id', 'normal'])
  release('done')
  assert.deepEqual(await Promise.all([a, b, c, d]), ['done', 'done', 'done', 'done'])
})
