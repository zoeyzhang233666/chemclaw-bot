import assert from 'node:assert/strict'
import { test } from 'node:test'
import { protocolsOf, PROTOCOLS } from '../src/host/providers.js'

test('rc.1 uses the safe baseline protocols when DSH does not expose a schema', () => {
  assert.deepEqual(protocolsOf(undefined), PROTOCOLS)
  assert.deepEqual(protocolsOf({ schema: {} }), PROTOCOLS)
})

test('rc.2 dynamic schema protocols are reflected without a hard-coded DSH version', () => {
  const schema = {
    uid: 1,
    refs: {
      1: { dict: { providers: 2 } },
      2: { inner: 3 },
      3: { dict: { api: 4 } },
      4: { list: [5, 6, 7] },
      5: { value: 'openai-completions' },
      6: { value: 'anthropic-messages' },
      7: { value: 'google-generative-ai' },
    },
  }
  assert.deepEqual(protocolsOf({ schema }), ['openai-completions', 'anthropic-messages', 'google-generative-ai'])
})
