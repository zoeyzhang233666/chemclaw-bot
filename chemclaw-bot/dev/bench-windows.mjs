import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { createServer } from 'node:net'
import { cpSync, existsSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const plugin = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const root = dirname(plugin)
const anchor = join(root, 'app/package.json')
const require = createRequire(anchor)
// npm can retain an older same-version file dependency. Only synchronize our own
// package, resolved through its public export, before testing the source revision.
const installedPlugin = dirname(require.resolve('chemclaw-bot/package.json'))
if (resolve(installedPlugin) !== plugin) {
  for (const path of ['package.json', 'index.js', 'client.js', 'NOTICE', 'LICENSE', 'src/host', 'src/shared', 'seed', 'skills/builtin', 'skills/vendor']) {
    if (existsSync(join(plugin, path))) cpSync(join(plugin, path), join(installedPlugin, path), { recursive: true })
  }
}
const boot = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-app-boot')))
const { runProfile } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh/profile-boot')))
const name = process.argv[2] ?? `chemclaw-${Date.now()}`
const inspectUi = process.argv.includes('--ui')
const reuseUi = inspectUi && process.argv.includes('--reuse')
if (!/^[a-z0-9-]+$/.test(name)) throw new Error('Invalid bench name')
const home = join(root, `.dsh-test-${name}`)
if (existsSync(home) && !reuseUi) throw new Error('Use a fresh bench name; existing test data is retained')
if (reuseUi && existsSync(join(home, 'stop'))) unlinkSync(join(home, 'stop'))
mkdirSync(home, { recursive: true })
const freePort = () => new Promise(resolve => { const server = createServer(); server.listen(0, '127.0.0.1', () => { const port = server.address().port; server.close(() => resolve(port)) }) })
const mockPort = await freePort()
const portAt = process.argv.indexOf('--web-port')
const webPort = portAt < 0 ? await freePort() : Number(process.argv[portAt + 1])
if (!Number.isInteger(webPort) || webPort < 1024 || webPort > 65535 || webPort === 3080) throw new Error('Use a free test port between 1024 and 65535, excluding 3080')
for (const key of Object.keys(process.env)) if (/KEY|TOKEN|PASSWORD|SECRET/i.test(key) && !/^(?:PATHEXT|SYSTEMROOT)$/i.test(key)) delete process.env[key]
Object.assign(process.env, { DSH_HOME: home, DEEPSEEK_API_KEY: 'mock-key', DEEPSEEK_BASE_URL: `http://127.0.0.1:${mockPort}/v1` })
const mock = spawn(process.execPath, [join(plugin, 'dev/mock-llm.mjs'), home], { env: { ...process.env, MOCK_PORT: String(mockPort), MOCK_LOG: join(home, 'mock.jsonl'), MOCK_DELAY_MS: '100' }, windowsHide: true, stdio: 'ignore' })
const dir = join(home, 'profiles', 'chemclaw-test')
boot.initProfile(dir, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'chemclaw-bot'])
writeFileSync(join(dir, 'cordis.patch.yml'), `- id: chemclaw\n  config:\n    seedTeam: false\n    companyConnectors: false\n    mainName: Chief\n    mainRole: Chief of Staff\n    checkRatio: 0.45\n    updateCheck: false\n- id: llm-deepseek\n  config:\n    models:\n      - { id: deepseek-v4.1-flash, contextWindow: 100000, maxTokens: 8000, inputModalities: [text, image] }\n      - { id: deepseek-v4-pro, contextWindow: 100000, maxTokens: 8000 }\n- id: ui-settings-account\n  config:\n    version: 1\n    step: done\n    purpose: office\n    process: compact\n    completion: completed\n    usage: compact\n    developerTools: true\n`)
writeFileSync(join(dir, 'cordis.patch.yml'), readFileSync(join(dir, 'cordis.patch.yml'), 'utf8') + '\n- id: session-log-deepseek\n  disabled: true\n- id: session-telemetry-otel\n  disabled: true\n- id: workspace-changes\n  disabled: true\n');
if (inspectUi) writeFileSync(join(dir, 'cordis.patch.yml'), readFileSync(join(dir, 'cordis.patch.yml'), 'utf8').replace('seedTeam: false', 'seedTeam: true'))
const profile = boot.loadProfileDirectory('dsh', dir, anchor)
let running
try {
  const pnpm = join(root, 'app/node_modules/pnpm/bin/pnpm.mjs')
  running = await runProfile({ environment: boot.loadLayeredEnv('dsh'), profile: 'chemclaw-test', resolvedProfile: { profile, installAnchor: anchor }, args: ['--no-open', '--port', String(webPort)], patchFiles: [], packageManager: { command: process.execPath, args: ['--expose-internals', pnpm] } })
  const connection = running.ctx.get('connection')
  const url = connection.authenticatedUrl(`http://127.0.0.1:${webPort}`)
  writeFileSync(join(home, 'web.log'), `dsh web: ${url}\n`)
  if (inspectUi) {
    console.log(`Isolated skill UI bench ready on port ${webPort}; create its stop file to finish.`)
    await new Promise(done => { const timer = setInterval(() => { if (existsSync(join(home, 'stop'))) { clearInterval(timer); done() } }, 250) })
  } else {
    const result = await new Promise(resolve => { const smoke = spawn(process.execPath, [join(plugin, 'dev/smoke.mjs'), name, String(webPort)], { env: process.env, stdio: 'inherit', windowsHide: true }); smoke.once('exit', resolve) })
    process.exitCode = result ?? 1
  }
} finally { mock.kill(); await running?.shutdown.shutdown(process.exitCode ?? 0) }
