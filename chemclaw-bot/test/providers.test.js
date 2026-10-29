import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install as installModels } from '../src/host/models.js'
import { checkKey, install, keyRefFor } from '../src/host/providers.js'
import { APIHUB } from '../src/shared/model-providers.js'

// A DSH with the official DeepSeek route, an account route, and the pi-ai adapter: its
// directory offers catalog providers, and its settings take path writes the way DSH's
// do, under a revision. Routes come and go with the pi-ai section.
function dsh({ keys = {}, readOnly = [], user = {}, base = {}, catalog = { anthropic: ['claude-a', 'claude-b'], moonshotai: ['kimi-k3'] }, defaultSelection = { provider: 'deepseek-official', model: 'deepseek-flash' } } = {}) {
  const store = { ...keys }
  const writes = []
  const listeners = new Map()
  let revision = 0
  let pi = { user: structuredClone(user), base: structuredClone(base) }
  const piValue = () => ({ providers: { ...pi.base.providers, ...pi.user.providers } })
  const routes = () => Object.keys(piValue().providers)
  const metadata = model => typeof model === 'string' ? { id: model } : model
  const services = {
    agentDefaultModel: { currentSelection: () => defaultSelection },
    settings: {
      describe: () => [
        { ns: 'llm-deepseek', revision: 0, value: { apiKeyEnv: 'DEEPSEEK_API_KEY' }, user: {}, base: { apiKeyEnv: 'DEEPSEEK_API_KEY' } },
        { ns: 'llm-deepseek-account', revision: 0, value: {}, user: {}, base: {} },
        { ns: 'llm-pi-ai', revision, value: piValue(), user: structuredClone(pi.user), base: structuredClone(pi.base) },
      ],
      mutate: async (ns, ops, expected) => {
        if (expected !== revision) throw new Error(`settings namespace "${ns}" changed since it was read`)
        const next = structuredClone(pi.user)
        for (const op of ops) {
          const parent = op.path.slice(0, -1).reduce((value, key) => (value[key] ??= {}), next)
          if (op.op === 'set') parent[op.path.at(-1)] = op.value
          else delete parent[op.path.at(-1)]
        }
        for (const [id, profile] of Object.entries(next.providers ?? {})) {
          if (!(id in catalog) && !(profile.models?.length > 0)) throw new Error(`llm-pi-ai: provider "${id}" resolves no models`)
        }
        writes.push([ns, ops])
        pi = { ...pi, user: next }
        revision += 1
      },
    },
    credentials: {
      resolve: async ref => ref in store ? { value: store[ref] } : undefined,
      describe: async ref => ({ configured: ref in store, writable: !readOnly.includes(ref) }),
      set: async (ref, value) => { writes.push(['set', ref]); store[ref] = value },
      unset: async (ref) => { writes.push(['unset', ref]); delete store[ref] },
    },
  }
  const discovered = []
  const ctx = {
    on(name, listener) { listeners.set(name, listener); return () => listeners.delete(name) },
    get: name => services[name],
    llm: {
      listProviders: () => [{ id: 'deepseek-official', name: 'DeepSeek' }, { id: 'deepseek-account', name: 'DeepSeek Account' }, ...routes().map(id => ({ id, name: piValue().providers[id].displayName ?? id }))],
      listModels: async (id) => {
        if (id === 'deepseek-official') return [{ id: 'deepseek-flash', name: 'DeepSeek Flash' }]
        if (id === 'deepseek-account') return []
        const profile = piValue().providers[id]
        return (profile.models ?? catalog[id] ?? []).map(model => {
          const entry = metadata(model)
          return { ...entry, ...(entry.input ? { inputModalities: entry.input } : {}) }
        })
      },
      listConfigurableProviders: () => [
        { provider: 'deepseek-official', displayName: 'DeepSeek', settingsNs: 'llm-deepseek', settingsPath: [] },
        { provider: 'deepseek-account', displayName: 'DeepSeek Account', settingsNs: 'llm-deepseek-account', settingsPath: [] },
        ...Object.keys(catalog).map(id => ({ provider: id, displayName: id, settingsNs: 'llm-pi-ai', settingsPath: ['providers', id], declared: false })),
        ...routes().filter(id => !(id in catalog)).map(id => ({ provider: id, displayName: piValue().providers[id].displayName ?? id, settingsNs: 'llm-pi-ai', settingsPath: ['providers', id], declared: true })),
      ],
      discoverModels: async (ns, request) => {
        discovered.push([ns, request])
        return request.provider in catalog ? catalog[request.provider].map(metadata)
          : [{ id: 'relay-1', name: 'Relay One', contextWindow: 128000, inputModalities: ['text'] }, { id: 'relay-2' }]
      },
    },
  }
  const rt = { ctx, state: { bots: {} }, botOf: id => rt.state.bots[id], selfOf: id => id === 'group-member' ? 'preset' : id, save: async () => {} }
  installModels(rt)
  install(rt)
  return { rt, store, writes, listeners, discovered }
}

const needing = async rt => (await rt.catalog({ fresh: true })).filter(entry => entry.needsKey).map(entry => entry.provider)
const row = (view, id) => view.providers.find(provider => provider.id === id)

