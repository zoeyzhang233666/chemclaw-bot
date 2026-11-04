import assert from 'node:assert/strict'
import { test } from 'node:test'
import { withLogTail } from '../src/host-process.mjs'

// DSH's fatal IPC error should keep the engine's more detailed stderr cause.
test('DSH fatal load error includes the engine stderr tail', () => {
  const stderr = 'dsh: fatal load failure: Error: Assertion error\n    at FrameManager.frameAttached'
  const message = withLogTail('The DSH Host failed to start', stderr)
  assert.match(message, /^The DSH Host failed to start:\n/)
  assert.match(message, /FrameManager\.frameAttached/)
})

test('DSH startup diagnostics redact launch tokens and omit blank tails', () => {
  assert.equal(
    withLogTail('The DSH Host stopped (exit 1)', 'server http://localhost/?token=abc123 details'),
    'The DSH Host stopped (exit 1):\nserver http://localhost/?token=<hidden> details')
  assert.equal(withLogTail('The DSH Host stopped (exit 0)', '  \n'), 'The DSH Host stopped (exit 0)')
})
