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

test('upstream #1317 range is extracted without confusing legacy or truncated round replies', () => {
  assert.deepEqual(relayRange(JSON.stringify({ from: 1, anchor: 'round-one', replies: [] })), { from: 1, anchor: 'round-one' })
  assert.deepEqual(relayRange(JSON.stringify({ from: 40, to: 55, anchor: 'round-two', replies: [] })), { from: 40, to: 55, anchor: 'round-two' })
  assert.deepEqual(relayRange(JSON.stringify({ from: 7, to: 2, anchor: '', replies: [] })), { from: 7 })
  for (const result of ['{}', 'not JSON', '{"replies":[]}', '{"from":-1}', '{"from":1.5}', '{"from":"1"}', '{"from":1,"replies":[']) {
    assert.equal(relayRange(result), undefined)
  }
  assert.deepEqual(parseReplies(JSON.stringify({ from: 1, anchor: 'round-one', replies: [{ botId: 'a', text: 'legacy fallback' }] })),
    { replies: [{ botId: 'a', text: 'legacy fallback' }], broken: false })
})
