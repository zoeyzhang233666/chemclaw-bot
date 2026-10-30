import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { existsSync, readFileSync, readdirSync, realpathSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'

export function launchSource(checkout, args = [], env = process.env) {
  const origin = realpathSync(resolve(env.CHEMCLAW_LAUNCH_HOME || checkout))
  const at = args.indexOf('--source')
  if (at >= 0 && (!args[at + 1] || args[at + 1].startsWith('--'))) throw new Error('--source needs a ChemClaw checkout path')
  const file = join(origin, '.chemclaw-dev', 'source.json')
  let selected = checkout
  let config = null
  if (at >= 0) selected = resolve(checkout, args[at + 1])
  else if (!env.CHEMCLAW_LAUNCH_HOME && existsSync(file)) {
    config = JSON.parse(readFileSync(file, 'utf8'))
    if (typeof config.source !== 'string' || !config.source.trim()) throw new Error('The local source selection needs a source path')
    selected = resolve(origin, config.source)
  } else if (existsSync(file)) {
    // Forwarded launches keep origin data root but may still want profile/manifest metadata.
    try { config = JSON.parse(readFileSync(file, 'utf8')) } catch { config = null }
  }
  const source = realpathSync(selected)
  for (const [folder, name] of [['app', 'chemclaw'], ['chemclaw-bot', 'chemclaw-bot']]) {
    const manifest = JSON.parse(readFileSync(join(source, folder, 'package.json'), 'utf8'))
    if (manifest.name !== name) throw new Error('The selected folder is not a ChemClaw source checkout')
  }
  if (!existsSync(join(source, 'scripts', 'launch-chemclaw.mjs'))) throw new Error('The selected source has no ChemClaw launcher')
  const forwarded = args.filter((_, index) => at < 0 || (index !== at && index !== at + 1))
  const selection = config?.selection || null
  const manifest = config?.manifest
    || (selection?.kind === 'integration' ? readPreviewManifest(origin) : null)
  return {
    source,
    origin,
    args: forwarded,
    profile: config?.profile || null,
    selection,
    remoteConfirmed: config?.remoteConfirmed,
    manifest,
  }
}

function readPreviewManifest(origin) {
  const file = join(origin, '.chemclaw-dev', 'preview-manifest.json')
  try {
    if (!existsSync(file)) return null
    return JSON.parse(readFileSync(file, 'utf8'))
  } catch {
    return null
  }
}

export function sourceRevision(source) {
  try {
    const git = (...args) => execFileSync('git', ['-C', source, ...args], { encoding: 'utf8', windowsHide: true, stdio: ['ignore', 'pipe', 'ignore'] }).trim()
    return {
      branch: git('branch', '--show-current') || 'detached',
      revision: git('rev-parse', '--short=8', 'HEAD'),
      fullRevision: git('rev-parse', 'HEAD'),
      modified: git('status', '--porcelain', '--untracked-files=no') !== '',
    }
  } catch {
    return { branch: 'source', revision: 'unversioned', fullRevision: 'unversioned', modified: false }
  }
}

// Check the selected source plugin's direct dependencies against the app's *actual*
// modules, not a stamp. A stamp can survive an interrupted or skipped npm install.
function installedVersion(fromPlugin, name) {
  try {
    const pkg = JSON.parse(readFileSync(fromPlugin.resolve(`${name}/package.json`), 'utf8'))
    if (pkg.name === name) return pkg.version
  } catch { /* Some packages do not export package.json. */ }
  let entry
  try { entry = fromPlugin.resolve(name) } catch { return undefined }
  let dir = dirname(entry)
  for (;;) {
    try {
      const pkg = JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8'))
      if (pkg.name === name) return pkg.version
    } catch { /* Walk to the module's package root. */ }
    const parent = dirname(dir)
    if (parent === dir) return undefined
    dir = parent
  }
}

export function missingPluginDependencies(app, dependencies) {
  const fromPlugin = createRequire(join(app, 'node_modules', 'chemclaw-bot', 'package.json'))
  return Object.entries(dependencies).filter(([name, version]) => installedVersion(fromPlugin, name) !== version)
    .map(([name, version]) => `${name}@${version}`)
}

// A PR may change the desktop shell, profile, or dependency lockfile as well as
// the Bot plugin. Reusing main's already-installed app in that case silently
// runs *old desktop code* and gives misleading PR/GenUI test results.
function sameFiles(left, right) {
  if (!existsSync(left) || !existsSync(right)) return !existsSync(left) && !existsSync(right)
  const a = statSync(left)
  const b = statSync(right)
  if (a.isDirectory() !== b.isDirectory()) return false
  if (a.isDirectory()) {
    const first = readdirSync(left).sort()
    const second = readdirSync(right).sort()
    if (first.length !== second.length) return false
    return first.every((name, i) => name === second[i] && sameFiles(join(left, name), join(right, name)))
  }
  if (!a.isFile() || !b.isFile()) return false
  return a.size === b.size && readFileSync(left).equals(readFileSync(right))
}

function needsSelectedApp(sourceApp, entryApp) {
  if (resolve(sourceApp) === resolve(entryApp)) return false
  return ['src', 'scripts', 'package.json', 'package-lock.json', 'electron-builder.yml'].some(
    path => !sameFiles(join(sourceApp, path), join(entryApp, path)),
  )
}

export function resolveAppHost(sourceRoot, origin) {
  const sourceAppPath = join(sourceRoot, 'app')
  const entryAppPath = join(origin, 'app')
  const rel = process.platform === 'win32'
    ? 'node_modules/electron/dist/electron.exe'
    : process.platform === 'darwin'
      ? 'node_modules/electron/dist/Electron.app/Contents/MacOS/Electron'
      : 'node_modules/electron/dist/electron'
  if (needsSelectedApp(sourceAppPath, entryAppPath)) {
    // The launcher installs Electron here once if this preview app has none.
    return { app: sourceAppPath, host: 'selected-source-app-changed' }
  }
  if (existsSync(join(sourceAppPath, rel))) return { app: sourceAppPath, host: 'selected-source' }
  if (existsSync(join(entryAppPath, rel))) return { app: entryAppPath, host: 'entry-reuse-identical-app' }
  return { app: sourceAppPath, host: 'selected-source' }
}


// Electron's npm package can exist without the downloaded runtime binary when
// install scripts were skipped or a previous download failed. Repeating npm ci
// on every launch is expensive and still may not download electron.exe.
export function ensureElectronRuntime(app, executableRelativePath, { installDependencies, installBinary }) {
  const executable = join(app, executableRelativePath)
  if (existsSync(executable)) return { repaired: false, path: executable }
  const installer = join(app, 'node_modules', 'electron', 'install.js')
  if (!existsSync(installer)) {
    console.log('Electron npm package missing; installing app dependencies once.')
    installDependencies()
  }
  if (!existsSync(installer)) {
    throw new Error(`Electron package installer is missing from ${app}. Restore app/node_modules/electron before launching.`)
  }
  if (!existsSync(executable)) {
    console.log('Electron npm package is present but its runtime binary is missing; running the official Electron install script without reinstalling npm packages.')
    installBinary(installer)
  }
  if (!existsSync(executable)) {
    throw new Error(`Electron executable was not installed: ${executable}. Check Electron download/network/proxy settings. npm ci is not required again if node_modules/electron/install.js exists.`)
  }
  return { repaired: true, path: executable }
}
