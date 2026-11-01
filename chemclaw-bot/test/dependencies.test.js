import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { install } from '../src/host/dependencies.js'
import { UV_VERSION, uvRelease, verifyArchive } from '../src/host/python-runtime.js'

async function fixture(t, { run, automatic = false } = {}) {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-runtime-'))
  const commands = []
  const tools = new Map()
  let effect
  const config = { automaticDependencies: automatic, dependencyBundle: async () => undefined, dependencyRun: async (command, args, options) => {
    commands.push({ command, args, options })
    return await run?.(command, args, options) ?? { stdout: '{"data":[],"source":"test"}' }
  } }
  const ctx = { tools: { register: tool => tools.set(tool.name, tool) }, effect: callback => { effect = callback } }
  const rt = { home, config, ctx }
  await mkdir(join(home, 'runtime', `uv-${UV_VERSION}`), { recursive: true })
  await writeFile(join(home, 'runtime', `uv-${UV_VERSION}`, process.platform === 'win32' ? 'uv.exe' : 'uv'), '')
  install(rt)
  t.after(() => rm(home, { recursive: true, force: true, maxRetries: 5 }))
  return { rt, home, tools, commands, restart: () => { install(rt) }, start: () => effect() }
}

test('installer archives are pinned and a modified download is rejected', () => {
  for (const platform of ['win32', 'darwin', 'linux']) for (const arch of ['x64', 'arm64']) {
    assert.match(uvRelease(platform, arch).sha256, /^[a-f0-9]{64}$/)
  }
  assert.throws(() => uvRelease('unknown', 'x64'), /unavailable/)
  const data = Buffer.from('verified archive')
  const hash = createHash('sha256').update(data).digest('hex')
  verifyArchive(data, hash)
  assert.throws(() => verifyArchive(Buffer.from('modified'), hash), /verification failed/)
})

test('concurrent first queries share managed Python setup, without invoking system Python', async t => {
  const { rt, commands, home, tools } = await fixture(t)
  await Promise.all([rt.ensureMarketEnvironment(), rt.ensureMarketEnvironment(), rt.ensureScienceEnvironment()])
  assert.equal(commands.filter(item => item.args.includes('venv')).length, 1)
  assert.equal(commands.filter(item => item.args.includes('install')).length, 2)
  assert.ok(commands.every(item => item.command.startsWith(home)))
  const venv = commands.find(item => item.args.includes('venv'))
  assert.ok(venv.args.includes('--managed-python'))
  assert.equal(venv.options.env.UV_PYTHON_INSTALL_DIR, join(home, 'runtime', 'interpreters'))
  assert.equal((await rt.dependenciesStatus()).science, true)
  const tool = tools.get('chem_futures_history')
  const data = await tool.execute({ market: 'domestic', symbol: 'MA0' }, {})
  assert.equal(JSON.parse(data).source, 'test')
  assert.equal(commands.at(-1).args[0], join(home, 'runtime', 'resources', 'futures.py'))
  const stock = tools.get('chem_stock_history')
  assert.ok(stock, 'stock OHLC must be a first-class tool on the existing AKShare runtime')
  const observed = []
  rt.noteMarketOhlcSource = (id, status) => observed.push({ id, status })
  const stockResult = await stock.execute({ symbol: '601857', start: '2026-10-01', end: '2026-10-30', adjust: 'none' }, { agent: { id: 'bot-1' } })
  assert.equal(JSON.parse(stockResult).source, 'test')
  assert.deepEqual(JSON.parse(commands.at(-1).args[1]), { symbol: '601857', start: '2026-10-01', end: '2026-10-30', adjust: 'none', market: 'stock' })
  assert.deepEqual(observed, [{ id: 'bot-1', status: 'ready' }])
  assert.match(await readFile(join(home, 'runtime', 'resources', 'requirements.txt'), 'utf8'), /akshare==/)
})

test('a verified existing environment starts offline without downloading or reinstalling', async t => {
  const { rt, commands, restart } = await fixture(t)
  await rt.ensureScienceEnvironment()
  commands.length = 0
  restart()
  await rt.ensureScienceEnvironment()
  assert.equal(commands.length, 2)
  assert.ok(commands.every(item => item.args[0] === '-c'))
})

test('broken environments are repaired and stale package manifests are updated', async t => {
  let broken = false
  const { rt, commands, home, restart } = await fixture(t, { run: (_command, args) => {
    if (broken && args[0] === '-c') { broken = false; throw new Error('broken import') }
  } })
  await rt.ensureMarketEnvironment()
  broken = true
  restart()
  await rt.ensureMarketEnvironment()
  assert.equal(commands.filter(item => item.args.includes('venv')).length, 2)
  await writeFile(join(home, 'runtime', 'market.json'), '{"fingerprint":"old"}')
  restart()
  await rt.ensureMarketEnvironment()
  assert.equal(commands.filter(item => item.args.includes('venv')).length, 3)
})