const visionIds = ['minimax-m3.1-flash', 'kimi-k2.6', 'minimax-m3', 'qwen3.8-max']
const visionCatalog = { native: visionIds.map(id => ({ id, inputModalities: ['text', 'image'] })) }
const apiHubRoute = models => ({ displayName: APIHUB.name, api: APIHUB.api, baseURL: APIHUB.baseURL, apiKeyEnv: 'APIHUB_API_KEY', models })

test('APIHub setup fills exact catalog IDs while preserving explicit inputs and unknown IDs', async () => {
  const { rt, writes } = dsh({ catalog: visionCatalog })
  await rt.addProvider({ preset: 'apihub', key: 'synthetic-only', models: [
    ...visionIds.filter(id => id !== 'kimi-k2.6').map(id => ({ id })), { id: 'unknown' }, { id: 'kimi-k2.6-custom' },
    { id: 'kimi-k2.6', input: ['text'] },
  ] })
  const saved = writes[0][1][0].value.models
  assert.deepEqual(saved, [
    ...visionIds.filter(id => id !== 'kimi-k2.6').map(id => ({ id, input: ['text', 'image'] })),
    { id: 'unknown' }, { id: 'kimi-k2.6-custom' }, { id: 'kimi-k2.6', input: ['text'] },
  ])
})

test('APIHub migration preserves route and model controls, keys and selections; concurrent reads write once', async () => {
  const profile = { ...apiHubRoute(visionIds.map(id => ({ id, contextWindow: 12345, compat: { supportsDeveloperRole: false } }))),
    headers: { 'x-deployment': 'synthetic' }, retryPolicy: { mode: 'disabled' } }
  const { rt, writes, store } = dsh({ catalog: visionCatalog, user: { providers: { apihub: profile } }, keys: { APIHUB_API_KEY: 'synthetic-only' } })
  rt.state.bots.preset = { model: 'apihub/kimi-k2.6' }
  await Promise.all([rt.prepareProviderRoutes(), rt.prepareProviderRoutes(), rt.catalog()])
  assert.equal(writes.length, 1)
  assert.deepEqual(writes[0][1][0].value, { ...profile, models: profile.models.map(model => ({ ...model, input: ['text', 'image'] })) })
  assert.equal(store.APIHUB_API_KEY, 'synthetic-only')
  assert.equal(rt.state.bots.preset.model, 'apihub/kimi-k2.6')
  await rt.providersView()
  assert.equal(writes.length, 1)
  assert.deepEqual((await rt.catalog()).filter(model => model.provider === 'apihub').map(model => model.input), visionIds.map(() => ['text', 'image']))
})

test('APIHub never overwrites explicit modalities or fills conflicting and inexact catalog IDs', async () => {
  const models = [{ id: 'unknown' }, { id: 'Kimi-k2.6' }, { id: 'prefix/kimi-k2.6' },
    { id: 'kimi-k2.6', input: ['text'] }, { id: 'minimax-m3', inputModalities: ['text'] }, { id: 'conflict' }]
  const catalog = { ...visionCatalog, one: [{ id: 'conflict', inputModalities: ['text'] }], two: [{ id: 'conflict', inputModalities: ['text', 'image'] }] }
  const { rt, writes } = dsh({ catalog, user: { providers: { apihub: apiHubRoute(models) } } })
  await rt.prepareProviderRoutes()
  assert.deepEqual(writes, [])
})

test('APIHub migration ignores other endpoints, protocols, routes and adapters', async () => {
  for (const change of [{ baseURL: 'https://custom.invalid/v1' }, { api: 'anthropic-messages' }]) {
    const { rt, writes } = dsh({ catalog: visionCatalog, user: { providers: { apihub: { ...apiHubRoute(['kimi-k2.6']), ...change } } } })
    await rt.prepareProviderRoutes()
    assert.deepEqual(writes, [])
  }
  const { rt, writes } = dsh({ catalog: visionCatalog, user: { providers: { relay: apiHubRoute(['kimi-k2.6']) } } })
  await rt.prepareProviderRoutes()
  assert.deepEqual(writes, [])
})

test('APIHub discovery exposes filled input modalities; generic discovery remains unchanged', async () => {
  const { rt } = dsh({ catalog: { native: [{ id: 'relay-2', inputModalities: ['text', 'image'] }] } })
  const candidates = await rt.discoverModels({ preset: 'apihub', key: 'synthetic-only' })
  assert.deepEqual(candidates.map(model => model.inputModalities), [['text'], ['text', 'image']])
  const generic = await rt.discoverModels({ baseURL: 'https://custom.invalid/v1' })
  assert.equal(generic[1].inputModalities, undefined)
})

