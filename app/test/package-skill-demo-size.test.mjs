// Protect executable skill content while excluding duplicate generated demo exports from the installer.
// The canonical examples/, scripts/, templates/ and all skill instructions remain installable.
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { FileMatcher } from 'app-builder-lib/out/fileMatcher.js'
import { parse } from 'yaml'

const pluginRoot = fileURLToPath(new URL('../../chemclaw-bot/', import.meta.url))

function* walk(folder) {
  for (const entry of readdirSync(folder, { withFileTypes: true })) {
    const path = join(folder, entry.name)
    if (entry.isDirectory()) yield* walk(path)
    else if (entry.isFile()) yield path
  }
}

test('only generated HTML/XLSX files live in the Chinese-named demo mirrors', () => {
  const files = [...walk(join(pluginRoot, 'skills', 'domain'))]
  const mirrors = files.filter(path => path.split(/[\\/]/u).includes('例子'))
  assert.ok(mirrors.length >= 250, 'verify the large mirrored demo set has not changed shape')
  for (const path of mirrors) {
    assert.match(path, /\\.(?:html|xlsx)$/iu, 'never exclude code, data, templates or skill instructions')
    assert.ok(statSync(path).size > 0)
  }
  const skills = files.filter(path => path.endsWith('SKILL.md'))
  assert.ok(skills.length >= 100, 'domain skills remain present')
  for (const path of skills) {
    assert.doesNotMatch(readFileSync(path, 'utf8'), /[\\/]例子[\\/]/u, 'a registered skill references an excluded demo path')
  }
})

test('the desktop and npm package filter mirrored demos but preserve canonical skill assets', () => {
  const config = parse(readFileSync(new URL('../electron-builder.yml', import.meta.url), 'utf8'))
  const npm = JSON.parse(readFileSync(new URL('../../chemclaw-bot/package.json', import.meta.url), 'utf8'))
  assert.ok(npm.files.includes('!skills/domain/**/例子/**'))
  assert.ok(config.files.includes('!node_modules/chemclaw-bot/skills/domain/**/例子/**'))
  const root = resolve('app-size-fixture')
  const stat = { isDirectory: () => false }
  const filter = new FileMatcher(root, root, value => value, ['**/*', ...config.files.filter(pattern => pattern.startsWith('!'))]).createFilter()
  const domain = 'node_modules/chemclaw-bot/skills/domain/期现-价差与量化/22.扫描异常区域价差/22.扫描异常区域价差'
  assert.equal(filter(join(root, domain, '例子/报告.html'), stat), false)
  assert.equal(filter(join(root, domain, '例子/工作簿.xlsx'), stat), false)
  for (const path of ['SKILL.md', 'scripts/run_all.py', 'templates/工作簿模板.xlsx', 'examples/01-纯碱甲醇区域价差扫描/outputs/区域价差扫描工作簿.xlsx']) {
    assert.equal(filter(join(root, domain, path), stat), true, path)
  }
})
