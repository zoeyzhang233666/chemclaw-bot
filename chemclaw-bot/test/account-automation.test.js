import { test } from 'node:test'
import assert from 'node:assert/strict'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { runInNewContext } from 'node:vm'
import { build } from 'esbuild'

// AccountLauncher's Automation tasks entry must open ChemClaw's schedules page.
// The shell schedules panel's New button calls startSession(), which in Bot mode
// jumps into an existing chat instead of creating a task.
const PLUGIN = dirname(dirname(fileURLToPath(import.meta.url)))
const { outputFiles } = await build({
  stdin: {
    contents: "export { AccountLauncher } from './src/client/sidebar.js'",
    resolveDir: PLUGIN,
  },
  bundle: true, format: 'cjs', platform: 'browser', write: false, logLevel: 'silent',
  external: ['react', 'react-dom', '@deepseek-ai/dsh-client-ui-primitives'],
})

const cells = []
let hook = 0
let dirty = false
const react = {
  createElement: (type, props, ...children) => ({ type, props: { ...(props ?? {}), children: children.flat(Infinity) }, children: children.flat(Infinity) }),
  Fragment: 'fragment',
  useState(initial) {
    const i = hook++
    if (!(i in cells)) cells[i] = typeof initial === 'function' ? initial() : initial
    return [cells[i], (next) => { cells[i] = typeof next === 'function' ? next(cells[i]) : next; dirty = true }]
  },
  useEffect() {},
  useLayoutEffect() {},
  useRef: initial => ({ current: initial }),
  useMemo: make => make(),
  useSyncExternalStore: (_subscribe, getSnapshot) => getSnapshot(),
}
const module = { exports: {} }
runInNewContext(outputFiles[0].text, {
  module, exports: module.exports,
  document: { body: {} },
  window: {
    addEventListener() {},
    removeEventListener() {},
    matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
  },
  require: name => (name === 'react' ? react : name === 'react-dom' ? { createPortal: node => node } : {}),
})
const { AccountLauncher } = module.exports

const walk = (node, visit) => {
  if (!node || typeof node !== 'object') return
  visit(node)
  const kids = node.children ?? node.props?.children
  if (Array.isArray(kids)) for (const child of kids) walk(child, visit)
  else if (kids) walk(kids, visit)
}

const labelOf = (node) => {
  const kids = node.children ?? node.props?.children
  if (!Array.isArray(kids)) return null
  const label = kids.find(child => child?.props?.className === 'bt-menu-label')
  const text = label?.props?.children ?? label?.children
  return Array.isArray(text) ? text.join('') : text ?? null
}

test('account menu Automation tasks opens ChemClaw schedules settings, not the shell panel', () => {
  cells.length = 0
  cells[0] = true
  cells[1] = { left: 0, bottom: 0 }
  const opened = []
  const selected = []
  const actions = {
    seatAccount() {},
    openSettings: (...args) => { opened.push(args) },
    selectPanel: (id) => { selected.push(id) },
    reportError() {},
  }

  let tree
  do {
    dirty = false
    hook = 0
    tree = AccountLauncher({ seat: true, actions })
  } while (dirty)

  const items = []
  walk(tree, (node) => {
    if (node.type === 'button' && node.props?.role === 'menuitem') items.push(node)
  })
  const automation = items.find(node => labelOf(node) === 'Automation tasks')
  assert.ok(automation, 'Automation tasks menu item is present')
  automation.props.onClick()
  assert.deepEqual(opened, [['schedules']])
  assert.deepEqual(selected, [])
})
