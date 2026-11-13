import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createOrderedGroupPostQueue, publishSavedGroupReply } from '../src/host/group-post-queue.js'

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

test('round reply waits for required save before showing the answer or committing the draft', async () => {
  const saving = deferred()
  const room = { seq: 0, log: [] }
  const round = { replies: [] }
  const member = { id: 'analyst', name: '分析师', color: 'orange' }
  const options = []
  let drafts = 0
  const commit = publishSavedGroupReply({
    room, round, member, visible: '分析完成', duration: 1000,
    append: (target, line) => {
      target.seq++
      target.log.push({ ...line, seq: target.seq })
    },
    save: option => { options.push(option); return saving.promise },
    commitDraft: () => { drafts++ },
  })
  assert.equal(room.seq, 1)
  assert.deepEqual(room.log, [{ who: '分析师', botId: 'analyst', text: '分析完成', seq: 1 }])
  await Promise.resolve() // await the synchronous legacy append's completion
  assert.deepEqual(options, [{ required: true }])
  assert.deepEqual(round.replies, [], 'the round must not show an uncommitted reply')
  assert.equal(drafts, 0, 'the draft must not be dismissed before persistence')
  saving.resolve()
  assert.equal(await commit, true)
  assert.equal(drafts, 1)
  assert.equal(round.replies.length, 1)
  assert.equal(round.replies[0].text, '分析完成')
  assert.equal(round.replies[0].duration, 1000)
})

test('round reply refuses to report success when required save fails', async () => {
  const room = { seq: 0, log: [] }
  const round = { replies: [] }
  let drafts = 0
  const failure = new Error('state.lock is unavailable')
  await assert.rejects(publishSavedGroupReply({
    room, round, member: { id: 'a', name: 'Bot' }, visible: 'not durable',
    append: target => { target.seq++ },
    save: () => Promise.reject(failure),
    commitDraft: () => { drafts++ },
  }), error => error === failure)
  assert.equal(room.seq, 1, 'legacy memory may change: Ledger cutover is not enabled')
  assert.equal(drafts, 0)
  assert.deepEqual(round.replies, [])
})

test('empty or protocol-only reply is never appended or saved', async () => {
  let calls = 0
  const result = await publishSavedGroupReply({
    room: {}, round: { replies: [] }, member: {}, visible: '',
    append: () => { calls++ }, save: () => { calls++ },
    commitDraft: () => { calls++ },
  })
  assert.equal(result, false)
  assert.equal(calls, 0)
})

test('round reply waits for an asynchronous append and does not save after an append failure', async () => {
  const appending = deferred()
  const calls = []
  const round = { replies: [] }
  const task = publishSavedGroupReply({
    room: {}, round, member: { id: 'analyst', name: 'Analyst' }, visible: 'answer',
    append: async () => { calls.push('append'); await appending.promise },
    save: async () => { calls.push('save') },
    commitDraft: () => calls.push('draft'),
  })
  assert.deepEqual(calls, ['append'])
  assert.deepEqual(round.replies, [])
  appending.resolve()
  assert.equal(await task, true)
  assert.deepEqual(calls, ['append', 'save', 'draft'])
  assert.equal(round.replies.length, 1)

  let saves = 0
  const error = new Error('Ledger fsync failed')
  await assert.rejects(publishSavedGroupReply({
    room: {}, round: { replies: [] }, member: { id: 'a', name: 'A' }, visible: 'not durable',
    append: async () => { throw error },
    save: async () => { saves++ },
  }), observed => observed === error)
  assert.equal(saves, 0)
})
