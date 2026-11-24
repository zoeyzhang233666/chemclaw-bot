import { randomUUID } from 'node:crypto'
import { Agent, ProxyAgent } from 'undici'

const DIRECT = 'DIRECT'
const protocols = new Map([['PROXY', 'http:'], ['HTTP', 'http:'], ['HTTPS', 'https:'], ['SOCKS5', 'socks5:']])
const transientCodes = new Set([
  'ECONNREFUSED', 'ECONNRESET', 'EHOSTUNREACH', 'ENETUNREACH', 'ETIMEDOUT',
  'EAI_AGAIN', 'ENOTFOUND', 'UND_ERR_CONNECT_TIMEOUT', 'UND_ERR_HEADERS_TIMEOUT',
  'UND_ERR_BODY_TIMEOUT', 'UND_ERR_SOCKET',
])

export function transientGitHubError(error) {
  return transientCodes.has(error?.cause?.code ?? error?.code)
}

export function gitHubRateLimited(response) {
  return response.status === 429 || (response.status === 403 &&
    (response.headers.get('x-ratelimit-remaining') === '0' || response.headers.has('retry-after')))
}

export function gitHubProxyRoutes(value) {
  if (typeof value !== 'string') return []
  const routes = new Set()
  for (const directive of value.split(';')) {
    const [kind, endpoint, extra] = directive.trim().split(/\s+/)
    if (kind === DIRECT && !endpoint) routes.add(DIRECT)
    const protocol = protocols.get(kind)
    if (!protocol || !endpoint || extra || !/^(?:[\w.-]+|\[[\da-f:.]+\]):\d+$/i.test(endpoint)) continue
    try {
      const url = new URL(`${protocol}//${endpoint}`)
      routes.add(url.href)
    } catch { /* A malformed directive cannot be used. */ }
  }
  if (routes.size === 0 || (routes.size === 1 && routes.has(DIRECT))) return []
  const first = [...routes].slice(0, 2)
  if (!first.includes(DIRECT)) first.push(DIRECT)
  return first
}

function resolveAppProxies(signal) {
  if (process.env.DS_BOT_APP !== '1' || !process.connected || typeof process.send !== 'function') return undefined
  if (signal.aborted) return undefined
  const id = randomUUID()
  return new Promise(resolve => {
    const finish = routes => {
      clearTimeout(timer)
      process.off('message', receive)
      process.off('disconnect', unavailable)
      signal.removeEventListener('abort', unavailable)
      resolve(routes)
    }
    const unavailable = () => finish(undefined)
    const receive = message => {
      if (message?.type === 'chemclaw:github-proxies-response' && message.id === id) finish(message.routes)
    }
    const timer = setTimeout(unavailable, 3_000)
    process.on('message', receive)
    process.once('disconnect', unavailable)
    signal.addEventListener('abort', unavailable, { once: true })
    try {
      process.send({ type: 'chemclaw:github-proxies', id }, error => { if (error) unavailable() })
    } catch { unavailable() }
  })
}

export function createGitHubTransport(routes, {
  fetch: fetchUrl = fetch,
  dispatcherFor = route => route === DIRECT ? new Agent() : new ProxyAgent(route),
} = {}) {
  const candidates = new Map([
    ['api.github.com', gitHubProxyRoutes(routes?.api)],
    ['raw.githubusercontent.com', gitHubProxyRoutes(routes?.raw)],
  ])
  const dispatchers = new Map()
  let apiPreference
  const request = async (url, options) => {
    const hostname = new URL(url).hostname
    const configured = candidates.get(hostname)
    if (!configured?.length) return fetchUrl(url, options)
    const routes = hostname === 'api.github.com' && apiPreference
      ? [apiPreference, ...configured.filter(route => route !== apiPreference)]
      : configured
    let rateLimit
    let failure
    for (const route of routes) {
      options.signal.throwIfAborted()
      try {
        if (!dispatchers.has(route)) dispatchers.set(route, dispatcherFor(route))
        const response = await fetchUrl(url, { ...options, dispatcher: dispatchers.get(route) })
        if (hostname === 'api.github.com' && gitHubRateLimited(response)) {
          rateLimit ??= response
          await response.body?.cancel().catch(() => undefined)
          continue
        }
        if (hostname === 'api.github.com' && response.ok) apiPreference = route
        return response
      } catch (error) {
        if (options.signal.aborted) throw error
        if (!transientGitHubError(error)) {
          if (rateLimit) return rateLimit
          throw error
        }
        failure = error
      }
    }
    if (rateLimit) return rateLimit
    throw failure
  }
  const close = () => Promise.allSettled([...dispatchers.values()].map(dispatcher => dispatcher.destroy()))
  return { request, close }
}

export async function desktopGitHubTransport(signal) {
  const routes = await resolveAppProxies(signal)
  signal.throwIfAborted()
  return createGitHubTransport(routes)
}
