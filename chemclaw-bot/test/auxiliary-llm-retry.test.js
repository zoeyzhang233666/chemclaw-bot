import assert from 'node:assert/strict'
import { test } from 'node:test'
import { assembleAuxiliaryLlm } from '../src/host/auxiliary-llm.js'
import { sessionComplete } from '../src/host/browser/session-model.js'

const failure = (code, extra = {}) => ({
  type: 'finish',
  reason: { kind: 'error', failure: { code, message: code, ...extra } },
})
const textChunks = value => [
  { type: 'text-delta', index: 0, text: value },
  { type: 'finish', reason: { kind: 'stop' } },
]
const policy = (maxRetries = 2) => ({
  mode: 'normal', maxRetries, retryableCodes: ['TRANSPORT', 'TIMEOUT'],
  initialDelayMs: 1, maxDelayMs: 5, jitterRatio: 0,
})
const request = { provider: 'mock', model: 'chat', messages: [{ role: 'user', content: [{ type: 'text', text: 'read only' }] }] }
const answer = assembler => assembler.blocks().filter(block => block.type === 'text').map(block => block.text).join('')
const streamOf = (scripts, retry = policy()) => {
  const calls = []
  const ctx = {
    llm: {
      providerRetryPolicy: () => retry,
      async *stream(options) {
        calls.push(options)
        const items = scripts[calls.length - 1] ?? [failure('TRANSPORT')]
        for (const item of items) {
          if (item instanceof Error) throw item
          yield item
        }
      },
    },
  }
  return { ctx, calls }
}

test('auxiliary retry discards partial chunks from transient TRANSPORT and TIMEOUT failures', async () => {
  const { ctx, calls } = streamOf([
    [{ type: 'text-delta', index: 0, text: 'WRONG HALF' }, failure('TRANSPORT')],
    [failure('TIMEOUT')],
    textChunks('Clean and complete.'),
  ])
  const result = await assembleAuxiliaryLlm(ctx, request)
  assert.equal(result.finish.kind, 'stop')
  assert.equal(answer(result), 'Clean and complete.')
  assert.equal(calls.length, 3)
  assert.deepEqual(calls.map(c => c.messages), [request.messages, request.messages, request.messages])
})

test('provider retry cap and disabled strategy prevent unbounded repetitions', async () => {
  const capped = streamOf([[failure('TRANSPORT')], [failure('TRANSPORT')], textChunks('must not run')], policy(1))
  const capResult = await assembleAuxiliaryLlm(capped.ctx, request)
  assert.equal(capResult.finish.kind, 'error')
  assert.equal(capped.calls.length, 2)
  const disabled = streamOf([[failure('TIMEOUT')], textChunks('must not run')], { ...policy(5), mode: 'disabled' })
  const disabledResult = await assembleAuxiliaryLlm(disabled.ctx, request)
  assert.equal(disabledResult.finish.kind, 'error')
  assert.equal(disabled.calls.length, 1)
  const always = streamOf(Array.from({ length: 7 }, () => [failure('TIMEOUT')]), { ...policy(99), mode: 'always' })
  const alwaysResult = await assembleAuxiliaryLlm(always.ctx, request)
  assert.equal(alwaysResult.finish.kind, 'error')
  assert.equal(always.calls.length, 4, 'hard cap is three retries even in always mode')
})

test('authorization failures, normal completions and output-limit truncations are not retried', async () => {
  for (const script of [[failure('AUTH')], [{ type: 'finish', reason: { kind: 'max-tokens' } }], textChunks('fine')]) {
    const { ctx, calls } = streamOf([script])
    const result = await assembleAuxiliaryLlm(ctx, request)
    assert.equal(calls.length, 1)
    assert.ok(['error', 'max-tokens', 'stop'].includes(result.finish.kind))
  }
})

test('thrown transient exceptions retry, but non-transient ones propagate immediately', async () => {
  const timeout = Object.assign(new Error('transient network timeout'), { code: 'TIMEOUT' })
  const { ctx, calls } = streamOf([[timeout], textChunks('retried')])
  const result = await assembleAuxiliaryLlm(ctx, request)
  assert.equal(calls.length, 2)
  assert.equal(answer(result), 'retried')
  const fatal = Object.assign(new Error('bad model key'), { code: 'AUTH' })
  const bad = streamOf([[fatal], textChunks('should not happen')])
  await assert.rejects(assembleAuxiliaryLlm(bad.ctx, request), /bad model key/)
  assert.equal(bad.calls.length, 1)
})

test('abort during backoff ends retry immediately and does not emit partial output', async () => {
  const controller = new AbortController()
  const { ctx, calls } = streamOf([
    [{ type: 'text-delta', index: 0, text: 'partial wrong' }, failure('TRANSPORT')],
    textChunks('should never run'),
  ], { ...policy(2), initialDelayMs: 10_000, maxDelayMs: 10_000 })
  const running = assembleAuxiliaryLlm(ctx, { ...request, signal: controller.signal })
  setTimeout(() => controller.abort(new Error('user cancelled')), 5)
  const result = await running
  assert.equal(result.finish.kind, 'aborted')
  assert.equal(answer(result), '')
  assert.equal(calls.length, 1)
})

test('a provider Retry-After longer than its normal delay ceiling is not ignored', async () => {
  const { ctx, calls } = streamOf([
    [failure('TRANSPORT', { providerRetryAfterMs: 15_000 })],
    textChunks('must not run'),
  ])
  const result = await assembleAuxiliaryLlm(ctx, request)
  assert.equal(result.finish.kind, 'error')
  assert.equal(calls.length, 1)
})

test('pinned DSH fallback policy works when a provider retry policy method is absent', async () => {
  const { ctx, calls } = streamOf([
    [failure('TIMEOUT')],
    textChunks('fallback recovered'),
  ])
  delete ctx.llm.providerRetryPolicy
  const result = await assembleAuxiliaryLlm(ctx, request, { backoff: { initialDelayMs: 0, maxDelayMs: 0, jitterRatio: 0 } })
  assert.equal(answer(result), 'fallback recovered')
  assert.equal(calls.length, 2)
})

test('browser_task completion retries model-stream transport without replaying a browser tool', async () => {
  let calls = 0
  const header = { config: { provider: 'mock', model: 'chat' } }
  const ctx = {
    get: () => undefined,
    llm: {
      providerRetryPolicy: () => policy(1),
      async *stream(options) {
        calls += 1
        assert.equal(options.sessionId, 'browser-session')
        if (calls === 1) { yield failure('TRANSPORT'); return }
        yield* textChunks('Browser observation complete.')
      },
    },
  }
  const exec = {
    signal: new AbortController().signal,
    agent: { session: { id: 'browser-session', requestHeader: () => header } },
  }
  const complete = sessionComplete(ctx, exec, { config: { llmRetryBackoff: { initialDelayMs: 0, maxDelayMs: 0 } } })
  const response = await complete({ messages: [{ role: 'user', content: 'Check the page.' }], tools: [] })
  assert.equal(response.choices[0].message.content, 'Browser observation complete.')
  assert.equal(calls, 2)
})
