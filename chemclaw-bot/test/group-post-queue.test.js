import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createOrderedGroupPostQueue } from '../src/host/group-post-queue.js'

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('group post lane keeps member speech ordered and waits for every commit', async () => {
  const first = deferred()
  const observed = []
  const lane = createOrderedGroupPostQueue(async text => {
    observed.push('start:' + text)
    if (text === 'first') await first.promise
    observed.push('saved:' + text)
  })
  const a = lane.enqueue('first')
  const b = lane.enqueue('second')
  await Promise.resolve()
  assert.deepEqual(observed, ['start:first'])
  first.resolve()
  await Promise.all([a, b, lane.drain()])
  assert.deepEqual(observed, ['start:first', 'saved:first', 'start:second', 'saved:second'])
})

test('group post lane never publishes a later reply after a failed commit', async () => {
  const failure = new Error('ENOSPC: cannot save group state')
  const gate = deferred()
  const published = []
  const lane = createOrderedGroupPostQueue(async text => {
    if (text === 'first') {
      await gate.promise
      throw failure
    }
    published.push(text)
  })
  const first = lane.enqueue('first')
  const second = lane.enqueue('second')
  gate.resolve()
  await assert.rejects(first, error => error === failure)
  await assert.rejects(second, error => error === failure)
  await assert.rejects(lane.drain(), error => error === failure)
  assert.deepEqual(published, [])
  await assert.rejects(lane.enqueue('third'), error => error === failure)
  assert.deepEqual(published, [])
})

test('group post lane closes on turn completion but lets already queued commits finish', async () => {
  const saving = deferred()
  let written = 0
  const lane = createOrderedGroupPostQueue(async () => { await saving.promise; written++ })
  const first = lane.enqueue('before-stop')
  const closed = lane.close()
  await assert.rejects(lane.enqueue('after-stop'), /lane is closed/)
  saving.resolve()
  await Promise.all([first, closed])
  assert.equal(written, 1)
})

test('group post lane rejects missing callbacks', () => {
  assert.throws(() => createOrderedGroupPostQueue(null), /callback is required/)
})
