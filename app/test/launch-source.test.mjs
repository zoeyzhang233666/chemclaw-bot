import { execFileSync } from 'node:child_process'
import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, mkdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { ensureElectronRuntime, launchSource, missingPluginDependencies, resolveAppHost } from '../../scripts/launch-source.mjs'
import { ensurePrWorktree, syncSelectedMain } from '../../scripts/launch-discover.mjs'

test('an explicit source wins and forwarded launches keep the original data root without following another selection', t => {
  const dir = mkdtempSync(join(tmpdir(), 'chemclaw-launch-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const make = name => {
    const root = join(dir, name)
    for (const [folder, pkg] of [['app', 'chemclaw'], ['chemclaw-bot', 'chemclaw-bot']]) {
      mkdirSync(join(root, folder), { recursive: true })
      writeFileSync(join(root, folder, 'package.json'), JSON.stringify({ name: pkg }))
    }
    mkdirSync(join(root, 'scripts'))
    writeFileSync(join(root, 'scripts', 'launch-chemclaw.mjs'), '')
    return realpathSync(root)
  }
  const original = make('original')
  const preview = make('preview')
  mkdirSync(join(original, '.chemclaw-dev'))
  writeFileSync(join(original, '.chemclaw-dev', 'source.json'), JSON.stringify({ source: preview }))
  assert.equal(launchSource(original, [], {}).source, preview)
  const explicit = launchSource(original, ['--watch', '--source', original, '--sync-only'], {})
  assert.equal(explicit.source, original)
  assert.deepEqual(explicit.args, ['--watch', '--sync-only'])
  const forwarded = launchSource(preview, [], { CHEMCLAW_LAUNCH_HOME: original })
  assert.equal(forwarded.source, preview)
  assert.equal(forwarded.origin, original)
  assert.throws(() => launchSource(original, ['--source'], {}), /needs a ChemClaw/)
  writeFileSync(join(original, '.chemclaw-dev', 'source.json'), '{"source":"missing"}')
  assert.throws(() => launchSource(original, [], {}), /ENOENT/)
  assert.equal(launchSource(original, ['--source', preview], {}).source, preview)
})


test('dependency audit catches missing and stale bundles even when a previous stamp says ready', t => {
  const dir = mkdtempSync(join(tmpdir(), 'chemclaw-deps-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const name = '@changfenhuang/dsh-genui'
  const packageDir = join(dir, 'node_modules', '@changfenhuang', 'dsh-genui')
  const pluginDir = join(dir, 'node_modules', 'chemclaw-bot')
  mkdirSync(pluginDir, { recursive: true })
  writeFileSync(join(pluginDir, 'package.json'), JSON.stringify({ name: 'chemclaw-bot' }))
  const expected = { [name]: '0.15.0' }
  assert.deepEqual(missingPluginDependencies(dir, expected), [`${name}@0.15.0`])
  mkdirSync(packageDir, { recursive: true })
  const save = version => {
    // package.json is intentionally not exported, as with some third-party plugins.
    writeFileSync(join(packageDir, 'package.json'), JSON.stringify({ name, version, exports: { '.': './index.js' } }))
    writeFileSync(join(packageDir, 'index.js'), '')
  }
  save('0.14.0')
  assert.deepEqual(missingPluginDependencies(dir, expected), [`${name}@0.15.0`])
  save('0.15.0')
  assert.deepEqual(missingPluginDependencies(dir, expected), [])
  assert.deepEqual(missingPluginDependencies(dir, { ...expected, 'future-plugin': '1.0.0' }), ['future-plugin@1.0.0'])
})

test('picker Git sync fast-forwards clean main and PR but preserves dirty worktrees and untracked files', t => {
  const dir = mkdtempSync(join(tmpdir(), 'chemclaw-safe-git-'))
  const source = join(dir, 'source')
  const remote = join(dir, 'remote.git')
  const prPath = join(dir, 'cursor-chembot-pr-86')
  const git = (cwd, ...args) => execFileSync('git', ['-C', cwd, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim()
  t.after(() => {
    try { if (existsSync(prPath)) git(source, 'worktree', 'remove', '--force', prPath) } catch {}
    rmSync(dir, { recursive: true, force: true })
  })
  git(dir, 'init', '--bare', remote)
  git(dir, 'init', '-b', 'main', source)
  git(source, 'config', 'user.name', 'ChemClaw Test')
  git(source, 'config', 'user.email', 'test@example.invalid')
  for (const [folder, name] of [['app', 'chemclaw'], ['chemclaw-bot', 'chemclaw-bot']]) {
    mkdirSync(join(source, folder), { recursive: true })
    writeFileSync(join(source, folder, 'package.json'), JSON.stringify({ name }))
  }
  mkdirSync(join(source, 'scripts'))
  writeFileSync(join(source, 'scripts', 'launch-chemclaw.mjs'), '// Fixture')
  writeFileSync(join(source, 'README.md'), 'base\n')
  git(source, 'add', '.')
  git(source, 'commit', '-m', 'baseline')
  git(source, 'remote', 'add', 'chemclaw', remote)
  git(source, 'push', 'chemclaw', 'main')
  git(source, 'checkout', '-b', 'publish')
  writeFileSync(join(source, 'README.md'), 'upstream one\n')
  git(source, 'add', 'README.md')
  git(source, 'commit', '-m', 'upstream one')
  git(source, 'push', 'chemclaw', 'HEAD:main')
  git(source, 'checkout', 'main')
  git(source, 'fetch', 'chemclaw', '--prune')
  assert.equal(syncSelectedMain(source).updated, true)
  assert.equal(readFileSync(join(source, 'README.md'), 'utf8'), 'upstream one\n')
  git(source, 'checkout', 'publish')
  writeFileSync(join(source, 'README.md'), 'upstream two\n')
  git(source, 'add', 'README.md')
  git(source, 'commit', '-m', 'upstream two')
  git(source, 'push', 'chemclaw', 'HEAD:main')
  git(source, 'checkout', 'main')
  git(source, 'fetch', 'chemclaw', '--prune')
  writeFileSync(join(source, 'README.md'), 'uncommitted work\n')
  assert.match(syncSelectedMain(source).reason, /local changes/u)
  assert.equal(readFileSync(join(source, 'README.md'), 'utf8'), 'uncommitted work\n')
  git(source, 'restore', 'README.md')
  writeFileSync(join(source, 'untracked.txt'), 'do not erase')
  assert.match(syncSelectedMain(source).reason, /untracked/u)
  assert.equal(readFileSync(join(source, 'untracked.txt'), 'utf8'), 'do not erase')
  rmSync(join(source, 'untracked.txt'))
  assert.equal(syncSelectedMain(source).updated, true)
  // A previously created detached PR worktree must move to its newest GitHub head.
  git(source, 'checkout', 'publish')
  writeFileSync(join(source, 'README.md'), 'pr one\n')
  git(source, 'add', 'README.md')
  git(source, 'commit', '-m', 'pr one')
  git(source, 'push', 'chemclaw', 'HEAD:refs/pull/86/head')
  const firstSha = git(source, 'rev-parse', 'HEAD')
  git(source, 'checkout', 'main')
  const pr = { number: 86, headRefName: 'feat/preview-86', headRefOid: firstSha }
  const first = ensurePrWorktree(source, pr)
  assert.equal(first.created, true)
  assert.equal(first.head, firstSha)
  git(source, 'checkout', 'publish')
  writeFileSync(join(source, 'README.md'), 'pr two\n')
  git(source, 'add', 'README.md')
  git(source, 'commit', '-m', 'pr two')
  git(source, 'push', 'chemclaw', 'HEAD:refs/pull/86/head')
  const secondSha = git(source, 'rev-parse', 'HEAD')
  git(source, 'checkout', 'main')
  const refreshed = ensurePrWorktree(source, pr)
  assert.equal(refreshed.created, false)
  assert.equal(refreshed.updated, true)
  assert.equal(refreshed.head, secondSha, 'fresh PR fetch overrides stale picker metadata')
  git(source, 'checkout', 'publish')
  writeFileSync(join(source, 'README.md'), 'pr three\\n')
  git(source, 'add', 'README.md')
  git(source, 'commit', '-m', 'pr three')
  git(source, 'push', 'chemclaw', 'HEAD:refs/pull/86/head')
  git(source, 'checkout', 'main')
  writeFileSync(join(prPath, 'untracked-pr.txt'), 'user work')
  const dirty = ensurePrWorktree(source, pr)
  assert.match(dirty.reason, /untracked/u)
  assert.equal(dirty.head, secondSha, 'local PR must not be silently advanced')
  assert.equal(readFileSync(join(prPath, 'untracked-pr.txt'), 'utf8'), 'user work')
})

test('a PR with different desktop code or dependencies uses its own app instead of stale main Electron', t => {
  const dir = mkdtempSync(join(tmpdir(), 'chemclaw-app-host-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const entry = join(dir, 'main')
  const preview = join(dir, 'pr')
  for (const root of [entry, preview]) {
    mkdirSync(join(root, 'app', 'src'), { recursive: true })
    writeFileSync(join(root, 'app', 'package.json'), JSON.stringify({ name: 'chemclaw' }))
    writeFileSync(join(root, 'app', 'package-lock.json'), JSON.stringify({ version: 1 }))
    writeFileSync(join(root, 'app', 'src', 'main.mjs'), '// same app')
  }
  const electronPath = process.platform === 'win32'
    ? join(entry, 'app', 'node_modules', 'electron', 'dist', 'electron.exe')
    : process.platform === 'darwin'
      ? join(entry, 'app', 'node_modules', 'electron', 'dist', 'Electron.app', 'Contents', 'MacOS', 'Electron')
      : join(entry, 'app', 'node_modules', 'electron', 'dist', 'electron')
  mkdirSync(dirname(electronPath), { recursive: true })
  writeFileSync(electronPath, 'fake electron binary for selection test')
  let selected = resolveAppHost(preview, entry)
  assert.equal(selected.app, join(entry, 'app'))
  assert.equal(selected.host, 'entry-reuse-identical-app')
  writeFileSync(join(preview, 'app', 'src', 'main.mjs'), '// PR changed desktop profile')
  selected = resolveAppHost(preview, entry)
  assert.equal(selected.app, join(preview, 'app'))
  assert.equal(selected.host, 'selected-source-app-changed')
  writeFileSync(join(preview, 'app', 'src', 'main.mjs'), '// same app')
  writeFileSync(join(preview, 'app', 'package-lock.json'), JSON.stringify({ version: 2 }))
  selected = resolveAppHost(preview, entry)
  assert.equal(selected.app, join(preview, 'app'), 'a new dependency lockfile must never run against main Electron')
})

test('Electron repair runs the official binary installer without repeating npm ci', t => {
  const app = mkdtempSync(join(tmpdir(), 'chemclaw-electron-repair-'))
  t.after(() => rmSync(app, { recursive: true, force: true }))
  const executableRelativePath = join('node_modules', 'electron', 'dist', process.platform === 'win32' ? 'electron.exe' : 'electron')
  const binary = join(app, executableRelativePath)
  const installer = join(app, 'node_modules', 'electron', 'install.js')
  mkdirSync(dirname(installer), { recursive: true })
  writeFileSync(installer, '// npm package is present, runtime was not downloaded')
  let npmCiCalls = 0
  let binaryInstallerCalls = 0
  const options = {
    installDependencies: () => { npmCiCalls++ },
    installBinary: path => {
      assert.equal(path, installer)
      binaryInstallerCalls++
      mkdirSync(dirname(binary), { recursive: true })
      writeFileSync(binary, 'fake runtime for launch repair test')
    },
  }
  assert.equal(ensureElectronRuntime(app, executableRelativePath, options).repaired, true)
  assert.equal(npmCiCalls, 0, 'do not reinstall a thousand npm dependencies')
  assert.equal(binaryInstallerCalls, 1)
  assert.equal(ensureElectronRuntime(app, executableRelativePath, options).repaired, false)
  assert.equal(binaryInstallerCalls, 1, 'subsequent launches must skip the installer')
})

test('Electron repair never reports success when installer exits without creating the runtime', t => {
  const app = mkdtempSync(join(tmpdir(), 'chemclaw-electron-fail-'))
  t.after(() => rmSync(app, { recursive: true, force: true }))
  const rel = join('node_modules', 'electron', 'dist', 'electron.exe')
  assert.throws(() => ensureElectronRuntime(app, rel, {
    installDependencies: () => {},
    installBinary: () => {},
  }), /Electron package installer is missing/u)
  const installer = join(app, 'node_modules', 'electron', 'install.js')
  mkdirSync(dirname(installer), { recursive: true })
  writeFileSync(installer, '')
  assert.throws(() => ensureElectronRuntime(app, rel, {
    installDependencies: () => { throw new Error('unexpected npm ci') },
    installBinary: () => {},
  }), /Electron executable was not installed/u)
})
