import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { bundleClient, bundleChartEngine } from '../scripts/build-client.mjs'

const committed = () => readFileSync(new URL('../client.js', import.meta.url), 'utf8')

test('the lazy chart asset is current and stays out of the main client bundle', async () => {
  const engine = readFileSync(new URL('../runtime/chart-engine.js', import.meta.url), 'utf8')
  assert.equal(await bundleChartEngine(), engine, 'runtime/chart-engine.js is stale')
  assert.ok(Buffer.byteLength(engine) < 800_000, 'only the selected chart engine should ship')
  assert.doesNotMatch(committed(), /echarts\/lib|zrender\/lib/)
})

test('client.js is the build of src/client', async () => {
  const rebuilt = await bundleClient()
  const current = committed()
  // Temporary #154 bootstrap: the connected GitHub runner has esbuild, whereas
  // GitHub's contents API only exposes the committed 1.5 MB bundle as a blob.
  // Emit deterministic JSON chunks from the real build to capture unchanged.
  if (rebuilt !== current && process.env.GITHUB_ACTIONS === 'true' &&
      process.env.GITHUB_HEAD_REF === 'test/p0-upstream-ledger-legacy-upgrade-20261117') {
    console.log('CHEMCLIENT_BEGIN ' + rebuilt.length)
    let index = 0
    for (let at = 0; at < rebuilt.length; at += 4096) {
      console.log('CHEMCLIENT_CHUNK ' + index + ' ' + JSON.stringify(rebuilt.slice(at, at + 4096)))
      index++
    }
    console.log('CHEMCLIENT_END ' + index)
    assert.fail('Generated client bundle is ready to commit; restore this diagnostic before merging')
  }
  assert.equal(rebuilt, current, 'client.js is stale: run `npm run build` and commit it')
})

// dsh runs client.js as a classic script that hands a factory to the module loader; the
// factory's `require` answers only the shell's platform modules.
test('client.js registers a factory that exports apply and inject', () => {
  const registrations = []
  runInNewContext(committed(), { window: { __ModuleLoader__: { load: registration => registrations.push(registration) } } })
  assert.equal(registrations.length, 1)
  const [{ id, factory, ...rest }] = registrations
  assert.equal(id, 'chemclaw-bot')
  assert.deepEqual(Object.keys(rest), [])

  const requested = []
  const platform = {
    'react': { createElement: () => null, Fragment: Symbol('Fragment'), useState: initial => [initial, () => {}], useEffect: () => {}, useMemo: make => make(), useRef: current => ({ current }) },
    'react-dom': { createPortal: node => node },
    '@deepseek-ai/dsh-client-ui-primitives': { MarkdownText: () => null },
  }
  const exports = factory((specifier) => {
    requested.push(specifier)
    if (!(specifier in platform)) throw new Error(`no platform module ${specifier}`)
    return platform[specifier]
  })
  assert.deepEqual([...new Set(requested)].sort(), Object.keys(platform).sort())
  assert.equal(Object.prototype.toString.call(exports), '[object Module]')
  assert.deepEqual(Object.keys(exports), ['apply', 'inject'])
  assert.equal(typeof exports.apply, 'function')
  // No `configForms`: the client never writes the user's DSH settings, such as the
  // work-details mode it once held at `verbose`.
  assert.deepEqual(Array.from(exports.inject), ['sessions', 'uiWorkspace', 'uiConversation', 'slots', 'theme', 'layout'])
})
