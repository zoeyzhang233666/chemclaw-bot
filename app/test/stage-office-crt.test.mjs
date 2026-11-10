import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { stageOfficeCrt, verifyOfficeCrt } from '../scripts/stage-office-crt.mjs'

const hash = value => createHash('sha256').update(value).digest('hex')

function setup(t) {
  const root = mkdtempSync(join(tmpdir(), 'chemclaw-office-crt-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const engine = join(root, 'engine'), archive = join(root, 'archive'), license = join(root, 'license.docx')
  mkdirSync(join(engine, 'helper'), { recursive: true })
  mkdirSync(join(archive, 'release'), { recursive: true })
  writeFileSync(join(engine, 'package.json'), JSON.stringify({ name: '@fixture/engine', exports: { './prebuilds.json': './manifest.json' } }))
  const manifest = { platform: 'win32-x64', engine: { kind: 'native', executable: 'helper/convert.exe' }, files: { 'helper/convert.exe': hash('engine') } }
  const save = () => writeFileSync(join(engine, 'manifest.json'), JSON.stringify(manifest))
  save()
  writeFileSync(join(engine, 'helper/convert.exe'), 'engine')
  writeFileSync(license, 'synthetic license')
  const files = { 'msvcp140.dll': hash('synthetic c++'), 'vcruntime140.dll': hash('synthetic c') }
  writeFileSync(join(archive, 'release/msvcp140.dll'), 'synthetic c++')
  writeFileSync(join(archive, 'release/vcruntime140.dll'), 'synthetic c')
  const lock = { version: 'synthetic', directory: 'release', files, license: { sha256: hash('synthetic license') }, redistribution: 'https://example.invalid' }
  return { engine, archive, license, lock, manifest, save }
}

test('Office CRT follows the exported manifest and stages the complete verified release set with provenance', t => {
  const { engine, archive, license, lock } = setup(t)
  assert.equal(stageOfficeCrt(engine, archive, license, lock).files, 2)
  verifyOfficeCrt(engine, lock)
  assert.equal(readFileSync(join(engine, 'helper/convert.exe'), 'utf8'), 'engine')
  assert.deepEqual(JSON.parse(readFileSync(join(engine, 'licenses/chemclaw-visual-cpp/provenance.json'), 'utf8')), lock)
  assert.ok(existsSync(join(engine, 'licenses/chemclaw-visual-cpp/Microsoft-VC-Runtime-License.docx')))
  writeFileSync(join(engine, 'helper/msvcp140.dll'), 'corrupt')
  assert.throws(() => verifyOfficeCrt(engine, lock), /checksum mismatch/)
})

test('a missing or corrupt CRT member or license fails before copying any DLL', t => {
  const { engine, archive, license, lock } = setup(t)
  writeFileSync(join(archive, 'release/vcruntime140.dll'), 'wrong')
  assert.throws(() => stageOfficeCrt(engine, archive, license, lock), /checksum mismatch/)
  assert.ok(!existsSync(join(engine, 'helper/msvcp140.dll')))
  rmSync(join(archive, 'release/vcruntime140.dll'))
  assert.throws(() => stageOfficeCrt(engine, archive, license, lock), /ENOENT/)
  writeFileSync(join(archive, 'release/vcruntime140.dll'), 'synthetic c')
  writeFileSync(license, 'wrong')
  assert.throws(() => stageOfficeCrt(engine, archive, license, lock), /license checksum mismatch/)
  assert.ok(!existsSync(join(engine, 'helper/msvcp140.dll')))
})

test('Office CRT refuses a wrong platform, escaping manifest and overwriting engine-owned files', t => {
  const { engine, archive, license, lock, manifest, save } = setup(t)
  manifest.platform = 'darwin-x64'; save()
  assert.throws(() => stageOfficeCrt(engine, archive, license, lock), /Windows x64/)
  manifest.platform = 'win32-x64'; manifest.engine.executable = '../outside.exe'; save()
  assert.throws(() => stageOfficeCrt(engine, archive, license, lock), /escapes/)
  manifest.engine.executable = 'helper/convert.exe'; manifest.files['helper/msvcp140.dll'] = hash('old'); save()
  assert.throws(() => stageOfficeCrt(engine, archive, license, lock), /overwrite/)
  assert.ok(!existsSync(join(engine, 'helper/msvcp140.dll')))
})
