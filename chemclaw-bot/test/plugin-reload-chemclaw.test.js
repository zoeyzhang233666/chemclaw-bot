// A plugin reload must re-adopt DSH's surviving Agents and re-apply ChemClaw's
// own restrictions. No turn or delegated tool is replayed by this repair.
import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { createRuntime } from './legacy-runtime.js'
import { fakeContext } from './fake-ctx.js'

const team = () => ({
  version: 1, mainBotIds: ['a'],
  bots: {
    a: { id: 'a', name: 'Chief', role: 'Boss', sessionId: 'a', createdAt: 1 },
    b: { id: 'b', name: 'Writer', role: 'Research', sessionId: 'b', createdAt: 2 },
  },
  rooms: {
    r1: { id: 'r1', name: 'Ops', mode: 'admin', admin: 'a', members: ['a', 'b'], named: true, sessions: { b: 'gb' }, log: [], seq: 0, seen: {} },
  },
  agents: { dsh1: { id: 'dsh1', name: 'DSH Agent', sessions: ['dsh'], createdAt: 1 } },
  exchanges: [], exchangeTurns: {}, questions: {}, prefs: {}, revision: 0,
})

function dshSide() {
  const all = new Map()
  const agent = (id, { status = 'idle', header = {} } = {}) => {
    if (all.has(id)) return all.get(id)
    const denied = []
    const cancelled = []
    const value = {
      id, status, denied, cancelled,
      session: { id, header, requestHeader: () => undefined, deriveMessages: () => [] },
      ctx: { tools: { restrict: ({ deny }) => { denied.push(deny); return () => {} } } },
      cancel: reason => { cancelled.push(reason) },
      followup() {}, steer() {}, inbox: { nextStep: [], nextTurn: [], remove: () => false },
    }
    all.set(id, value)
    return value
  }
  return { all, agent, services: { agents: { list: () => [...all.values()], get: id => all.get(id) } } }
}

async function run(t, dsh) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-plugin-reload-'))
  writeFileSync(join(home, 'state.json'), JSON.stringify(team()))
  const ctx = fakeContext({ services: dsh.services })
  const served = new Set(['message_bot', 'create_bot', 'read_group_chat', 'subagent', 'workflow'])
  ctx.tools.schemas = () => [...served].map(name => ({ name }))
  Object.assign(ctx, {
    llm: { listProviders: () => [], listModels: async () => [], resolveModelInfo: async () => ({}) },
    workspaceRegistry: {
      get: () => undefined, resolveByPath: async () => undefined,
      create: async path => ({ id: 'w1', path }), archiveSession: async () => {},
    },
    sessionController: {
      create: async () => ({ sessionId: 'new-session' }),
      resolveAgent: async id => ({ agent: dsh.all.get(id) ?? dsh.agent(id) }),
      selectModel: async () => {}, page: async () => ({ records: [], hasMore: false }),
      inspect: async () => ({ events: [] }),
    },
    sessionTitle: { rename: async () => {} },
    sessions: { flush: async () => {} },
  })
  const rt = createRuntime(ctx, { home })
  await rt.adoptLiveWork()
  t.after(async () => {
    await ctx.dispose()
    rmSync(home, { recursive: true, force: true, maxRetries: 5 })
  })
  return { ctx, rt, served }
}

function emit(ctx, id, type, data) {
  for (const listener of ctx.listeners.get('session/event') ?? []) {
    if (listener.length >= 2) listener({ id }, { type, data })
  }
}

test('reload adopts only running team turns, not idle sessions or unrelated agents', async t => {
  const dsh = dshSide()
  dsh.agent('gb', { status: 'running' })
  dsh.agent('b')
  dsh.agent('external', { status: 'running' })
  dsh.agent('child', { status: 'running', header: { origin: 'subagent', parentSession: 'gb' } })
  const { rt } = await run(t, dsh)
  assert.equal(rt.live.get('gb')?.turn, -1)
  assert.equal(rt.live.get('gb')?.opened, true)
  assert.equal(rt.live.get('b')?.turn, undefined)
  assert.equal(rt.live.get('external')?.turn, undefined)
  assert.equal(rt.live.get('child')?.turn, undefined)
  assert.equal(rt.roomWorkView().r1?.[0]?.botId, 'b')
  assert.equal(rt.activityView().b, 'thinking')
  await rt.adoptLiveWork()
  assert.equal(rt.live.get('gb')?.turn, -1, 'repeated adoption never starts a second turn')
})

test('Stop cancels an adopted running group member, then turn/end clears its activity', async t => {
  const dsh = dshSide()
  const member = dsh.agent('gb', { status: 'running' })
  const { ctx, rt } = await run(t, dsh)
  assert.equal(await rt.stopMemberWork('r1', 'b'), true)
  assert.deepEqual(member.cancelled, [{ kind: 'user' }])
  emit(ctx, 'gb', 'turn/end', { turn: 1, reason: { kind: 'aborted' } })
  assert.equal(rt.live.get('gb')?.turn, undefined)
  assert.equal((rt.roomWorkView().r1 ?? []).length, 0)
})

test('a recovered group relay can still be stopped when its round object is gone', async t => {
  const dsh = dshSide()
  const relay = dsh.agent('r1', { status: 'running' })
  const { rt } = await run(t, dsh)
  assert.equal(rt.live.get('r1')?.turn, -1)
  assert.equal(await rt.stopRoomWork('r1'), true)
  assert.deepEqual(relay.cancelled, [{ kind: 'user' }])
})

test('a new Bot request during a recovered turn is deferred, not answered by old work', async t => {
  const dsh = dshSide()
  dsh.agent('b', { status: 'running' })
  const { ctx, rt } = await run(t, dsh)
  const deliveries = []
  rt.deliver = async args => { deliveries.push(args) }
  const request = { kind: 'bot', form: 'relay', role: 'request', exchangeId: 'new-work', senderSessionId: 'a' }
  emit(ctx, 'b', 'user/message', { source: request, content: [{ type: 'text', text: 'A new task' }] })
  emit(ctx, 'b', 'assistant/message', { message: { content: [{ type: 'text', text: 'Result of the old task' }] } })
  emit(ctx, 'b', 'turn/end', { turn: 1, reason: { kind: 'completed' } })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(deliveries.some(item => item.replyTo === 'new-work'), false)
  assert.equal(deliveries.some(item => item.deferred === true && item.exchangeId === 'new-work'), true)
})

test('reloading reapplies Bot and DSH Agent permission restrictions; later team tools are denied too', async t => {
  const dsh = dshSide()
  const group = dsh.agent('gb', { status: 'running' })
  const normal = dsh.agent('b')
  const dshAgent = dsh.agent('dsh')
  const { rt, served } = await run(t, dsh)
  const flattened = agent => agent.denied.flat()
  assert.equal(flattened(group).includes('create_bot'), true, 'group member cannot administer team')
  assert.equal(flattened(group).includes('message_bot'), false, 'group member can delegate work to another Bot')
  assert.equal(flattened(normal).includes('create_bot'), true, 'ordinary Bot does not get admin tools')
  assert.equal(flattened(dshAgent).includes('message_bot'), true, 'DSH Agent must not receive team tools')
  const first = dshAgent.denied.length
  served.add('post_to_group')
  await rt.restrictDshAgentTools(dshAgent)
  assert.equal(dshAgent.denied.length, first + 1)
  assert.equal(dshAgent.denied.at(-1).includes('post_to_group'), true)
  assert.equal(dshAgent.denied.at(-1).includes('message_bot'), false, 'already denied tools stay denied')
})
