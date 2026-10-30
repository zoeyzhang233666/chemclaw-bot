import { spawn, spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { cpSync, existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, watch, writeFileSync } from 'node:fs'
import { dirname, join, matchesGlob, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { launchSource, missingPluginDependencies, sourceRevision } from './launch-source.mjs'
import { resolveProfile } from './launch-profiles.mjs'
import { runPicker, shouldShowPicker } from './launch-picker.mjs'

const checkout = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const argv = process.argv.slice(2)

if (shouldShowPicker(argv) && !process.env.CHEMCLAW_LAUNCH_HOME) {
  const picked = runPicker(checkout)
  for (const note of picked.notes || []) console.log(`Note: ${note}`)
}

const selected = launchSource(checkout, argv)
const root = selected.source
const revision = sourceRevision(root)
const selection = selected.selection || (
  selected.profile && selected.profile !== 'baseline'
    ? { kind: selected.profile.startsWith('pr-') ? 'pr' : selected.profile, number: Number(String(selected.profile).replace(/^pr-/, '')), profile: selected.profile }
    : { kind: 'main' }
)
const effectiveProfile = resolveProfile(selected.origin, selection, { copyCredentials: false })

function resolveAppHost(sourceRoot, origin) {
  const sourceAppPath = join(sourceRoot, 'app')
  const entryAppPath = join(origin, 'app')
  const rel = process.platform === 'win32'
    ? 'node_modules/electron/dist/electron.exe'
    : process.platform === 'darwin'
      ? 'node_modules/electron/dist/Electron.app/Contents/MacOS/Electron'
      : 'node_modules/electron/dist/electron'
  if (existsSync(join(sourceAppPath, rel))) return { app: sourceAppPath, host: 'selected-source' }
  if (existsSync(join(entryAppPath, rel))) return { app: entryAppPath, host: 'entry-reuse' }
  return { app: sourceAppPath, host: 'selected-source' }
}

if (argv.includes('--info')) {
  const host = resolveAppHost(root, selected.origin)
  console.log(JSON.stringify({
    source: root,
    branch: revision.branch,
    revision: revision.revision,
    fullRevision: revision.fullRevision,
    modified: revision.modified,
    remoteConfirmed: selected.remoteConfirmed,
    profile: effectiveProfile.key,
    data: effectiveProfile.data,
    shell: effectiveProfile.shell,
    workspace: effectiveProfile.workspace,
    isolated: effectiveProfile.isolated,
    app: host.app,
    appHost: host.host,
    included: selected.manifest?.included || null,
    manifest: selected.manifest || null,
  }, null, 2))
  process.exit(0)
}

// Build the selected source plugin. Prefer that tree's app when Electron is
// already installed there; otherwise reuse the entry checkout app to avoid a
// full npm ci on every PR worktree.
const plugin = join(root, 'chemclaw-bot')
const sourceApp = join(root, 'app')
const hostInfo = resolveAppHost(root, selected.origin)
const app = hostInfo.app
const appHost = hostInfo.host
const electronRel = process.platform === 'win32'
  ? 'node_modules/electron/dist/electron.exe'
  : process.platform === 'darwin'
    ? 'node_modules/electron/dist/Electron.app/Contents/MacOS/Electron'
    : 'node_modules/electron/dist/electron'
const environment = { ...process.env }
delete environment.ELECTRON_RUN_AS_NODE
environment.CHEMCLAW_LAUNCH_HOME = selected.origin
environment.CHEMCLAW_NO_PICKER = '1'

function run(args, cwd) {
  const command = process.platform === 'win32' ? process.env.ComSpec || 'cmd.exe' : 'npm'
  const quoted = args.map(arg => /[\s&<>|^"]/u.test(arg) ? `"${arg.replaceAll('"', '')}"` : arg).join(' ')
  const commandArgs = process.platform === 'win32' ? ['/d', '/s', '/c', `npm.cmd ${quoted}`] : args
  const result = spawnSync(command, commandArgs, { cwd, env: environment, stdio: 'inherit', windowsHide: true })
  if (result.status !== 0) throw new Error(`npm ${args.join(' ')} failed. Check network access and use Node.js 24 LTS.`)
}

function hashPaths(paths) {
  const hash = createHash('sha256')
  for (const path of paths) {
    if (!existsSync(path)) continue
    const st = statSync(path)
    if (st.isDirectory()) {
      for (const name of readdirSync(path).sort()) hash.update(hashPaths([join(path, name)]))
    } else {
      hash.update(path)
      hash.update(String(st.mtimeMs))
      hash.update(String(st.size))
    }
  }
  return hash.digest('hex')
}

const dependencyStamp = join(app, 'node_modules', '.chemclaw-dependencies.json')
const syncStampPath = join(app, 'node_modules', '.chemclaw-sync-stamp.json')
const pluginDependencies = JSON.parse(readFileSync(join(plugin, 'package.json'), 'utf8')).dependencies
const expectedDependencies = JSON.stringify(pluginDependencies)
const sourceFingerprint = hashPaths([
  join(plugin, 'src'),
  join(plugin, 'seed'),
  join(plugin, 'skills'),
  join(plugin, 'runtime'),
  join(plugin, 'package.json'),
  join(plugin, 'index.js'),
  join(plugin, 'web-search.js'),
  join(sourceApp, 'src'),
  join(sourceApp, 'package.json'),
])

const entryPlugin = join(selected.origin, 'chemclaw-bot')
if (!existsSync(join(plugin, 'node_modules/esbuild'))) {
  if (existsSync(join(entryPlugin, 'node_modules/esbuild'))) {
    // Build using the selected sources but the entry tree's esbuild binary via npm run
    // still needs local node_modules; fall back to a one-time ci in the selected plugin.
    console.log(`Installing build tools in selected plugin: ${plugin}`)
    run(['ci'], plugin)
  } else {
    run(['ci'], plugin)
  }
}
if (!existsSync(join(app, electronRel))) {
  console.log(`Electron missing in ${app} — running npm ci (one-time for this app host)`)
  run(['ci'], app)
}
// Avoid reinstalling the whole plugin graph when switching preview sources. The
 // sync() step replaces node_modules/chemclaw-bot contents from the selected tree.
const stampOk = existsSync(dependencyStamp) && readFileSync(dependencyStamp, 'utf8') === expectedDependencies
const pluginLinked = existsSync(join(app, 'node_modules', 'chemclaw-bot', 'package.json'))
if (!pluginLinked) {
  const installSpec = app === sourceApp ? '../chemclaw-bot' : plugin
  console.log(`Linking plugin into app host via npm install (${installSpec})`)
  run(['install', installSpec, '--no-save', '--package-lock=false', '--install-links', '--ignore-scripts', '--no-audit', '--no-fund'], app)
}

const target = resolve(app, 'node_modules/chemclaw-bot')
if (target !== join(app, 'node_modules', 'chemclaw-bot') || !target.startsWith(`${app}${sep}`)) throw new Error('Invalid plugin sync target')

function sync() {
  run(['run', 'build'], plugin)
  // npm may nest conflicting versions under this plugin. Preserve those modules
  // while replacing the synchronized source files; deleting them broke upgrades.
  // A first-time npm file: install can be a symlink: unlink it, never remove its
  // contents (which may point into the user's source checkout).
  if (existsSync(target) && lstatSync(target).isSymbolicLink()) rmSync(target, { force: true })
  mkdirSync(target, { recursive: true })
  for (const entry of readdirSync(target)) {
    if (entry !== 'node_modules') rmSync(join(target, entry), { recursive: true, force: true })
  }
  const manifest = JSON.parse(readFileSync(join(plugin, 'package.json'), 'utf8'))
  const excluded = manifest.files.filter(path => path.startsWith('!')).map(path => path.slice(1))
  const include = source => {
    const path = relative(plugin, source).split(sep).join('/')
    return !excluded.some(pattern => matchesGlob(path, pattern) || (pattern.endsWith('/**') && path === pattern.slice(0, -3)))
  }
  for (const path of ['package.json', ...manifest.files.filter(path => !path.startsWith('!'))]) {
    const source = join(plugin, path)
    if (existsSync(source)) cpSync(source, join(target, path), { recursive: true, filter: include })
  }
  writeFileSync(syncStampPath, JSON.stringify({
    source: root,
    revision: revision.fullRevision,
    modified: revision.modified,
    fingerprint: sourceFingerprint,
    syncedAt: new Date().toISOString(),
  }))
}

let previousStamp = null
try { previousStamp = JSON.parse(readFileSync(syncStampPath, 'utf8')) } catch { previousStamp = null }
const canReuse = previousStamp
  && previousStamp.source === root
  && previousStamp.revision === revision.fullRevision
  && previousStamp.modified === revision.modified
  && previousStamp.fingerprint === sourceFingerprint
  && existsSync(join(target, 'package.json'))
  && existsSync(join(plugin, 'client.js'))

if (canReuse) console.log('Source fingerprint unchanged — reusing existing plugin build sync.')
else sync()

// Audit *after* source sync: npm can put conflicting pinned dependencies inside
// node_modules/chemclaw-bot, so a sync must never erase the only installed copy.
// An existing stamp is not proof that a dependency really exists (GenUI #79).
const OPTIONAL_VISUAL_DEP = '@changfenhuang/dsh-genui'
const missing = missingPluginDependencies(app, pluginDependencies)
if (missing.length) {
  console.log(`Installing missing ChemClaw dependencies: ${missing.join(', ')}`)
  try {
    run(['install', '--no-save', '--package-lock=false', '--install-links', '--ignore-scripts', '--no-audit', '--no-fund', ...missing], app)
  } catch (error) {
    // GenUI is optional. An unavailable npm registry should not take away
    // the user's working Bot chat and existing show_view charts.
    if (missing.some(spec => !spec.startsWith(`${OPTIONAL_VISUAL_DEP}@`))) throw error
    console.warn('ChemClaw: optional GenUI install failed; launching with original charts:', error.message)
  }
  // npm may refresh a file: dependency; restore the selected source tree
  // while keeping nested dependency folders intact.
  sync()
}
const unresolved = missingPluginDependencies(app, pluginDependencies)
const blocking = unresolved.filter(spec => !spec.startsWith(`${OPTIONAL_VISUAL_DEP}@`))
if (blocking.length) throw new Error(`ChemClaw required dependencies remain unavailable: ${blocking.join(', ')}. Check npm/network access.`)
if (unresolved.length) console.warn(`ChemClaw: optional GenUI is not installed (${unresolved.join(', ')}); existing chat and charts remain available.`)
if (!stampOk || !pluginLinked || missing.length) writeFileSync(dependencyStamp, expectedDependencies)
console.log(!unresolved.length && missing.length ? 'ChemClaw plugin dependencies repaired.' : 'App host checked — existing features preserved.')

if (argv.includes('--sync-only')) process.exit(0)

mkdirSync(effectiveProfile.workspace, { recursive: true })
mkdirSync(effectiveProfile.data, { recursive: true })
mkdirSync(effectiveProfile.shell, { recursive: true })
Object.assign(environment, {
  DS_BOT_HOME: effectiveProfile.data,
  DS_BOT_WORKSPACE: effectiveProfile.workspace,
  DS_BOT_SHELL_DATA: effectiveProfile.shell,
  CHEMCLAW_SOURCE_BRANCH: revision.branch,
  CHEMCLAW_SOURCE_REVISION: `${revision.revision}${revision.modified ? ' + local changes' : ''}${selected.remoteConfirmed === false ? ' (not confirmed remote-latest)' : ''}`,
  CHEMCLAW_PROFILE_KEY: effectiveProfile.key,
})

const electron = join(app, 'node_modules/electron/dist', process.platform === 'win32' ? 'electron.exe' : process.platform === 'darwin' ? 'Electron.app/Contents/MacOS/Electron' : 'electron')
const pidFile = join(selected.origin, '.chemclaw-dev', 'launcher-electron.json')
stopOwnedElectron(pidFile, root)

const included = selected.manifest?.included || []
const includedLine = included.length
  ? included.map(pr => `#${pr.number} ${pr.branch}@${pr.sha}`).join(', ')
  : '(none / main only)'

console.log([
  'ChemClaw development preview',
  `Source: ${root}`,
  `Branch: ${revision.branch}`,
  `Revision: ${environment.CHEMCLAW_SOURCE_REVISION}`,
  `Full SHA: ${revision.fullRevision}`,
  `App host: ${app} (${appHost})`,
  `Profile: ${effectiveProfile.key}${effectiveProfile.isolated ? ' (isolated)' : ' (baseline)'}`,
  `Development data: ${effectiveProfile.data}`,
  `Shell data: ${effectiveProfile.shell}`,
  `Workspace: ${effectiveProfile.workspace}`,
  `Included PRs: ${includedLine}`,
  `Plugin sync: ${canReuse ? 'reused' : 'rebuilt'} → ${target}`,
  'Starting the desktop window automatically. Keep this console open while using ChemClaw.',
].join('\n'))

const watchers = []
let child
function launch() {
  child = spawn(electron, ['.'], {
    cwd: app,
    env: environment,
    stdio: ['inherit', 'inherit', 'inherit', 'ipc'],
    windowsHide: false,
  })
  writeFileSync(pidFile, JSON.stringify({
    pid: child.pid,
    source: root,
    app,
    token: `chemclaw-launcher:${root}`,
    profile: effectiveProfile.key,
    startedAt: new Date().toISOString(),
  }))
  child.once('error', error => {
    console.error(`Cannot start the ChemClaw desktop window: ${error.message}`)
    clearPid(pidFile, child.pid)
    for (const watcher of watchers) watcher.close()
    process.exitCode = 1
  })
  child.once('exit', code => {
    clearPid(pidFile, child.pid)
    if (code === 75 && argv.includes('--watch')) { launch(); return }
    for (const watcher of watchers) watcher.close()
    process.exitCode = code ?? 0
  })
}
launch()
process.once('SIGINT', () => { try { child.send({ type: 'chemclaw-dev-quit' }) } catch { /* ignore */ } })
if (argv.includes('--watch')) {
  let timer
  let running = false
  const changed = () => {
    clearTimeout(timer)
    timer = setTimeout(() => {
      if (running) return
      running = true
      try { sync(); child.send({ type: 'chemclaw-dev-reload' }) } catch (error) { console.error(error.message) } finally { running = false }
    }, 500)
  }
  for (const path of ['chemclaw-bot/src', 'chemclaw-bot/seed', 'chemclaw-bot/runtime', 'chemclaw-bot/skills', 'app/src']) {
    watchers.push(watch(join(root, path), { recursive: true }, changed))
  }
  console.log('Watching plugin sources. Changes rebuild and restart the isolated Host.')
}

function clearPid(file, pid) {
  try {
    if (!existsSync(file)) return
    const info = JSON.parse(readFileSync(file, 'utf8'))
    if (info.pid === pid) rmSync(file, { force: true })
  } catch { /* ignore */ }
}

function stopOwnedElectron(file, source) {
  try {
    if (!existsSync(file)) return
    const info = JSON.parse(readFileSync(file, 'utf8'))
    if (!info?.pid || info.source !== source) return
    if (process.platform === 'win32') {
      const probe = spawnSync('powershell.exe', [
        '-NoProfile', '-Command',
        `$p = Get-CimInstance Win32_Process -Filter "ProcessId = ${Number(info.pid)}"; if ($null -eq $p) { exit 2 }; if ($p.CommandLine -notlike '*${info.app.replaceAll("'", "''")}*') { exit 3 }; Stop-Process -Id ${Number(info.pid)} -Force; exit 0`,
      ], { windowsHide: true, encoding: 'utf8' })
      if (probe.status === 0) console.log(`Stopped previous launcher-owned Electron pid ${info.pid}`)
    } else {
      try { process.kill(info.pid, 'SIGTERM') } catch { /* ignore */ }
    }
    rmSync(file, { force: true })
  } catch { /* ignore */ }
}
