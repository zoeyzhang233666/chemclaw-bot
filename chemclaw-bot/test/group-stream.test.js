import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install } from '../src/host/group-stream.js'

function bench() {
  const listeners = new Map()
  const rt = {
    ctx: { on: (name, fn) => listeners.set(name, fn), effect: () => {} },
    groupOwners: new Map([['session', { roomId: 'room', botId: 'bot' }]]),
    live: new Map([['session', { turn: 1, info: { role: 'room', exchangeId: 'exchange' } }]]),
    stoppedRoomTurns: new Set(),
    roomOf: () => ({ members: ['bot'] }), botOf: () => ({ id: 'bot', name: 'Expert' }),
  }
  rt.isStoppedRoomTurn = id => rt.stoppedRoomTurns.has(id)
  install(rt)
  return { rt, frame: frame => listeners.get('agent/assistant-stream')({ agent: { id: 'session' }, frame }), event: type => listeners.get('session/event')({ id: 'session' }, { type }) }
}

test('group text stays visible through assistant/message until the round commits it', () => {
  const { rt, frame, event } = bench()
  frame({ type: 'start', attemptId: 'a' })
  frame({ type: 'chunk', attemptId: 'a', chunk: { type: 'reasoning-delta', text: 'private reasoning' } })
  assert.deepEqual(rt.roomDrafts('room'), [])
  frame({ type: 'chunk', attemptId: 'a', chunk: { type: 'text-delta', text: 'Expert: First ' } })
  frame({ type: 'chunk', attemptId: 'a', chunk: { type: 'text-delta', text: 'words' } })
  assert.equal(rt.roomDrafts('room')[0].text, 'First words')
  assert.deepEqual(rt.roomDrafts('other-room'), [])
  frame({ type: 'end', attemptId: 'a' })
  assert.equal(rt.roomDrafts('room').length, 1)
  event('assistant/message')
  assert.equal(rt.roomDrafts('room')[0].text, 'First words')
  rt.live.delete('session')
  event('turn/end')
  assert.equal(rt.roomDrafts('room')[0].text, 'First words')
  rt.commitRoomDraft('session')
  assert.deepEqual(rt.roomDrafts('room'), [])
})

test('private exchanges, cancelled turns, deleted members, retries and PASS do not leak group drafts', () => {
  for (const role of ['request', 'stopped', 'handoff']) {
    const { rt, frame } = bench()
    rt.live.get('session').info.role = role
    frame({ type: 'start', attemptId: 'a' })
    frame({ type: 'chunk', attemptId: 'a', chunk: { type: 'text-delta', text: 'private' } })
    assert.deepEqual(rt.roomDrafts('room'), [])
  }
  const { rt, frame, event } = bench()
  frame({ type: 'start', attemptId: 'a' })
  for (const text of ['[P', 'A', 'SS]']) {
    frame({ type: 'chunk', attemptId: 'a', chunk: { type: 'text-delta', text } })
    assert.deepEqual(rt.roomDrafts('room'), [])
  }
  frame({ type: 'start', attemptId: 'retry' })
  frame({ type: 'chunk', attemptId: 'a', chunk: { type: 'text-delta', text: 'stale' } })
  frame({ type: 'chunk', attemptId: 'retry', chunk: { type: 'text-delta', text: 'new answer' } })
  assert.equal(rt.roomDrafts('room')[0].text, 'new answer')
  rt.stoppedRoomTurns.add('exchange')
  assert.deepEqual(rt.roomDrafts('room'), [])
  rt.stoppedRoomTurns.clear()
  rt.roomOf = () => ({ members: [] })
  assert.deepEqual(rt.roomDrafts('room'), [])
  event('turn/end')
  rt.roomOf = () => ({ members: ['bot'] })
  rt.discardRoomDraft('session')
  assert.deepEqual(rt.roomDrafts('room'), [])
})

test('discard clears a held draft when the member passes or misses', () => {
  const { rt, frame, event } = bench()
  frame({ type: 'start', attemptId: 'a' })
  frame({ type: 'chunk', attemptId: 'a', chunk: { type: 'text-delta', text: 'hello' } })
  event('assistant/message')
  event('turn/end')
  rt.live.delete('session')
  assert.equal(rt.roomDrafts('room')[0].text, 'hello')
  rt.discardRoomDraft('session')
  assert.deepEqual(rt.roomDrafts('room'), [])
})
