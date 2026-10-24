import { existsSync } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { join } from 'node:path'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { packageRoot } from './catalog-seed.js'

const execute = promisify(execFile)
export function install(rt) {
  const env = join(rt.home, 'runtime', 'python')
  const python = join(env, process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  let status = { state: 'unchecked' }
  let installing
  const run = (command, args, options = {}) => execute(command, args, { windowsHide: true, timeout: 120_000, maxBuffer: 8_000_000, ...options })
  rt.dependenciesStatus = async () => {
    if (installing) return { ...status, python, node: process.version }
    if (!existsSync(python)) status = { state: 'missing' }
    else {
      try {
        await run(python, ['-c', 'import akshare'], { timeout: 15_000 })
        let science = false
        try { await run(python, ['-c', 'import rdkit, networkx, sympy, scipy, statsmodels, matplotlib, seaborn'], { timeout: 15_000 }); science = true } catch { /* Optional scientific profile. */ }
        status = { state: 'ready', science }
      }
      catch { status = { state: 'error', error: 'Managed AKShare environment needs repair. Click install or import market data files.' } }
    }
    return { ...status, python, node: process.version }
  }
  rt.installDependencies = ({ science = false } = {}) => {
    if (installing) return Promise.resolve({ ...status })
    status = { state: 'installing' }
    installing = (async () => {
      try {
        await mkdir(join(rt.home, 'runtime'), { recursive: true })
        if (!existsSync(python)) {
          const candidates = process.platform === 'win32' ? [['py', '-3.11'], ['py', '-3.12'], ['py', '-3'], ['python']] : [['python3.11'], ['python3.12'], ['python3'], ['python']]
          let created = false
          for (const [command, ...args] of candidates) {
            try { await run(command, [...args, '-m', 'venv', env]); created = true; break } catch { /* Try the next installed interpreter. */ }
          }
          if (!created) throw new Error('Python is unavailable')
        }
        await run(python, ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', join(packageRoot, science ? 'runtime/requirements-science.txt' : 'runtime/requirements.txt')], { timeout: 600_000 })
        status = { state: 'ready', science }
      } catch { status = { state: 'error', error: 'Install Python 3.11 or later, check network access, then retry. No system packages were changed.' } }
    })().finally(() => { installing = undefined })
    return Promise.resolve({ ...status })
  }
  rt.ctx.tools.register(defineTool({ name: 'chem_futures_history', description: 'Fetch documented AKShare domestic main-continuous or foreign daily historical futures data with provenance. Requires the managed environment installed from Connectors. Never treat continuous data as tradable contracts or delayed quotes as real-time.', parameters: { market: { type: 'string', required: true, enum: ['domestic', 'foreign'] }, symbol: { type: 'string', required: true }, start: { type: 'string' }, end: { type: 'string' } }, output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] }, execute: async (args, exec) => {
    if ((await rt.dependenciesStatus()).state !== 'ready') throw new Error('Install the managed market-data environment in Connectors, or import a CSV/XLSX file.')
    const result = await run(python, [join(packageRoot, 'runtime/futures.py'), JSON.stringify(args)], { signal: exec.signal })
    const value = JSON.parse(result.stdout)
    if (value.error) throw new Error(value.error)
    return JSON.stringify(value)
  } }))
}