test('APIHub migration does not overwrite an editor save made during discovery', async () => {
  const { rt, writes } = dsh({ catalog: visionCatalog, user: { providers: { apihub: apiHubRoute(['kimi-k2.6']) } } })
  const discover = rt.ctx.llm.discoverModels
  rt.ctx.llm.discoverModels = async (...args) => {
    await rt.ctx.get('settings').mutate('llm-pi-ai', [{ op: 'set', path: ['providers', 'apihub'], value: apiHubRoute(['editor-chosen']) }], 0)
    return discover(...args)
  }
  await rt.prepareProviderRoutes()
  assert.equal(writes.length, 1)
  assert.deepEqual(writes[0][1][0].value.models, ['editor-chosen'])
})

test('APIHub repair needs no credential reads and tolerates an unavailable native catalog', async () => {
  const { rt, writes, listeners } = dsh({ catalog: visionCatalog, user: { providers: { apihub: apiHubRoute(['kimi-k2.6']) } } })
  rt.ctx.get('credentials').resolve = async () => { throw new Error('must not read credentials') }
  const discover = rt.ctx.llm.discoverModels
  rt.ctx.llm.discoverModels = async () => { throw new Error('catalog unavailable') }
  await rt.prepareProviderRoutes()
  assert.deepEqual(writes, [])
  rt.ctx.llm.discoverModels = discover
  listeners.get('llm/adapters-updated')()
  await rt.prepareProviderRoutes()
  assert.equal(writes.length, 1)
})

test('the official DSH catalog repairs supported APIHub IDs and sends durable images', async t => {
  const { apply, Config } = await import('@deepseek-ai/dsh-llm-pi-ai')
  let directory, discover
  const image = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==', 'base64')
  const adapterFor = profile => {
    let adapter
    apply({
      fiber: { entry: { options: { id: 'llm-pi-ai' } } }, inject() {}, on() {},
      get: name => name === 'credentials' ? { resolve: async () => ({ value: 'synthetic-only' }) }
        : name === 'attachments' ? { imageHostPath: () => undefined, readImageRequest: async () => ({ data: image, bytes: image.length, width: 1, height: 1, mediaType: 'image/png' }) } : undefined,
      llm: {
        registerConfigurableProviders: entries => { directory = entries; return { replace() {} } },
        registerModelDiscovery: (_ns, callback) => { discover = callback },
        registerAdapter: (_providers, value) => { adapter = value; return { replace() {} } },
      },
    }, Config({ providers: { apihub: profile } }))
    return adapter
  }
  const seen = []
  t.mock.method(globalThis, 'fetch', async (input, init) => {
    const request = new Request(input, init)
    assert.equal(request.url, `${APIHUB.baseURL}/chat/completions`)
    const body = await request.json()
    assert.ok(body.messages.some(message => Array.isArray(message.content) && message.content.some(block => block.type === 'image_url' && block.image_url.url === `data:image/png;base64,${image.toString('base64')}`)))
    seen.push(body.model)
    return new Response(`data: ${JSON.stringify({ id: 'synthetic', choices: [{ index: 0, delta: { role: 'assistant', content: 'red' }, finish_reason: null }] })}\n\ndata: ${JSON.stringify({ id: 'synthetic', choices: [{ index: 0, delta: {}, finish_reason: 'stop' }] })}\n\ndata: [DONE]\n\n`, { headers: { 'content-type': 'text/event-stream' } })
  })
  const profile = apiHubRoute(visionIds.map(id => ({ id })))
  const before = adapterFor(profile)
  assert.deepEqual((await before.resolveModel('apihub', 'kimi-k2.6')).inputModalities, ['text'])
  const catalog = await Promise.all(directory.filter(entry => entry.declared === false).map(entry => discover({ provider: entry.provider })))
  const known = new Set(catalog.flat().filter(model => model.inputModalities?.includes('image')).map(model => model.id))
  const { rt, writes } = dsh({ user: { providers: { apihub: profile } } })
  const fixtureDirectory = rt.ctx.llm.listConfigurableProviders()
  rt.ctx.llm.listConfigurableProviders = () => [...directory.filter(entry => entry.declared === false), ...fixtureDirectory.filter(entry => entry.declared !== false)]
  rt.ctx.llm.discoverModels = (_ns, request) => discover(request)
  await rt.prepareProviderRoutes()
  const fixed = adapterFor(writes[0][1][0].value)
  for (const id of visionIds) {
    if (!known.has(id)) {
      assert.deepEqual((await fixed.resolveModel('apihub', id)).inputModalities, ['text'])
      t.diagnostic(`Installed official catalog has no image declaration for ${id}; leave it unchanged`)
      continue
    }
    assert.deepEqual((await fixed.resolveModel('apihub', id)).inputModalities, ['text', 'image'])
    const chunks = []
    for await (const chunk of fixed.stream({ provider: 'apihub', model: id, sessionId: 'synthetic-session', messages: [{ role: 'user', source: { kind: 'user' }, content: [
      { type: 'text', text: 'Which color?' }, { type: 'image', attachment: { attachmentId: 'sha256:synthetic', width: 1, height: 1, mediaType: 'image/png', bytes: image.length } },
    ] }] })) chunks.push(chunk)
    assert.ok(chunks.some(chunk => chunk.type === 'text-delta' && chunk.text === 'red'), JSON.stringify(chunks))
    assert.ok(chunks.some(chunk => chunk.type === 'finish' && chunk.reason.kind === 'stop'), JSON.stringify(chunks))
  }
  assert.ok(seen.length > 0)
  assert.deepEqual(seen, visionIds.filter(id => known.has(id)))
})

