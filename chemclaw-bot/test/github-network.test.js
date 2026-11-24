import assert from 'node:assert/strict'
import test from 'node:test'
import { createGitHubTransport, gitHubProxyRoutes, gitHubRateLimited } from '../src/host/github-network.js'

const api = 'https://api.github.com/repos/owner/repo'
const raw = 'https://raw.githubusercontent.com/owner/repo/main/SKILL.md'
const proxyRules = 'PROXY proxy.example:8080; DIRECT'
const connectionError = code => new TypeError('fetch failed', { cause: Object.assign(new Error(code), { code }) })

function fixture(resolve, routes = { api: proxyRules, raw: proxyRules }) {
  const calls = []
  const closed = []
  const transport = createGitHubTransport(routes, {
    dispatcherFor: route => ({ route, destroy: async () => { closed.push(route) } }),
    fetch: (url, options) => {
      calls.push([url, options.dispatcher?.route])
      return resolve(options.dispatcher?.route, url)
    },
  })
  const options = { signal: new AbortController().signal, redirect: 'error' }
  return { ...transport, send: url => transport.request(url, options), calls, closed }
}

test('Chromium proxy directives preserve order and ignore unsupported or malformed endpoints', () => {
  assert.deepEqual(gitHubProxyRoutes('DIRECT'), [])
  assert.deepEqual(gitHubProxyRoutes('HTTPS proxy.example:8443; SOCKS5 [::1]:1080; DIRECT'),
    ['https://proxy.example:8443/', 'socks5://[::1]:1080', 'DIRECT'])
  assert.deepEqual(gitHubProxyRoutes('SOCKS4 proxy.example:1080; PROXY user@proxy.example:8080'), [])
  assert.deepEqual(gitHubProxyRoutes('DIRECT; PROXY proxy.example:8080'), ['DIRECT', 'http://proxy.example:8080/'])
})

test('API rate limit falls back to direct and reuses that route without changing raw routing', async () => {
  const f = fixture((route, url) => url.startsWith(api) && route !== 'DIRECT'
    ? new Response('limited', { status: 403, headers: { 'x-ratelimit-remaining': '0' } })
    : Response.json({ ok: true }))
  assert.equal((await f.send(api)).status, 200)
  assert.equal((await f.send(api + '/git/trees/main')).status, 200)
  assert.equal((await f.send(raw)).status, 200)
  assert.deepEqual(f.calls.map(([, route]) => route), ['http://proxy.example:8080/', 'DIRECT', 'DIRECT', 'http://proxy.example:8080/'])
  await f.close()
  assert.deepEqual(f.closed, ['http://proxy.example:8080/', 'DIRECT'])
})

test('fallback preserves a rate limit if the alternate cannot connect', async () => {
  const f = fixture(route => {
    if (route === 'DIRECT') throw connectionError('UND_ERR_CONNECT_TIMEOUT')
    return new Response('limited', { status: 403, headers: { 'retry-after': '60' } })
  })
  assert.ok(gitHubRateLimited(await f.send(api)))
})

test('raw falls back on transport failure, but HTTP errors and TLS rejection do not bypass a route', async () => {
  const reachable = fixture(route => {
    if (route !== 'DIRECT') throw connectionError('ECONNREFUSED')
    return new Response('content')
  })
  assert.equal(await (await reachable.send(raw)).text(), 'content')
  const denied = fixture(() => new Response(null, { status: 403 }))
  assert.equal((await denied.send(api)).status, 403)
  assert.equal(denied.calls.length, 1)
  const tls = fixture(() => { throw connectionError('UNABLE_TO_VERIFY_LEAF_SIGNATURE') })
  await assert.rejects(tls.send(raw), error => error.cause?.code === 'UNABLE_TO_VERIFY_LEAF_SIGNATURE')
  assert.equal(tls.calls.length, 1)
})

test('direct and standalone installs use normal fetch without a custom dispatcher', async () => {
  const f = fixture(() => new Response('content'), { api: 'DIRECT' })
  assert.equal(await (await f.send(api)).text(), 'content')
  assert.equal(await (await f.send(raw)).text(), 'content')
  assert.deepEqual(f.calls, [[api, undefined], [raw, undefined]])
})

test('an aborted request never falls back to another route', async () => {
  const controller = new AbortController()
  const f = fixture(() => {
    controller.abort()
    throw connectionError('ECONNRESET')
  })
  await assert.rejects(f.request(raw, { signal: controller.signal }))
  assert.equal(f.calls.length, 1)
})
