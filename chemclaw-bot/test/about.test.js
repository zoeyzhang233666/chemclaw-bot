import assert from 'node:assert/strict'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { runInNewContext } from 'node:vm'
import { build } from 'esbuild'

const bundle = await build({
  entryPoints: [fileURLToPath(new URL('../src/client/about.js', import.meta.url))],
  bundle: true, format: 'cjs', platform: 'node', write: false,
  external: ['react', 'react-dom', '@deepseek-ai/dsh-client-ui-primitives'],
})

test('About checks and installs through the desktop bridge instead of the plugin manager', async () => {
  let snapshot = { enabled: true, phase: 'idle', current: '0.2.1', checkedAt: 1 }
  let checks = 0
  let installs = 0
  let pluginChecks = 0
  const bridge = {
    status: async () => snapshot,
    check: async () => { checks++; return { ...snapshot, phase: 'ready', latest: '0.2.2' } },
    install: async () => { installs++ },
  }
  const values = []
  let cursor = 0
  const effects = []
  const react = {
    createElement: (type, props, ...children) => ({ type, props: props ?? {}, children: children.flat(Infinity) }),
    useState: initial => {
      const index = cursor++
      if (!(index in values)) values[index] = initial
      return [values[index], value => { values[index] = value }]
    },
    useEffect: effect => { effects.push(effect) },
    useRef: current => ({ current }),
    useLayoutEffect: () => {},
  }
  const module = { exports: {} }
  runInNewContext(bundle.outputFiles[0].text, {
    module, exports: module.exports, window: { dsBotApp: { updates: bridge } },
    setTimeout, clearTimeout, setInterval: () => 1, clearInterval: () => {},
    require: name => name === 'react' ? react : {},
  })
  const run = promise => promise
  const tree = module.exports.AboutPage({
    useUpdate: () => ({ source: 'app', enabled: false }),
    actions: { checkUpdate: () => { pluginChecks++ } }, run, Section: 'section', Row: 'row',
  })
  const find = (node, predicate) => Array.isArray(node) ? node.flatMap(item => find(item, predicate))
    : node && typeof node === 'object' ? [...(predicate(node) ? [node] : []), ...find(node.children, predicate)] : []
  const [desktop] = find(tree, node => node.type?.name === 'DesktopUpdates')
  assert.ok(desktop)
  values.length = 0
  cursor = 0
  effects.length = 0
  desktop.type(desktop.props)
  const dispose = effects[0]()
  await Promise.resolve()
  cursor = 0
  let row = desktop.type(desktop.props)
  const [check] = find(row, node => node.type === 'button')
  assert.equal(check.props.disabled, false)
  check.props.onClick()
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(checks, 1)
  assert.equal(pluginChecks, 0)
  cursor = 0
  row = desktop.type(desktop.props)
  const [install] = find(row, node => node.type === 'button' && node.children.includes('Restart now'))
  assert.ok(install)
  await install.props.onClick()
  assert.equal(installs, 1)
  dispose()
})