test('built-in APIHub uses the verified endpoint, stores credentials separately and ranks first', async () => {
  const { rt, store, discovered } = dsh()
  const { APIHUB } = await import('../src/shared/model-providers.js')
  assert.equal(APIHUB.baseURL, 'https://apihub.chem-cloud.cn/v1')
  assert.equal(APIHUB.tokenUrl, 'https://apihub.chem-cloud.cn/keys')
  assert.equal(APIHUB.portalUrl, 'https://apihub.chem-cloud.cn/')
  await rt.discoverModels({ preset: 'apihub', baseURL: 'https://wrong.invalid', key: 'synthetic-apihub-test' })
  assert.equal(discovered[0][1].baseURL, 'https://apihub.chem-cloud.cn/v1')
  const view = await rt.addProvider({ preset: 'apihub', key: 'synthetic-apihub-test', models: [{ id: 'test-model' }] })
  assert.equal(view.providers[0].id, 'apihub')
  assert.equal(store.APIHUB_API_KEY, 'synthetic-apihub-test')
  assert.ok(!JSON.stringify(view).includes('synthetic-apihub-test'))
  await rt.discoverModels({ preset: 'apihub' })
  assert.equal(discovered.at(-1)[1].apiKey, 'synthetic-apihub-test')
  assert.equal((await rt.catalog({ fresh: true }))[0].provider, 'apihub')
})

test('OpenCode Go keeps the official catalog provider and its session headers', async () => {
  const { rt, store, writes, discovered } = dsh({ catalog: { 'opencode-go': ['deepseek-v4.1-flash', 'glm-5.3-flash'] } })
  const { OPENCODE_GO } = await import('../src/shared/model-providers.js')
  assert.equal(OPENCODE_GO.id, 'opencode-go')
  assert.equal(OPENCODE_GO.baseURL, 'https://opencode.ai/zen/go/v1')
  assert.equal(OPENCODE_GO.apiKeyEnv, 'OPENCODE_API_KEY')
  const before = await rt.providersView()
  assert.deepEqual(before.addable.find(entry => entry.id === OPENCODE_GO.id), { id: 'opencode-go', name: 'opencode-go' })
  const view = await rt.addProvider({ provider: OPENCODE_GO.id, key: 'synthetic-opencode-go' })
  assert.deepEqual(discovered, [])
  assert.deepEqual(writes[0], ['llm-pi-ai', [{ op: 'set', path: ['providers', 'opencode-go'], value: {
    displayName: 'opencode-go', apiKeyEnv: 'OPENCODE_API_KEY',
  } }]])
  assert.equal(store.OPENCODE_API_KEY, 'synthetic-opencode-go')
  assert.equal(row(view, 'opencode-go').models.length, 2)
  assert.equal(view.addable.some(entry => entry.id === 'opencode-go'), false)
  await assert.rejects(rt.addProvider({ provider: 'opencode-go', key: 'again' }), /already set up/)
})

test('OpenCode Go requires DSH native support instead of creating a generic route', async () => {
  const { rt, writes } = dsh()
  await assert.rejects(rt.addProvider({ provider: 'opencode-go', key: 'synthetic-key' }), /Update DSH/)
  assert.deepEqual(writes, [])
})

const legacyGo = {
  displayName: 'opencode-go', api: 'openai-completions', baseURL: 'https://opencode.ai/zen/go/v1',
  apiKeyEnv: 'OPENCODE_API_KEY', models: [{ id: 'deepseek-v4.1-flash' }],
}

test('existing Go presets restore native routing before a request without changing keys or Bot selections', async () => {
  const profile = { ...legacyGo, headers: { 'x-deployment': 'test' }, cacheRetention: 'long' }
  const { rt, writes, store, listeners } = dsh({
    user: { providers: { 'opencode-go': profile } }, keys: { OPENCODE_API_KEY: 'synthetic-existing' },
    catalog: { 'opencode-go': ['deepseek-v4.1-flash'] },
  })
  rt.state.bots.preset = { id: 'preset', model: 'opencode-go/deepseek-v4.1-flash' }
  const config = await listeners.get('agent/request')({ agent: { id: 'preset' }, signal: new AbortController().signal }, async () => {
    assert.equal(writes.length, 1)
    return { provider: 'opencode-go', model: 'deepseek-v4.1-flash' }
  })
  assert.equal(config.provider, 'opencode-go')
  assert.equal(rt.state.bots.preset.model, 'opencode-go/deepseek-v4.1-flash')
  assert.deepEqual(writes, [['llm-pi-ai', [{ op: 'set', path: ['providers', 'opencode-go'], value: {
    displayName: 'opencode-go', apiKeyEnv: 'OPENCODE_API_KEY', headers: profile.headers, cacheRetention: 'long',
  } }]]])
  assert.deepEqual(store, { OPENCODE_API_KEY: 'synthetic-existing' })
  await Promise.all([rt.providersView(), rt.prepareProviderRoutes(), rt.catalog({ fresh: true })])
  assert.equal(writes.length, 1)
})

