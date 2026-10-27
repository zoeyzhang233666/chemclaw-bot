import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { parse } from 'yaml'

const workflow = name => parse(readFileSync(new URL(`../../.github/workflows/${name}.yml`, import.meta.url), 'utf8'))
const runs = job => job.steps.map(step => step.run ?? '').join('\n')

test('ordinary macOS checks keep signing and startup coverage without making a ZIP', () => {
  const job = workflow('test').jobs['app-package-macos']
  const commands = runs(job)
  assert.match(commands, /npm run pack/)
  assert.doesNotMatch(commands, /npm run dist|ditto/)
  assert.match(commands, /codesign --verify --deep --strict/)
  assert.match(commands, /file -b/)
  assert.match(commands, /check-packed.mjs/)
  assert.match(commands, /check-update.mjs/)
  assert.equal(job.steps.find(step => step.run === 'npm run pack').env.CSC_FOR_PULL_REQUEST, 'true')
})

test('releases validate the extracted archive and still require both Mac architectures', () => {
  const config = workflow('release')
  const job = config.jobs['app-macos']
  assert.deepEqual(job.strategy.matrix.include.map(row => row.arch).sort(), ['arm64', 'x64'])
  const commands = runs(job)
  assert.match(commands, /npm run dist/)
  assert.match(commands, /ditto -x -k/)
  assert.match(commands, /codesign --verify --deep --strict/)
  assert.match(commands, /check-packed.mjs/)
  assert.match(commands, /check-update.mjs/)
  assert.ok(config.jobs.complete.needs.includes('app-macos'))
  const benchmark = job.steps.find(step => step.name === 'Compare ZIP compression')
  assert.match(benchmark.if, /inputs.dry_run/)
  assert.equal(config.on.workflow_dispatch.inputs.benchmark_mac_zip.default, false)
})

test('build tool caches distinguish OS, architecture and dependency lockfile', () => {
  for (const [name, id] of [['test', 'app-package-macos'], ['release', 'app-macos']]) {
    const job = workflow(name).jobs[id]
    const cache = job.steps.find(step => step.uses === 'actions/cache@v4')
    // Old exact-match caches hold only builder tools and cannot be updated.
    assert.ok(cache.with.key.startsWith('desktop-tools-v3-'))
    assert.ok(cache.with.path.includes('~/Library/Caches/electron'))
    assert.match(cache.with.key, /runner.os/)
    assert.match(cache.with.key, /matrix.arch/)
    assert.match(cache.with.key, /app\/package-lock.json/)
    const node = job.steps.find(step => step.uses === 'actions/setup-node@v4')
    assert.equal(node.with.cache, 'npm')
    const install = job.steps.find(step => step.run === 'npm ci --no-fund --no-audit')
    const pack = job.steps.find(step => /^npm run (pack|dist)$/.test(step.run ?? ''))
    assert.equal(install.env?.ELECTRON_BUILDER_CACHE, pack.env.ELECTRON_BUILDER_CACHE)
    assert.ok(cache.with.path.includes(pack.env.ELECTRON_BUILDER_CACHE))
  }
  assert.match(runs(workflow('test').jobs['app-package-macos']), /find "\$HOME\/Library\/Caches\/electron" -name "electron-v\*-darwin-/)
})
