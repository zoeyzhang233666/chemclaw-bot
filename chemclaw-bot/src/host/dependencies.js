import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { join } from 'node:path'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { packageRoot } from './catalog-seed.js'
import { provisionUv, UV_VERSION } from './python-runtime.js'
import { readRuntimeBundle, unpackRuntimeBundle } from './runtime-bundle.js'

const execute = promisify(execFile)
const RETRY_DELAY = 60_000
const SCIENCE_IMPORTS = 'import rdkit, networkx, sympy, scipy, statsmodels, matplotlib, seaborn, numpy, pandas'
const SETUP_ERROR = 'Analysis components could not be prepared. Check your connection and try the task again; setup will retry automatically. You can also provide a CSV/XLSX file.'

export function install(rt) {
  const root = join(rt.home, 'runtime')
  const env = join(root, 'python')
  const resources = join(root, 'resources')
  const python = join(env, process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  const controller = new AbortController()
  const environment = { ...process.env, UV_PYTHON_INSTALL_DIR: join(root, 'interpreters'), UV_CACHE_DIR: join(root, 'cache'), UV_NO_PROGRESS: '1' }
  const run = (command, args, options = {}) => (rt.config.dependencyRun ?? execute)(command, args, {
    windowsHide: true, timeout: 600_000, maxBuffer: 8_000_000, env: environment, signal: controller.signal, ...options,
  })
  let status = { state: 'unchecked', science: false }
  let market
  let science
  let uv
  let fingerprint
  let retryAt = 0
  let scienceRetryAt = 0
  const view = () => ({ ...status, python, node: process.version })
  const verify = async (optional, interpreter = python) => {
    await run(interpreter, ['-c', optional ? SCIENCE_IMPORTS : 'import akshare'], { timeout: 60_000 })
  }
  const stamp = optional => join(root, optional ? 'science.json' : 'market.json')
  const saved = async optional => {
    try { return JSON.parse(await readFile(stamp(optional), 'utf8')).fingerprint === fingerprint } catch { return false }
  }
  const save = optional => writeFile(stamp(optional), JSON.stringify({ fingerprint }))
  const prepare = async () => {
    await mkdir(resources, { recursive: true })
    const hash = createHash('sha256').update(`${UV_VERSION}:python3.12`)
    // Child processes cannot read resources inside an Electron ASAR archive.
    for (const file of ['requirements.txt', 'requirements-science.txt', 'futures.py']) {
      const content = await readFile(join(packageRoot, 'runtime', file))
      hash.update(content)
      await writeFile(join(resources, file), content)
    }
    fingerprint = hash.digest('hex')
  }
  const installer = async () => {
    uv ??= await provisionUv(root, { run, signal: controller.signal, fetch: rt.config.dependencyFetch })
    return uv
  }
  const installPackages = async optional => run(await installer(), ['--no-config', 'pip', 'install', '--break-system-packages', '--python', python, '-r', join(resources, optional ? 'requirements-science.txt' : 'requirements.txt')])
  rt.ensureMarketEnvironment = () => {
    if (status.state === 'ready') return Promise.resolve(python)
    if (market) return market
    if (Date.now() < retryAt) return Promise.reject(new Error(SETUP_ERROR))
    status = { state: 'installing', science: false }
    market = (async () => {
      await prepare()
      const bundle = await (rt.config.dependencyBundle ?? readRuntimeBundle)(packageRoot)
      if (bundle) {
        await unpackRuntimeBundle(bundle, root, { run, verify: interpreter => verify(false, interpreter) })
        status = { state: 'ready', science: false, bundled: true }
        return python
      }
      let ready = false
      if (await saved(false)) {
        try { await verify(false); ready = true } catch { /* Repair an incomplete environment. */ }
      }
      if (!ready) {
        await run(await installer(), ['--no-config', 'venv', '--python', '3.12', '--managed-python', '--allow-existing', env])
        await installPackages(false)
        await verify(false)
        await save(false)
      }
      status = { state: 'ready', science: false }
      return python
    })().catch(() => {
      retryAt = Date.now() + RETRY_DELAY
      status = { state: 'error', science: false, error: SETUP_ERROR }
      throw new Error(SETUP_ERROR)
    }).finally(() => { market = undefined })
    return market
  }
  rt.ensureScienceEnvironment = () => {
    if (science) return science
    if (status.science || Date.now() < scienceRetryAt) return Promise.resolve(view())
    science = (async () => {
      await rt.ensureMarketEnvironment()
      let ready = false
      if (await saved(true)) {
        try { await verify(true); ready = true } catch { /* Repair scientific packages independently of market data. */ }
      }
      if (!ready) { await installPackages(true); await verify(true); await save(true) }
      status.science = true
      return view()
    })().catch(() => {
      scienceRetryAt = Date.now() + RETRY_DELAY
      return view()
    }).finally(() => { science = undefined })
    return science
  }
  rt.dependenciesStatus = async () => view()
  // Kept for older clients while setup now starts automatically.
  rt.installDependencies = ({ science: optional = false } = {}) => {
    void (optional ? rt.ensureScienceEnvironment() : rt.ensureMarketEnvironment()).catch(() => {})
    return Promise.resolve(view())
  }
  if (rt.config.automaticDependencies !== false) rt.ctx.effect(() => {
    const timer = setTimeout(() => { void rt.ensureMarketEnvironment().catch(() => {}) }, 1000)
    timer.unref?.()
    return async () => { clearTimeout(timer); controller.abort(); await Promise.allSettled([market, science]) }
  }, 'chemclaw-bot: automatic analysis setup')
  rt.ctx.tools.register(defineTool({ name: 'chem_futures_history', description: 'Fetch documented AKShare domestic main-continuous or foreign daily historical futures data with provenance. Analysis components are prepared automatically; the first query may wait for setup. Never treat continuous data as tradable contracts or delayed quotes as real-time.', parameters: { market: { type: 'string', required: true, enum: ['domestic', 'foreign'] }, symbol: { type: 'string', required: true }, start: { type: 'string' }, end: { type: 'string' } }, output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] }, execute: async (args, exec) => {
    await rt.ensureMarketEnvironment()
    const result = await run(python, [join(resources, 'futures.py'), JSON.stringify(args)], { signal: exec.signal ? AbortSignal.any([exec.signal, controller.signal]) : controller.signal })
    const value = JSON.parse(result.stdout)
    if (value.error) throw new Error(value.error)
    return JSON.stringify(value)
  } }))
}