test('concurrent first requests share the Go migration', async () => {
  const { rt, writes } = dsh({ user: { providers: { 'opencode-go': legacyGo } }, catalog: { 'opencode-go': ['deepseek-v4.1-flash'] } })
  await Promise.all([rt.prepareProviderRoutes(), rt.prepareProviderRoutes(), rt.prepareProviderRoutes()])
  assert.equal(writes.length, 1)
})

test('a selected Go model missing from the native catalog stops migration instead of switching provider', async () => {
  const { rt, writes } = dsh({ user: { providers: { 'opencode-go': legacyGo } }, catalog: { 'opencode-go': ['deepseek-v4.1-flash'] } })
  rt.state.bots.preset = { model: 'opencode-go/new-model' }
  await assert.rejects(rt.prepareProviderRoutes(), /Update DSH.*new-model/)
  assert.deepEqual(writes, [])
  assert.equal(rt.state.bots.preset.model, 'opencode-go/new-model')
})

test('Go migration leaves custom endpoints and intentional protocol settings alone', async () => {
  for (const profile of [
    { ...legacyGo, baseURL: 'https://relay.example/v1' },
    { ...legacyGo, displayName: 'Custom Go' },
    { ...legacyGo, api: 'anthropic-messages' },
    { apiKeyEnv: 'OPENCODE_API_KEY' },
  ]) {
    const { rt, writes } = dsh({ user: { providers: { 'opencode-go': profile } }, catalog: { 'opencode-go': ['deepseek-v4.1-flash'] } })
    await rt.prepareProviderRoutes()
    assert.deepEqual(writes, [])
  }
  const { rt, writes } = dsh({ base: { providers: { 'opencode-go': legacyGo } }, catalog: { 'opencode-go': ['deepseek-v4.1-flash'] } })
  await rt.prepareProviderRoutes()
  assert.deepEqual(writes, [])
})

test('the official DSH adapter sends stable Go session headers after preset migration', async (t) => {
  const { apply, Config } = await import('@deepseek-ai/dsh-llm-pi-ai')
  const captured = []
  t.mock.method(globalThis, 'fetch', async (input, init) => {
    const request = new Request(input, init)
    assert.equal(new URL(request.url).hostname, 'opencode.ai')
    const body = await request.json()
    captured.push({ session: request.headers.get('x-opencode-session'), model: body.model })
    if (!request.headers.has('x-opencode-session')) return Response.json({ type: 'MissingSessionID', message: 'Missing conversation header' }, { status: 400 })
    if (new URL(request.url).pathname.endsWith('/messages')) {
      const events = [
        { type: 'message_start', message: { id: 'synthetic-message', type: 'message', role: 'assistant', model: body.model, content: [], usage: { input_tokens: 5, output_tokens: 0 } } },
        { type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } },
        { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'OK' } },
        { type: 'content_block_stop', index: 0 },
        { type: 'message_delta', delta: { stop_reason: 'end_turn', stop_sequence: null }, usage: { output_tokens: 1 } },
        { type: 'message_stop' },
      ]
      return new Response(events.map(event => `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`).join(''), { headers: { 'content-type': 'text/event-stream' } })
    }
    const chunks = [
      { id: 'synthetic-chat', choices: [{ index: 0, delta: { role: 'assistant', content: 'OK' }, finish_reason: null }] },
      { id: 'synthetic-chat', choices: [{ index: 0, delta: {}, finish_reason: 'stop' }], usage: { prompt_tokens: 5, completion_tokens: 1, total_tokens: 6 } },
    ]
    return new Response(chunks.map(chunk => `data: ${JSON.stringify(chunk)}\n\n`).join('') + 'data: [DONE]\n\n', { headers: { 'content-type': 'text/event-stream' } })
  })
  const adapterFor = (profile) => {
    let adapter
    apply({
      fiber: { entry: { options: { id: 'llm-pi-ai' } } },
      inject() {}, on() {},
      get: name => name === 'credentials' ? { resolve: async () => ({ value: 'synthetic-only' }) } : undefined,
      llm: {
        registerConfigurableProviders: () => ({ replace() {} }), registerModelDiscovery() {},
        registerAdapter: (_providers, value) => { adapter = value; return { replace() {} } },
      },
    }, Config({ providers: { 'opencode-go': profile } }))
    return adapter
  }
  const request = (sessionId, model = 'deepseek-v4.1-flash') => ({ provider: 'opencode-go', model, sessionId,
    messages: [{ role: 'user', source: { kind: 'user' }, content: [{ type: 'text', text: 'Reply OK' }] }] })
  const consume = async (adapter, session, model) => {
    const chunks = []
    for await (const chunk of adapter.stream(request(session, model))) chunks.push(chunk)
    return chunks
  }
  const first = 'session-11111111-1111-4111-8111-111111111111'
  const second = 'session-22222222-2222-4222-8222-222222222222'
  const old = await consume(adapterFor(legacyGo), first)
  if (captured[0].session === null) {
    assert.ok(old.some(chunk => chunk.type === 'finish' && chunk.reason.kind === 'error'))
    t.diagnostic('Legacy generic route reproduced MissingSessionID with this official Pi version')
  } else {
    assert.equal(captured[0].session, first)
    t.diagnostic('This newer official Pi version also fixes the generic route')
  }
  const { rt, writes } = dsh({ user: { providers: { 'opencode-go': legacyGo } }, catalog: { 'opencode-go': ['deepseek-v4.1-flash'] } })
  await rt.prepareProviderRoutes()
  const fixed = adapterFor(writes[0][1][0].value)
  const results = await Promise.all([consume(fixed, first), consume(fixed, second)])
  results.push(await consume(fixed, first))
  results.push(await consume(fixed, second, 'claude-haiku-5-5'))
  for (const chunks of results) {
    assert.ok(chunks.some(chunk => chunk.type === 'text-delta' && chunk.text === 'OK'), JSON.stringify(chunks))
    assert.ok(chunks.some(chunk => chunk.type === 'finish' && chunk.reason.kind === 'stop'), JSON.stringify(chunks))
  }
  assert.deepEqual(captured.slice(1).map(item => item.session).sort(), [first, first, second, second].sort())
  assert.equal(captured.at(-1).model, 'claude-haiku-5-5')
})

