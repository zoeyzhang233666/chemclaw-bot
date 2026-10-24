// Anonymous network check in a disposable profile; no model or user credentials.
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const root = resolve(import.meta.dirname, '../..')
const home = join(root, `.dsh-test-search-${Date.now()}`)
mkdirSync(home)
for (const key of Object.keys(process.env)) if (/KEY|TOKEN|PASSWORD|SECRET|DSH_WEB_/i.test(key)) delete process.env[key]
process.env.DSH_HOME = home
const require = createRequire(join(root, 'app/package.json'))
const boot = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-app-boot')))
const { runProfile } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh/profile-boot')))
const dir = join(home, 'profiles/search')
boot.initProfile(dir, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'chemclaw-bot'])
writeFileSync(join(dir, 'cordis.patch.yml'), '- id: chemclaw\n  config:\n    seedTeam: false\n    companyConnectors: false\n    updateCheck: false\n- id: session-log-deepseek\n  disabled: true\n- id: session-telemetry-otel\n  disabled: true\n')
let running
let exitCode = 0
try {
  running = await runProfile({ environment: boot.loadLayeredEnv('dsh'), profile: 'search', resolvedProfile: { profile: boot.loadProfileDirectory('dsh', dir, join(root, 'app/package.json')), installAnchor: join(root, 'app/package.json') }, args: ['--no-open', '--port', '0'], patchFiles: [] })
  const startedAt = Date.now()
  let report
  try {
    const result = await running.ctx.get('web').search({ query: '聚氨酯 MDI 产业链', maxResults: 3 }, AbortSignal.timeout(30_000))
    report = { anonymous: true, elapsedMs: Date.now() - startedAt, sourceCount: result.sources.length, sourceHosts: result.sources.map(source => new URL(source.url).hostname), ok: result.sources.length > 0 }
  } catch (error) {
    report = { anonymous: true, elapsedMs: Date.now() - startedAt, ok: false, code: error.code ?? error.name }
  }
  console.log(JSON.stringify(report))
  writeFileSync(join(root, 'chemclaw/verification/search.json'), JSON.stringify(report, null, 2))
  assert.ok(report.ok, 'Anonymous search must return sources')
} catch (error) { console.error(error.message); exitCode = 1 }
finally { await running?.shutdown.shutdown(exitCode); process.exitCode = exitCode }
