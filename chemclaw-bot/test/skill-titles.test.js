import assert from 'node:assert/strict'
import { test } from 'node:test'
import skillDisplay from '../seed/skill-display.json' with { type: 'json' }
import { matchingSkills, skillLabel } from '../src/shared/skills.js'

test('built-in skills retain Chinese business names when summary metadata is absent', () => {
  for (const [name, [title]] of Object.entries(skillDisplay)) {
    const item = { name, kind: 'skill' }
    assert.equal(skillLabel(item), title)
    assert.equal(matchingSkills([item], title)[0], item)
    assert.equal(skillLabel({ ...item, displayName: '我的工作流' }), '我的工作流')
    assert.equal(skillLabel({ ...item, labels: { zh: '自定义名称' } }), '自定义名称')
  }
  assert.equal(skillLabel({ name: 'custom-skill', kind: 'skill' }), 'custom-skill')
})
