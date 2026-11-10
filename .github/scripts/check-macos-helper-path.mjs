import assert from 'node:assert/strict'
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, renameSync, statSync, writeFileSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { homedir } from 'node:os'
import { basename, dirname, isAbsolute, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { setTimeout as sleep } from 'node:timers/promises'

const modes = new Set(['normal', 'quit-move', 'live-move'])
const expectedUUID = '4c4c44be-5555-3144-a1e3-83408f6c571f'

export function inside(root, path) {
  const target = resolve(root, path)
  const part = relative(resolve(root), target)
  assert.ok(part && part !== '..' && !part.startsWith('../') && !part.startsWith('..\\') && !isAbsolute(part), 'Path must stay below audit root')
  return target
}

export async function probe(evaluate, port) {
  const { existsSync, renameSync, writeFileSync } = await import('node:fs')
  const { randomUUID } = await import('node:crypto')
  const { setTimeout: pause } = await import('node:timers/promises')
  const config = JSON.parse(process.env.CHEMCLAW_HELPER_CONFIG)
  const state = { mode: config.mode, stage: 'before-probe', completed: [], appAtStart: config.appFrom }
  const save = () => writeFileSync(config.checkpoint, JSON.stringify(state, null, 2) + '\n')
  save()
  if (config.mode === 'live-move') {
    if (!existsSync(config.appFrom) || existsSync(config.appTo)) throw new Error('Unexpected move fixture state')
    renameSync(config.appFrom, config.appTo)
    state.stage = 'moved-while-running'
    save()
  }
  const bot = 'session-00000000-0000-4000-8000-000000000001'
  const bridge = 'window.dsBotApp.browser.views.'
  for (let turn = 0; turn < 4; turn++) {
    const tab = randomUUID()
    const first = 'http://127.0.0.1:' + port + '/?case=' + turn
    const second = 'http://localhost:' + port + '/?case=' + turn
    state.stage = 'create-' + turn
    save()
    await evaluate(bridge + 'create(' + [bot, tab, first].map(value => JSON.stringify(value)).join(',') + ')')
    for (const url of [first, second]) {
      state.stage = 'navigate-' + turn + '-' + new URL(url).hostname
      save()
      // Creation already starts the first load; await its content before cross-site navigation.
      if (url !== first) await evaluate(bridge + 'navigate(' + [bot, tab, url].map(value => JSON.stringify(value)).join(',') + ')')
      const end = Date.now() + 15000
      let body = '', lastError
      while (Date.now() < end) {
        try {
          body = await evaluate(bridge + 'read(' + [bot, tab, 'document.body.innerText'].map(value => JSON.stringify(value)).join(',') + ')')
          if (String(body).includes('企业资料查询测试')) break
        } catch (error) { lastError = error.message }
        await pause(100)
      }
      if (!String(body).includes('企业资料查询测试')) throw new Error('Synthetic browser body missing: ' + (lastError || String(body)))
      state.completed.push({ turn, hostname: new URL(url).hostname })
      save()
    }
    await evaluate(bridge + 'close(' + [bot, tab].map(value => JSON.stringify(value)).join(',') + ')')
  }
  state.stage = 'probe-complete'
  save()
  console.log('helper-path-audit: ' + JSON.stringify(state))
}

export function instrument(source) {
  const patch = (before, after) => {
    assert.equal(source.split(before).length, 2, 'Unexpected checker anchor: ' + before.slice(0, 65))
    source = source.replace(before, after)
  }
  patch("  console.log('check-packed: browser tool, native bridge, takeover and give-back passed')",
    "  console.log('check-packed: browser tool, native bridge, takeover and give-back passed')\n  await (" + probe.toString() + ')(evaluate, browserFixture.address().port)')
  patch('  children.push(app)', '  children.push(app)\n  writeFileSync(JSON.parse(process.env.CHEMCLAW_HELPER_CONFIG).owned, JSON.stringify({ pid: app.pid, executable: packedApp }))')
  patch("const graphics = process.env.CHEMCLAW_HTML_GRAPHICS === 'software' ? ['--disable-gpu'] : []", 'const graphics = []')
  patch('    }, 90_000)', '    }, 15_000)')
  const detailAnchor = "    await until(\"document.querySelector('.bt-skill-library .bt-skill-detail')\", 'the skill details panel')"
  patch(detailAnchor, detailAnchor + "\n    await until(\"Boolean(document.querySelector('.bt-skill-detail .bt-skill-purpose')?.textContent.trim())\", 'the populated skill purpose')")
  return source
}

export function crashSignature(crash, pid) {
  if (crash.pid !== pid || crash.procName !== 'ChemClaw') return false
  const thread = crash.threads?.[crash.faultingThread]
  const first = thread?.frames?.[0]
  const image = crash.usedImages?.[first?.imageIndex]
  return crash.exception?.signal === 'SIGTRAP' && first?.imageOffset === 46270992 && image?.uuid?.toLowerCase() === expectedUUID
}

function run(command, args, env, cwd, logPath) {
  return new Promise((done, reject) => {
    const child = spawn(command, args, { env, cwd, stdio: ['ignore', 'pipe', 'pipe'] })
    let output = ''
    const accept = chunk => { const text = String(chunk); output += text; process.stdout.write(text) }
    child.stdout.on('data', accept)
    child.stderr.on('data', accept)
    child.on('error', reject)
    child.on('close', (code, signal) => {
      writeFileSync(logPath, output)
      done({ code, signal, output })
    })
  })
}

async function crashes(pid, started, outputDir) {
  const folder = join(homedir(), 'Library', 'Logs', 'DiagnosticReports')
  const found = []
  for (let attempt = 0; attempt < 8; attempt++) {
    for (const name of existsSync(folder) ? readdirSync(folder) : []) {
      if (!name.startsWith('ChemClaw') || !name.endsWith('.ips') || found.some(x => x.name === name)) continue
      const path = join(folder, name)
      const stat = statSync(path)
      if (stat.mtimeMs < started || stat.size > 4 * 1024 * 1024) continue
      const text = readFileSync(path, 'utf8')
      let crash
      try { crash = JSON.parse(text.slice(text.indexOf('\n') + 1)) } catch { continue }
      if (crash.pid !== pid) continue
      writeFileSync(join(outputDir, basename(name)), text)
      found.push({ name, matching: crashSignature(crash, pid), exception: crash.exception, path: crash.procPath })
    }
    if (found.length) break
    await sleep(1000)
  }
  return found
}

export async function main() {
  assert.equal(process.platform, 'darwin', 'Native fault experiment requires an approved macOS runner')
  assert.equal(process.arch, 'arm64')
  const [mode, appInput, checkerInput, rootInput] = process.argv.slice(2)
  assert.ok(modes.has(mode), 'Unknown audit mode')
  const root = resolve(rootInput), input = resolve(appInput), checker = resolve(checkerInput)
  assert.equal(basename(input), 'ChemClaw.app')
  assert.ok(existsSync(input) && existsSync(checker))
  assert.ok(root.startsWith(resolve(process.env.RUNNER_TEMP) + '/'), 'Use only runner temporary data')
  assert.ok(!existsSync(root), 'Never overwrite an earlier experiment')
  mkdirSync(root, { recursive: true })
  const from = inside(root, 'A/ChemClaw.app'), to = inside(root, 'B/ChemClaw.app')
  mkdirSync(dirname(from)); mkdirSync(dirname(to))
  cpSync(input, from, { recursive: true, verbatimSymlinks: true })
  const instrumented = join(dirname(checker), 'check-packed-helper-path.mjs')
  assert.ok(!existsSync(instrumented), 'Keep checker copies distinct')
  writeFileSync(instrumented, instrument(readFileSync(checker, 'utf8')))
  const summary = { mode, status: 'started', completedAt: null, productFixed: false, nativeFaultSignatureMatched: false, runs: [] }
  const save = () => writeFileSync(join(root, 'summary.json'), JSON.stringify(summary, null, 2) + '\n')
  save()
  const execute = async (appPath, phase, actualMode) => {
    const out = inside(root, phase)
    mkdirSync(out)
    const temporary = join(out, 'tmp'), unused = join(out, 'unused-user-dsh')
    mkdirSync(temporary); mkdirSync(unused)
    const config = { mode: actualMode, appFrom: appPath, appTo: to, checkpoint: join(out, 'checkpoint.json'), owned: join(out, 'owned-process.json') }
    const env = { ...process.env, CHEMCLAW_HELPER_CONFIG: JSON.stringify(config), TMPDIR: temporary, DSH_HOME: unused, DS_BOT_USER_DSH_HOME: unused }
    for (const key of Object.keys(env)) if (/KEY|TOKEN|PASSWORD|SECRET/i.test(key)) delete env[key]
    const began = Date.now()
    const runResult = await run(process.execPath, [instrumented, join(appPath, 'Contents/MacOS/ChemClaw'), join(out, 'screen'), '--mac-ui'], env, out, join(out, 'test.log'))
    const owned = existsSync(config.owned) ? JSON.parse(readFileSync(config.owned, 'utf8')) : {}
    const native = owned.pid && runResult.code !== 0 ? await crashes(owned.pid, began, out) : []
    const checkpoint = existsSync(config.checkpoint) ? JSON.parse(readFileSync(config.checkpoint, 'utf8')) : null
    const record = { phase, checkerExit: runResult.code, checkerSignal: runResult.signal, checkpoint, native, exactCrash: native.some(x => x.matching) }
    summary.runs.push(record)
    summary.nativeFaultSignatureMatched ||= record.exactCrash
    save()
    return record
  }
  try {
    if (mode === 'quit-move') {
      const warm = await execute(from, 'warm', 'normal')
      assert.equal(warm.checkerExit, 0, 'Warm run must finish and quit before moving')
      const owned = JSON.parse(readFileSync(join(root, 'warm/owned-process.json'), 'utf8'))
      let live = false
      try { process.kill(owned.pid, 0); live = true } catch {}
      assert.equal(live, false, 'Warm app still running; do not move')
      renameSync(from, to)
    }
    const result = await execute(mode === 'quit-move' ? to : from, 'measured', mode === 'live-move' ? 'live-move' : 'normal')
    summary.status = result.exactCrash ? 'matching-native-crash' : result.checkerExit === 0 ? 'no-crash-observed' : 'other-failure'
    if (result.checkerExit !== 0) process.exitCode = 1
  } catch (error) {
    summary.status = 'harness-or-prerequisite-failure'
    summary.error = error.message
    process.exitCode = 1
  } finally {
    summary.completedAt = new Date().toISOString()
    save()
    console.log('helper-path-audit summary: ' + JSON.stringify(summary))
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main()