test('models of a provider whose API key is set nowhere need the key', async () => {
  const user = { providers: { moonshotai: { apiKeyEnv: 'MOONSHOTAI_API_KEY' }, bedrock: {} } }
  const catalog = { moonshotai: ['kimi-k3'], bedrock: ['nova'] }
  assert.deepEqual(await needing(dsh({ user, catalog }).rt), ['deepseek-official', 'moonshotai'])
  assert.deepEqual(await needing(dsh({ user, catalog, keys: { DEEPSEEK_API_KEY: 'k' } }).rt), ['moonshotai'])
  // A route without a key reference authenticates some other way.
  assert.ok((await dsh({ user, catalog }).rt.catalog()).some(entry => entry.provider === 'bedrock' && !entry.needsKey))
})

test('without DSH settings or credentials no model needs a key, and there is no Models page', async () => {
  const { rt } = dsh()
  rt.ctx.get = () => undefined
  assert.deepEqual(await needing(rt), [])
  assert.deepEqual(await rt.providersView(), { available: false })
})

test('the page lists the providers set up and the ones DSH can add', async () => {
  const { rt } = dsh({ keys: { DEEPSEEK_API_KEY: 'k' }, user: { providers: { moonshotai: { apiKeyEnv: 'MOONSHOTAI_API_KEY' } } } })
  const view = await rt.providersView()
  assert.deepEqual(view.providers.map(provider => [provider.id, provider.key, provider.removable, provider.models.length]), [
    ['deepseek-official', { configured: true, writable: true }, false, 1],
    ['moonshotai', { configured: false, writable: true }, true, 1],
  ])
  // The account route has no key and no models before a sign-in.
  assert.equal(row(view, 'deepseek-account'), undefined)
  assert.deepEqual(view.addable, [{ id: 'anthropic', name: 'anthropic' }, { id: 'opencode-go', name: 'opencode-go' }])
  assert.deepEqual(view.protocols, ['openai-completions', 'openai-responses', 'anthropic-messages'])
})

test('a saved API key goes to the provider\'s reference and frees its models', async () => {
  const { rt, store, writes } = dsh()
  await rt.setProviderKey('deepseek-official', '  sk-test  ')
  assert.deepEqual(writes, [['set', 'DEEPSEEK_API_KEY']])
  assert.equal(store.DEEPSEEK_API_KEY, 'sk-test')
  assert.deepEqual(await needing(rt), [])
  await rt.clearProviderKey('deepseek-official')
  assert.equal('DEEPSEEK_API_KEY' in store, false)
  await assert.rejects(rt.setProviderKey('deepseek-account', 'sk-test'), /deepseek-account takes no API key here/)
})

test('a key set outside ChemClaw is not overwritten or removed', async () => {
  const { rt, writes } = dsh({ keys: { DEEPSEEK_API_KEY: 'k' }, readOnly: ['DEEPSEEK_API_KEY'] })
  await assert.rejects(rt.setProviderKey('deepseek-official', 'sk-test'), /set outside ChemClaw/)
  await assert.rejects(rt.clearProviderKey('deepseek-official'), /set outside ChemClaw/)
  assert.deepEqual(writes, [])
  assert.deepEqual(row(await rt.providersView(), 'deepseek-official').key, { configured: true, writable: false })
})

