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

test('explicit single use loads an unassigned skill once, takes precedence and keeps Bot attachments', async () => {
  const calls = []
  const bot = { capabilities: ['chain'] }
  const ctx = fakeContext({ services: { skills: { get: async () => { throw new Error('Automatic routing must not run') } } } })
  const rt = { ctx, groupOwners: new Map(), isBotSession: () => true, selfOf: () => 'expert', botOf: () => bot,
    state: { capabilities: { items: { chain: items[1], specific: { name: 'specific', kind: 'skill', description: 'Specific workflow' } } } },
    skillDefinition: async name => { calls.push(name); return { name, content: 'Follow the specific workflow.', resourceBase: { kind: 'directory', path: '/isolated/skills/specific' } } },
  }
  install(rt)
  const hook = ctx.listeners.get('agent/pre-step')[0]
  const agent = { id: 'expert' }
  const signal = new AbortController().signal
  const decision = { kind: 'enter', messages: [{ role: 'user', source: { kind: 'user' }, content: [{ type: 'text', text: '/specific 研究聚氨酯产业链' }] }] }
  const first = await hook({ agent, signal, turn: 1 }, async () => decision)
  assert.equal(first.messages.at(-1).source.kind, 'skill-invocation')
  assert.match(first.messages.at(-1).content[0].text, /Follow the specific workflow/)
  assert.match(first.messages.at(-1).content[0].text, /isolated\/skills\/specific/)
  assert.equal(await hook({ agent, signal, turn: 1 }, async () => decision), decision)
  assert.deepEqual(calls, ['specific'])
  assert.deepEqual(bot.capabilities, ['chain'])
  const later = { kind: 'enter', messages: [{ role: 'user', source: { kind: 'user' }, content: [{ type: 'text', text: '研究聚氨酯产业链' }] }] }
  assert.equal(await hook({ agent, signal, turn: 1 }, async () => later), later)
})

test('relayed explicit skill selection uses durable message metadata rather than a later group log', async () => {
  const ctx = fakeContext({ services: { skills: {} } })
  const rt = { ctx, groupOwners: new Map([['member-session', { roomId: 'room', botId: 'member' }]]), isBotSession: () => true,
    roomOf: () => ({ log: [{ who: 'User', text: 'A different task arrived later' }] }),
    state: { capabilities: { items: { specific: { name: 'specific', kind: 'skill' } } } },
    skillDefinition: async name => ({ name, content: 'Original selected skill.' }),
  }
  install(rt)
  const hook = ctx.listeners.get('agent/pre-step')[0]
  const decision = { kind: 'enter', messages: [{ role: 'user', source: { kind: 'bot', role: 'room', skillNames: ['specific'] }, content: [{ type: 'text', text: 'Group relay' }] }] }
  const result = await hook({ agent: { id: 'member-session' }, signal: new AbortController().signal, turn: 1 }, async () => decision)
  assert.equal(result.messages.at(-1).source.name, 'specific')
  delete rt.state.capabilities.items.specific
  await assert.rejects(hook({ agent: { id: 'member-session' }, signal: new AbortController().signal, turn: 2 }, async () => decision), /unavailable/)
})

test('native human invocation delegates once without injecting a second skill or changing assignments', async () => {
  const ctx = fakeContext({ services: { skills: {} } })
  let mounts = 0
  const bot = { capabilities: ['chain'] }
  const rt = { ctx, groupOwners: new Map(), isBotSession: () => true, botOf: () => bot,
    state: { capabilities: { items: { specific: { name: 'specific', kind: 'skill' } } } },
    ensureUserSkillCatalog: () => { mounts++; return true },
    skillDefinition: () => { throw new Error('DSH owns native explicit loading') },
  }
  install(rt)
  const hook = ctx.listeners.get('agent/pre-step')[0]
  const decision = { kind: 'enter', messages: [{ role: 'user', source: { kind: 'user' }, content: [{ type: 'text', text: '/specific 研究产业链' }] }] }
  const agent = { id: 'expert' }
  assert.equal(await hook({ agent, turn: 1, signal: new AbortController().signal }, async () => decision), decision)
  assert.equal(mounts, 1)
  assert.deepEqual(bot.capabilities, ['chain'])
})