test('scientific package failure does not prevent futures queries', async t => {
  const { rt, tools } = await fixture(t, { run: (_command, args) => {
    if (args.some(arg => arg.endsWith('requirements-science.txt'))) throw new Error('offline')
  } })
  await rt.ensureScienceEnvironment()
  assert.deepEqual(await rt.dependenciesStatus().then(({ state, science }) => ({ state, science })), { state: 'ready', science: false })
  assert.equal(JSON.parse(await tools.get('chem_futures_history').execute({ market: 'domestic', symbol: 'MA0' }, {})).source, 'test')
})

test('failed setup explains automatic retry and throttles repeated failures', async t => {
  let offline = true
  const { rt, commands } = await fixture(t, { run: () => { if (offline) throw new Error('private machine details') } })
  await assert.rejects(rt.ensureMarketEnvironment(), /retry automatically/)
  const count = commands.length
  await assert.rejects(rt.ensureMarketEnvironment(), /retry automatically/)
  assert.equal(commands.length, count)
  assert.equal((await rt.dependenciesStatus()).state, 'error')
  assert.doesNotMatch((await rt.dependenciesStatus()).error, /private machine details/)
  const later = Date.now() + 61_000
  t.mock.method(Date, 'now', () => later)
  offline = false
  await rt.ensureMarketEnvironment()
  assert.equal((await rt.dependenciesStatus()).state, 'ready')
  assert.ok(commands.length > count)
})

test('startup prepares market data without science packages or settings and cleanup cancels pending setup', async t => {
  const { rt, start, commands } = await fixture(t, { automatic: true })
  const dispose = start()
  await new Promise(resolve => setTimeout(resolve, 1100))
  await rt.ensureMarketEnvironment()
  assert.equal((await rt.dependenciesStatus()).science, false)
  assert.ok(commands.every(item => !item.args.some(arg => arg.endsWith('requirements-science.txt'))))
  await dispose()
  assert.equal(commands[0].options.signal.aborted, true)
})

test('failed AKShare history is recorded as unavailable for an honest single line fallback', async t => {
  const { rt, tools } = await fixture(t, { run: (_cmd, args) => {
    if (args[0]?.endsWith('futures.py')) return { stdout: '{"error":"No stock OHLC"}' }
  } })
  const seen = []
  rt.noteMarketOhlcSource = (id, status) => seen.push([id, status])
  const stockResult = JSON.parse(await tools.get('chem_stock_history').execute(
    { symbol: '601857' }, { agent: { id: 's' } },
  ))
  assert.equal(stockResult.status, 'unavailable')
  assert.match(stockResult.next, /web_search\/web_fetch/)
  assert.deepEqual(seen, [['s', 'unavailable']])
})

test('a failed managed runtime also returns a usable web fallback rather than crashing or fabricating prices', async t => {
  const { tools } = await fixture(t, { run: () => { throw new Error('offline') } })
  const result = JSON.parse(await tools.get('chem_stock_history').execute(
    { symbol: '601857' }, { agent: { id: 'stock-chat' } },
  ))
  assert.equal(result.status, 'unavailable')
  assert.match(result.next, /web_search\/web_fetch/)
  assert.equal(result.data, undefined)
})

test('explicit spot inquiries cannot call futures or stock OHLC tools', async t => {
  const { rt, tools, commands } = await fixture(t)
  rt.explicitSpotRequestOf = id => id === 'spot-bot'
  const before = commands.length
  for (const [name, args] of [
    ['chem_futures_history', { market: 'domestic', query: '纯碱' }],
    ['chem_futures_history', { market: 'foreign', symbol: 'CL' }],
    ['chem_stock_history', { symbol: '601857' }],
  ]) {
    const response = JSON.parse(await tools.get(name).execute(args, { agent: { id: 'spot-bot' } }))
    assert.equal(response.status, 'market_mismatch')
    assert.equal(response.requestedMarket, 'spot')
    assert.deepEqual(response.data, [])
    assert.match(response.next, /chem-data-hub/)
  }
  assert.equal(commands.length, before, 'must not install Python or query AKShare for a spot price')
  const actualFuture = JSON.parse(await tools.get('chem_futures_history').execute(
    { market: 'domestic', query: '纯碱' }, { agent: { id: 'futures-bot' } },
  ))
  assert.equal(actualFuture.source, 'test', 'normal futures queries remain supported')
})
