// Integration gate for #133: real DSH Host + real Cordis HMR + retained DSH Agents.
// No real model credentials, browser UI, private files, or user profile are used.
// Run from repo root: node --expose-internals app/scripts/check-chemclaw-hmr.mjs
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { createServer } from 'node:net'
import { existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { initProfile, loadLayeredEnv, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot'
import { runProfile } from '@deepseek-ai/dsh/profile-boot'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const appRoot = join(root, 'app')
const home = realpathSync(mkdtempSync(join(tmpdir(), 'chemclaw-real-hmr-')))
const profileDir = join(home, 'profiles', 'chemclaw-hmr-test')
const profilePatch = join(profileDir, 'cordis.patch.yml')
const mockLog = join(home, 'mock.jsonl')
let application
let mock
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
async function eventually(predicate, label, timeoutMs = 35_000) {
  const deadline = Date.now() + timeoutMs
  let last
  while (Date.now() < deadline) {
    try { if (await predicate()) return } catch (error) { last = error }
    await sleep(100)
  }
  throw new Error(`Timed out: ${label}${last ? ` (${last.message})` : ''}`)
}
async function freePort() {
  const server = createServer()
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const port = server.address().port
  await new Promise(resolve => server.close(resolve))
  return port
}
const patch = role => `- id: hmr
  disabled: false
  config:
    root: []
- id: chemclaw
  config:
    seedTeam: false
    companyConnectors: false
    updateCheck: false
    mainName: Chief
    mainRole: ${role}
- id: llm-deepseek
  config:
    models:
      - { id: deepseek-v4.1-flash, contextWindow: 100000, maxTokens: 8000, inputModalities: [text, image] }
- id: session-log-deepseek
  disabled: true
- id: session-telemetry-otel
  disabled: true
- id: workspace-changes
  disabled: true
`
function mockCalls() {
  if (!existsSync(mockLog)) return 0
  return readFileSync(mockLog, 'utf8').split('\n').filter(Boolean).length
}
async function main() {
  assert.ok(process.execArgv.includes('--expose-internals'), 'DSH HMR requires Node --expose-internals')
  // Explicitly isolate DSH from the real desktop profile. All credentials point to
  // a loopback-only scripted mock server which runs without a paid API token.
  const mockPort = await freePort()
  const webPort = await freePort()
  for (const key of ['DSH_HOME', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_API_KEY']) delete process.env[key]
  Object.assign(process.env, {
    DSH_HOME: home,
    DEEPSEEK_BASE_URL: `http://127.0.0.1:${mockPort}/v1`,
    DEEPSEEK_API_KEY: 'mock-key',
  })
  mock = spawn(process.execPath, [join(root, 'chemclaw-bot', 'dev', 'mock-llm.mjs'), home], {
    env: { ...process.env, MOCK_PORT: String(mockPort), MOCK_LOG: mockLog, MOCK_DELAY_MS: '20000' },
    stdio: 'ignore',
    windowsHide: true,
  })
  await eventually(async () => {
    try { return (await fetch(`http://127.0.0.1:${mockPort}/`)).status > 0 } catch { return false }
  }, 'scripted mock model startup', 15_000)
  initProfile(profileDir, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'chemclaw-bot'])
  writeFileSync(profilePatch, patch('Chief of Staff'), 'utf8')
  const anchor = join(appRoot, 'package.json')
  const profile = loadProfileDirectory('dsh', profileDir, anchor)
  const pnpm = join(appRoot, 'node_modules', 'pnpm', 'bin', 'pnpm.mjs')
  application = await runProfile({
    environment: loadLayeredEnv('dsh'),
    profile: 'chemclaw-hmr-test',
    resolvedProfile: { profile, installAnchor: anchor },
    patchFiles: [],
    args: ['--no-open', '--port', String(webPort)],
    packageManager: { command: process.execPath, args: ['--expose-internals', pnpm] },
  })
  const { ctx } = application
  const hmr = ctx.get('hmr')
  assert.ok(hmr && typeof hmr.runExclusive === 'function' && typeof hmr.reconcileProfile === 'function',
    'The real pinned DSH Host must expose the public HMR reconciliation service')
  const connection = ctx.get('connection')
  assert.ok(connection, 'The real DSH connection service must be available')
  const url = connection.authenticatedUrl(`http://127.0.0.1:${webPort}`)
  const login = await fetch(url, { redirect: 'manual' })
  const cookies = login.headers.getSetCookie().map(value => value.split(';')[0])
  assert.ok(cookies.length > 0, `DSH test Host failed authentication (HTTP ${login.status})`)
  const cookie = cookies.join('; ')
  async function api(endpoint, payload = {}) {
    const response = await fetch(`http://127.0.0.1:${webPort}/api/bot`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', cookie },
      body: JSON.stringify({ endpoint, payload }),
    })
    assert.equal(response.status, 200, `${endpoint} HTTP ${response.status}`)
    const body = await response.json()
    assert.equal(body.ok, true, `${endpoint}: ${body.error?.message ?? JSON.stringify(body)}`)
    return body.value
  }
  const view = await api('state')
  const mainId = view.mainBotId
  assert.ok(mainId && view.bots.some(bot => bot.id === mainId), 'Real ChemClaw Main Bot must bootstrap')
  const model = view.models.find(row => row.ref?.includes('deepseek-v4.1-flash'))
  assert.ok(model, 'Scripted model must appear in the real model catalog')
  // A normal (non-team) DSH Agent must never acquire ChemClaw's team tools.
  const external = await api('add-agent')
  const externalSessionId = external.sessions?.[0]
  assert.ok(externalSessionId, 'Real DSH Agent needs a Session')
  const agents = ctx.get('agents')
  assert.ok(agents && typeof agents.list === 'function', 'Real DSH Agent service must be registered')
  const externalAgent = agents.get(externalSessionId)
  assert.ok(externalAgent, 'Real normal DSH Agent must be resident')
  const teamTools = new Set(['message_bot', 'create_bot'])
  const available = agent => new Set(ctx.tools.schemas(agent).map(tool => tool.name))
  for (const name of teamTools) assert.equal(available(externalAgent).has(name), false,
    `Normal DSH Agent unexpectedly sees ${name} before hot reload`)

  // Picking the model starts the Main Bot's held kickoff on a deliberately slow
  // scripted model. Unlike a fake agent, this is the actual DSH Agent runtime.
  await api('update-bot', { id: mainId, model: model.ref })
  await eventually(() => agents.get(mainId)?.status === 'running', 'real Main Bot running before hot reload')
  await eventually(() => mockCalls() > 0, 'real DSH calling the scripted model')
  const currentAgent = agents.get(mainId)
  const initialCalls = mockCalls()
  const initialReady = ctx.get('chemclawReady')
  assert.ok(initialReady && await initialReady.check())
  // Reconcile a real profile edit using the pinned DSH HMR queue. This replaces
  // ChemClaw's Cordis plugin fiber in-process WITHOUT restarting the Host or the
  // running Agent. It is not an Electron window refresh or a second application.
  writeFileSync(profilePatch, patch('Team Supervisor'), 'utf8')
  const reconciled = await hmr.runExclusive(() => hmr.reconcileProfile(['chemclaw']))
  assert.equal(reconciled.restartReason, undefined,
    `Real plugin reload was deferred to restart: ${reconciled.restartReason}`)
  const reloadedReady = ctx.get('chemclawReady')
  assert.ok(reloadedReady && reloadedReady !== initialReady && await reloadedReady.check(),
    'ChemClaw must be disposed and activated again in the same real DSH Host')
  assert.equal(ctx.get('agents').get(mainId), currentAgent,
    'Real running DSH Agent must survive ChemClaw plugin reload')
  assert.equal(currentAgent.status, 'running',
    'Plugin reload must not cancel the real in-flight model request')
  assert.equal(mockCalls(), initialCalls, 'Reload must not replay the original model call')
  const restored = await api('state')
  assert.ok(restored.activity?.[mainId], 'Reloaded ChemClaw must still show an active Main Bot')
  const afterAgent = ctx.get('agents').get(externalSessionId)
  assert.equal(afterAgent, externalAgent, 'Normal DSH Agent must survive plugin reload')
  for (const name of teamTools) assert.equal(available(afterAgent).has(name), false,
    `Normal DSH Agent gained ${name} after reload`)
  // Stop the original real DSH Agent. The after-reload ChemClaw listener must
  // clear the phantom activity rather than keep the user waiting indefinitely.
  currentAgent.cancel({ kind: 'user' })
  await eventually(() => currentAgent.status === 'idle', 'real DSH Agent stops after reload', 20_000)
  await eventually(async () => !(await api('state')).activity?.[mainId],
    'ChemClaw activity clears on actual DSH turn completion', 10_000)
  console.log('PASS: real DSH Agent retained, actual Cordis HMR plugin replaced, Stop cleared, permissions isolated, no duplicate model call')
}
let failed = false
try { await main() } catch (error) {
  failed = true
  console.error('FAIL: real DSH in-process ChemClaw HMR integration:', error)
} finally {
  try { await application?.shutdown.shutdown(failed ? 1 : 0) } catch (error) { console.error('Host cleanup:', error); failed = true }
  try { mock?.kill('SIGTERM') } catch {}
  try { rmSync(home, { recursive: true, force: true, maxRetries: 8, retryDelay: 150 }) } catch (error) { console.error('Temp cleanup:', error); failed = true }
}
if (failed) process.exitCode = 1
