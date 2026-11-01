import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { Arch } from 'electron-builder'
import { archProblem, beforePack, officeRuntimeRequest } from '../scripts/before-pack.mjs'

test('a build for the architecture of this Node goes on', async () => {
  assert.equal(archProblem({ target: 'arm64', platform: 'darwin', host: 'arm64' }), undefined)
  assert.equal(archProblem({ target: 'x64', platform: 'win32', host: 'x64' }), undefined)
  let prepared = false
  await beforePack({ arch: Arch[process.arch], electronPlatformName: process.platform }, async () => { prepared = true }, async () => {})
  assert.equal(prepared, true)
})

test('a build for another architecture stops and says where to build it', async () => {
  assert.equal(archProblem({ target: 'x64', platform: 'darwin', host: 'arm64' }),
    'This Node runs on arm64, so npm installed arm64 native modules, and an x64 app with them would not start. Install the dependencies and build on an Intel Mac, or under Rosetta with an x64 Node.')
  assert.match(archProblem({ target: 'arm64', platform: 'darwin', host: 'x64' }), /build on a Mac with Apple silicon\.$/)
  assert.match(archProblem({ target: 'x64', platform: 'win32', host: 'arm64' }), /build with an x64 Node\.$/)
  assert.match(archProblem({ target: 'universal', platform: 'darwin', host: 'arm64' }), /Build one app per architecture\./)
  const other = process.arch === 'x64' ? 'arm64' : 'x64'
  await assert.rejects(beforePack({ arch: Arch[other], electronPlatformName: process.platform }), new RegExp(`an ${other} app with them would not start`))
})

test('a requested universal build stops before packing either architecture', async () => {
  // electron-builder's MacPackager.doUniversalPack packs x64 then arm64: the hook sees a concrete
  // arch each time, and the universal request only shows in packager.packagerOptions.targets.
  const packager = { packagerOptions: { targets: new Map([[{ nodeName: 'darwin' }, new Map([[Arch.universal, ['dmg']]])]]) } }
  await assert.rejects(beforePack({ arch: Arch.x64, electronPlatformName: 'darwin', packager }), /Build one app per architecture\./)
  await assert.rejects(beforePack({ arch: Arch.arm64, electronPlatformName: 'darwin', packager }), /Build one app per architecture\./)
})

test('electron-builder runs the check before it packs', () => {
  assert.match(readFileSync(new URL('../electron-builder.yml', import.meta.url), 'utf8'), /^beforePack: \.\/scripts\/before-pack\.mjs$/m)
})

test('cross-platform packaging stops before preparing the wrong runtime', async () => {
  const platform = process.platform === 'win32' ? 'linux' : 'win32'
  await assert.rejects(beforePack({ arch: Arch[process.arch], electronPlatformName: platform }, async () => assert.fail('must not prepare')), /target operating system/)
})

test('market and Office runtime stages run separately without replacing existing ChemClaw packaging', async () => {
  const stages = []
  const packager = { projectDir: 'app-dir', appInfo: { version: '0.2.2' } }
  await beforePack({ arch: Arch[process.arch], electronPlatformName: process.platform, packager },
    async () => stages.push('market'),
    async req => { stages.push('office'); assert.equal(req.version, '0.2.2') })
  assert.deepEqual(stages, ['market', 'office'])
})
test('Office package includes locked resources beside ASAR', () => {
  const request = officeRuntimeRequest({ arch: Arch.x64, electronPlatformName: 'win32', packager: { projectDir: 'app-dir', appInfo: { version: '9.9.9' } } })
  assert.equal(request.target, 'win-x64')
  assert.equal(request.version, '9.9.9')
  assert.match(readFileSync(new URL('../electron-builder.yml', import.meta.url), 'utf8'), /from: build\/runtime\/primary-runtime/)
})