test('a provider from DSH\'s list goes in with the key DSH\'s own page would name', async () => {
  const { rt, store, writes } = dsh()
  const view = await rt.addProvider({ provider: 'moonshotai', key: 'sk-kimi' })
  assert.deepEqual(writes, [['llm-pi-ai', [{ op: 'set', path: ['providers', 'moonshotai'], value: { apiKeyEnv: 'MOONSHOTAI_API_KEY' } }]], ['set', 'MOONSHOTAI_API_KEY']])
  assert.equal(store.MOONSHOTAI_API_KEY, 'sk-kimi')
  assert.deepEqual(row(view, 'moonshotai').models.map(model => model.ref), ['moonshotai/kimi-k3'])
  assert.equal(view.addable.some(entry => entry.id === 'moonshotai'), false)
  await assert.rejects(rt.addProvider({ provider: 'moonshotai', key: 'sk-kimi' }), /moonshotai is already set up/)
  await assert.rejects(rt.addProvider({ provider: 'deepseek-official' }), /already set up/)
  await assert.rejects(rt.addProvider({ provider: 'nowhere' }), /DSH offers no provider nowhere/)
})

test('a blank key keeps a key that is already there, else leaves the route without one', async () => {
  const { rt, writes } = dsh({ keys: { ANTHROPIC_API_KEY: 'k' } })
  await rt.addProvider({ provider: 'anthropic', key: '' })
  await rt.addProvider({ provider: 'moonshotai' })
  assert.deepEqual(writes.map(([, ops]) => ops[0].value), [{ apiKeyEnv: 'ANTHROPIC_API_KEY' }, {}])
})

test('a custom API goes in with its endpoint, protocol and the models picked', async () => {
  const { rt, store, writes } = dsh()
  await rt.addProvider({
    custom: true, provider: 'relay', name: ' My relay ', api: 'openai-completions', baseURL: ' https://relay.example/v1 ', key: 'sk-relay',
    models: [{ id: 'relay-1', name: 'Relay One', contextWindow: 128000, inputModalities: ['text'] }, 'relay-2'],
  })
  assert.deepEqual(writes[0], ['llm-pi-ai', [{ op: 'set', path: ['providers', 'relay'], value: {
    displayName: 'My relay', api: 'openai-completions', baseURL: 'https://relay.example/v1', apiKeyEnv: 'RELAY_API_KEY',
    models: [{ id: 'relay-1', name: 'Relay One', contextWindow: 128000, input: ['text'] }, { id: 'relay-2' }],
  } }]])
  assert.equal(store.RELAY_API_KEY, 'sk-relay')
  const view = await rt.providersView()
  assert.deepEqual([row(view, 'relay').name, row(view, 'relay').custom, row(view, 'relay').removable], ['My relay', true, true])
})

test('a custom API is refused before anything is written when it cannot serve', async () => {
  const { rt, writes } = dsh()
  const custom = { custom: true, provider: 'relay', api: 'openai-completions', baseURL: 'https://relay.example/v1', models: ['m'] }
  await assert.rejects(rt.addProvider({ ...custom, provider: 'My Relay' }), /lowercase letters, digits and dashes/)
  await assert.rejects(rt.addProvider({ ...custom, provider: 'anthropic' }), /DSH already offers anthropic/)
  await assert.rejects(rt.addProvider({ ...custom, api: 'grpc' }), /protocol must be one of/)
  await assert.rejects(rt.addProvider({ ...custom, baseURL: 'relay.example' }), /http or https/)
  await assert.rejects(rt.addProvider({ ...custom, baseURL: 'ftp://relay.example' }), /http or https/)
  await assert.rejects(rt.addProvider({ ...custom, models: [] }), /at least one model/)
  await assert.rejects(rt.addProvider({ ...custom, models: ['m', ' m '] }), /same id/)
  await assert.rejects(rt.addProvider({ ...custom, key: 'KEY=sk' }), /NAME=value/)
  assert.deepEqual(writes, [])
})

test('fetching models asks DSH about the endpoint, with the typed key for that question only', async () => {
  const { rt, discovered, store } = dsh()
  const models = await rt.discoverModels({ baseURL: 'https://relay.example/v1', api: 'openai-completions', key: 'sk-relay' })
  assert.deepEqual(discovered, [['llm-pi-ai', { baseURL: 'https://relay.example/v1', api: 'openai-completions', apiKey: 'sk-relay' }]])
  assert.deepEqual(models, [{ id: 'relay-1', name: 'Relay One', contextWindow: 128000, inputModalities: ['text'] }, { id: 'relay-2' }])
  assert.deepEqual(store, {})
  // A provider DSH ships is answered from its own catalog.
  await rt.discoverModels({ provider: 'anthropic' })
  assert.deepEqual(discovered.at(-1), ['llm-pi-ai', { provider: 'anthropic' }])
})

test('removing a provider takes its key along unless another provider names it', async () => {
  const user = { providers: { moonshotai: { apiKeyEnv: 'MOONSHOTAI_API_KEY' }, kimi: { apiKeyEnv: 'MOONSHOTAI_API_KEY', api: 'openai-completions', baseURL: 'https://k.example/v1', models: [{ id: 'k' }] }, relay: { apiKeyEnv: 'RELAY_API_KEY', api: 'openai-completions', baseURL: 'https://r.example/v1', models: [{ id: 'r' }] } } }
  const { rt, store } = dsh({ user, keys: { MOONSHOTAI_API_KEY: 'a', RELAY_API_KEY: 'b' } })
  await rt.removeProvider('moonshotai')
  assert.equal(store.MOONSHOTAI_API_KEY, 'a')
  const view = await rt.removeProvider('relay')
  assert.equal('RELAY_API_KEY' in store, false)
  assert.deepEqual(view.providers.map(provider => provider.id), ['deepseek-official', 'kimi'])
  await assert.rejects(rt.removeProvider('relay'), /relay is not set up/)
  await assert.rejects(rt.removeProvider('deepseek-official'), /not set up/)
})

