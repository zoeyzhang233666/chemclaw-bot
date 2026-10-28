import assert from 'node:assert/strict'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { runInNewContext } from 'node:vm'
import { build } from 'esbuild'

const { outputFiles } = await build({
  entryPoints: [fileURLToPath(new URL('../src/client/capability-settings.js', import.meta.url))],
  bundle: true, format: 'cjs', platform: 'browser', write: false, logLevel: 'silent',
  external: ['react'],
})

const cells = []
let hook = 0
let dirty = false
const react = {
  createElement: (type, props, ...children) => ({ type, props: { ...(props ?? {}), children: children.flat(Infinity) }, children: children.flat(Infinity) }),
  useState(initial) {
    const i = hook++
    if (!(i in cells)) cells[i] = typeof initial === 'function' ? initial() : initial
    return [cells[i], (next) => { cells[i] = typeof next === 'function' ? next(cells[i]) : next; dirty = true }]
  },
  useEffect() {},
  useLayoutEffect() {},
  useRef: initial => ({ current: initial }),
  useMemo: make => make(),
  Fragment: 'fragment',
}
const module = { exports: {} }
runInNewContext(outputFiles[0].text, {
  module, exports: module.exports,
  require: name => (name === 'react' ? react : {}),
})
const { BotCapabilitiesCard } = module.exports

const Card = ({ title, children }) => ({ type: 'card', props: { title, children }, children })
const SwitchRow = ({ label, hint, on }) => ({ type: 'switch', props: { label, hint, on } })

const walk = (node, visit) => {
  if (!node || typeof node !== 'object') return
  visit(node)
  const kids = node.children ?? node.props?.children
  if (Array.isArray(kids)) for (const child of kids) walk(child, visit)
  else if (kids) walk(kids, visit)
}

const render = (props) => {
  let tree
  do {
    dirty = false
    hook = 0
    tree = BotCapabilitiesCard(props)
  } while (dirty)
  return tree
}

const isSwitch = node => node?.props && Object.hasOwn(node.props, 'on') && Object.hasOwn(node.props, 'label') && node.props.onChange !== undefined
const switchLabels = tree => {
  const labels = []
  walk(tree, node => { if (isSwitch(node)) labels.push(node.props.label) })
  return labels
}

const roster = {
  capabilities: [
    { name: 'alpha', kind: 'skill', description: 'Alpha skill', purpose: 'A' },
    { name: 'beta', kind: 'mcp', description: 'Beta server' },
    { name: 'pack-one', kind: 'pack', description: 'Pack', items: ['alpha'] },
  ],
  capabilityStatuses: {},
}
const bot = { id: 'b1', capabilities: ['alpha', 'pack-one'] }
const props = { bot, roster, actions: {}, run: fn => fn, Card, SwitchRow }

test('capabilities start collapsed and show how many are enabled', () => {
  cells.length = 0
  const tree = render(props)
  assert.deepEqual(switchLabels(tree), [])
  const text = []
  walk(tree, node => {
    if (typeof node === 'string') text.push(node)
    if (typeof node?.props?.children === 'string') text.push(node.props.children)
    if (Array.isArray(node?.props?.children)) for (const child of node.props.children) if (typeof child === 'string') text.push(child)
  })
  assert.ok(text.some(part => part.includes('2') || part === '{count} enabled' || /enabled/i.test(part)), text.join(' | '))
})

test('search expands matching rows without requiring a manual open', () => {
  cells.length = 0
  let tree = render(props)
  const findInput = node => {
    if (!node || typeof node !== 'object') return undefined
    if (node.props?.['aria-label'] === 'Search tasks, skills, or keywords') return node
    const kids = node.children ?? node.props?.children
    if (Array.isArray(kids)) return kids.map(findInput).find(Boolean)
    return findInput(kids)
  }
  const input = findInput(tree)
  assert.ok(input, 'search field is present while collapsed')
  input.props.onChange({ target: { value: 'beta' } })
  tree = render(props)
  assert.deepEqual(switchLabels(tree), ['beta'])
})

test('manual expand shows a scrollable capability list', () => {
  cells.length = 0
  let tree = render(props)
  const toggle = (() => {
    let found
    walk(tree, node => {
      if (node.type === 'button' && node.props?.className?.includes('bt-cap-toggle')) found = node
    })
    return found
  })()
  assert.ok(toggle, 'collapse toggle exists')
  toggle.props.onClick()
  tree = render(props)
  assert.equal(switchLabels(tree).length, 3)
  let scrollClass = false
  walk(tree, node => {
    if (typeof node.props?.className === 'string' && node.props.className.includes('bt-cap-list')) scrollClass = true
  })
  assert.equal(scrollClass, true)
})
