import { test } from 'node:test'
import assert from 'node:assert/strict'
import { activityText, toolActivityDetail } from '../src/shared/tool-activity.js'

test('activity reads presentation fields without copying arbitrary arguments or output', () => {
  const args = { command: 'echo test', description: 'Check the fixture', env: { PRIVATE: 'do not expose' } }
  assert.deepEqual(toolActivityDetail('pwsh', key => args[key]), {
    tool: 'pwsh', label: 'Running command', summary: 'Check the fixture', detail: 'echo test',
  })
  assert.equal(toolActivityDetail('load_skill', key => ({ name: 'chem-market-brief' })[key]).label, 'Loading skill')
  assert.equal(toolActivityDetail('mcp__prices', () => undefined).summary, 'mcp__prices')
  assert.equal(toolActivityDetail('request_secret', () => 'private value').detail, undefined)
})

test('activity handles partial arguments, caps long commands and hides credential forms', () => {
  assert.equal(toolActivityDetail('read_file', () => undefined).summary, 'read_file')
  assert.equal(activityText('x'.repeat(1000)).length, 600)
  const result = activityText('token=fixture-token password="fixture password" Bearer fixture-bearer https://fixture:password@example.test')
  assert.doesNotMatch(result, /fixture-token|fixture password|fixture-bearer|fixture:password/)
})
