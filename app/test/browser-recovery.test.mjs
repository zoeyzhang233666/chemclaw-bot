import assert from 'node:assert/strict'
import { test } from 'node:test'
import { BROWSER_SAFE_ARG, browserFrameAssertion, browserSafeMode, browserRecoveryArgs } from '../src/browser-recovery.mjs'

test('recognizes the actual DSH Playwright FrameManager assertion trace', () => {
  const error = new Error('The DSH Host stopped (exit 1):\ndsh: fatal load failure: Error: Assertion error\n    at FrameManager.frameAttached\n    at _FrameSession._onFrameAttached')
  assert.equal(browserFrameAssertion(error), true)
  assert.equal(browserFrameAssertion(new Error('The DSH Host stopped (exit 1): unexpected shutdown')), false)
  assert.equal(browserFrameAssertion(new Error('Assertion error: not in Playwright frames')), false)
  assert.equal(browserFrameAssertion(new Error('FrameManager.frameAttached: a different error')), false)
})

test('safe mode relaunch is one-run and never creates repeated arguments', () => {
  const original = ['--no-sandbox']
  const recovery = browserRecoveryArgs(original)
  assert.deepEqual(recovery, ['--no-sandbox', BROWSER_SAFE_ARG])
  assert.deepEqual(browserRecoveryArgs(recovery), recovery)
  assert.equal(browserSafeMode(original), false)
  assert.equal(browserSafeMode(recovery), true)
})
