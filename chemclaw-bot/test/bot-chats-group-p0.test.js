import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { createRuntime } from './legacy-runtime.js'
import { fakeContext } from './fake-ctx.js'

function open(saved) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-gchat-p0-'))
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
  const rt = createRuntime(ctx, { home })
  const call = async (endpoint, payload) => {
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
  return { call, stop, home, disk, ctx, rt }
}

const legacy = () => ({
  version: 1,
  mainBotIds: ['chief'],
  bots: {
    chief: { id: 'chief', sessionId: 'tip-c', name: 'Chief', role: 'Chief', instructions: '', createdAt: 1, capabilities: [] },
    writer: { id: 'writer', sessionId: 'tip-w', name: 'Writer', role: 'Writer', instructions: '', createdAt: 2, capabilities: [] },
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

test('G1–G2: migration keeps room id, members, admin, history and session bytes', async (t) => {
  const { call, stop, disk } = open(legacy())
  t.after(stop)
  await call('state', {})
  const after = disk()
  assert.equal(after.rooms.ops.id, 'ops')
  assert.deepEqual(after.rooms.ops.members, ['chief', 'writer'])
  assert.equal(after.rooms.ops.admin, 'chief')
  assert.equal(after.rooms.ops.notice, 'keep shipping')
  assert.deepEqual(after.rooms.ops.log, [{ seq: 1, who: 'User', text: 'hi', at: 1 }])
  assert.equal(after.rooms.ops.sessions.chief, 'room-chief')
  assert.equal(after.rooms.ops.sessions.writer, 'room-writer')
  assert.deepEqual(after.rooms.ops.segments.writer, [{ sessionId: 'room-old-w', endedAt: 9 }])
})

test('G2/G10: creating and opening private chats leaves room.sessions unchanged', async (t) => {
  const { call, stop, disk } = open(legacy())
  t.after(stop)
  await call('state', {})
  const before = disk().rooms.ops.sessions
  await call('bot-chat-create', { botId: 'writer' })
  await call('bot-chat-rename', { botId: 'writer', chatId: 'writer', title: 'Private A' })
  await call('bot-chat-open', { botId: 'writer', chatId: 'writer' })
  assert.deepEqual(disk().rooms.ops.sessions, before)
  const rooms = (await call('state', {})).value.rooms
  assert.ok(rooms.some(room => room.id === 'ops' && room.name === 'Ops'))
  assert.equal(rooms.find(room => room.id === 'ops').members.includes('writer'), true)
})

test('G3/G8/C1–C3: active private chat B does not own tip A or room tips', async (t) => {
  const { call, stop, disk } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  const owners = (await call('bot-chat-owners', { botId: 'writer' })).value
  assert.equal(owners.activeChatId, created.chat.id)
  const tipA = owners.chats.find(chat => chat.id === 'writer')
  assert.equal(tipA.sessionId, 'tip-w')
  assert.equal(tipA.owner.chatId, 'writer')
  assert.notEqual(created.chat.sessionId, 'tip-w')
  assert.equal(disk().rooms.ops.sessions.writer, 'room-writer')
  assert.equal(disk().rooms.ops.sessions.chief, 'room-chief')
  const tipB = owners.chats.find(chat => chat.id === created.chat.id)
  assert.equal(tipB.owner?.chatId, created.chat.id)
  assert.equal(tipB.owner?.kind, 'private')
})

test('G4/G5/G9: room tips stay room-owned after private create and reload', async (t) => {
  const { call, stop, disk, rt } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  assert.equal(rt.ownerOf('room-writer')?.kind, 'room')
  assert.equal(rt.ownerOf('room-writer')?.roomId, 'ops')
  assert.equal(rt.ownerOf('room-chief')?.kind, 'room')
  assert.equal(rt.ownerOf('tip-w')?.kind, 'private')
  assert.equal(rt.ownerOf('tip-w')?.chatId, 'writer')
  assert.equal(rt.ownerOf(created.chat.sessionId)?.chatId, created.chat.id)
  const snapshot = disk()
  const { call: call2, stop: stop2, rt: rt2 } = open(snapshot)
  t.after(stop2)
  await call2('state', {})
  assert.equal(rt2.ownerOf('room-writer')?.kind, 'room')
  assert.equal(rt2.ownerOf('tip-w')?.chatId, 'writer')
  assert.equal(rt2.ownerOf(created.chat.sessionId)?.chatId, created.chat.id)
})

test('G6/G12: group read_own_chat anchor ignores activeChatId', async (t) => {
  const { call, stop, rt } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  assert.equal(rt.chatOf('writer'), created.chat.sessionId)
  // From the group Session: always the original private tip, not the active Chat B tip.
  assert.equal(rt.ownChatAnchor('writer', 'room-writer'), 'tip-w')
  // From Chat B: stay on Chat B.
  assert.equal(rt.ownChatAnchor('writer', created.chat.sessionId), created.chat.sessionId)
  // From Chat A: stay on Chat A even while B is active.
  assert.equal(rt.ownChatAnchor('writer', 'tip-w'), 'tip-w')
  const partsFromGroup = rt.partsOf('writer', undefined, rt.ownChatAnchor('writer', 'room-writer'))
  assert.equal(partsFromGroup.at(-1)?.sessionId, 'tip-w')
})

test('G7: private part chain is per-chat; room segments stay on the room', async (t) => {
  const { call, stop, rt, disk } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  const bot = rt.botOf('writer')
  const chatA = rt.chatById(bot, 'writer')
  chatA.segments = [{ sessionId: 'tip-w', endedAt: 100 }]
  chatA.sessionId = 'tip-w-fresh'
  rt.indexSessions()
  assert.equal(rt.ownerOf('tip-w')?.chatId, 'writer')
  assert.equal(rt.ownerOf('tip-w-fresh')?.chatId, 'writer')
  assert.equal(rt.ownerOf(created.chat.sessionId)?.chatId, created.chat.id)
  assert.deepEqual(disk().rooms.ops.segments.writer, [{ sessionId: 'room-old-w', endedAt: 9 }])
  assert.equal(disk().rooms.ops.sessions.writer, 'room-writer')
  const roomParts = rt.partsOf('writer', 'ops')
  assert.equal(roomParts.at(-1)?.sessionId, 'room-writer')
  assert.ok(roomParts.some(part => part.sessionId === 'room-old-w'))
})

test('G11: archiving a private chat is allowed even when the Bot is a group admin', async (t) => {
  const { call, stop } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'chief' })).value
  const archived = await call('bot-chat-archive', { botId: 'chief', chatId: created.chat.id })
  assert.equal(archived.ok, true, archived.error?.message)
  assert.equal(archived.value.chat.archived, true)
  const state = (await call('state', {})).value
  assert.equal(state.rooms.find(room => room.id === 'ops').admin, 'chief')
})

test('message_bot without room uses active private tip (documented default)', async (t) => {
  const { call, stop, rt } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  assert.equal(rt.chatOf('writer'), created.chat.sessionId)
  // Seed tip remains owned by Chat A after the switch.
  assert.equal(rt.ownerOf('tip-w')?.chatId, 'writer')
})
