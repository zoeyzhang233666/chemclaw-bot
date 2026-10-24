// The GUI bench mirrors the app's separate Host process, using only profile APIs.
import { createRequire } from 'node:module'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
const root = resolve(import.meta.dirname, '../..')
const require = createRequire(join(root, 'app/package.json'))
const boot = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh-app-boot')))
const { runProfile } = await import(pathToFileURL(require.resolve('@deepseek-ai/dsh/profile-boot')))
const [dir, port] = process.argv.slice(2)
if (!process.env.DSH_HOME?.includes('.dsh-test-')) throw new Error('Use an isolated test home')
const running = await runProfile({ environment: boot.loadLayeredEnv('dsh'), profile: 'latency', resolvedProfile: { profile: boot.loadProfileDirectory('dsh', dir, join(root, 'app/package.json')), installAnchor: join(root, 'app/package.json') }, args: ['--no-open', '--port', port], patchFiles: [] })
process.on('message', message => { if (message.type === 'shutdown') void running.shutdown.shutdown(0) })
process.once('disconnect', () => { void running.shutdown.shutdown(0) })
running.ctx.on('session/event', (session, event) => {
  process.send?.({ type: 'diagnostic', value: { sessionId: session.id, type: event.type, reason: event.type === 'turn/end' ? event.data.reason?.kind : undefined } })
})
running.ctx.on('agent/status', ({ agent, status }) => process.send?.({ type: 'diagnostic', value: { sessionId: agent.id, status } }))
running.ctx.on('agent/pre-step', async ({ agent }, next) => {
  const at = Date.now()
  process.send?.({ type: 'diagnostic', value: { sessionId: agent.id, phase: 'pre-step-enter' } })
  const decision = await next()
  process.send?.({ type: 'diagnostic', value: { sessionId: agent.id, phase: 'pre-step-exit', elapsedMs: Date.now() - at, decision: decision.kind } })
  return decision
})
running.ctx.on('tools/execute', async (exec, next) => {
  const at = Date.now()
  process.send?.({ type: 'diagnostic', value: { sessionId: exec.agent?.id, phase: 'tool-enter', name: exec.name } })
  try { return await next() }
  finally { process.send?.({ type: 'diagnostic', value: { sessionId: exec.agent?.id, phase: 'tool-exit', name: exec.name, elapsedMs: Date.now() - at } }) }
})
process.send({ type: 'ready', url: running.ctx.get('connection').authenticatedUrl(`http://127.0.0.1:${port}`) })
