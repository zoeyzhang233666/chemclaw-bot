import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { apply } from './legacy-runtime.js'
import { fakeContext } from './fake-ctx.js'

function open(saved) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-bot-chats-'))
  if (saved !== undefined) writeFileSync(join(home, 'state.json'), JSON.stringify(saved))
  const ctx = fakeContext()
  const workspaces = new Map()
  let sessions = 0
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
      resolveAgent: async sessionId => ({ agent: { session: { id: sessionId }, followup: () => {} } }),
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
  apply(ctx, { home })
  const call = async (endpoint, payload) => {
    const response = await route.fetch(new Request('http://localhost/api/bot', {
      method: 'POST',
      body: JSON.stringify({ endpoint, payload }),
    }))
    return response.json()
  }
  const stop = async () => {
    await ctx.dispose()
    rmSync(home, { recursive: true, force: true, maxRetries: 5 })
  }
  return { call, stop, home, ctx }
}

const legacyTeam = () => ({
  version: 1,
  mainBotIds: ['chief'],
  bots: {
    chief: {
      id: 'chief', sessionId: 'tip-a', name: 'Chief', role: 'Chief', instructions: '', createdAt: 1,
      segments: [{ sessionId: 'old-a', endedAt: 10 }],
      capabilities: [],
    },
    writer: {
      id: 'writer', sessionId: 'tip-w', name: 'Writer', role: 'Writer', instructions: '', createdAt: 2,
      capabilities: ['guide'],
    },
  },
  rooms: {
    ops: {
      id: 'ops', name: 'Ops', named: true, members: ['chief', 'writer'], admin: 'chief', mode: 'everyone',
      notice: '', createdAt: 3,
      sessions: { chief: 'room-chief', writer: 'room-writer' },
      segments: { chief: [{ sessionId: 'room-old', endedAt: 20 }] },
    },
  },
  agents: {},
  capabilities: { items: { guide: { name: 'guide', kind: 'skill', description: 'Guide', content: 'Body' } } },
  exchanges: [],
  exchangeTurns: {},
  questions: {},
  revision: 1,
})

test('legacy bots gain one chat that keeps tip, segments and room sessions', async (t) => {
  const saved = legacyTeam()
  const { call, stop, home } = open(saved)
  t.after(stop)
  const team = (await call('state', {})).value
  const chief = team.bots.find(bot => bot.id === 'chief')
  assert.ok(Array.isArray(chief.chats))
  assert.equal(chief.chats.length, 1)
  assert.equal(chief.activeChatId, 'chief')
  assert.equal(chief.chats[0].id, 'chief')
  assert.equal(chief.chats[0].sessionId, 'tip-a')
  assert.deepEqual(chief.chats[0].parts, ['old-a'])
  assert.equal(chief.sessionId, 'tip-a')

  const disk = JSON.parse(readFileSync(join(home, 'state.json'), 'utf8'))
  assert.deepEqual(disk.bots.chief.chats[0].segments, [{ sessionId: 'old-a', endedAt: 10 }])
  assert.equal(disk.rooms.ops.sessions.chief, 'room-chief')
  assert.equal(disk.rooms.ops.sessions.writer, 'room-writer')
  assert.deepEqual(disk.rooms.ops.segments.chief, [{ sessionId: 'room-old', endedAt: 20 }])
  assert.ok(readdirSync(home).some(name => name.startsWith('state.json.pre-multichat-')))
})

test('chat migration is idempotent and does not remapping session ids', async (t) => {
  const saved = legacyTeam()
  const { call, stop, home } = open(saved)
  t.after(stop)
  await call('state', {})
  const first = JSON.parse(readFileSync(join(home, 'state.json'), 'utf8'))
  const { call: call2, stop: stop2, home: home2 } = open(first)
  t.after(stop2)
  await call2('state', {})
  const second = JSON.parse(readFileSync(join(home2, 'state.json'), 'utf8'))
  assert.equal(second.bots.chief.chats.length, 1)
  assert.equal(second.bots.chief.chats[0].sessionId, 'tip-a')
  assert.equal(second.bots.chief.chats[0].segments[0].sessionId, 'old-a')
  assert.equal(second.rooms.ops.sessions.writer, 'room-writer')
})

test('ownerOf indexes every private chat tip and every room tip, never activeChatId alone', async (t) => {
  const { call, stop, home } = open()
  t.after(stop)
  await call('state', {})
  const chief = (await call('state', {})).value.mainBotId
  const writer = (await call('create-bot', { name: 'Writer' })).value
  const room = (await call('create-room', { members: [chief, writer.id], admin: writer.id, name: 'Ops' })).value
  const created = await call('bot-chat-create', { botId: writer.id })
  assert.equal(created.ok, true, created.error?.message)
  assert.ok(created.value.chat?.id)
  assert.notEqual(created.value.chat.id, writer.id)
  assert.notEqual(created.value.chat.sessionId, writer.id)

  const opened = await call('bot-chat-open', { botId: writer.id, chatId: created.value.chat.id })
  assert.equal(opened.ok, true, opened.error?.message)
  assert.equal(opened.value.activeChatId, created.value.chat.id)

  // Original tip remains owned by the first chat even while B is active.
  const owners = (await call('bot-chat-owners', { botId: writer.id })).value
  const tipA = owners.chats.find(chat => chat.id === writer.id)
  const tipB = owners.chats.find(chat => chat.id === created.value.chat.id)
  assert.ok(tipA, `missing original chat in ${JSON.stringify(owners)}`)
  assert.ok(tipB, `missing new chat in ${JSON.stringify(owners)}`)
  assert.equal(tipA.sessionId, writer.id)
  assert.notEqual(tipB.sessionId, tipA.sessionId)
  assert.equal(owners.activeChatId, created.value.chat.id)

  const disk = JSON.parse(readFileSync(join(home, 'state.json'), 'utf8'))
  assert.deepEqual([...disk.rooms[room.id].members].sort(), [chief, writer.id].sort())
})

test('creating and switching private chats does not touch room.sessions', async (t) => {
  const saved = legacyTeam()
  const { call, stop, home } = open(saved)
  t.after(stop)
  await call('state', {})
  const before = JSON.parse(readFileSync(join(home, 'state.json'), 'utf8')).rooms.ops.sessions
  await call('bot-chat-create', { botId: 'writer' })
  await call('bot-chat-open', { botId: 'writer', chatId: 'writer' })
  const after = JSON.parse(readFileSync(join(home, 'state.json'), 'utf8')).rooms.ops.sessions
  assert.deepEqual(after, before)
})

test('bot-chat rename archive and list expose Batch 3 fields', async (t) => {
  const { call, stop } = open()
  t.after(stop)
  await call('state', {})
  const writer = (await call('create-bot', { name: 'Writer' })).value
  const created = (await call('bot-chat-create', { botId: writer.id })).value
  const renamed = (await call('bot-chat-rename', {
    botId: writer.id, chatId: created.chat.id, title: 'Acrylic brief',
  })).value
  assert.equal(renamed.chat.title, 'Acrylic brief')
  assert.equal(renamed.chat.titleSource, 'user')

  const archived = (await call('bot-chat-archive', { botId: writer.id, chatId: created.chat.id })).value
  assert.equal(archived.chat.archived, true)

  const listed = (await call('bot-chat-list', { botId: writer.id })).value
  assert.ok(listed.chats.some(chat => chat.id === created.chat.id && chat.archived === true))
  assert.ok(listed.chats.every(chat => Object.hasOwn(chat, 'running')))
  assert.ok(listed.chats.every(chat => Object.hasOwn(chat, 'needsInput')))
})
