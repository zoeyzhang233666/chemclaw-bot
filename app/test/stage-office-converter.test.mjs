import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { officeConverterCli, stageOfficeConverter } from '../scripts/stage-office-converter.mjs'

function setup(t) {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-office-bundle-'))
  t.after(() => rmSync(home, { recursive: true, force: true }))
  const installed = join(home, 'node_modules')
  const output = join(home, 'runtime')
  const put = (name, { dependencies = {}, optionalDependencies = {} } = {}, location = installed) => {
    const dir = join(location, name)
    mkdirSync(dir, { recursive: true })
    writeFileSync(join(dir, 'package.json'), JSON.stringify({ name, version: '1.0.0', dependencies, optionalDependencies }))
    return dir
  }
  return { installed, output, put }
}

test('standalone Office kit stages required and nested npm packages without needing a global Node', t => {
  const { installed, output, put } = setup(t)
  const kit = put('@deepseek-ai/libreoffice-kit', {
    dependencies: { fflate: '0.8.2', fontkit: '2.0.4' },
    optionalDependencies: { '@deepseek-ai/libreoffice-kit-win32-x64': '1.0.0', '@deepseek-ai/libreoffice-kit-darwin-x64': '1.0.0' },
  })
  mkdirSync(join(kit, 'lib'), { recursive: true })
  writeFileSync(join(kit, 'lib', 'cli.js'), '// synthetic Office CLI')
  put('fflate', {}, join(kit, 'node_modules'))
  put('fontkit', { dependencies: { brotli: '1.0.0' } })
  put('brotli')
  put('@deepseek-ai/libreoffice-kit-win32-x64')
  const staged = stageOfficeConverter(output, { installed, platform: 'win32', arch: 'x64' })
  assert.equal(staged.packages.length, 5)
  assert.ok(existsSync(officeConverterCli(output)))
  assert.ok(existsSync(join(output, 'office-converter', 'node_modules', '@deepseek-ai', 'libreoffice-kit', 'node_modules', 'fflate', 'package.json')))
  assert.ok(existsSync(join(output, 'office-converter', 'node_modules', 'brotli', 'package.json')))
  assert.ok(existsSync(join(output, 'office-converter', 'node_modules', '@deepseek-ai', 'libreoffice-kit-win32-x64', 'package.json')))
  assert.ok(!existsSync(join(output, 'office-converter', 'node_modules', '@deepseek-ai', 'libreoffice-kit-darwin-x64')))
})

test('build refuses a missing native Office conversion engine or mandatory package', t => {
  const { installed, output, put } = setup(t)
  const kit = put('@deepseek-ai/libreoffice-kit', { dependencies: { fflate: '0.8.2' } })
  mkdirSync(join(kit, 'lib'), { recursive: true })
  writeFileSync(join(kit, 'lib', 'cli.js'), '')
  assert.throws(() => stageOfficeConverter(output, { installed, platform: 'win32', arch: 'x64' }), /Missing required Office conversion engine/)
  put('@deepseek-ai/libreoffice-kit-win32-x64')
  assert.throws(() => stageOfficeConverter(output, { installed, platform: 'win32', arch: 'x64' }), /Missing Office dependency fflate/)
})
