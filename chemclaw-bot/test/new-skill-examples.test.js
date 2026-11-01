import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { CURATED_SKILL_EXAMPLES_ZH } from '../src/shared/skill-examples.js'
import { NATIVE_SKILL_ZH } from '../src/shared/native-skill-copy.js'
import { NATIVE_OFFICE_COPY, nativeOfficeSummary } from '../src/host/native-skill-catalog.js'
import { BUILTIN_SKILL_PRESENTATION, skillExample } from '../src/shared/skill-presentation.js'
import legacyIdentities from '../seed/legacy-skill-identities.json' with { type: 'json' }

test('every new bundled/legacy/native skill has a distinct concrete Chinese question (except unavailable ppt-master)', () => {
  const expected = new Set([...Object.keys(legacyIdentities), ...Object.keys(NATIVE_SKILL_ZH), ...Object.keys(NATIVE_OFFICE_COPY)])
  expected.delete('ppt-master') // source-only, excluded from the published plugin
  for (const name of expected) {
    const entry = CURATED_SKILL_EXAMPLES_ZH[name]
    assert.ok(entry, 'Missing tailored example: ' + name)
    assert.ok(entry.length >= 22 && entry.length <= 110, name)
    assert.match(entry, /[\u4e00-\u9fff]/, name)
    assert.doesNotMatch(entry, /请用「|填写具体需求|处理这项任务|\[填写|请使用.{0,25}技能/, name)
    assert.equal(skillExample({ name, kind: 'skill', builtinSource: 'chemclaw-legacy' }), entry, name)
  }
  assert.equal(new Set(expected).size, Object.keys(CURATED_SKILL_EXAMPLES_ZH).length)
  assert.equal(new Set(Object.values(CURATED_SKILL_EXAMPLES_ZH)).size, expected.size)
  assert.equal(skillExample({ name: 'ppt-master', kind: 'skill', builtinSource: 'chemclaw-legacy' }), '')
})

test('native Office cards and details get different examples based on what the skill actually does', () => {
  const questions = Object.keys(NATIVE_OFFICE_COPY).map(name =>
    skillExample(nativeOfficeSummary(name, 'Office skill', 'chemclaw-office')))
  assert.equal(new Set(questions).size, 8)
  assert.match(skillExample(nativeOfficeSummary('office-docx', '', 'dsh-office')), /Word 报告/)
  assert.match(skillExample(nativeOfficeSummary('office-recalculate', '', 'dsh-office')), /重新计算关联公式/)
  assert.match(skillExample(nativeOfficeSummary('office-render', '', 'dsh-office')), /图表遮挡/)
  assert.match(skillExample(nativeOfficeSummary('office-export-pdf', '', 'dsh-office')), /PDF/)
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
