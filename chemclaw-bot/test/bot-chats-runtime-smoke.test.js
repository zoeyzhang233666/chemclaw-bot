import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { createRuntime } from './legacy-runtime.js'
import { fakeContext } from './fake-ctx.js'

// Runtime acceptance smoke for Batch 2 multi-chat (host + API, mock Sessions).
// Complements unit safety tests when a full DSH bench checkout is unavailable.

function open(saved) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-multichat-smoke-'))
  if (saved !== undefined) writeFileSync(join(home, 'state.json'), JSON.stringify(saved))
  const ctx = fakeContext()
  const workspaces = new Map()
  let sessions = 0
  const live = new Map()
  Object.assign(ctx, {
    llm: {
      listProviders: () => [{ id: 'deepseek', name: 'DeepSeek' }],
      listModels: async () => [{ id: 'deepseek-v4-flash' }],
      resolveModelInfo: async () => ({}),
    },
    workspaceRegistry: {
      get: id => workspaces.get(id),
      resolveByPath: async path => [...workspaces.values()].find(workspace => workspace.path === path),
      create: async (path) => {
        const workspace = { id: `w${workspaces.size + 1}`, path }
        workspaces.set(workspace.id, workspace)
        return workspace
      },
      archiveSession: async () => {},
    },
    sessionController: {
      create: async () => ({ sessionId: `s${++sessions}` }),
      resolveAgent: async sessionId => ({ agent: { session: { id: sessionId }, followup: () => {}, inbox: { nextStep: [], nextTurn: [] } } }),
      selectModel: async () => {},
    },
    sessionTitle: { rename: async () => {} },
    sessions: { flush: async () => {} },
  })
  let route
  const register = ctx.connection.fetch.register
  ctx.connection.fetch.register = (options) => {
    route = options
    return register(options)
  }
  const rt = createRuntime(ctx, { home, updateCheck: false })
  rt.live = live
  const call = async (endpoint, payload = {}) => {
    const response = await route.fetch(new Request('http://localhost/api/bot', {
      method: 'POST', body: JSON.stringify({ endpoint, payload }),
    }))
    return response.json()
  }
  const stop = async () => {
    await ctx.dispose()
    rmSync(home, { recursive: true, force: true, maxRetries: 5 })
  }
  const disk = () => JSON.parse(readFileSync(join(home, 'state.json'), 'utf8'))
  return { call, stop, home, disk, rt, live }
}

const legacy = () => ({
  version: 1,
  mainBotIds: ['chief'],
  bots: {
    chief: { id: 'chief', sessionId: 'tip-c', name: 'Chief', role: 'Chief', instructions: '', createdAt: 1, capabilities: [], model: 'deepseek/v4' },
    writer: {
      id: 'writer', sessionId: 'tip-w', name: 'Writer', role: 'Writer', instructions: '', createdAt: 2, capabilities: [], model: 'deepseek/v4',
      segments: [{ sessionId: 'old-w', endedAt: 5 }],
    },
  },
  rooms: {
    ops: {
      id: 'ops', name: 'Ops', named: true, members: ['chief', 'writer'], admin: 'chief', mode: 'everyone',
      notice: 'keep shipping', createdAt: 3,
      sessions: { chief: 'room-chief', writer: 'room-writer' },
      segments: { writer: [{ sessionId: 'room-old-w', endedAt: 9 }] },
      log: [{ seq: 1, who: 'User', text: 'hi', at: 1 }],
    },
  },
  agents: {},
  capabilities: { items: {} },
  exchanges: [],
  exchangeTurns: {},
  questions: {},
  revision: 1,
})

