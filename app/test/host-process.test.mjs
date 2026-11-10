import assert from 'node:assert/strict'
import { test } from 'node:test'
import { withFatalDiagnostic, withLogTail } from '../src/host-process.mjs'

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

test('fatal IPC diagnostic identifies Playwright frame assertion before stderr is available', () => {
  const diagnostic = 'Error: Assertion error\n    at FrameManager.frameAttached\n    endpoint: http://127.0.0.1/?token=secret-value'
  const error = withFatalDiagnostic('DSH fatal load failure', '', diagnostic)
  assert.match(error, /FrameManager\.frameAttached/)
  assert.match(error, /token=<hidden>/)
  assert.doesNotMatch(error, /secret-value/)
})

test('fatal IPC retains its own cause even when stderr already has unrelated warnings', () => {
  const error = withFatalDiagnostic('DSH Host stopped', 'stderr cause\n', 'unused fallback')
  assert.equal(error, 'DSH Host stopped:\nstderr cause\nunused fallback')
  assert.equal(withFatalDiagnostic('DSH Host stopped', '  ', undefined), 'DSH Host stopped')
  const diagnostic = 'Assertion error\n    at FrameManager.frameAttached'
  assert.match(withFatalDiagnostic('Host failed', 'earlier warning', diagnostic), /FrameManager\.frameAttached/)
  assert.equal(withFatalDiagnostic('Host failed', diagnostic, diagnostic), `Host failed:\n${diagnostic}`)
})
