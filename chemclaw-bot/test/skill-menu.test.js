import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createSource, indexRoster } from '../src/client/sources.js'
import { nativeSkillRows, skillRows, skillSource } from '../src/client/skill-menu.js'
import { installSkillTextRule, syncSkillTextNames } from '../src/client/skill-text-rule.js'
import { explicitSkillNames, matchingSkills } from '../src/shared/skills.js'
import { installLocale } from '../src/client/i18n.js'

const roster = () => indexRoster({ bots: [{ id: 'bot', sessionId: 'current', name: '采购员', capabilities: ['assigned'] }, { id: 'other', name: '销售员' }], rooms: [{ id: 'group', name: '研究群', members: ['bot', 'other'], admin: 'bot' }],
  capabilities: [
    { name: 'unassigned', kind: 'skill', labels: { zh: '看原料行情', en: 'Market brief' }, category: '内贸采购', purpose: '查看价格与成本', originalName: 'market-brief' },
    { name: 'assigned', kind: 'skill', labels: { zh: '找备选供应商', en: 'Find suppliers' }, category: '内贸采购' },
    { name: 'internal', kind: 'skill', description: 'Internal skill', invocation: { userInvocable: false } },
  ] })

test('the slash source lists all human skills, ranks assigned skills first and searches Chinese aliases', () => {
  const off = installLocale({ register: () => () => {}, bind: () => key => key })
  try {
    const snapshot = roster()
    assert.deepEqual(skillRows(snapshot, 'current').map(item => item.name), ['assigned', 'unassigned'])
    assert.equal(skillRows(snapshot, 'bot', '行情')[0].label, '看原料行情')
    assert.equal(skillRows(snapshot, 'group', '价格')[0].name, 'unassigned')
    assert.equal(skillRows(snapshot, 'current', 'market-brief')[0].name, 'unassigned')
    assert.deepEqual(skillRows(snapshot, 'ordinary-agent'), [])
    assert.deepEqual(matchingSkills(snapshot.capabilities, '行情 成本').map(item => item.name), ['unassigned'])
  } finally { off() }
})

test('installation changes the source immediately and removed references block submission', async () => {
  const source = createSource(roster())
  const errors = []
  const menu = skillSource({ roster: source, actions: { reportError: error => errors.push(error), openSettings() { throw new Error('Picking a skill must stay in the composer') } } })
  let changes = 0
  const off = menu.subscribeLexicon({}, () => { changes++ })
  const row = (await menu.candidates({ sessionId: 'bot' }, { query: 'unassigned' }))[0]
  assert.equal(menu.onPick({ candidate: row, session: { sessionId: 'bot' } }).insert.clipboardText, '/unassigned')
  assert.equal(await menu.codec.serialize('unassigned'), '/unassigned')
  assert.equal(menu.onPick({ candidate: row, session: { sessionId: 'group' } }).insert.clipboardText, '/unassigned')
  source.set({ ...source.getSnapshot(), capabilities: source.getSnapshot().capabilities.filter(item => item.name !== 'unassigned') })
  assert.equal(changes, 1)
  assert.deepEqual(await menu.candidates({ sessionId: 'bot' }, { query: 'unassigned' }), [])
  await assert.rejects(menu.codec.serialize('unassigned'), /no longer available/)
  assert.equal(menu.onPick({ candidate: row, session: { sessionId: 'bot' } }), undefined)
  assert.equal(errors.length, 1)
  off()
})

test('single-use selection recognizes stable IDs and respects manual invocation policy', () => {
  assert.deepEqual(explicitSkillNames('/unassigned 看行情', roster().capabilities), ['unassigned'])
  assert.deepEqual(explicitSkillNames('/internal', roster().capabilities), [])
})

test('supplemental menu waits for native skill results, deduplicates IDs and cancels cleanly', async () => {
  let snapshot = { groups: [{ source: 'skill', status: 'pending', items: [] }] }
  const listeners = new Set()
  const controller = { menu: { getSnapshot: () => snapshot, subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener) } } }
  const source = skillSource({ roster: createSource(roster()), actions: {}, controllerOf: () => controller })
  const result = source.candidates({ sessionId: 'bot' }, { query: '', signal: new AbortController().signal })
  assert.equal(listeners.size, 1)
  snapshot = { groups: [{ source: 'skill', status: 'ready', items: [{ name: 'assigned' }] }] }
  for (const listener of [...listeners]) listener()
  assert.deepEqual((await result).map(item => item.name), ['unassigned'])
  assert.equal(listeners.size, 0)
  snapshot = { groups: [{ source: 'skill', status: 'pending', items: [] }] }
  const abort = new AbortController()
  const pending = nativeSkillRows(controller, abort.signal)
  abort.abort()
  assert.deepEqual(await pending, [])
  assert.equal(listeners.size, 0)
  assert.deepEqual(await nativeSkillRows(controller, abort.signal), [])
  assert.equal(listeners.size, 0)
})

test('user-text rule matches ChemClaw skill IDs even without native skillNames facts', () => {
  let rule
  const off = installSkillTextRule({ userText: { register: value => { rule = value; return () => {} } } })
  syncSkillTextNames(roster().capabilities)
  const glued = '保留草稿内容。/unassigned'
  const hit = rule.match(glued, 0)
  assert.equal(hit?.id, 'chemclaw-skill')
  assert.equal(hit?.data?.name, 'unassigned')
  assert.equal(glued.slice(hit.start, hit.end), '/unassigned')
  assert.equal(rule.match('保留草稿内容。/internal', 0), undefined)
  assert.equal(rule.match('保留草稿内容。/missing', 0), undefined)
  off()
})
