import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { ensureOfficePreviewRuntime } from '../src/office-preview-runtime.mjs'

function setup(t) {
  const appDir = mkdtempSync(join(tmpdir(), 'chemclaw-office-preview-'))
  t.after(() => rmSync(appDir, { recursive: true, force: true }))
  writeFileSync(join(appDir, 'package.json'), JSON.stringify({ version: '0.2.2', scripts: { runtime: 'node scripts/prepare-runtime.mjs' } }))
  return appDir
}

test('normal and packaged sessions do not provision a preview runtime', async () => {
  assert.deepEqual(await ensureOfficePreviewRuntime({ packaged: true, profile: 'pr-101' }), { status: 'skipped' })
  assert.deepEqual(await ensureOfficePreviewRuntime({ profile: 'baseline' }), { status: 'skipped' })
})

test('PR preview prepares incomplete Office runtime before Host then validates bundled interpreters', async t => {
  const appDir = setup(t)
  let built = false
  const calls = []
  const result = await ensureOfficePreviewRuntime({
    profile: 'pr-101', appDir, platform: 'win32', arch: 'x64',
    reusable: () => built,
    fileExists: () => built,
    prepare: async params => { built = true; assert.equal(params.target, 'win-x64') },
    run: (binary, args) => {
      calls.push([binary, args])
      return { status: 0, stdout: 'OK' }
    },
  })
  assert.equal(result.status, 'ready')
  assert.equal(calls.length, 2)
  assert.match(calls[0][0], /node\.exe$/)
  assert.match(calls[1][0], /python\.exe$/)
  assert.deepEqual(calls[1][1], ['-I', '-B', '-c', 'import docx, pptx, openpyxl; print("OFFICE_READY")'])
})

test('PR preview reuses complete payload without another installer', async t => {
  const appDir = setup(t)
  const result = await ensureOfficePreviewRuntime({
    profile: 'pr-101', appDir, platform: 'win32', arch: 'x64',
    reusable: () => true, fileExists: () => true,
    prepare: async () => assert.fail('must not reinstall a complete runtime'),
    run: () => ({ status: 0 }),
  })
  assert.equal(result.status, 'ready')
})

test('PR preview cannot silently start without working Python Office libraries', async t => {
  const appDir = setup(t)
  await assert.rejects(ensureOfficePreviewRuntime({
    profile: 'pr-101', appDir, platform: 'win32', arch: 'x64',
    reusable: () => true, fileExists: () => true,
    run: (binary, args) => args[0] === '--version'
      ? { status: 0 }
      : { status: 1, stderr: "ModuleNotFoundError: No module named 'docx'" },
  }), /Office preview interpreter is unusable/)
})

test('a failed download never becomes a usable Office preview', async t => {
  const appDir = setup(t)
  await assert.rejects(ensureOfficePreviewRuntime({
    profile: 'pr-101', appDir, platform: 'win32', arch: 'x64',
    reusable: () => false, fileExists: () => false,
    prepare: async () => {},
  }), /not complete after preparation/)
})
