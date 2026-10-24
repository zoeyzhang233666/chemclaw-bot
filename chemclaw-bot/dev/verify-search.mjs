import { createRequire } from 'node:module'
import { mkdirSync, existsSync, writeFileSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { pathToFileURL } from 'node:url'
const anchor = resolve('../app/package.json')
const require = createRequire(anchor)
const boot = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-app-boot')))
const { runProfile } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh/profile-boot')))
const home = resolve(`../.dsh-test-search-${Date.now()}`)
const originalLog = console.log
console.log = (...args) => originalLog(...args.map(value => typeof value === 'string' ? value.replace(/([?&]token=)[^\s&]+/g, '$1<hidden>') : value))
if (existsSync(home)) throw new Error('Use a new test home')
mkdirSync(home)
for (const name of Object.keys(process.env)) if (/KEY|TOKEN|PASSWORD|SECRET|DSH_WEB_/.test(name)) delete process.env[name]
process.env.DSH_HOME = home
const dir = join(home, 'profiles/check')
boot.initProfile(dir, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'chemclaw-bot'])
writeFileSync(join(dir, 'cordis.patch.yml'), '- id: chemclaw\n  config:\n    seedTeam: false\n    companyConnectors: false\n    updateCheck: false\n- id: session-log-deepseek\n  disabled: true\n- id: session-telemetry-otel\n  disabled: true\n')
if (process.argv.includes('--without-free')) writeFileSync(join(dir, 'cordis.patch.yml'), '- id: chemclaw\n  config:\n    seedTeam: false\n    companyConnectors: false\n    updateCheck: false\n- id: web-search-free\n  disabled: true\n- id: web\n  config:\n    searchProvider: auto\n    fetchProvider: http\n')
let running
const results = {}
try {
  console.log('search verification: boot starting')
  const timer = setTimeout(() => { console.error('search verification: boot did not settle in 45 seconds'); process.exit(2) }, 45000)
  running = await runProfile({ environment: boot.loadLayeredEnv('dsh'), profile: 'check', resolvedProfile: { profile: boot.loadProfileDirectory('dsh', dir, anchor), installAnchor: anchor }, args: ['--no-open', '--port', '0'], patchFiles: [], packageManager: { command: process.execPath, args: ['--expose-internals', resolve('../app/node_modules/pnpm/bin/pnpm.mjs')] } })
  clearTimeout(timer)
  console.log('search verification: boot ready')
  const web = running.ctx.get('web')
  for (const [name, run] of [
    ['search', () => web.search({ query: 'methanol PubChem', maxResults: 3 }, AbortSignal.timeout(90000))],
    ['fetch', () => web.fetch({ url: 'https://pubchem.ncbi.nlm.nih.gov/compound/Methanol' }, AbortSignal.timeout(60000))],
  ]) {
    try { results[name] = { ok: true, result: await run() }; console.log(`${name}: success`) }
    catch (error) { results[name] = { ok: false, error: error.message }; console.log(`${name}: ${error.message}`) }
  }
  writeFileSync(resolve(`../chemclaw/verification/search-${process.argv.includes('--without-free') ? 'control' : 'live'}.json`), JSON.stringify(results, null, 2))
} finally { await running?.shutdown.shutdown(0) }
if (!results.search?.ok || !results.fetch?.ok) process.exitCode = 1
