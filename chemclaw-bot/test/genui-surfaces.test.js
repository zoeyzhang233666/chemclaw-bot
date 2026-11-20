import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { createGenuiSurfaces, assistantTextBlocks } from '../src/client/genui-surfaces.js'
import { GENUI_GRAPH_POLICY, VIEW_POLICY } from '../src/host/view-policy.js'

const root = source => ({ isConnected: true, getAttribute: () => source })
const surface = (threadId, sendPrompt = async () => {}) => ({
  root: root('chemclaw-bot/assistant'), source: 'chemclaw-bot/assistant', threadId,
  eventSeq: 42, contentBlockIndex: 3, text: '```dsh-ui\n{}\n```', sendPrompt,
})

test('GenUI arrives before or after messages and routes identical specs to their owners', async () => {
  const service = createGenuiSurfaces()
  const sent = []
  const first = surface('a', async text => { sent.push(['a', text]) })
  const dropFirst = service.add(first)
  const mounted = []
  const released = []
  const adapter = { id: 'dsh-genui', mount: entry => { mounted.push(entry); return () => released.push(entry.threadId) } }
  const unload = service.registerSidechatSurfaceAdapter(adapter)
  const dropSecond = service.add(surface('b', async text => { sent.push(['b', text]) }))
  await mounted[0].sendPrompt('one')
  await mounted[1].sendPrompt('two')
  assert.deepEqual(sent, [['a', 'one'], ['b', 'two']])
  assert.equal(mounted[0].eventSeq, 42)
  assert.equal(mounted[0].contentBlockIndex, 3)
  dropFirst()
  await assert.rejects(mounted[0].sendPrompt('stale'), /no longer active/)
  unload()
  await assert.rejects(mounted[1].sendPrompt('stale'), /no longer active/)
  const reload = service.registerSidechatSurfaceAdapter(adapter)
  assert.equal(mounted.length, 3)
  await mounted[2].sendPrompt('three')
  unload()
  await mounted[2].sendPrompt('still active')
  dropSecond(); reload(); service.dispose()
  assert.deepEqual(released, ['a', 'b', 'b'])
})

test('GenUI refuses invented identities and gates detached, changed or disposed roots', async () => {
  const service = createGenuiSurfaces()
  const mounted = []
  service.registerSidechatSurfaceAdapter({ id: 'dsh-genui', mount: item => { mounted.push(item); return () => {} } })
  for (const patch of [{ eventSeq: undefined }, { eventSeq: 2.5 }, { eventSeq: -1 }, { contentBlockIndex: -1 }, { threadId: '' }]) service.add({ ...surface('a'), ...patch })
  assert.equal(mounted.length, 0)
  const item = surface('a')
  service.add(item)
  item.root.isConnected = false
  await assert.rejects(mounted[0].sendPrompt('no'), /no longer active/)
  item.root.isConnected = true
  item.root.getAttribute = () => 'another-provider'
  await assert.rejects(mounted[0].sendPrompt('no'), /no longer active/)
  service.dispose()
  await assert.rejects(mounted[0].sendPrompt('no'), /no longer active/)
})

test('GenUI delivery failures are reported and remain rejected', async () => {
  const errors = []
  const service = createGenuiSurfaces(error => errors.push(error.message))
  let mounted
  service.registerSidechatSurfaceAdapter({ id: 'dsh-genui', mount: item => { mounted = item; return () => {} } })
  service.add(surface('group', async () => { throw new Error('room gone') }))
  await assert.rejects(mounted.sendPrompt('send'), /room gone/)
  assert.deepEqual(errors, ['room gone'])
  service.dispose()
})

test('original text block indices survive empty, image and reasoning blocks', () => {
  assert.deepEqual(assistantTextBlocks([{ kind: 'text', text: '' }, { kind: 'image' }, { kind: 'reasoning', text: 'hidden' }, { kind: 'text', text: 'same' }, { kind: 'text', text: 'same' }]), [{ text: 'same', contentBlockIndex: 3 }, { text: 'same', contentBlockIndex: 4 }])
})

test('diagram connector elbows stay within the correct segments when turning up or left', async () => {
  const { roundDiagramConnector } = await import('../src/client/genui-diagram-layout.js')
  assert.equal(roundDiagramConnector('M 40 20 H 28 Q 20 20 20 28 V -8 Q 20 0 28 0 H 0'),
    'M 40 20 L 28 20 Q 20 20 20 12 L 20 8 Q 20 0 12 0 L 0 0')
  assert.equal(roundDiagramConnector('M 40 20 V 38 Q 40 30 48 30 H 28 Q 36 30 36 38 V 40'),
    'M 40 20 L 40 28 Q 40 30 38 30 L 38 30 Q 36 30 36 32 L 36 40')
  assert.equal(roundDiagramConnector('M 40 20 L 40 40'), 'M 40 20 L 40 40')
})

test('current policy and delivery skill teach automatic GenUI selection and protocol separation', () => {
  const skill = readFileSync(new URL('../skills/builtin/delivery/SKILL.md', import.meta.url), 'utf8')
  for (const text of [skill, `${VIEW_POLICY}\n${GENUI_GRAPH_POLICY}`]) {
    for (const component of ['timeline', 'svg', 'diagram', 'plot', 'scene3d']) assert.ok(text.includes(component), component)
    assert.match(text, /Use Mermaid only/)
    assert.ok(text.includes('panel:true'))
    assert.match(text, /same (?:data|relationship)/)
  }
  const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url)))
  assert.equal(pkg.dependencies['@changfenhuang/dsh-genui'], '0.16.0')
})
