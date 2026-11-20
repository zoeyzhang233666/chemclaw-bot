import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install } from '../src/host/response-timing.js'

test('response diagnostics retain only timings and distinguish preparation from model output', async () => {
  const hooks = new Map()
  const rt = { ctx: { on: (name, fn) => hooks.set(name, fn), effect: () => {} }, isBotSession: id => id === 's', groupOwners: new Map(), ownRequest: () => false }
  install(rt)
  hooks.get('session/event')({ id: 's' }, { type: 'turn/start' })
  const chunks = [{ type: 'reasoning-delta', text: 'private' }, { type: 'text-delta', text: 'private answer' }]
  const output = []
  for await (const chunk of hooks.get('llm/stream')({ sessionId: 's', messages: ['private prompt'], apiKey: 'mock-secret' }, async function* () { yield* chunks })) output.push(chunk)
  assert.deepEqual(output, chunks)
  hooks.get('session/event')({ id: 's' }, { type: 'turn/end' })
  const [row] = rt.responseTimings()
  assert.equal(row.requests, 1)
  assert.ok(row.requestMs <= row.firstChunkMs && row.firstChunkMs <= row.firstTextMs && row.firstTextMs <= row.endMs)
  assert.deepEqual(Object.keys(row).sort(), ['startedAt', 'kind', 'requests', 'requestMs', 'firstChunkMs', 'firstReasoningMs', 'firstTextMs', 'endMs'].sort())
  assert.ok(!JSON.stringify(row).includes('private'))
})

test('Classic diagnostics separate visible text, reasoning and tool timing from auxiliary requests', async () => {
  const hooks = new Map()
  const rt = { ctx: { on: (name, fn) => hooks.set(name, fn), effect: () => {} }, isBotSession: () => false, groupOwners: new Map() }
  install(rt)
  const events = hooks.get('session/event')
  const onStream = hooks.get('llm/stream')
  events({ id: 'classic' }, { type: 'turn/start' })
  const stream = async function* () { yield { type: 'reasoning-delta' }; yield { type: 'text-delta', text: 'Hi' }; yield { type: 'tool-call-delta' } }
  await Array.fromAsync(onStream({ sessionId: 'classic', purpose: 'title' }, stream))
  await Array.fromAsync(onStream({ sessionId: 'classic' }, stream))
  const [row] = rt.responseTimings()
  assert.equal(row.kind, 'classic')
  assert.equal(row.requests, 1)
  assert.ok(row.requestMs <= row.firstReasoningMs && row.firstReasoningMs <= row.firstTextMs && row.firstTextMs <= row.firstToolMs)
})
