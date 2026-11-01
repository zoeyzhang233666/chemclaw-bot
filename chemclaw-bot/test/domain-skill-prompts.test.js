import assert from 'node:assert/strict'
import { test } from 'node:test'
import domainSkills from '../seed/domain-skills.json' with { type: 'json' }
import { BUILTIN_SKILL_PRESENTATION, skillExample } from '../src/shared/skill-presentation.js'

test('all 108 chemical business skill examples are independently copyable', () => {
  assert.equal(domainSkills.length, 108)
  const examples = domainSkills.map(skill => {
    const answer = skillExample({ kind: 'skill', name: skill.id, builtinSource: 'chemclaw' })
    assert.equal(answer, BUILTIN_SKILL_PRESENTATION[skill.id]?.[1], skill.id)
    assert.match(answer, /[\u4e00-\u9fff]/, skill.id)
    assert.ok(answer.length >= 33 && answer.length <= 120, skill.id)
    assert.doesNotMatch(answer, /这家|这份|这三|这些|附件|上述|上文|已提供的|按原技能|填写具体需求|这个产品|这个问题|这条研究|本次询盘|处理这项任务/, skill.id)
    return answer
  })
  assert.equal(new Set(examples).size, domainSkills.length, 'Each skill needs a distinct real-life question')
})

test('supplier comparison, FX impact, export compliance, supplier verification and basis seasonality are immediately usable', () => {
  for (const [id, words] of [
    ['domain-16', ['山东海化', '唐山三友', '江苏苏盐井神']],
    ['domain-49', ['钛白粉', '汇率', '6.9']],
    ['domain-46', ['甲醇', '7.0', '7.4']],
    ['domain-55', ['钛白粉', '越南', '出口']],
    ['domain-13', ['山东海化', '纯碱']],
    ['domain-15', ['山东海化', '最近三个月']],
    ['domain-84', ['甲醇', '基差', '季节性']],
    ['domain-56', ['二氧化钛', 'HS编码']],
  ]) {
    const sample = skillExample({ kind: 'skill', name: id, builtinSource: 'chemclaw' })
    for (const word of words) assert.ok(sample.includes(word), id + ' must contain ' + word)
  }
})

test('a user-installed skill never inherits ChemClaw domain skill example', () => {
  const sample = skillExample({
    kind: 'skill', name: 'domain-16', directory: 'skills/installed/one',
    displayName: '自定义报价助手', examples: ['分析甲醇与乙醇的成本。'],
  })
  assert.equal(sample, '分析甲醇与乙醇的成本。')
})
