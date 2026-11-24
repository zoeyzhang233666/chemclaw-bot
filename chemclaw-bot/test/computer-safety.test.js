import test from 'node:test'
import assert from 'node:assert/strict'
import { classify, levelAllows, DRIVER_REFUSED } from '../src/host/computer/catalog.js'
import { createLeases } from '../src/host/computer/leases.js'

test('Computer Use tools fail closed when method or level is unknown', () => {
  assert.equal(classify('ordinary_tool'), undefined)
  assert.equal(classify('cua', { method: 'listApps' }).kind, 'observe')
  assert.equal(classify('cua', { method: 'click' }).kind, 'background')
  assert.equal(classify('cua', { method: 'activate' }).kind, 'foreground')
  assert.equal(classify('cua', { method: 'unknownFutureMethod' }).kind, 'foreground')
  assert.equal(classify('cua_driver_native__unknown_future_method').kind, 'foreground')
  assert.equal(levelAllows('off', 'observe'), false)
  assert.equal(levelAllows('view', 'observe'), true)
  assert.equal(levelAllows('view', 'background'), false)
  assert.equal(levelAllows('background', 'foreground'), false)
  assert.equal(levelAllows('foreground', 'foreground'), true)
})

test('Driver recording, reconfiguration and replay cannot bypass app consent', () => {
  for (const method of ['set_config', 'start_recording', 'stop_recording', 'replay_trajectory']) {
    assert.equal(DRIVER_REFUSED.has(method), true)
  }
})

test('Computer Use leases isolate Bots and release after a session ends', () => {
  const leases = createLeases({ idleMs: 1000 })
  try {
    assert.equal(leases.takeApp('editor', 'bot-A', 'session-A'), undefined)
    assert.equal(leases.takeApp('editor', 'bot-B', 'session-B')?.botId, 'bot-A')
    assert.equal(leases.takeForeground('bot-A', 'session-A'), undefined)
    assert.equal(leases.takeForeground('bot-B', 'session-B')?.botId, 'bot-A')
    assert.equal(leases.takeApp('browser', 'bot-B', 'session-B'), undefined)
    leases.endSession('session-A')
    assert.equal(leases.takeApp('editor', 'bot-B', 'session-B'), undefined)
    assert.equal(leases.takeForeground('bot-B', 'session-B'), undefined)
    assert.equal(leases.entries().every(entry => entry.botId === 'bot-B'), true)
    leases.releaseBot('bot-B')
    assert.equal(leases.entries().length, 0)
  } finally {
    leases.dispose()
  }
})

test('computer handback keeps a producer-owned, non-relay source', async (t) => {
  const { mkdtempSync, rmSync, writeFileSync } = await import('node:fs')
  const { tmpdir } = await import('node:os')
  const { join } = await import('node:path')
  const { createRuntime } = await import('./legacy-runtime.js')
  const { fakeContext } = await import('./fake-ctx.js')
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-handback-'))
  writeFileSync(join(home, 'state.json'), JSON.stringify({
    version: 1, mainBotIds: ['w1'], revision: 1,
    bots: { w1: { id: 'w1', sessionId: 'w1', name: 'Writer', role: 'Test', instructions: '', createdAt: 1 } },
    rooms: {}, exchanges: [], exchangeTurns: {}, questions: {},
  }))
  const ctx = fakeContext()
  const rt = createRuntime(ctx, { home })
  t.after(async () => { await ctx.dispose(); rmSync(home, { recursive: true, force: true, maxRetries: 5 }) })
  await rt.load()
  await rt.computerEndpoint('set-enabled', { enabled: true })
  const followups = []
  ctx.sessions = { flush: async () => {} }
  rt.resolveAgent = async () => ({ followup: message => followups.push(message), session: { id: 'w1' } })
  rt.chatOf = () => 'w1'
  await rt.computerEndpoint('handback', { botId: 'w1' })
  assert.deepEqual(followups.at(-1)?.source, { kind: 'bot', role: 'handback' })
  assert.match(followups.at(-1)?.content?.[0]?.text ?? '', /handed the computer back/i)
})
