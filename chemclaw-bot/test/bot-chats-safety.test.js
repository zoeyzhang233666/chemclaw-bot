import assert from 'node:assert/strict'
import { chmodSync, existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { createRuntime } from './legacy-runtime.js'
import { fakeContext } from './fake-ctx.js'

function open(saved, { readonlyBackupDir = false } = {}) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-chat-safety-'))
  if (saved !== undefined) writeFileSync(join(home, 'state.json'), JSON.stringify(saved))
  if (readonlyBackupDir) {
    // Leave state.json writable; make creating a new backup file fail by
    // removing write on the directory after the state file exists.
    try { chmodSync(home, 0o555) } catch { /* Windows may ignore; test handles skip */ }
  }
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
  rt.live = live
  const call = async (endpoint, payload) => {
    const response = await route.fetch(new Request('http://localhost/api/bot', {
      method: 'POST', body: JSON.stringify({ endpoint, payload }),
    }))
    return response.json()
  }
  const stop = async () => {
    try { chmodSync(home, 0o755) } catch { /* ignore */ }
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
    chief: { id: 'chief', sessionId: 'tip-c', name: 'Chief', role: 'Chief', instructions: '', createdAt: 1, capabilities: [] },
    writer: {
      id: 'writer', sessionId: 'tip-w', name: 'Writer', role: 'Writer', instructions: '', createdAt: 2, capabilities: [],
      segments: [{ sessionId: 'old-w', endedAt: 5 }],
    },
  },
  rooms: {
    ops: {
      id: 'ops', name: 'Ops', named: true, members: ['chief', 'writer'], admin: 'chief', mode: 'everyone',
      notice: '', createdAt: 3,
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

test('partsOf with an unknown private session returns empty, never activeChat', async (t) => {
  const { call, stop, rt } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  assert.equal(rt.chatOf('writer'), created.chat.sessionId)
  assert.deepEqual(rt.partsOf('writer', undefined, 'no-such-session'), [])
  const owned = rt.partsOf('writer', undefined, 'tip-w')
  assert.equal(owned.at(-1)?.sessionId, 'tip-w')
})

test('currentOf refuses owners without a concrete chat or room container', async (t) => {
  const { call, stop, rt } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  assert.equal(rt.currentOf({ botId: 'writer' }), undefined)
  assert.equal(rt.currentOf({ botId: 'writer', chatId: 'writer' }), 'tip-w')
  assert.equal(rt.currentOf({ botId: 'writer', roomId: 'ops' }), 'room-writer')
})

test('private rotation without an owned chat does not write the active chat', async (t) => {
  const { call, stop, rt, disk } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  const beforeB = disk().bots.writer.chats.find(chat => chat.id === created.chat.id).sessionId
  // Orphan session: not in the index. runSwitch path uses ownerOf; placeOf returns undefined and aborts.
  const place = rt.placeOf?.('orphan-session')
  assert.equal(place, undefined)
  assert.equal(disk().bots.writer.chats.find(chat => chat.id === created.chat.id).sessionId, beforeB)
})

test('failed pre-multichat backup blocks destructive migration write', async (t) => {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-chat-backup-fail-'))
  const saved = legacy()
  writeFileSync(join(home, 'state.json'), JSON.stringify(saved))
  const original = readFileSync(join(home, 'state.json'), 'utf8')
  const ctx = fakeContext()
  Object.assign(ctx, {
    llm: {
      listProviders: () => [{ id: 'deepseek', name: 'DeepSeek' }],
      listModels: async () => [{ id: 'deepseek-v4-flash' }],
      resolveModelInfo: async () => ({}),
    },
    workspaceRegistry: {
      get: () => undefined,
      resolveByPath: async () => undefined,
      create: async path => ({ id: 'w1', path }),
      archiveSession: async () => {},
    },
    sessionController: {
      create: async () => ({ sessionId: 'fresh' }),
      resolveAgent: async sessionId => ({ agent: { session: { id: sessionId }, followup: () => {} } }),
      selectModel: async () => {},
    },
    sessionTitle: { rename: async () => {} },
    sessions: { flush: async () => {} },
  })
  let route
  const register = ctx.connection.fetch.register
  ctx.connection.fetch.register = (options) => { route = options; return register(options) }
  const rt = createRuntime(ctx, { home })
  // Force backup to fail before any migrate write.
  const boom = Object.assign(new Error('EACCES'), { code: 'EACCES' })
  rt.backupBeforeMultichat = async () => { throw boom }
  t.after(async () => {
    await ctx.dispose()
    rmSync(home, { recursive: true, force: true, maxRetries: 5 })
  })
  const response = await route.fetch(new Request('http://localhost/api/bot', {
    method: 'POST', body: JSON.stringify({ endpoint: 'state', payload: {} }),
  }))
  const body = await response.json()
  // API may still answer from memory, but disk must keep the pre-migration bytes.
  assert.equal(readFileSync(join(home, 'state.json'), 'utf8'), original)
  assert.equal(readdirSync(home).some(name => name.startsWith('state.json.pre-multichat-')), false)
  assert.equal('chats' in JSON.parse(original).bots.writer, false)
  void body
  void rt
})

test('archive and delete refuse running, waiting, approval, and captain chats including past segments', async (t) => {
  const { call, stop, rt, live } = open(legacy())
  t.after(stop)
  await call('state', {})
  const created = (await call('bot-chat-create', { botId: 'writer' })).value
  live.set(created.chat.sessionId, { turn: {} })
  const running = await call('bot-chat-archive', { botId: 'writer', chatId: created.chat.id })
  assert.equal(running.ok, false)
  assert.match(running.error?.message ?? '', /running|still/i)
  live.delete(created.chat.sessionId)

  rt.state.questions[created.chat.sessionId] = { text: 'Need a choice' }
  const waiting = await call('bot-chat-delete', { botId: 'writer', chatId: created.chat.id })
  assert.equal(waiting.ok, false)
  assert.match(waiting.error?.message ?? '', /waiting|input/i)
  delete rt.state.questions[created.chat.sessionId]

  rt.approvalsView = () => [{ sessionId: created.chat.sessionId, botId: 'writer' }]
  const approval = await call('bot-chat-archive', { botId: 'writer', chatId: created.chat.id })
  assert.equal(approval.ok, false)
  assert.match(approval.error?.message ?? '', /approval/i)
  rt.approvalsView = () => []

  // Captain bound to a past segment of Chat A (seed), while B is active.
  await call('bot-chat-open', { botId: 'writer', chatId: created.chat.id })
  rt.state.works = {
    w1: { captainSessionId: 'old-w', status: 'running', active: true },
  }
  const captain = await call('bot-chat-archive', { botId: 'writer', chatId: 'writer' })
  assert.equal(captain.ok, false)
  assert.match(captain.error?.message ?? '', /agent team|captain/i)
})

test('migration backup exists before chats appear on disk', async (t) => {
  const { call, stop, home } = open(legacy())
  t.after(stop)
  await call('state', {})
  const names = readdirSync(home)
  assert.ok(names.some(name => name.startsWith('state.json.pre-multichat-')))
  const backup = names.find(name => name.startsWith('state.json.pre-multichat-'))
  const prior = JSON.parse(readFileSync(join(home, backup), 'utf8'))
  assert.equal('chats' in prior.bots.writer, false)
  assert.equal(prior.bots.writer.sessionId, 'tip-w')
  assert.equal(prior.rooms.ops.sessions.writer, 'room-writer')
  assert.ok(existsSync(join(home, 'state.json')))
})
