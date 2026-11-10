import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { test } from 'node:test'
import { watchRenderer } from '../src/renderer-recovery.mjs'

test('renderer recovery is bounded, can be retried explicitly, and stops on shutdown', async () => {
  const contents = new EventEmitter()
  let loads = 0
  let prompts = 0
  let answer = false
  let active = true
  const recovery = watchRenderer({ contents, available: () => active, reload: async () => { loads += 1 }, ask: async () => { prompts += 1; return answer } })
  const crash = async () => { contents.emit('render-process-gone', {}, { reason: 'crashed' }); await recovery.recover() }
  await crash()
  await crash()
  await crash()
  assert.equal(loads, 2)
  assert.equal(prompts, 1)
  answer = true
  await recovery.recover()
  assert.equal(loads, 3)
  active = false
  await crash()
  assert.equal(loads, 3)
})

test('a reload failure stays retryable and concurrent recovery shares a single load', async () => {
  const contents = new EventEmitter()
  let rejectLoad
  let loads = 0
  const errors = []
  const recovery = watchRenderer({ contents, available: () => true, reload: () => { loads += 1; return new Promise((_, reject) => { rejectLoad = reject }) }, ask: async () => false, report: error => errors.push(error) })
  contents.emit('render-process-gone', {}, { reason: 'oom' })
  const pending = recovery.recover()
  assert.equal(loads, 1)
  rejectLoad(new Error('mock navigation failure'))
  await pending
  assert.equal(errors.length, 1)
  const retry = recovery.recover()
  assert.equal(loads, 2)
  rejectLoad(new Error('mock failure again'))
  await retry
})

test('a renderer that crashes again during reload cannot be marked healthy', async () => {
  const contents = new EventEmitter()
  let complete
  let loads = 0
  const recovery = watchRenderer({ contents, available: () => true, reload: async () => { loads += 1; if (loads === 1) await new Promise(resolve => { complete = resolve }) }, ask: async () => false })
  contents.emit('render-process-gone', {}, { reason: 'crashed' })
  contents.emit('render-process-gone', {}, { reason: 'crashed' })
  complete()
  await recovery.recover()
  await recovery.recover()
  assert.equal(loads, 2)
})
