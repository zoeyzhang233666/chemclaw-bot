import { execFileSync } from 'node:child_process'
import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, mkdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { launchSource, missingPluginDependencies } from '../../scripts/launch-source.mjs'
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
  writeFileSync(join(prPath, 'untracked-pr.txt'), 'user work')
  const dirty = ensurePrWorktree(source, pr)
  assert.match(dirty.reason, /untracked/u)
  assert.equal(readFileSync(join(prPath, 'untracked-pr.txt'), 'utf8'), 'user work')
})
