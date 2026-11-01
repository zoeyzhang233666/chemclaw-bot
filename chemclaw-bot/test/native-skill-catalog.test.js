import assert from 'node:assert/strict'
import { test } from 'node:test'
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import legacySeed from '../seed/capabilities-library.json' with { type: 'json' }
import { reconcileLegacyBuiltins } from '../src/host/catalog-seed.js'
import { nativeSkillCatalog, NATIVE_OFFICE_COPY } from '../src/host/native-skill-catalog.js'
import { isMyInstallation, matchingSkills, skillCategory, skillLabel } from '../src/shared/skills.js'

test('migrate all legacy seeded skills to built-in groups with short Chinese names', () => {
  const items = Object.fromEntries(Object.entries(legacySeed.items).filter(([, value]) => value.kind === 'skill')
    .map(([name, item]) => [name, { name, kind: 'skill', description: item.description,
      content: item.content, createdBy: null, createdAt: 1 }]))
  assert.equal(Object.keys(items).length, 17)
  assert.equal(reconcileLegacyBuiltins(items), true)
  for (const item of Object.values(items)) {
    assert.equal(item.builtinSource, 'chemclaw-legacy')
    assert.equal(isMyInstallation(item), false)
    assert.notEqual(skillCategory(item), '我的安装')
    assert.match(skillLabel(item), /[\u4e00-\u9fff]/)
    assert.match(item.purpose, /[\u4e00-\u9fff]/)
    assert.deepEqual(matchingSkills([item], '', '我的安装'), [])
  }
  assert.equal(skillCategory(items['dom-buy-cn']), '内贸采购')
  assert.equal(skillCategory(items['dom-sales-ex']), '外贸销售')
  assert.equal(skillCategory(items['ppt-master']), '通用办公')
  assert.equal(items['ppt-master'].invocation.userInvocable, false)
  assert.equal(reconcileLegacyBuiltins(items), false)
})

test('only exact first-run seed identities are migrated; user imports and edits remain untouched', () => {
  const original = legacySeed.items.brainstorming
  const user = { name: 'brainstorming', kind: 'skill', description: original.description, directory: 'skills/installed/user', category: '科学分析', displayName: '自建方案' }
  const changedDescription = { name: 'grill-me', kind: 'skill', description: 'My own skill', createdBy: null }
  const manual = { name: 'my-skill', kind: 'skill', category: '通用办公', displayName: '我的技能' }
  const items = { brainstorming: user, 'grill-me': changedDescription, 'my-skill': manual }
  assert.equal(reconcileLegacyBuiltins(items), false)
  assert.equal(isMyInstallation(user), true)
  assert.equal(isMyInstallation(changedDescription), true)
  assert.equal(isMyInstallation(manual), true)
  assert.deepEqual(matchingSkills([user, manual], '', '我的安装'), [user, manual])
  assert.deepEqual(matchingSkills([user, manual], '', '通用办公'), [manual])
  assert.equal(skillLabel(user), '自建方案')
})

test('native Office catalog lists only present assets, de-duplicates office and preserves Chinese copy', async t => {
  const home = mkdtempSync(join(tmpdir(), 'chemclaw-office-catalog-'))
  t.after(() => rmSync(home, { force: true, recursive: true }))
  const standalone = await nativeSkillCatalog(undefined, { CHEMCLAW_OFFICE_RUNTIME_DIR: join(home, 'missing') })
  assert.deepEqual(standalone.map(x => x.name).sort(), ['office', 'office-tools'])
  mkdirSync(join(home, 'primary-runtime'), { recursive: true })
  mkdirSync(join(home, 'office-skills'), { recursive: true })
  writeFileSync(join(home, 'primary-runtime', 'runtime.json'), '{}')
  for (const name of Object.keys(NATIVE_OFFICE_COPY).filter(name => name !== 'office-tools')) {
    const dir = join(home, 'office-skills', name)
    mkdirSync(dir, { recursive: true })
    writeFileSync(join(dir, 'SKILL.md'), '---\\nname: ' + name + '\\ndescription: Native Office capability\\n---\\n')
  }
  const list = await nativeSkillCatalog(undefined, { CHEMCLAW_OFFICE_RUNTIME_DIR: home })
  assert.equal(list.length, 8)
  assert.equal(new Set(list.map(x => x.name)).size, 8)
  for (const item of list) {
    assert.equal(item.builtinSource.startsWith('dsh-') || item.builtinSource.startsWith('chemclaw-'), true)
    assert.equal(item.nativeSkill, true)
    assert.equal(isMyInstallation(item), false)
    assert.equal(skillCategory(item), '通用办公')
    assert.match(skillLabel(item), /[\u4e00-\u9fff]/)
    assert.match(item.purpose, /[\u4e00-\u9fff]/)
  }
  assert.equal(list.find(item => item.name === 'office').builtinSource, 'chemclaw-office')
  assert.equal(list.find(item => item.name === 'office-pptx').builtinSource, 'dsh-office')
  rmSync(join(home, 'office-skills', 'office-pptx', 'SKILL.md'))
  const missing = await nativeSkillCatalog(undefined, { CHEMCLAW_OFFICE_RUNTIME_DIR: home })
  assert.equal(missing.some(x => x.name === 'office-pptx'), false)
  assert.equal(existsSync(join(home, 'office-skills', 'office', 'SKILL.md')), true)
})

test('DSH registry contributes real native skills and separates user DSH roots', async () => {
  const registry = { list: async () => [
    { name: 'grilling', description: 'Review ideas', provider: 'dsh-skill-filesystem', source: 'bundled', invocation: { modelInvocable: true, userInvocable: true } },
    { name: 'b2b-lead-sourcing', description: 'Sales leads', provider: 'dsh-skill-filesystem', source: 'bundled' },
    { name: 'my-extra-workflow', description: 'Imported by user', provider: 'dsh-skill-filesystem', source: 'user-dsh' },
    { name: 'domain-1', description: 'ChemClaw managed', provider: 'chemclaw-user-skills', source: 'custom' },
  ] }
  const items = await nativeSkillCatalog(registry, {})
  assert.equal(items.some(x => x.name === 'domain-1'), false)
  assert.equal(items.find(x => x.name === 'grilling').labels.zh, '深入推敲一个方案')
  assert.equal(items.find(x => x.name === 'b2b-lead-sourcing').category, '内贸销售')
  assert.equal(isMyInstallation(items.find(x => x.name === 'grilling')), false)
  const user = items.find(x => x.name === 'my-extra-workflow')
  assert.equal(isMyInstallation(user), true)
  assert.equal(user.category, '我的安装')
  assert.deepEqual(matchingSkills(items, '', '我的安装').map(x => x.name), ['my-extra-workflow'])
})
