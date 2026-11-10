import assert from 'node:assert/strict'
import { mkdtemp, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { setTimeout as delay } from 'node:timers/promises'
import { HostProcess } from '../src/host-process.mjs'

test('a silent owned mock Host times out once and is shut down', async t => {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-host-deadline-'))
  await writeFile(join(home, 'office-kit-loader.mjs'), '')
  await writeFile(join(home, 'host.mjs'), "process.on('message', m => { if (m.type === 'shutdown') process.exit(0) })")
  const failures = []
  const host = new HostProcess({ entry: join(home, 'host.mjs'), cwd: home, env: process.env, pnpm: 'mock', startupTimeoutMs: 100, onFailure: error => failures.push(error) })
  t.after(async () => { await host.stop(); await rm(home, { recursive: true, force: true, maxRetries: 5 }) })
  await assert.rejects(host.start(), /startup deadline/)
  await host.stop()
  assert.equal(failures.length, 1)
})

test('force-killing only the test-owned ready Host reports one failure and cleanup remains safe', async t => {
  const home = await mkdtemp(join(tmpdir(), 'chemclaw-host-owned-'))
  await writeFile(join(home, 'office-kit-loader.mjs'), '')
  await writeFile(join(home, 'host.mjs'), "process.on('message', m => { if (m.type === 'shutdown') process.exit(0) }); process.send({ type: 'ready', url: 'http://127.0.0.1:1/', injections: [] }); process.send({ type: 'owned-pid', pid: process.pid })")
  const failures = []
  const host = new HostProcess({ entry: join(home, 'host.mjs'), cwd: home, env: process.env, pnpm: 'mock', onFailure: error => failures.push(error) })
  t.after(async () => { await host.stop(); await rm(home, { recursive: true, force: true, maxRetries: 5 }) })
  let pid
  host.onMessage(message => { if (message?.type === 'owned-pid') pid = message.pid })
  await host.start()
  const until = Date.now() + 3000
  while (!pid && Date.now() < until) await delay(10)
  assert.ok(Number.isInteger(pid) && pid !== process.pid)
  process.kill(pid, 'SIGKILL')
  while (failures.length === 0 && Date.now() < until) await delay(10)
  assert.equal(failures.length, 1)
  await host.stop()
  assert.match(failures[0].message, /DSH Host stopped/)
})
