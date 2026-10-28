import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { BUILTIN_SKILL_PRESENTATION, SKILL_EMOJIS, skillEmoji, skillExample, validSkillEmoji } from '../src/shared/skill-presentation.js'

test('every shipped skill has a curated emoji and a concrete task example', () => {
  const read = file => JSON.parse(readFileSync(new URL(`../seed/${file}`, import.meta.url), 'utf8'))
  const names = [...read('domain-skills.json').map(item => item.id), ...read('supplemental-skills.json').map(item => item.id),
    'chemclaw-presentations', 'guizang-ppt-skill', 'chemclaw-chemistry', 'chemclaw-delivery', 'chemclaw-research-process']
  assert.deepEqual(Object.keys(BUILTIN_SKILL_PRESENTATION).sort(), names.sort())
  for (const name of names) {
    assert.ok(validSkillEmoji(skillEmoji({ name })), name)
    assert.notEqual(skillEmoji({ name }), '🧰', name)
    assert.ok(skillExample({ name }).length > 15, name)
    assert.ok(!skillExample({ name }).includes('填写具体需求'), name)
  }
  assert.equal(new Set(SKILL_EMOJIS).size, SKILL_EMOJIS.length)
})

test('related built-ins use meaningful families without confusing costs, prices and customer work', () => {
  assert.equal(skillEmoji({ name: 'domain-1' }), '🏭')
  assert.equal(skillEmoji({ name: 'domain-4' }), '📈')
  assert.equal(skillEmoji({ name: 'domain-6' }), '📜')
  assert.equal(skillEmoji({ name: 'domain-9' }), '🧮')
  assert.equal(skillEmoji({ name: 'domain-18' }), '🎯')
  assert.equal(skillEmoji({ name: 'domain-20' }), '💬')
  assert.equal(skillEmoji({ name: 'aux-rdkit' }), '🧬')
})

test('custom skills prefer explicit choices, then title, purpose, category and a neutral fallback', () => {
  assert.equal(skillEmoji({ name: 'domain-1', emoji: '🧬' }), '🧬')
  assert.equal(skillEmoji({ name: 'daily-market', displayName: '行情简报', purpose: '核查供应商的报价和合同' }), '📈')
  assert.equal(skillEmoji({ name: 'my-task', purpose: '核验合同中的交付条款' }), '📜')
  assert.equal(skillEmoji({ name: 'supplier-sourcing' }), '🏭')
  assert.equal(skillEmoji({ name: 'my-task', category: '科学分析' }), '🔬')
  assert.equal(skillEmoji({ name: 'unknown-workflow', category: '我的安装' }), '🧰')
  assert.equal(skillEmoji({ name: 'constructor', category: 'toString' }), '🧰')
  assert.equal(skillEmoji({ name: 'domain-1', emoji: '' }), '🏭')
  assert.equal(skillEmoji({ name: 'domain-1', emoji: '<img>' }), '🏭')
})

test('custom examples are retained and missing examples ask for task inputs without inventing abilities', () => {
  assert.equal(skillExample({ name: 'custom', examples: ['', 'Use the attached data.'] }), 'Use the attached data.')
  const item = { kind: 'skill', name: 'custom', displayName: '自定义流程' }
  assert.match(skillExample(item), /自定义流程.*填写具体需求/)
  assert.match(skillExample(item, 'en'), /describe your requirements/)
  assert.notEqual(skillExample({ name: 'domain-1' }), skillExample({ name: 'domain-2' }))
})