test('a route that comes with the setup stays', async () => {
  const { rt } = dsh({ base: { providers: { moonshotai: { apiKeyEnv: 'MOONSHOTAI_API_KEY' } } } })
  assert.equal(row(await rt.providersView(), 'moonshotai').removable, false)
  await assert.rejects(rt.removeProvider('moonshotai'), /comes with this setup/)
})

test('a changed credential drops the cached catalog', async () => {
  const { rt, store, listeners } = dsh()
  assert.deepEqual(await needing(rt), ['deepseek-official'])
  store.DEEPSEEK_API_KEY = 'k'
  assert.deepEqual((await rt.catalog()).filter(entry => entry.needsKey).map(entry => entry.provider), ['deepseek-official'])
  listeners.get('credentials/reference-updated')()
  assert.deepEqual((await rt.catalog()).filter(entry => entry.needsKey).map(entry => entry.provider), [])
})

test('an API key is what an HTTP header carries, without a NAME= or quotes', () => {
  assert.equal(checkKey(' sk-abc '), 'sk-abc')
  assert.equal(checkKey('YWJj=='), 'YWJj==')
  assert.throws(() => checkKey('   '), /Enter the API key/)
  assert.throws(() => checkKey(undefined), /Enter the API key/)
  assert.throws(() => checkKey('DEEPSEEK_API_KEY=sk-abc'), /not a NAME=value line/)
  assert.throws(() => checkKey('"sk-abc"'), /without quotes/)
  assert.throws(() => checkKey('sk abc'), /no spaces/)
  assert.throws(() => checkKey('sk-密钥'), /no spaces/)
})

test('a route\'s key reference follows DSH\'s own Models page', () => {
  assert.equal(keyRefFor('moonshotai'), 'MOONSHOTAI_API_KEY')
  assert.equal(keyRefFor('my-gateway2'), 'MY_GATEWAY2_API_KEY')
})


test('first APIHub private and group requests skip the unkeyed profile default without warming idle presets', async () => {
  const { rt, listeners } = dsh()
  assert.equal(await rt.defaultModel(), undefined)
  rt.state.bots.preset = { id: 'preset', templateId: 'chemical-main' }
  rt.state.bots.idle = { id: 'idle', templateId: 'chemical-specialist' }
  await rt.addProvider({ preset: 'apihub', key: 'synthetic-first-run', models: [{ id: 'ready-model' }] })
  assert.equal(await rt.defaultModel(), 'apihub/ready-model')
  assert.equal(rt.cachedDefault(), 'apihub/ready-model')
  const request = listeners.get('agent/request')
  const initial = { provider: 'deepseek-official', model: 'deepseek-flash', reasoningEffort: 'unsupported', temperature: 0.4 }
  for (const id of ['preset', 'group-member']) {
    const selected = await request({ agent: { id }, signal: new AbortController().signal }, async () => initial)
    assert.deepEqual(selected, { provider: 'apihub', model: 'ready-model', temperature: 0.4 })
  }
  assert.equal(rt.state.bots.preset.appliedModel, 'apihub/ready-model')
  assert.equal(rt.state.bots.idle.appliedModel, undefined)
  assert.equal(rt.state.bots.preset.model, undefined)
  const other = await request({ agent: { id: 'unrelated' }, signal: new AbortController().signal }, async () => initial)
  assert.equal(other, initial)
})

test('usable explicit choices survive APIHub setup; missing-key legacy choices fall back and recover when keyed', async () => {
  const { rt } = dsh({ keys: { DEEPSEEK_API_KEY: 'synthetic-official' } })
  await rt.addProvider({ preset: 'apihub', key: 'synthetic-hub', models: [{ id: 'hub-model' }] })
  const bot = { model: 'deepseek-official/deepseek-flash' }
  assert.equal(await rt.desiredModel(bot), bot.model)
  assert.equal(await rt.defaultModel(), bot.model)
  await rt.clearProviderKey('deepseek-official')
  assert.equal(await rt.defaultModel(), 'apihub/hub-model')
  assert.equal(await rt.desiredModel(bot), 'apihub/hub-model')
  await rt.setProviderKey('deepseek-official', 'synthetic-restored')
  assert.equal(await rt.desiredModel(bot), bot.model)
})

test('unconfigured presets fail before an official request with an actionable setup message', async () => {
  const { rt, listeners } = dsh()
  rt.state.bots.preset = { id: 'preset', templateId: 'chemical-main' }
  await assert.rejects(listeners.get('agent/request')({ agent: { id: 'preset' }, signal: new AbortController().signal }, async () => ({ provider: 'deepseek-official', model: 'deepseek-flash' })), /No configured model.*Settings > Models/)
})
