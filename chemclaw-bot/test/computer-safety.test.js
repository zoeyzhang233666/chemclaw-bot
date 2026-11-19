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
