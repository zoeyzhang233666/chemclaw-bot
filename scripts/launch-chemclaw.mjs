import { spawn, spawnSync } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, watch, writeFileSync } from 'node:fs'
import { dirname, join, matchesGlob, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { launchSource, sourceRevision } from './launch-source.mjs'

const checkout = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const selected = launchSource(checkout, process.argv.slice(2))
const root = selected.source
const revision = sourceRevision(root)
if (process.argv.includes('--info')) {
  console.log(JSON.stringify({ source: root, data: join(selected.origin, '.chemclaw-dev'), workspace: join(selected.origin, '.chemclaw-workspace'), ...revision }, null, 2))
  process.exit(0)
}
if (root !== checkout) {
  const forwarded = spawnSync(process.execPath, [join(root, 'scripts', 'launch-chemclaw.mjs'), ...selected.args], {
    cwd: root, env: { ...process.env, CHEMCLAW_LAUNCH_HOME: selected.origin }, stdio: 'inherit', windowsHide: true,
  })
  if (forwarded.error) console.error(forwarded.error.message)
  process.exit(forwarded.status ?? 1)
}
const plugin = join(root, 'chemclaw-bot')
const app = join(root, 'app')
const environment = { ...process.env }
delete environment.ELECTRON_RUN_AS_NODE
function run(args, cwd) {
  // These are fixed npm arguments; invoke cmd explicitly without Node's shell concatenation.
  if (args.some(arg => !/^[\w./-]+$/u.test(arg))) throw new Error('Invalid npm argument')
  const command = process.platform === 'win32' ? process.env.ComSpec || 'cmd.exe' : 'npm'
  const commandArgs = process.platform === 'win32' ? ['/d', '/s', '/c', `npm.cmd ${args.join(' ')}`] : args
  const result = spawnSync(command, commandArgs, { cwd, env: environment, stdio: 'inherit', windowsHide: true })
  if (result.status !== 0) throw new Error(`npm ${args.join(' ')} failed. Check network access and use Node.js 24 LTS.`)
}
if (!existsSync(join(plugin, 'node_modules/esbuild'))) run(['ci'], plugin)
if (!existsSync(join(app, 'node_modules/electron/dist/electron.exe')) && process.platform === 'win32') run(['ci'], app)
const dependencyStamp = join(app, 'node_modules', '.chemclaw-dependencies.json')
const expectedDependencies = JSON.stringify(JSON.parse(readFileSync(join(plugin, 'package.json'), 'utf8')).dependencies)
if (!existsSync(dependencyStamp) || readFileSync(dependencyStamp, 'utf8') !== expectedDependencies) {
  run(['install', '../chemclaw-bot', '--ignore-scripts', '--no-audit', '--no-fund'], app)
  writeFileSync(dependencyStamp, expectedDependencies)
}
const target = resolve(app, 'node_modules/chemclaw-bot')
if (target !== join(app, 'node_modules', 'chemclaw-bot') || !target.startsWith(`${app}${sep}`)) throw new Error('Invalid plugin sync target')
function sync() {
  run(['run', 'build'], plugin)
  rmSync(target, { recursive: true, force: true })
  mkdirSync(target, { recursive: true })
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
}
sync()
if (process.argv.includes('--sync-only')) process.exit(0)
const home = join(selected.origin, '.chemclaw-dev')
const workspace = join(selected.origin, '.chemclaw-workspace')
mkdirSync(workspace, { recursive: true })
Object.assign(environment, { DS_BOT_HOME: join(home, 'data'), DS_BOT_WORKSPACE: workspace, DS_BOT_SHELL_DATA: join(home, 'shell') })
Object.assign(environment, { CHEMCLAW_SOURCE_BRANCH: revision.branch, CHEMCLAW_SOURCE_REVISION: `${revision.revision}${revision.modified ? ' + local changes' : ''}` })
const electron = join(app, 'node_modules/electron/dist', process.platform === 'win32' ? 'electron.exe' : process.platform === 'darwin' ? 'Electron.app/Contents/MacOS/Electron' : 'electron')
console.log(`ChemClaw development preview\nSource: ${root}\nBranch: ${revision.branch}\nRevision: ${environment.CHEMCLAW_SOURCE_REVISION}\nDevelopment data: ${home}\nWorkspace: ${workspace}\nStarting the desktop window automatically. Keep this console open while using ChemClaw.`)
const watchers = []
let child
function launch() {
  child = spawn(electron, ['.'], { cwd: app, env: environment, stdio: ['inherit', 'inherit', 'inherit', 'ipc'], windowsHide: false })
  child.once('error', error => {
    console.error(`Cannot start the ChemClaw desktop window: ${error.message}`)
    for (const watcher of watchers) watcher.close()
    process.exitCode = 1
  })
  child.once('exit', code => {
    if (code === 75 && process.argv.includes('--watch')) { launch(); return }
    for (const watcher of watchers) watcher.close()
    process.exitCode = code ?? 0
  })
}
launch()
process.once('SIGINT', () => { child.send({ type: 'chemclaw-dev-quit' }) })
if (process.argv.includes('--watch')) {
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
  for (const path of ['chemclaw-bot/src', 'chemclaw-bot/seed', 'chemclaw-bot/runtime', 'chemclaw-bot/skills', 'app/src']) watchers.push(watch(join(root, path), { recursive: true }, changed))
  console.log('Watching plugin sources. Changes rebuild and restart the isolated Host.')
}
