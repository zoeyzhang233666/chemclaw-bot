import assert from 'node:assert/strict'
import { test } from 'node:test'
import { fakeContext } from './fake-ctx.js'
import { install } from '../src/host/tools.js'

function harness() {
  const ctx = fakeContext()
  const shown = []
  const rt = {
    ctx, state: { exchangeTurns: {}, views: {} },
    chatOwners: new Map(), groupOwners: new Map(), live: new Map(),
    load: async () => {}, roomOf: () => undefined,
    noteVisualDelivery: (id, view) => shown.push({ id, view }),
  }
  install(rt)
  return { tool: ctx.registeredTools.get('show_view'), rt, shown }
}
const display = { title: 'Price', view: { type: 'metric', label: 'Price', value: 100 } }
const root = (id = 'classic') => ({ agent: { id, session: { id, header: {} } }, callId: 'call1' })

test('native independent root accepts the original display card without adopting a Bot session', async () => {
  const { tool, rt, shown } = harness()
  assert.equal(await tool.execute(display, root()), 'The view is on screen.')
  assert.deepEqual(shown, [{ id: 'classic', view: display.view }])
  assert.equal(rt.chatOwners.has('classic'), false)
  assert.equal(rt.state.views.classic, undefined)
})

test('native interactive submissions cannot create an orphaned Bot reply card', async () => {
  const { tool, shown } = harness()
  const result = await tool.execute({ title: 'Confirm', view: { type: 'confirm', id: 'approve' } }, root())
  assert.match(result, /cannot submit responses/)
  assert.equal(shown.length, 0)
})

test('non-root DSH Agents do not acquire the native display privilege', async () => {
  const { tool, shown } = harness()
  const child = root('child')
  child.agent.session.header.parentSession = 'parent'
  const result = await tool.execute(display, child)
  assert.match(result, /Only Bots/)
  assert.equal(shown.length, 0)
})

test('the original Bot view is unchanged', async () => {
  const { tool, rt, shown } = harness()
  rt.chatOwners.set('bot', 'bot')
  assert.equal(await tool.execute(display, root('bot')), 'The view is on screen.')
  assert.deepEqual(shown.map(x => x.id), ['bot'])
})
