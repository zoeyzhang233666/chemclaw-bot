import assert from 'node:assert/strict'
import { test } from 'node:test'
import { call } from '../src/client/api.js'

test('a stalled roster request is cancelled and the next poll can succeed', async t => {
  const deadline = new AbortController()
  t.mock.method(AbortSignal, 'timeout', ms => { assert.equal(ms, 15000); return deadline.signal })
  let started
  t.mock.method(globalThis, 'fetch', async (_url, init) => {
    started = init.signal
    return new Promise((_, reject) => init.signal.addEventListener('abort', () => reject(init.signal.reason), { once: true }))
  })
  const pending = call('state', {})
  const rejected = assert.rejects(pending, /Could not reach DSH/)
  assert.ok(started)
  deadline.abort(new DOMException('mock deadline', 'TimeoutError'))
  await rejected
  t.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => ({ ok: true, value: { bots: ['kept'] } }) }))
  t.mock.method(AbortSignal, 'timeout', () => new AbortController().signal)
  assert.deepEqual(await call('state', {}), { bots: ['kept'] })
})

test('caller cancellation survives the roster deadline and mutations retain their own signal', async t => {
  const caller = new AbortController()
  let seen
  t.mock.method(globalThis, 'fetch', async (_url, init) => {
    seen = init.signal
    return { ok: true, json: async () => ({ ok: true, value: null }) }
  })
  await call('state', {}, caller.signal)
  caller.abort()
  assert.equal(seen.aborted, true)
  const mutation = new AbortController()
  await call('send', {}, mutation.signal)
  assert.equal(seen, mutation.signal)
})
