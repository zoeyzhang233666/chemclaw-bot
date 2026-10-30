import assert from 'node:assert/strict'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { runInNewContext } from 'node:vm'
import { build } from 'esbuild'

// Render the actual slot component with DSH's injected selectors, without a DOM.
const bundle = await build({
  entryPoints: [fileURLToPath(new URL('../src/client/team-intro.js', import.meta.url))],
  bundle: true, format: 'cjs', platform: 'node', write: false, external: ['react'],
})
const module = { exports: {} }
runInNewContext(bundle.outputFiles[0].text, {
  module, exports: module.exports,
  require: name => {
    if (name !== 'react') throw new Error(`Unexpected module ${name}`)
    return { createElement: (type, props, ...children) => ({ type, props, children }) }
  },
})
const { TeamIntro } = module.exports

const templateInfo = { description: 'Capabilities', examples: ['Example'], deliverables: 'Report' }
const bot = (patch = {}) => ({ id: 'bot', sessionId: 'chat', name: 'ChemClaw', templateInfo, parts: [], ...patch })
const room = (patch = {}) => ({ id: 'chat', name: 'Research team', templateInfo, parts: ['member-session'], ...patch })
const sessionList = (session = { blank: true }, outline) => ({
  byId: session ? { chat: session } : {},
  ...(outline === undefined ? {} : { projectionsBySession: { chat: { values: { turnOutline: outline } } } }),
})
const render = ({ item = bot(), list = sessionList(), isRoom = false, running = false } = {}) => {
  const roster = {
    bots: isRoom ? [] : [item],
    roomsById: isRoom ? { chat: item } : {},
    mainBotId: 'bot',
    rooms: [],
  }
  return TeamIntro({
    sessionId: 'chat',
    useRoster: select => select(roster),
    useSessions: select => select(list),
    useSessionStatus: select => select(new Map([['chat', { running }]])),
    actions: { openSettings() {}, openSession() {} },
  })
}

test('intro appears in a truly blank Bot or group conversation', () => {
  assert.equal(render()?.type, 'section')
  assert.equal(render({ item: room(), isRoom: true })?.type, 'section')
})

test('unknown session state does not falsely count as a blank conversation', () => {
  assert.equal(render({ list: sessionList(null) }), null)
  assert.equal(render({ list: sessionList({}) }), null)
})

test('first user turn and existing history hide the intro, even if the preview has no text', () => {
  assert.equal(render({ list: sessionList({ blank: false }) }), null)
  assert.equal(render({ list: sessionList({ blank: true }, [{ turn: 1, prompt: '', response: '' }]) }), null)
  assert.equal(render({ list: sessionList({ blank: true, projectionValues: { turnOutline: [{ turn: 1 }] } }) }), null)
  assert.equal(render({ item: room({ preview: 'User asked a question' }), isRoom: true }), null)
})

test('running Bot hides the intro before a text response or outline is ready', () => {
  assert.equal(render({ running: true }), null)
  assert.equal(render({ item: room(), isRoom: true, running: true }), null)
})

test('a fresh Bot part after context handoff does not redisplay the intro', () => {
  assert.equal(render({ item: bot({ parts: ['prior-session'] }) }), null)
  // Group parts track member work, not earlier messages in the group chat.
  assert.equal(render({ item: room(), isRoom: true })?.type, 'section')
})

test('missing template description or a persisted preview cannot render an intro', () => {
  assert.equal(render({ item: bot({ templateInfo: undefined }) }), null)
  assert.equal(render({ item: bot({ preview: 'old reply' }) }), null)
})
