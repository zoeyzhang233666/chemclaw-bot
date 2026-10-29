import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { promisify } from 'node:util'
import { test } from 'node:test'
import { readRuntimeBundle, requirementsFingerprint, requirementsHash, runtimePython, runtimeTarget, runtimeTar, unpackRuntimeBundle } from '../src/host/runtime-bundle.js'

const execute = promisify(execFile)
async function fixture(t) {
  const dir = await mkdtemp(join(tmpdir(), 'chemclaw-bundle-test-'))
  t.after(() => rm(dir, { recursive: true, force: true, maxRetries: 5 }))
  const packageRoot = join(dir, 'plugin')
  const bundled = join(packageRoot, 'runtime', 'bundled')
  const payload = join(dir, 'payload')
  const root = join(dir, 'home', 'runtime')
  await mkdir(bundled, { recursive: true })
  await mkdir(join(payload, process.platform === 'win32' ? 'Scripts' : 'bin'), { recursive: true })
  await writeFile(runtimePython(payload), 'private interpreter fixture')
  const requirements = Buffer.from('akshare==1.17.74\n')
  await writeFile(join(packageRoot, 'runtime', 'requirements.txt'), requirements)
  const target = runtimeTarget()
  const archive = join(bundled, `${target}.tar.gz`)
  await execute(runtimeTar(), ['-czf', archive, '-C', payload, '.'], { windowsHide: true })
  const manifest = { version: 1, target, requirements: requirementsFingerprint(requirements), sha256: requirementsHash(await readFile(archive)) }
  await writeFile(join(bundled, `${target}.json`), JSON.stringify(manifest))
  const calls = []
  const run = async (command, args) => {
    assert.equal(command, runtimeTar())
    calls.push(args)
    return execute(command, args, { windowsHide: true })
  }
  const verify = async python => assert.equal(await readFile(python, 'utf8'), 'private interpreter fixture')
  return { packageRoot, root, archive, calls, run, verify }
}

test('a bundled environment unpacks and is reused entirely offline', async t => {
  const f = await fixture(t)
  const bundle = await readRuntimeBundle(f.packageRoot)
  assert.ok(bundle)
  assert.equal(await unpackRuntimeBundle(bundle, f.root, f), runtimePython(join(f.root, 'python')))
  assert.equal(f.calls.length, 1)
  await unpackRuntimeBundle(bundle, f.root, f)
  assert.equal(f.calls.length, 1)
  await writeFile(runtimePython(join(f.root, 'python')), 'broken')
  await unpackRuntimeBundle(bundle, f.root, f)
  assert.equal(f.calls.length, 2)
  await f.verify(runtimePython(join(f.root, 'python')))
})

test('a corrupt archive is rejected before replacing an existing environment', async t => {
  const f = await fixture(t)
  const bundle = await readRuntimeBundle(f.packageRoot)
  await writeFile(f.archive, 'corrupt archive')
  await assert.rejects(unpackRuntimeBundle(bundle, f.root, f), /failed verification/)
  assert.equal(f.calls.length, 0)
})

test('requirements fingerprints survive Windows and Unix checkout line endings', async t => {
  const f = await fixture(t)
  const before = await readRuntimeBundle(f.packageRoot)
  await writeFile(join(f.packageRoot, 'runtime', 'requirements.txt'), 'akshare==1.17.74\r\n')
  const after = await readRuntimeBundle(f.packageRoot)
  assert.equal(after.manifest.requirements, before.manifest.requirements)
  assert.equal(after.manifest.sha256, before.manifest.sha256)
})

test('stale release runtimes fail rather than downloading a silent replacement', async t => {
  const f = await fixture(t)
  await writeFile(join(f.packageRoot, 'runtime', 'requirements.txt'), 'akshare==0.0.0')
  await assert.rejects(readRuntimeBundle(f.packageRoot), /do not match/)
  assert.equal(await readRuntimeBundle(f.packageRoot, 'unsupported-target'), undefined)
})

test('a failed import leaves the previous interpreter intact', async t => {
  const f = await fixture(t)
  const bundle = await readRuntimeBundle(f.packageRoot)
  await unpackRuntimeBundle(bundle, f.root, f)
  const python = runtimePython(join(f.root, 'python'))
  await writeFile(python, 'previous interpreter')
  await assert.rejects(unpackRuntimeBundle(bundle, f.root, { run: f.run, verify: async () => { throw new Error('import failed') } }), /import failed/)
  assert.equal(await readFile(python, 'utf8'), 'previous interpreter')
})
