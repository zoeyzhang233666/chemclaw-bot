import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { CURATED_SKILL_EXAMPLES_ZH } from '../src/shared/skill-examples.js'
import { NATIVE_SKILL_ZH } from '../src/shared/native-skill-copy.js'
import { NATIVE_OFFICE_COPY } from '../src/shared/native-office-copy.js'
import { BUILTIN_SKILL_PRESENTATION, skillExample } from '../src/shared/skill-presentation.js'
import { SKILL_CATEGORIES } from '../src/shared/skills.js'
import legacyIdentities from '../seed/legacy-skill-identities.json' with { type: 'json' }

test('every new bundled/legacy/native skill has a distinct concrete Chinese question (except unavailable ppt-master)', () => {
  const expected = new Set([...Object.keys(legacyIdentities), ...Object.keys(NATIVE_SKILL_ZH), ...Object.keys(NATIVE_OFFICE_COPY)])
  expected.delete('ppt-master') // source-only, excluded from the published plugin
  for (const name of expected) {
    const entry = CURATED_SKILL_EXAMPLES_ZH[name]
    assert.ok(entry, 'Missing tailored example: ' + name)
    assert.ok(entry.length >= 22 && entry.length <= 110, name)
    assert.match(entry, /[\u4e00-\u9fff]/, name)
    assert.doesNotMatch(entry, /请用「|填写具体需求|处理这项任务|\[填写|请使用.{0,25}技能|这份|这个方案|附件|上文|上述|按照既定计划|[（(]待补[）)]/, name)
    assert.equal(skillExample({ name, kind: 'skill', builtinSource: 'chemclaw-legacy' }), entry, name)
  }
  assert.equal(new Set(expected).size, Object.keys(CURATED_SKILL_EXAMPLES_ZH).length)
  assert.equal(new Set(Object.values(CURATED_SKILL_EXAMPLES_ZH)).size, expected.size)
  assert.equal(skillExample({ name: 'ppt-master', kind: 'skill', builtinSource: 'chemclaw-legacy' }), '')
})

test('native Office cards and details get different examples based on what the skill actually does', () => {
  const questions = Object.keys(NATIVE_OFFICE_COPY).map(name =>
    skillExample({ name, kind: 'skill', nativeSkill: true, builtinSource: 'chemclaw-office' }))
  assert.equal(new Set(questions).size, 8)
  assert.match(skillExample({ name: 'office-docx', kind: 'skill', nativeSkill: true, builtinSource: 'dsh-office' }), /Word审查表/)
  assert.match(skillExample({ name: 'office-recalculate', kind: 'skill', nativeSkill: true, builtinSource: 'dsh-office' }), /重新计算全部结果/)
  assert.match(skillExample({ name: 'office-render', kind: 'skill', nativeSkill: true, builtinSource: 'dsh-office' }), /曲线遮挡/)
  assert.match(skillExample({ name: 'office-export-pdf', kind: 'skill', nativeSkill: true, builtinSource: 'dsh-office' }), /PDF/)
})

test('business skill examples and user-supplied examples remain authoritative', () => {
  assert.equal(skillExample({ name: 'domain-1', kind: 'skill', builtinSource: 'chemclaw' }),
    BUILTIN_SKILL_PRESENTATION['domain-1'][1])
  assert.equal(skillExample({ name: 'brainstorming', kind: 'skill', directory: 'skills/installed/one',
    examples: ['把我整理的采购数据变成指标表。'] }), '把我整理的采购数据变成指标表。')
  assert.match(skillExample({ name: 'brainstorming', kind: 'skill', directory: 'skills/installed/two',
    displayName: '个人构思工具' }), /个人构思工具.*填写具体需求/)
  assert.equal(skillExample({ name: 'unknown-dsh-skill', kind: 'skill', nativeSkill: true,
    builtinSource: 'dsh-skill-filesystem' }), '')
  assert.equal(skillExample({ name: 'unknown-dsh-skill', kind: 'skill', nativeSkill: true,
    builtinSource: 'dsh-skill-filesystem', examples: ['检查附件文件中的重复记录。'] }), '检查附件文件中的重复记录。')
  assert.equal(skillExample({ name: 'unlisted-package-skill', kind: 'skill', builtinSource: 'chemclaw' }), '')
})

test('GenUI uses correct capitalization, real chemical visualization purpose, and directly usable question', () => {
  const meta = NATIVE_SKILL_ZH.genui
  assert.match(meta[0], /GenUI/)
  assert.match(meta[0], /对话.*图表/)
  assert.equal(meta[2], '数据可视化')
  assert.match(meta[1], /聊天消息|对话/)
  assert.match(meta[1], /趋势图/)
  assert.ok(SKILL_CATEGORIES.includes(meta[2]))
  assert.ok(SKILL_CATEGORIES.includes('研发与调试'))
  const example = skillExample({ kind: 'skill', name: 'genui', builtinSource: 'dsh-genui', nativeSkill: true })
  assert.match(example, /乙二醇/)
  assert.match(example, /现货/)
  assert.match(example, /期货/)
  assert.match(example, /基差/)
  assert.match(example, /对话/)
  assert.doesNotMatch(example, /使用.+(?:技能|工具)|提供资料|填写|上传/)
})

test('known native catalog descriptions name specific capabilities without default placeholder', () => {
  for (const [name, [title, purpose, category]] of Object.entries(NATIVE_SKILL_ZH)) {
    assert.match(title, /[\u4e00-\u9fff]/, name)
    assert.match(purpose, /[\u4e00-\u9fff]/, name)
    assert.ok(purpose.length >= 25, name)
    assert.ok(SKILL_CATEGORIES.includes(category), name + ': ' + category)
    assert.doesNotMatch(title + purpose, /专项技能|按技能说明|查看技术名称|适用范围|填写具体需求/, name)
  }
})
