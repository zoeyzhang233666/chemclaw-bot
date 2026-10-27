import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mountBrowserPlugin } from '../src/host/browser/mount.js'
import { gateScope } from '../src/host/browser/gate.js'
import { runToolLoop } from '../src/host/browser/loop.js'

const deferred = () => {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}
const tick = () => new Promise(resolve => setImmediate(resolve))
function fixture(execute, extra = {}) {
  let cleanup
  let tool
  mountBrowserPlugin({ effect(create) { cleanup = create() }, tools: { register(value) { tool = value } } }, {
    toolDefs: [{ name: 'browser_test', needsBrowser: true, execute }],
    defineTool: value => value,
    keyOf: async exec => exec.agent.id,
    profileRoot: '/test-browser-profiles', headless: true,
    openSession: async () => ({ close: async () => {} }),
    ...extra,
  })
  return { run: (botId = 'a', signal) => tool.execute({}, { agent: { id: botId }, signal }), stop: () => cleanup() }
}

test('direct and group browser calls for a Bot serialize while another Bot proceeds', async t => {
  const blocked = deferred()
  const order = []
  const env = fixture(async (_args, { botId }) => {
    order.push(botId)
    if (order.length === 1) await blocked.promise
    return botId
  })
  t.after(env.stop)
  const first = env.run()
  await tick()
  const second = env.run()
  assert.equal(await env.run('b'), 'b')
  assert.deepEqual(order, ['a', 'b'])
  blocked.resolve()
  assert.deepEqual(await Promise.all([first, second]), ['a', 'a'])
  assert.deepEqual(order, ['a', 'b', 'a'])
})

test('a cancelled queued browser call never executes', async t => {
  const blocked = deferred()
  let calls = 0
  const env = fixture(async () => { calls += 1; await blocked.promise })
  t.after(env.stop)
  const first = env.run()
  await tick()
  const controller = new AbortController()
  const second = env.run('a', controller.signal)
  controller.abort()
  blocked.resolve()
  await first
  await assert.rejects(second, { name: 'AbortError' })
  assert.equal(calls, 1)
})

test('cancellation while launching closes the resolved browser and permits a fresh launch', async t => {
  const opening = deferred()
  let closed = 0
  let launches = 0
  let calls = 0
  const env = fixture(async () => { calls += 1 }, {
    openSession: async () => {
      launches += 1
      if (launches === 1) await opening.promise
      return { close: async () => { closed += 1 } }
    },
  })
  t.after(env.stop)
  const controller = new AbortController()
  const run = env.run('a', controller.signal)
  await tick()
  controller.abort()
  opening.resolve()
  await assert.rejects(run, { name: 'AbortError' })
  assert.equal(closed, 1)
  assert.equal(calls, 0)
  await env.run()
  assert.equal(launches, 2)
})

test('cancelling an in-flight operation closes its connection', async t => {
  const closed = deferred()
  const env = fixture(async () => { await closed.promise; throw new Error('Connection closed') }, {
    openSession: async () => ({ close: async () => { closed.resolve() } }),
  })
  t.after(env.stop)
  const controller = new AbortController()
  const run = env.run('a', controller.signal)
  await tick()
  controller.abort()
  await assert.rejects(run, /Connection closed/u)
})

test('a takeover or cancellation during approval cannot send the approved action', async t => {
  for (const cause of ['takeover', 'cancel']) {
    const approval = deferred()
    const controller = new AbortController()
    let held = null
    let sent = 0
    const env = fixture(async () => {
      await gateScope.getStore()({ kind: 'post' })
      sent += 1
    }, { getHold: () => held, authorize: async () => approval.promise })
    t.after(env.stop)
    const run = env.run('a', controller.signal)
    await tick()
    if (cause === 'takeover') held = { by: 'user' }
    else controller.abort()
    approval.resolve()
    await assert.rejects(run)
    assert.equal(sent, 0)
  }
})

test('plugin disposal prevents queued browser work from starting', async () => {
  const blocked = deferred()
  let calls = 0
  const env = fixture(async () => { calls += 1; await blocked.promise })
  const first = env.run()
  await tick()
  const queued = env.run()
  await env.stop()
  blocked.resolve()
  await first
  await assert.rejects(queued, /plugin has stopped/u)
  assert.equal(calls, 1)
})

test('a whole browser task stops at handoff before any subsequent tool in the response', async () => {
  let clicks = 0
  const result = await runToolLoop({
    goal: 'Inspect the supplier', system: 'Read only',
    tools: [
      { name: 'browser_handoff', execute: async () => 'Waiting for the user to sign in' },
      { name: 'browser_click', execute: async () => { clicks += 1 } },
    ],
    complete: async () => ({ choices: [{ message: { tool_calls: [
      { id: 'handoff', function: { name: 'browser_handoff', arguments: '{}' } },
      { id: 'click', function: { name: 'browser_click', arguments: '{}' } },
    ] } }] }),
  })
  assert.equal(result.stopped, 'handoff')
  assert.equal(clicks, 0)
})

test('a cancelled whole task cannot issue another browser action', async () => {
  const controller = new AbortController()
  let calls = 0
  await assert.rejects(runToolLoop({
    goal: 'Read the page', system: 'Read only', signal: controller.signal,
    tools: [{ name: 'browser_snapshot', execute: async () => { calls += 1; controller.abort() } }],
    complete: async () => ({ choices: [{ message: { tool_calls: [
      { id: 'first', function: { name: 'browser_snapshot', arguments: '{}' } },
      { id: 'second', function: { name: 'browser_snapshot', arguments: '{}' } },
    ] } }] }),
  }), { name: 'AbortError' })
  assert.equal(calls, 1)
})
