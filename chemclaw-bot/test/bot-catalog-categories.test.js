import assert from 'node:assert/strict'
import { test } from 'node:test'
import { build } from 'esbuild'
import { runInNewContext } from 'node:vm'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
const { outputFiles } = await build({
  stdin: { contents: "export { BotCatalog } from './src/client/bot-catalog.js'", resolveDir: dirname(dirname(fileURLToPath(import.meta.url))) },
  bundle: true, write: false, format: 'cjs', platform: 'node', external: ['react', 'react-dom', '@deepseek-ai/dsh-client-ui-primitives'], logLevel: 'silent',
})
const module = { exports: {} }
let stateIndex = 0
let selected = ''
runInNewContext(outputFiles[0].text, {
  module, exports: module.exports, require: name => name === 'react' ? {
    createElement: (type, props, ...children) => ({ type, props: props ?? {}, children: children.flat(Infinity) }),
    useState: initial => [stateIndex++ === 0 ? selected : initial, () => {}],
  } : {},
})
const { BotCatalog } = module.exports
const flatten = node => node && typeof node === 'object' ? [node, ...(node.children ?? []).flatMap(flatten)] : []
for (const kind of ['bot', 'room']) test(`${kind} catalog shares renamed, empty and reassigned sidebar categories`, () => {
  const category = { id: 'custom:empty', kind, name: 'New empty category' }
  const item = { id: 'item', name: 'Item', role: 'Old role', members: [], templateInfo: { category: 'Old template' } }
  const roster = { bots: kind === 'bot' ? [item] : [], rooms: kind === 'room' ? [item] : [], prefs: { sidebar: {
    categories: [category, { id: 'custom:moved', kind, name: 'Renamed category' }],
    categoryAssignments: { [`${kind}:item`]: 'custom:moved' },
  } } }
  stateIndex = 0
  selected = ''
  let nodes = flatten(BotCatalog({ roster, actions: {}, kind: kind === 'room' ? 'group' : 'role' }))
  const labels = nodes.filter(node => node.type === 'button').map(node => node.children[0])
  assert.ok(labels.includes('New empty category'))
  assert.ok(labels.includes('Renamed category'))
  assert.ok(!labels.includes('Old template'))
  assert.equal(nodes.filter(node => node.type === 'article').length, 1)
  stateIndex = 0
  selected = category.id
  nodes = flatten(BotCatalog({ roster, actions: {}, kind: kind === 'room' ? 'group' : 'role' }))
  assert.equal(nodes.filter(node => node.type === 'article').length, 0)
})
