import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { test } from 'node:test'
import { mountBrowserPlugin } from '../src/host/browser/mount.js'
import { createSession } from '../src/host/browser/session.js'

test('CDP disconnect and context close mark a browser session unusable', () => {
  for (const event of ['disconnected', 'close']) {
    const context = Object.assign(new EventEmitter(), { pages: () => [] })
    const browser = Object.assign(new EventEmitter(), { isConnected: () => true })
    const session = createSession({ context, browser, page: null })
    assert.equal(session.isClosed(), false)
    ;(event === 'close' ? context : browser).emit(event)
    assert.equal(session.isClosed(), true)
    assert.throws(() => session.handoff('other', 'mock'), /connection closed/)
  }
})

test('a disconnected session is evicted without replaying its failed action', async t => {
  const tools = new Map()
  const sessions = []
  let cleanup
  let actions = 0
  mountBrowserPlugin({ effect: create => { cleanup = create() }, tools: { register: tool => tools.set(tool.name, tool) } }, {
    defineTool: value => value,
    keyOf: async () => 'bot',
    profileRoot: '/unused-mock-root',
    toolDefs: [{ name: 'browser_test', needsBrowser: true, execute: async (_, { session }) => {
      actions += 1
      if (actions === 2) { session.closed = true; throw new Error('mock connection lost after action') }
      return 'ok'
    } }],
    openSession: async () => {
      const session = { closed: false, isClosed() { return this.closed }, async close() { this.closed = true } }
      sessions.push(session)
      return session
    },
  })
  t.after(() => cleanup())
  const tool = tools.get('browser_test')
  await tool.execute({}, {})
  await assert.rejects(tool.execute({}, {}), /connection lost/)
  assert.equal(actions, 2)
  assert.equal(sessions.length, 1)
  await tool.execute({}, {})
  assert.equal(actions, 3)
  assert.equal(sessions.length, 2)
  sessions[1].closed = true
  await tool.execute({}, {})
  assert.equal(sessions.length, 3)
})
