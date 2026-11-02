import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { officeKitPhysicalEntry, officeKitResolveHook, installOfficeKitHostResolver } from '../src/office-kit-loader.mjs'

test('redirect only DSH official Office provider imports to the physically unpacked kit', () => {
  const resources = join(tmpdir(), 'chemclaw-resources-stub')
  const resolver = officeKitResolveHook(resources)
  const parent = 'file:///C:/ChemClaw/resources/app.asar/node_modules/@deepseek-ai/dsh-office-to-pdf/lib/index.js'
  const result = resolver('@deepseek-ai/libreoffice-kit', { parentURL: parent }, () => { throw new Error('the DSH provider must be intercepted') })
  assert.equal(result.url, pathToFileURL(officeKitPhysicalEntry(resources)).href)
  assert.equal(result.shortCircuit, true)
  const original = { url: 'file:///original/kit.js' }
  const fallback = () => original
  assert.equal(resolver('@deepseek-ai/libreoffice-kit', { parentURL: 'file:///plugins/other.js' }, fallback), original)
  assert.equal(resolver('yaml', { parentURL: parent }, fallback), original)
  assert.equal(resolver('@deepseek-ai/libreoffice-kit/package.json', { parentURL: parent }, fallback), original)
})

test('missing physical converter is a no-op; installed converter registers one ESM hook', t => {
  const resources = mkdtempSync(join(tmpdir(), 'chemclaw-office-resolver-'))
  t.after(() => rmSync(resources, { recursive: true, force: true }))
  const hooks = []
  const register = hook => hooks.push(hook)
  assert.equal(installOfficeKitHostResolver(resources, { register }), false)
  const target = officeKitPhysicalEntry(resources)
  mkdirSync(dirname(target), { recursive: true })
  writeFileSync(target, '// fake physical kit')
  assert.equal(installOfficeKitHostResolver(resources, { register }), true)
  assert.equal(hooks.length, 1)
  assert.equal(typeof hooks[0].resolve, 'function')
})
