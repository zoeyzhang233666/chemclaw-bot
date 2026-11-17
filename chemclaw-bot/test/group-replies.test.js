import test from 'node:test'
import assert from 'node:assert/strict'
import { parseReplies, relayRange } from '../src/shared/group-replies.js'

test('settled replies preserve nested data, escaped quotes and literal prune text', () => {
  const replies = [{ botId: 'a', text: 'Use "{x}" and \\path [... tool result middle pruned ...]', meta: { nested: [1, { value: '}' }] } }]
  assert.deepEqual(parseReplies(JSON.stringify({ replies })), { replies, broken: false })
  assert.deepEqual(parseReplies('{"replies":[]}'), { replies: [], broken: false })
})

test('malformed reply shapes are rejected without hiding valid siblings', () => {
  for (const value of [null, [], {}, { replies: {} }, { replies: 'text' }]) {
    assert.deepEqual(parseReplies(JSON.stringify(value)), { replies: [], broken: true })
  }
  const reply = { botId: 'a', text: 'valid' }
  const replies = [null, 'text', [], {}, { text: 42 }, reply, { kind: 'paused', names: ['A'] }]
  assert.deepEqual(parseReplies(JSON.stringify({ replies })), { replies: [reply, replies.at(-1)], broken: true })
})

test('pruned replies recover complete objects on both sides with nested braces and whitespace', () => {
  const first = { botId: 'a', text: 'A "quote" and } brace', extra: { x: '{}' } }
  const last = { botId: 'b', text: 'Last' }
  const source = '{"replies":[' + JSON.stringify(first) + ',{"text":"cut[... tool result middle pruned ...]tail",' + JSON.stringify(last, null, 2) + ']}'
  assert.deepEqual(parseReplies(source), { replies: [first, last], broken: true })
})

test('partial reply fragments and ordinary ellipses do not become invented replies', () => {
  const reply = { botId: 'a', text: 'Step [... details ...] finished' }
  assert.deepEqual(parseReplies('{"replies":[' + JSON.stringify(reply) + ',{"text":"cut'), { replies: [reply], broken: true })
  assert.deepEqual(parseReplies('not a relay result'), { replies: [], broken: true })
  assert.deepEqual(parseReplies('{"replies":[{"text":"cut'), { replies: [], broken: true })
})

test('upstream #1317 relayRange recognizes sequence windows without losing legacy replies', () => {
  assert.deepEqual(relayRange('{"from":3,"to":9,"anchor":"first-round"}'), { from: 3, to: 9, anchor: 'first-round' })
  assert.deepEqual(relayRange('{"from":9}'), { from: 9 })
  assert.deepEqual(relayRange('{"from":9,"to":10.5,"anchor":21}'), { from: 9 })
  assert.equal(relayRange(JSON.stringify({ replies: [{ botId: 'a', text: 'old group reply' }], passed: [] })), undefined)
  assert.equal(relayRange('{"from":3,"replies":[{"text":"interrupted'), undefined)
  assert.equal(relayRange('{"from":"3"}'), undefined)
  assert.equal(relayRange('not a relay result'), undefined)
  const legacy = JSON.stringify({ replies: [{ botId: 'a', text: 'old group reply' }] })
  assert.deepEqual(parseReplies(legacy), { replies: [{ botId: 'a', text: 'old group reply' }], broken: false })
})
