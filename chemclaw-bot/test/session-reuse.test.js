import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install } from '../src/host/session-reuse.js'

test('desktop native create strips only team reuse hints after loading ownership', async () => {
  const app = process.env.DS_BOT_APP
  process.env.DS_BOT_APP = '1'
  let route
  let loaded = false
  const calls = []
  const peer = { principal: { kind: 'owner' } }
  const ctx = {
    inject: (_names, callback) => callback(ctx),
    effect: callback => callback(),
    connection: { browserPeer: peer, fetch: { register: value => { route = value } } },
    typertGateway: {
      invoke: async call => {
        calls.push(call)
        return { sessionId: call.args.request.sessionId ?? 'new-native-session' }
      },
    },
  }
  try {
    install({
      ctx,
      load: async () => { loaded = true },
      blocksSessionReuse: (id) => {
        assert.equal(loaded, true)
        return id === 'team-session'
      },
    })
  } finally {
    if (app === undefined) delete process.env.DS_BOT_APP
    else process.env.DS_BOT_APP = app
  }
  assert.equal(route.path, '/api/session/create')
  const create = async sessionId => {
    loaded = false
    const request = new Request(`http://localhost${route.path}`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        type: 'client-request', rpcId: 'test-create', method: 'session/create',
        payload: { args: { request: { sessionId, workspaceId: 'workspace', agentPreset: 'standard' } } },
      }),
    })
    const response = await route.fetch(request)
    const body = await response.json()
    assert.equal(body.type, 'server-response')
    assert.equal(body.rpcId, 'test-create')
    assert.equal(body.result.ok, true)
    return body.result.value.sessionId
  }
  assert.equal(await create('team-session'), 'new-native-session')
  assert.equal(await create('ordinary-blank'), 'ordinary-blank')
  assert.equal(await create(undefined), 'new-native-session')
  assert.deepEqual(calls.map(call => call.args.request), [
    { workspaceId: 'workspace', agentPreset: 'standard' },
    { workspaceId: 'workspace', agentPreset: 'standard', sessionId: 'ordinary-blank' },
    { workspaceId: 'workspace', agentPreset: 'standard' },
  ])
  assert.ok(calls.every(call => call.namespace === 'session' && call.method === 'create' && call.peer === peer))
})
