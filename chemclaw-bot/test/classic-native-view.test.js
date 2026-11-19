import assert from 'node:assert/strict'
import { test } from 'node:test'
import { classicNativeViewState } from '../src/client/classic-view-protocol.js'

const state = (phase, result, args = { title: 'Prices', view: { type: 'metric', label: 'Price', value: 100 } }) =>
  classicNativeViewState(phase, {
    content: [{ type: 'text', text: result }],
    args: { value: field => args[field] },
    argsRaw: JSON.stringify(args),
  })

test('classic native renderer draws only a Host-accepted display view', () => {
  assert.equal(state('start', '').status, 'pending')
  assert.deepEqual(state('result', 'The view is on screen.'), {
    status: 'ready', title: 'Prices', view: { type: 'metric', label: 'Price', value: 100 },
  })
  assert.equal(state('result', 'Only Bots on the team can use show_view.').status, 'rejected')
  assert.equal(state('result', 'The chart contains no drawable numeric observations.').status, 'rejected')
  assert.equal(state('result', 'The view is on screen.', { title: 'Empty', view: { type: 'chart', kind: 'line', categories: ['day'], series: [{ values: [] }] } }).status, 'invalid')
  assert.equal(state('result', 'The view is on screen.', { title: 'Question', view: { type: 'confirm', id: 'go' } }).status, 'invalid')
})
test('classic view result cannot fake an accepted UI on a failed tool', () => {
  assert.equal(classicNativeViewState('result', { isError: true, content: [{ type: 'text', text: 'The view is on screen.' }] }).status, 'failed')
})

// DSH's settled ToolResultNode stores the original call under `call`. Ensure
// native cards survive a real tool-result transition and persisted reload.
test('accepted DSH ToolResultNode reads its call.argsRaw for an inline native card', () => {
  const args = { title: 'Daily prices', view: { type: 'chart', kind: 'line', categories: ['Mon', 'Tue'], series: [{ name: 'Price', values: [1, 2] }] } }
  const block = { kind: 'tool-result', call: { name: 'show_view', argsRaw: JSON.stringify(args) }, content: [{ type: 'text', text: 'The view is on screen.' }] }
  assert.deepEqual(classicNativeViewState('result', block), { status: 'ready', ...args })
  assert.equal(classicNativeViewState('result', { ...block, isError: true }).status, 'failed')
  assert.equal(classicNativeViewState('result', { ...block, call: { ...block.call, argsRaw: '{broken' } }).status, 'invalid')
})
