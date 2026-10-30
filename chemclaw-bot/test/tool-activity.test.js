import { test } from 'node:test'
import assert from 'node:assert/strict'
import { activityText, toolActivityDetail, liveActivitySummary } from '../src/shared/tool-activity.js'

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

test('live task summary prefers explanations or safe search targets, not raw shell commands', () => {
  assert.equal(liveActivitySummary('pwsh', key => ({ description: '巨潮全文检索芯化和云', command: 'echo unsafe' })[key]), '巨潮全文检索芯化和云')
  assert.equal(liveActivitySummary('pwsh', key => ({ command: 'echo do-not-show' })[key]), '')
  assert.equal(liveActivitySummary('web_search', key => ({ query: '万华化学供应链' })[key]), '万华化学供应链')
  assert.equal(liveActivitySummary('read_file', key => ({ path: 'C:\\private\\reports\\annual.pdf' })[key]), 'annual.pdf')
  assert.equal(liveActivitySummary('request_secret', () => 'must-not-leak'), '')
  assert.equal(liveActivitySummary('pwsh', key => ({ description: 'token=fixture-secret' })[key]), '')
})
