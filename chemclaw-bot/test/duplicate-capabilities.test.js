import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { format } from 'node:util'
import { apply } from './legacy-runtime.js'
import { fakeContext } from './fake-ctx.js'

function start(team, { models = ['deepseek-v4-flash'] } = {}) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-dup-cap-'))
  if (team !== undefined) writeFileSync(join(home, 'state.json'), JSON.stringify(team))
  const ctx = fakeContext()
  const workspaces = new Map()
  let sessions = 0
  const warnings = []
  ctx.logger.warn = (...args) => warnings.push(format(...args))
  Object.assign(ctx, {
    llm: {
      listProviders: () => [{ id: 'deepseek', name: 'DeepSeek' }],
      listModels: async () => models.map(id => ({ id })),
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
    const response = await route.fetch(new Request('http://localhost/api/bot', { method: 'POST', body: JSON.stringify({ endpoint, payload }) }))
    return response.json()
  }
  const stop = async () => {
    await ctx.dispose()
    rmSync(home, { recursive: true, force: true, maxRetries: 5 })
  }
  return { call, stop, home, warnings }
}

test('duplicateBot copies attached skills, MCP and packs, not browser grants', async (t) => {
  const { call, stop } = start()
  t.after(stop)
  await call('state', {})
  const writer = (await call('create-bot', { name: 'Writer' })).value
  for (const [endpoint, payload] of [
    ['capability-save', { name: 'guide', kind: 'skill', description: 'Guide', content: 'Write carefully.' }],
    ['capability-save', { name: 'echo', kind: 'mcp', description: 'Echo', transport: 'stdio', command: 'node', args: [], env: {} }],
    ['capability-approve', { name: 'echo' }],
    ['capability-save', { name: 'kit', kind: 'pack', description: 'Kit', items: ['guide', 'echo'] }],
    ['bot-capability', { botId: writer.id, name: 'guide', attached: true }],
    ['bot-capability', { botId: writer.id, name: 'echo', attached: true }],
    ['bot-capability', { botId: writer.id, name: 'kit', attached: true }],
  ]) {
    const result = await call(endpoint, payload)
    assert.equal(result.ok, true, `${endpoint}: ${result.error?.message}`)
  }
  const grant = await call('update-bot', {
    id: writer.id,
    browserGrants: [{ site: 'example.com', kinds: ['download'], until: Date.now() + 3_600_000 }],
  })
  assert.equal(grant.ok, true, grant.error?.message)
  const before = (await call('state', {})).value.bots.find(bot => bot.id === writer.id)
  assert.deepEqual([...before.capabilities].sort(), ['echo', 'guide', 'kit'])
  assert.ok(before.browserGrants?.length > 0)

  const copy = (await call('duplicate-bot', { id: writer.id })).value
  assert.equal(copy.name, 'Writer copy')
  assert.notEqual(copy.id, writer.id)
  assert.deepEqual([...copy.capabilities].sort(), ['echo', 'guide', 'kit'])
  assert.equal(copy.browserGrants, undefined)

  const again = (await call('state', {})).value.bots.find(bot => bot.id === copy.id)
  assert.deepEqual([...again.capabilities].sort(), ['echo', 'guide', 'kit'])
  assert.equal(again.browserGrants, undefined)
  // History / memory stay on the original Session; the copy gets a fresh Session id.
  assert.notEqual(again.id, writer.id)
})

test('duplicateBot keeps the copy name rule and drops capabilities removed from the library', async (t) => {
  const { call, stop } = start()
  t.after(stop)
  await call('state', {})
  const writer = (await call('create-bot', { name: 'Writer' })).value
  await call('capability-save', { name: 'guide', kind: 'skill', description: 'Guide', content: 'Body' })
  await call('capability-save', { name: 'gone', kind: 'skill', description: 'Gone', content: 'Body' })
  await call('bot-capability', { botId: writer.id, name: 'guide', attached: true })
  await call('bot-capability', { botId: writer.id, name: 'gone', attached: true })
  await call('capability-delete', { name: 'gone' })
  const copy = (await call('duplicate-bot', { id: writer.id })).value
  assert.equal(copy.name, 'Writer copy')
  assert.deepEqual(copy.capabilities, ['guide'])
})

test('duplicateBot leaves the original Bot, room sessions and grants untouched', async (t) => {
  const { call, stop, home } = start()
  t.after(stop)
  await call('state', {})
  const chief = (await call('state', {})).value.mainBotId
  const writer = (await call('create-bot', { name: 'Writer' })).value
  for (const [endpoint, payload] of [
    ['capability-save', { name: 'guide', kind: 'skill', description: 'Guide', content: 'Write carefully.' }],
    ['capability-save', { name: 'echo', kind: 'mcp', description: 'Echo', transport: 'stdio', command: 'node', args: [], env: {} }],
    ['capability-approve', { name: 'echo' }],
    ['bot-capability', { botId: writer.id, name: 'guide', attached: true }],
    ['bot-capability', { botId: writer.id, name: 'echo', attached: true }],
  ]) {
    assert.equal((await call(endpoint, payload)).ok, true)
  }
  await call('update-bot', {
    id: writer.id,
    browserGrants: [{ site: 'example.com', kinds: ['download'], until: Date.now() + 3_600_000 }],
  })
  const room = (await call('create-room', { members: [chief, writer.id], admin: writer.id, name: 'Ops' })).value
  const before = JSON.parse(readFileSync(join(home, 'state.json'), 'utf8'))
  const beforeWriter = before.bots[writer.id]
  const beforeRoom = before.rooms[room.id]

  const copy = (await call('duplicate-bot', { id: writer.id })).value
  const after = JSON.parse(readFileSync(join(home, 'state.json'), 'utf8'))
  const afterWriter = after.bots[writer.id]
  const afterRoom = after.rooms[room.id]
  const afterCopy = after.bots[copy.id]

  assert.deepEqual(afterWriter.capabilities, beforeWriter.capabilities)
  assert.deepEqual(afterWriter.browserGrants, beforeWriter.browserGrants)
  assert.deepEqual(afterRoom.members, beforeRoom.members)
  assert.deepEqual(afterRoom.sessions, beforeRoom.sessions)
  assert.deepEqual(afterRoom.segments, beforeRoom.segments)
  assert.equal(Object.hasOwn(afterRoom.sessions ?? {}, copy.id), false)
  assert.deepEqual([...afterCopy.capabilities].sort(), ['echo', 'guide'])
  assert.equal(afterCopy.browserGrants, undefined)
  assert.notEqual(afterCopy.id, writer.id)
  // Copy is not silently added to existing groups.
  assert.equal(afterRoom.members.includes(copy.id), false)
})
