import { spawn } from 'node:child_process'
import { existsSync, readFileSync, realpathSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { resolveIntegration, writeManifest } from './launch-integrate.mjs'
import { writeSourceSelection } from './launch-picker.mjs'
import { resolveProfile } from './launch-profiles.mjs'
import { ensurePrWorktree, listOpenPullRequests } from './launch-discover.mjs'

const origin = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const node = process.execPath
const launcher = join(origin, 'scripts', 'launch-chemclaw.mjs')

function runInfo() {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(node, [launcher, '--no-picker', '--info'], { cwd: origin, windowsHide: true })
    let out = ''
    child.stdout.on('data', chunk => { out += chunk })
    child.stderr.on('data', chunk => { out += chunk })
    child.on('exit', code => {
      if (code !== 0) reject(new Error(`--info failed (${code}): ${out}`))
      else resolvePromise(JSON.parse(out))
    })
  })
}

function runSyncOnly() {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(node, [launcher, '--no-picker', '--sync-only'], { cwd: origin, stdio: 'inherit', windowsHide: true })
    child.on('exit', code => {
      if (code !== 0) reject(new Error(`--sync-only failed (${code})`))
      else resolvePromise()
    })
  })
}

function launchBriefly(ms = 20000) {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(node, [launcher, '--no-picker'], { cwd: origin, stdio: 'inherit', windowsHide: false })
    const timer = setTimeout(() => {
      try { child.kill() } catch { /* ignore */ }
      resolvePromise({ timedOut: true, pid: child.pid })
    }, ms)
    child.on('error', error => {
      clearTimeout(timer)
      reject(error)
    })
    child.on('exit', code => {
      clearTimeout(timer)
      resolvePromise({ timedOut: false, code, pid: child.pid })
    })
  })
}

function selectMain() {
  const profile = resolveProfile(origin, { kind: 'main' })
  writeSourceSelection(origin, {
    source: origin,
    profile: profile.key,
    selection: { kind: 'main' },
    remoteConfirmed: true,
  })
  return profile
}

function selectIntegration() {
  const integration = resolveIntegration(origin, { included: [64], excluded: [] })
  const manifest = writeManifest(origin, integration)
  const profile = resolveProfile(origin, { kind: 'integration' })
  writeSourceSelection(origin, {
    source: integration.source,
    profile: profile.key,
    selection: { kind: 'integration', included: [64], excluded: [] },
    manifest,
    remoteConfirmed: integration.remoteConfirmed,
  })
  return { integration, profile }
}

function selectPr64() {
  const listed = listOpenPullRequests(origin)
  const pr = (listed.prs || []).find(item => item.number === 64) || {
    number: 64, title: 'multi-session', headRefName: 'feat/bot-multi-session', headRefOid: 'HEAD',
  }
  const ensured = ensurePrWorktree(origin, pr)
  const profile = resolveProfile(origin, { kind: 'pr', number: 64 })
  writeSourceSelection(origin, {
    source: ensured.path,
    profile: profile.key,
    selection: { kind: 'pr', number: 64, branch: pr.headRefName },
    remoteConfirmed: listed.ok,
  })
  return { ensured, profile }
}

function assertIsolation(label, profile, baselineState) {
  const leakedState = existsSync(join(profile.data, 'chemclaw', 'state.json'))
  const leakedCred = existsSync(join(profile.data, '.credentials.yaml'))
  if (profile.isolated && leakedState) throw new Error(`${label}: isolated profile already has state.json before launch`)
  if (profile.isolated && leakedCred) throw new Error(`${label}: isolated profile has credentials without opt-in`)
  if (!existsSync(baselineState)) throw new Error('baseline state.json missing — cannot prove preservation')
  console.log(`OK isolation ${label}: baseline intact, profile empty of state/credentials`)
}

const baselineState = join(origin, '.chemclaw-dev', 'data', 'chemclaw', 'state.json')
const baselineBefore = existsSync(baselineState) ? readFileSync(baselineState) : null

console.log('=== 1) integration resolve + info + sync ===')
const integration = selectIntegration()
assertIsolation('integration', integration.profile, baselineState)
const integrationInfo = await runInfo()
console.log(integrationInfo)
if (!String(integrationInfo.source).toLowerCase().includes('batch2-multisession')) {
  throw new Error(`integration should reuse batch2 worktree, got ${integrationInfo.source}`)
}
if (integrationInfo.profile !== 'integration') throw new Error('integration profile mismatch')
await runSyncOnly()

console.log('=== 2) brief integration launch ===')
const integrationLaunch = await launchBriefly(25000)
console.log(integrationLaunch)

console.log('=== 3) main info + sync + brief launch ===')
const mainProfile = selectMain()
const mainInfo = await runInfo()
console.log(mainInfo)
if (realpathSync(mainInfo.source) !== realpathSync(origin)) throw new Error('main source mismatch')
if (mainInfo.profile !== 'baseline') throw new Error('main should use baseline profile')
await runSyncOnly()
const mainLaunch = await launchBriefly(25000)
console.log(mainLaunch)

console.log('=== 4) PR #64 info + sync + brief launch ===')
const pr = selectPr64()
assertIsolation('pr-64', pr.profile, baselineState)
const prInfo = await runInfo()
console.log(prInfo)
if (prInfo.profile !== 'pr-64') throw new Error('pr profile mismatch')
await runSyncOnly()
const prLaunch = await launchBriefly(25000)
console.log(prLaunch)

if (baselineBefore && Buffer.compare(baselineBefore, readFileSync(baselineState)) !== 0) {
  throw new Error('baseline state.json changed during PR/integration previews')
}
console.log('OK baseline state.json unchanged after all previews')

mkdirSync(join(origin, '.chemclaw-dev'), { recursive: true })
writeFileSync(join(origin, '.chemclaw-dev', 'launcher-verify.json'), JSON.stringify({
  ok: true,
  integrationInfo,
  mainInfo,
  prInfo,
  at: new Date().toISOString(),
}, null, 2))
console.log('All launcher verifications passed.')
