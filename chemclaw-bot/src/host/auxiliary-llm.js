// Transient retries for auxiliary, read-only model completions only.
// The DSH agent loop owns normal chat/tool retry and is never wrapped here.
import { BlockAssembler } from '@deepseek-ai/dsh-llm'

const TRANSIENT_CODES = new Set(['TRANSPORT', 'TIMEOUT'])
// DSH 0.2.1-rc.5 does not guarantee a public policy resolver.
const DEFAULT_POLICY = {
  mode: 'normal', retryableCodes: ['TRANSPORT', 'TIMEOUT'], maxRetries: 2,
  initialDelayMs: 250, maxDelayMs: 2_000, jitterRatio: 0.2,
}
const MAX_RETRIES = 3
const MAX_DELAY_MS = 10_000

function retryPolicy(ctx, provider) {
  try { return ctx.llm?.providerRetryPolicy?.(provider) ?? DEFAULT_POLICY }
  catch { return DEFAULT_POLICY }
}
const limit = (n, fallback, low, high) => Number.isFinite(n) ? Math.min(high, Math.max(low, n)) : fallback

function delayOf(policy, failure, attempt, backoff, random) {
  const first = limit(backoff?.initialDelayMs ?? policy.initialDelayMs, DEFAULT_POLICY.initialDelayMs, 0, MAX_DELAY_MS)
  const ceiling = limit(backoff?.maxDelayMs ?? policy.maxDelayMs, DEFAULT_POLICY.maxDelayMs, 0, MAX_DELAY_MS)
  const jitter = limit(backoff?.jitterRatio ?? policy.jitterRatio, DEFAULT_POLICY.jitterRatio, 0, 1)
  const providerAfter = failure?.providerRetryAfterMs
  if (Number.isFinite(providerAfter) && providerAfter > 0) {
    if (providerAfter <= ceiling) return providerAfter
    if (policy.mode === 'normal') return undefined // do not bypass provider Retry-After
  }
  const base = Math.min(first * 2 ** Math.min(attempt - 1, 12), ceiling)
  return Math.min(ceiling, base * (1 - jitter + 2 * jitter * limit(random(), 0.5, 0, 1)))
}

function allowed(policy, code, attempt) {
  const maxRetries = limit(policy.maxRetries, DEFAULT_POLICY.maxRetries, 0, MAX_RETRIES)
  if (attempt > maxRetries || policy.mode === 'disabled') return false
  if (policy.mode === 'always') return true // only transient errors; still bounded
  return policy.mode === 'normal' && Array.isArray(policy.retryableCodes) && policy.retryableCodes.includes(code)
}

function waitFor(delay, signal) {
  if (signal?.aborted) return Promise.resolve(false)
  return new Promise(resolve => {
    let timer
    function onAbort() {
      clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
      resolve(false)
    }
    signal?.addEventListener('abort', onAbort, { once: true })
    if (signal?.aborted) { onAbort(); return }
    timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve(true)
    }, delay)
  })
}

function abortedAssembler(failure) {
  const result = new BlockAssembler()
  result.push({ type: 'finish', reason: { kind: 'aborted', failure: { code: 'ABORTED', message: failure?.message ?? 'cancelled' } } })
  return result
}

// Failed partial text is never returned: each retry starts a new BlockAssembler.
// No tool execution happens here. Caller and plugin-lifetime abort both win
// during an active stream or the retry delay.
export async function assembleAuxiliaryLlm(ctx, options, { signal, backoff, random = Math.random } = {}) {
  const combined = options.signal && signal ? AbortSignal.any([options.signal, signal]) : options.signal ?? signal
  const request = combined === options.signal ? options : { ...options, signal: combined }
  for (let attempt = 1; ; attempt += 1) {
    if (combined?.aborted) return abortedAssembler()
    const assembler = new BlockAssembler()
    let thrown
    try {
      for await (const chunk of ctx.llm.stream(request)) assembler.push(chunk)
    } catch (error) {
      thrown = error
    }
    if (thrown !== undefined) {
      const code = thrown?.failure?.code ?? thrown?.code
      if (combined?.aborted || !TRANSIENT_CODES.has(code)) throw thrown
      const policy = retryPolicy(ctx, options.provider)
      if (!allowed(policy, code, attempt)) throw thrown
      const delay = delayOf(policy, thrown?.failure ?? thrown, attempt, backoff, random)
      if (delay === undefined) throw thrown
      if (!await waitFor(delay, combined)) throw combined?.reason ?? thrown
      continue
    }
    const finish = assembler.finish
    if (finish.kind !== 'error' || combined?.aborted) return assembler
    const code = finish.failure?.code
    if (!TRANSIENT_CODES.has(code)) return assembler
    const policy = retryPolicy(ctx, options.provider)
    if (!allowed(policy, code, attempt)) return assembler
    const delay = delayOf(policy, finish.failure, attempt, backoff, random)
    if (delay === undefined) return assembler
    if (!await waitFor(delay, combined)) return abortedAssembler(finish.failure)
  }
}
