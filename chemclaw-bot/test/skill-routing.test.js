import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install, selectTaskSkill } from '../src/host/skill-routing.js'
import { fakeContext } from './fake-ctx.js'

const items = [
  { name: 'profit', kind: 'skill', description: '期现 / 看产业链利润变化' },
  { name: 'chain', kind: 'skill', description: '期现 / 看一个品种的产业链图' },
]
test('task routing chooses the assigned chain skill and skips greetings and provenance questions', () => {
  assert.equal(selectTaskSkill('研究聚氨酯产业链全景', items), 'chain')
  assert.equal(selectTaskSkill('聚氨酯产业链', items), 'chain')
  assert.equal(selectTaskSkill('分析甲醇产业链利润', items), 'profit')
  assert.equal(selectTaskSkill('你好，介绍你自己', items), undefined)
  assert.equal(selectTaskSkill('你刚才有用 skill 吗？', items), undefined)
  assert.equal(selectTaskSkill('刚才产业链研究用到技能、MCP了吗？', items), undefined)
  assert.equal(selectTaskSkill('研究聚氨酯产业链全景', []), undefined)
})

test('matched skill loads through the scoped registry once and remains available for later steps', async () => {
  const calls = []
  const ctx = fakeContext({ services: {
    skills: { async get(name, lookup) { calls.push({ name, scope: lookup.scope }); return { name, provider: 'runtime', content: 'Verified workflow', invocation: { modelInvocable: true } } } },
    workingDirectory: { ensure: async () => 'workspace' },
  } })
  const rt = { ctx, groupOwners: new Map(), isBotSession: id => id === 'expert', selfOf: id => id,
    botOf: () => ({ capabilities: ['chain'] }), expandCapabilities: names => names,
    state: { capabilities: { items: { chain: items[1] } } },
  }
  install(rt)
  const hook = ctx.listeners.get('agent/pre-step')[0]
  const agent = { id: 'expert' }
  const signal = new AbortController().signal
  const decision = { kind: 'enter', messages: [{ role: 'user', source: { kind: 'user' }, content: [{ type: 'text', text: '研究聚氨酯产业链全景' }] }] }
  const first = await hook({ agent, signal }, async () => decision)
  assert.equal(first.messages.length, 2)
  assert.match(first.messages[1].content[0].text, /<skill_content name="chain">/)
  assert.equal(first.messages[1].source.kind, 'chemclaw-skill-routing')
  assert.equal(calls[0].scope, agent)
  assert.equal(await hook({ agent, signal }, async () => decision), decision)
  assert.equal(calls.length, 1)
  assert.equal((await hook({ agent, signal, turn: 2 }, async () => decision)).messages.length, 2)
  assert.equal(calls.length, 2)
  assert.deepEqual(await hook({ agent, signal }, async () => ({ kind: 'reject' })), { kind: 'reject' })
  assert.equal(await hook({ agent: { id: 'unrelated' }, signal }, async () => decision), decision)
})

test('group routing uses the latest user task rather than business examples in the relay', async () => {
  const calls = []
  const ctx = fakeContext({ services: {
    skills: { async get(name) { calls.push(name); return { name, provider: 'runtime', content: 'Chain workflow', invocation: { modelInvocable: true } } } },
    workingDirectory: { ensure: async () => 'workspace' },
  } })
  let text = '聚氨酯产业链'
  const rt = { ctx, groupOwners: new Map([['group-expert', { roomId: 'room', botId: 'expert' }]]),
    isBotSession: () => true, selfOf: () => 'expert', botOf: () => ({ capabilities: ['profit', 'chain'] }),
    roomOf: () => ({ log: [{ who: 'User', text }, { who: 'Other expert', text: '分析甲醇产业链利润' }] }),
    expandCapabilities: names => names, state: { capabilities: { items: Object.fromEntries(items.map(item => [item.name, item])) } },
  }
  install(rt)
  const hook = ctx.listeners.get('agent/pre-step')[0]
  const agent = { id: 'group-expert' }
  const signal = new AbortController().signal
  const decision = { kind: 'enter', messages: [{ role: 'user', source: { kind: 'bot', role: 'room' }, content: [{ type: 'text', text: 'Group examples: 分析甲醇产业链利润' }] }] }
  assert.equal((await hook({ agent, signal, turn: 1 }, async () => decision)).messages.length, 2)
  assert.deepEqual(calls, ['chain'])
  text = '你好'
  assert.equal(await hook({ agent, signal, turn: 2 }, async () => decision), decision)
  assert.deepEqual(calls, ['chain'])
})