test('smoke: A running → create/switch B → A result stays on A; B clean; reopen A', async (t) => {
  const { call, stop, disk, rt, live } = open(legacy())
  t.after(stop)
  await call('state', {})
  assert.ok(readdirSync(rt.home).some(name => name.startsWith('state.json.pre-multichat-')))

  const tipA = 'tip-w'
  live.set(tipA, { turn: { since: Date.now() } })
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  const tipB = created.chat.sessionId
  assert.notEqual(tipB, tipA)
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  assert.equal(rt.chatOf('writer'), tipB)
  assert.equal(rt.ownerOf(tipA)?.chatId, 'writer')
  assert.equal(rt.ownerOf(tipB)?.chatId, created.chat.id)

  // Simulate A completing while B is focused: rotate A's tip only.
  const bot = rt.botOf('writer')
  const chatA = rt.chatById(bot, 'writer')
  chatA.segments = [...(chatA.segments ?? []), { sessionId: tipA, endedAt: Date.now() }]
  chatA.sessionId = 'tip-w-done'
  rt.syncMirror?.(bot)
  rt.indexSessions()
  await rt.save()
  live.delete(tipA)

  const after = disk()
  const diskA = after.bots.writer.chats.find(chat => chat.id === 'writer')
  const diskB = after.bots.writer.chats.find(chat => chat.id === created.chat.id)
  assert.equal(diskA.sessionId, 'tip-w-done')
  assert.ok(diskA.segments.some(segment => segment.sessionId === tipA))
  assert.equal(diskB.sessionId, tipB)
  assert.deepEqual(diskB.segments ?? [], [])
  assert.equal(after.rooms.ops.sessions.writer, 'room-writer')

  await call('bot-chat-open', { botId: 'writer', chatId: 'writer' })
  assert.equal(rt.chatOf('writer'), 'tip-w-done')
  const partsA = rt.partsOf('writer', undefined, 'tip-w-done')
  assert.ok(partsA.some(part => part.sessionId === 'old-w'))
  assert.ok(partsA.some(part => part.sessionId === tipA))
  assert.equal(partsA.at(-1)?.sessionId, 'tip-w-done')
  assert.deepEqual(rt.partsOf('writer', undefined, tipB).map(part => part.sessionId), [tipB])
})

test('smoke: group running + private switch; room ownership and @ target stay on room tip', async (t) => {
  const { call, stop, rt, live } = open(legacy())
  t.after(stop)
  await call('state', {})
  live.set('room-writer', { turn: { since: Date.now() } })
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  assert.equal(rt.ownerOf('room-writer')?.kind, 'room')
  assert.equal(rt.ownerOf('room-writer')?.roomId, 'ops')
  assert.equal(rt.ownChatAnchor('writer', 'room-writer'), 'tip-w')
  assert.equal(rt.chatOf('writer'), created.chat.sessionId)
  // message_bot without room uses active tip (documented); with room uses room path.
  assert.equal(rt.roomOf('ops').sessions.writer, 'room-writer')
  assert.notEqual(rt.chatOf('writer'), 'room-writer')
})

test('smoke: restart restores index; multi-window second host sees same ownership', async (t) => {
  const { call, stop, disk } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  const snapshot = disk()
  const second = open(snapshot)
  t.after(second.stop)
  await second.call('state', {})
  assert.equal(second.rt.ownerOf('tip-w')?.chatId, 'writer')
  assert.equal(second.rt.ownerOf(created.chat.sessionId)?.chatId, created.chat.id)
  assert.equal(second.rt.ownerOf('room-writer')?.kind, 'room')
  assert.deepEqual(second.disk().rooms.ops.log, [{ seq: 1, who: 'User', text: 'hi', at: 1 }])
})

test('smoke: archive refused while A running; allowed after idle', async (t) => {
  const { call, stop, live } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  live.set(created.chat.sessionId, { turn: {} })
  const blocked = await call('bot-chat-archive', { botId: 'writer', chatId: created.chat.id })
  assert.equal(blocked.ok, false)
  live.delete(created.chat.sessionId)
  const ok = await call('bot-chat-archive', { botId: 'writer', chatId: created.chat.id })
  assert.equal(ok.ok, true, ok.error?.message)
})
