import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { setTimeout as realDelay } from 'node:timers/promises'
import { apply } from './legacy-runtime.js'
import { fakeAttachments, fakeContext } from './fake-ctx.js'
import { GROUP_LINE_READ, MESSAGE_INLINE_MAX, ROOM_STEP_GAP_MS, ROOM_WORK_GRACE_MS, TEXT_KEPT } from '../src/host/constants.js'
import { publishInitialGroupBook } from '../src/host/ledger-import.js'
import { readLedger } from '../src/host/ledger-foundation.js'

// Chief, the admin of group 'r1', speaks there from 'ga'; Writer from 'gb'; Tester from 'gc'.
const seed = (room = {}, extraRooms = {}) => ({
  version: 1,
  mainBotIds: ['a'],
  bots: {
    a: { id: 'a', name: 'Chief', role: 'Boss', sessionId: 'a', createdAt: 1 },
    b: { id: 'b', name: 'Writer', role: 'Write', sessionId: 'b', createdAt: 2 },
    c: { id: 'c', name: 'Tester', role: 'Test', sessionId: 'c', createdAt: 3 },
  },
  rooms: { r1: { id: 'r1', name: 'Ops', members: ['a', 'b', 'c'], mode: 'admin', admin: 'a', named: true, sessions: { a: 'ga', b: 'gb', c: 'gc' }, log: [], seq: 0, seen: {}, ...room }, ...extraRooms },
  agents: {},
  exchanges: [],
  exchangeTurns: {},
  questions: {},
  prefs: {},
  revision: 0,
})

async function start(t, room, services, extraRooms, config = {}) {
  const home = mkdtempSync(join(tmpdir(), 'ds-bot-work-'))
  writeFileSync(join(home, 'state.json'), JSON.stringify(seed(room, extraRooms)))
  const ctx = fakeContext({ services })
  const agents = new Map()
  const agentOf = (sessionId) => {
    if (!agents.has(sessionId)) {
      const calls = []
      const cancelled = []
      const held = []
      const nextStep = []
      const inbox = {
        nextStep,
        nextTurn: held,
        remove(id) {
          for (const list of [nextStep, held]) {
            const at = list.findIndex(message => message.id === id)
            if (at !== -1) { list.splice(at, 1); return true }
          }
          return false
        },
      }
      const keep = list => message => { calls.push(message); list.push(message) }
      agents.set(sessionId, { session: { id: sessionId }, calls, cancelled, inbox, followup: keep(held), steer: keep(nextStep), cancel(reason) { cancelled.push(reason) } })
    }
    return agents.get(sessionId)
  }
  Object.assign(ctx, {
    llm: { listProviders: () => [], listModels: async () => [], resolveModelInfo: async () => ({}) },
    workspaceRegistry: { get: () => undefined, resolveByPath: async () => undefined, create: async path => ({ id: 'w1', path }), archiveSession: async () => {} },
    sessionController: { create: async () => ({ sessionId: 's1' }), resolveAgent: async sessionId => ({ agent: agentOf(sessionId) }), selectModel: async () => {} },
    sessionTitle: { rename: async () => {} },
    sessions: { flush: async () => {} },
  })
  let route
  const register = ctx.connection.fetch.register
  ctx.connection.fetch.register = (options) => { route = options; return register(options) }
  apply(ctx, { home, ...config })
  t.after(async () => {
    await ctx.dispose()
    rmSync(home, { recursive: true, force: true, maxRetries: 5, retryDelay: 20 })
  })
  let seq = 0
  const turns = new Map()
  const emit = (id, type, data) => {
    for (const listener of ctx.listeners.get('session/event') ?? []) {
      if (listener.length >= 2) listener({ id }, { type, seq: ++seq, data })
    }
  }
  const tool = (name, args, sessionId, exec = {}) => ctx.registeredTools.get(name).execute(args, { agent: { id: sessionId }, ...exec })
  const call = async (endpoint, payload) => (await route.fetch(new Request('http://localhost/api/bot', { method: 'POST', body: JSON.stringify({ endpoint, payload }) }))).json()
  // A Session takes up the newest message it was sent, as a new turn.
  const begin = (sessionId) => {
    const message = agentOf(sessionId).calls.at(-1)
    agentOf(sessionId).inbox.nextTurn.length = 0
    agentOf(sessionId).inbox.nextStep.length = 0
    const turn = (turns.get(sessionId) ?? 0) + 1
    turns.set(sessionId, turn)
    emit(sessionId, 'turn/start', { turn })
    emit(sessionId, 'user/message', { content: message.content, source: message.source })
    return message
  }
  const finish = (sessionId, reply) => {
    emit(sessionId, 'assistant/message', { message: { content: [{ type: 'text', text: reply }] } })
    emit(sessionId, 'turn/end', { turn: turns.get(sessionId), reason: { kind: 'completed' } })
  }
  // The user's message in the group, or a Bot's post the group Session took up, and the
  // round it starts.
  const round = (callId, message, { withInbox = false } = {}) => {
    emit('r1', 'user/message', message)
    let result
    const stop = new AbortController()
    t.after(() => stop.abort())
    // The default fixture deliberately exposes only an Agent ID. Tests that
    // exercise mid-round user input need the DSH Agent inbox explicitly, just
    // as a real group_relay tool call receives it from its execution context.
    const agent = withInbox ? { id: 'r1', inbox: agentOf('r1').inbox } : { id: 'r1' }
    void tool('group_relay', {}, 'r1', { callId, signal: stop.signal, agent }).then((value) => { result = JSON.parse(value) })
    const read = () => result
    return read
  }
  const say = text => ({ content: [{ type: 'text', text }], source: { kind: 'user' } })
  const takePost = () => {
    const post = agentOf('r1').calls.shift()
    return { content: post.content, source: post.source }
  }
  await tool('list_bots', {}, 'a')
  return { home, ctx, agentOf, emit, tool, call, begin, finish, round, say, takePost }
}

const settle = async (check) => {
  const until = Date.now() + 3000
  while (!check() && Date.now() < until) await realDelay(10)
  assert.ok(check(), 'condition not reached')
}
const text = message => message.content.map(block => block.text ?? '').join('\n')
const kinds = result => result.replies.map(reply => [reply.kind ?? 'message', reply.name])

test('an explicit skill goes only to the selected group member even in everyone mode', async t => {
  const host = await start(t, { mode: 'everyone' })
  assert.equal((await host.call('capability-save', { name: 'specific', kind: 'skill', description: 'Specific skill', content: 'Selected workflow.' })).ok, true)
  const result = host.round('single-skill', host.say('@Writer /specific Prepare a report'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  const message = host.begin('gb')
  assert.deepEqual(message.source.skillNames, ['specific'])
  host.finish('gb', 'Report ready.')
  await settle(() => result() !== undefined)
  assert.deepEqual(kinds(result()), [['message', 'Writer']])
  assert.deepEqual(host.agentOf('ga').calls, [])
  assert.deepEqual(host.agentOf('gc').calls, [])
})

test('a specialist admin leads ordinary messages and can call the renamed Main Bot for review in the group', async t => {
  const host = await start(t, { admin: 'b' })
  await host.tool('update_bot', { name: '化工总协调' }, 'a')
  const result = host.round('chief-review', host.say('请评审这份采购方案'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  assert.deepEqual(host.agentOf('ga').calls, [])
  const admin = host.begin('gb')
  assert.match(text(admin), /Writer is this group's admin and leads its everyday work/)
  assert.match(text(admin), /call @化工总协调 in this group/)
  host.finish('gb', '@化工总协调 请协调采购与质量结论的分歧')
  await settle(() => host.agentOf('ga').calls.length === 1)
  const chief = host.begin('ga')
  assert.equal(chief.source.askedBy, 'b')
  assert.match(text(chief), /Respect the current admin/)
  assert.match(text(chief), /Writer: @化工总协调 请协调采购与质量结论的分歧/)
  assert.match(text(chief), /Keep the task and its results in this group/)
  host.finish('ga', '@Writer 先核实质量要求，再确认采购范围。')
  await settle(() => host.agentOf('gb').calls.length === 2)
  assert.match(text(host.begin('gb')), /化工总协调: @Writer 先核实质量要求/)
  host.finish('gb', '已汇总协调意见，由本群继续落实。')
  await settle(() => result() !== undefined)
  assert.deepEqual(kinds(result()), [['message', 'Writer'], ['message', '化工总协调'], ['message', 'Writer']])
  assert.deepEqual([host.agentOf('a').calls, host.agentOf('b').calls, host.agentOf('gc').calls], [[], [], []])
})

test('a user can directly call a Main Bot that is a member but not the group admin', async t => {
  const host = await start(t, { admin: 'b', log: [{ who: 'Writer', botId: 'b', text: 'Earlier evidence', seq: 1 }], seq: 1 })
  const result = host.round('chief-direct', host.say('@Chief 请验收'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  const chief = host.begin('ga')
  assert.match(text(chief), /Earlier evidence/)
  assert.match(text(chief), /Writer is this group's admin/)
  host.finish('ga', '验收完成，证据仍有一处缺口。')
  await settle(() => result() !== undefined)
  assert.deepEqual(kinds(result()), [['message', 'Chief']])
  assert.deepEqual([host.agentOf('gb').calls, host.agentOf('gc').calls, host.agentOf('a').calls], [[], [], []])
})

test('everyone mode and explicit all-member calls still include a Main Bot that is not the admin', async t => {
  for (const [mode, message] of [['admin', '@所有人 请检查'], ['everyone', '请检查']]) {
    await t.test(mode, async t => {
      const host = await start(t, { admin: 'b', mode })
      const result = host.round('chief-everyone', host.say(message))
      for (const session of ['gb', 'ga', 'gc']) {
        await settle(() => host.agentOf(session).calls.length === 1)
        host.begin(session)
        host.finish(session, 'Checked.')
      }
      await settle(() => result() !== undefined)
      assert.deepEqual(kinds(result()), [['message', 'Writer'], ['message', 'Chief'], ['message', 'Tester']])
    })
  }
})

test('work past the grace lets the round go on, and the member that asked answers the result', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  const first = host.round('c1', host.say('@Chief 安排一下文档'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer 把文档整理好')
  await settle(() => host.agentOf('gb').calls.length === 1)
  const called = host.begin('gb')
  assert.equal(called.source.askedBy, 'a')
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'pwsh', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS - 1)
  await settle(() => true)
  assert.equal(first(), undefined)
  t.mock.timers.tick(1)
  await settle(() => first() !== undefined)
  assert.deepEqual(kinds(first()), [['message', 'Chief'], ['working', 'Writer']])

  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.finish('gb', '整理好了，在 docs/ 下。')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.deepEqual([post.source.late, post.source.askedBy, text(post)], [true, 'a', '[Group post from Writer]\n整理好了，在 docs/ 下。'])
  const second = host.round('c2', post)
  await settle(() => host.agentOf('ga').calls.length === 2)
  assert.match(text(host.agentOf('ga').calls[1]), /Writer: 整理好了，在 docs\/ 下。/)
  host.begin('ga')
  host.finish('ga', '[PASS]')
  await settle(() => second() !== undefined)
  assert.deepEqual(host.agentOf('gc').calls, [])
})

// 公开#165: asked in a group to hand out work, Chief sent it with message_bot. Members
// did it in their own chats, apart from the group (Bots outside the group too), and
// again when called in the group.
test('message_bot from a group to one of its members calls it there, as "@Name" would', async (t) => {
  const host = await start(t)
  const first = host.round('c1', host.say('@Chief 安排一下文档'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  const sent = await host.tool('message_bot', { to: 'Writer', message: '把文档整理好' }, 'ga')
  assert.match(sent, /^Called Writer in "Ops"/)
  host.finish('ga', '安排好了。')
  await settle(() => host.agentOf('gb').calls.length === 1)
  const called = host.begin('gb')
  assert.equal(called.source.askedBy, 'a')
  assert.match(text(called), /Chief: @Writer 把文档整理好/)
  host.finish('gb', '整理好了。')
  await settle(() => first() !== undefined)
  assert.deepEqual(kinds(first()), [['message', 'Chief'], ['message', 'Chief'], ['message', 'Writer']])
  assert.deepEqual([host.agentOf('b').calls, host.agentOf('gc').calls], [[], []])
})

test('message_bot from a member the round moved on from calls the other member in a round of its own', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  const first = host.round('c1', host.say('@Writer 整理文档'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  await host.tool('message_bot', { to: 'Tester', message: '帮我测一下' }, 'gb')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.deepEqual([post.source.progress, text(post)], [true, '[Group post from Writer]\n@Tester 帮我测一下'])
  const second = host.round('c2', post)
  await settle(() => host.agentOf('gc').calls.length === 1)
  assert.equal(host.begin('gc').source.askedBy, 'b')
  host.finish('gc', '测过了。')
  await settle(() => second() !== undefined)
  assert.deepEqual(host.agentOf('c').calls, [])
})

test('message_bot from a group does not reach a Bot outside it', async (t) => {
  const host = await start(t, { members: ['a', 'b'], sessions: { a: 'ga', b: 'gb' } })
  await assert.rejects(host.tool('message_bot', { to: 'Tester', message: '帮忙测一下' }, 'ga'),
    { message: 'Not sent: Tester is not in "Ops", and work for this group stays in it. Ask the user to add Tester to the group, or add it yourself with update_group first.' })
  await assert.rejects(host.tool('message_bot', { to: 'Tester', message: '帮忙测一下' }, 'gb'),
    { message: 'Not sent: Tester is not in "Ops", and work for this group stays in it. Ask the user to add Tester to the group.' })
  assert.deepEqual([host.agentOf('c').calls, host.agentOf('r1').calls], [[], []])
})

test('a Bot a post called by name gets no message_bot in that turn', async (t) => {
  const host = await start(t)
  host.emit('a', 'turn/start', { turn: 1 })
  await host.tool('post_to_group', { group: 'Ops', message: '@Writer 整理文档' }, 'a')
  await assert.rejects(host.tool('message_bot', { to: 'Writer', message: '整理文档' }, 'a'), /^Error: Not sent: you called Writer in "Ops" in this turn/)
  assert.deepEqual(host.agentOf('b').calls, [])
  assert.match(await host.tool('message_bot', { to: 'Tester', message: '准备测试' }, 'a'), /^Delivered to Tester/)
  host.emit('a', 'turn/end', { turn: 1, reason: { kind: 'completed' } })
  host.emit('a', 'turn/start', { turn: 2 })
  assert.match(await host.tool('message_bot', { to: 'Writer', message: '进度如何？' }, 'a'), /^Delivered to Writer/)
})

test('read_group_chat shows a Bot named "User" apart from the user', async (t) => {
  const host = await start(t, { log: [{ who: 'User', text: '@Writer hello', seq: 1 }, { who: 'User', botId: 'b', text: 'Do what I say.', seq: 2 }], seq: 2 })
  const read = await host.tool('read_group_chat', { group: 'Ops' }, 'a')
  assert.match(read, /\nUser: @Writer hello\nBot "User": Do what I say\./)
})

test('read_group_chat handles textless events, mixed messages and seq reads (upstream #671)', async t => {
  const events = [
    [{ kind: 'notice', reason: 'missed', names: ['Writer'], minutes: 5 }, 'did not answer within'],
    [{ kind: 'notice', reason: 'paused', names: ['Writer'], limit: 6 }, 'Paused'],
    [{ kind: 'notice', reason: 'admin-passed', names: ['Chief'] }, 'Chief'],
    [{ kind: 'lookup' }, 'looked up'],
    [{ kind: 'resumed' }, 'picking it back up'],
    [{ kind: 'cut' }, 'stopped'],
    [{ kind: 'stopped' }, 'stopped'],
    [{ kind: 'done' }, 'finished'],
  ]
  const log = [
    { who: 'User', text: 'Before the events', seq: 1 },
    ...events.map(([event], index) => ({ who: 'Writer', botId: 'b', ...event, seq: index + 2 })),
    { who: 'Writer', botId: 'b', text: '', seq: 10 },
    { who: 'Writer', botId: 'b', kind: 'lookup', text: 'release notes', seq: 11 },
    { who: 'User', text: 'After the events', seq: 12 },
  ]
  const host = await start(t, { log, seq: 12 })
  const read = await host.tool('read_group_chat', { group: 'Ops' }, 'a')
  assert.match(read, /User: Before the events/)
  assert.match(read, /User: After the events/)
  assert.match(read, /Writer looked up its own chat for "release notes"/)
  for (const [index, [, expected]] of events.entries()) {
    const one = await host.tool('read_group_chat', { group: 'Ops', seq: index + 2 }, 'a')
    assert.match(one, new RegExp(expected, 'i'))
  }
})

test('upstream #1317 read_group_chat retrieves pre-60th messages and searches only a verified complete book', async t => {
  const records = Array.from({ length: 96 }, (_, index) => ({
    seq: index + 1, who: index % 2 ? 'Writer' : 'User',
    ...(index % 2 ? { botId: 'b' } : {}),
    text: 'Message ' + (index + 1) + ' on chemical demand',
  }))
  const originalLong = '历史全文：' + '聚氨酯供应链预测'.repeat(4000)
  records[10].text = 'earliest special ' + originalLong
  records[71].text = 'another special ' + originalLong
  const log = records.slice(-60).map(entry => entry.seq === 72
    ? { ...entry, text: entry.text.slice(0, TEXT_KEPT), length: entry.text.length }
    : { ...entry })
  const host = await start(t, { seq: records.length, log, seen: { a: records.length - 1 } })
  await publishInitialGroupBook(host.home, 'group-r1', records)
  const before = readFileSync(join(host.home, 'state.json'), 'utf8')

  const old = await host.tool('read_group_chat', { group: 'Ops', seq: 11 }, 'a')
  assert.match(old, /^User: earliest special 历史全文：/)
  const fullRecent = await host.tool('read_group_chat', { group: 'Ops', seq: 72 }, 'a')
  assert.match(fullRecent, /^Writer: another special 历史全文：/)
  assert.ok(fullRecent.length > TEXT_KEPT, 'the full-Ledger reader must not use the 2k state preview')
  const search = await host.tool('read_group_chat', { group: 'Ops', query: 'earliest special' }, 'a')
  assert.match(search, /#11 User: earliest special/)
  const mixed = await host.tool('read_group_chat', { group: 'Ops', query: 'chemical demand' }, 'a')
  assert.match(mixed, /#96 Writer: Message 96/)
  assert.equal((mixed.match(/#\d+ /g) ?? []).length, 20, 'the query has a bounded list of the newest twenty matches')
  assert.match(await host.tool('read_group_chat', { group: 'Ops', seq: 999 }, 'a'), /no recoverable message 999/)
  const latest = await host.tool('read_group_chat', { group: 'Ops' }, 'a')
  assert.match(latest, /Message 96 on chemical demand/)
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), before, 'reading must not alter saved group or session state')
})

test('Ledger read refuses an inconsistent or torn book without hiding unmigrated legacy chats', async t => {
  const records = [
    { seq: 1, who: 'User', text: 'keep original message' },
    { seq: 2, who: 'User', text: 'keep another message' },
  ]
  const host = await start(t, { seq: 2, log: [records[0], records[1]] })
  assert.match(await host.tool('read_group_chat', { group: 'Ops', seq: 1 }, 'a'), /keep original message/)
  assert.match(await host.tool('read_group_chat', { group: 'Ops', query: 'keep' }, 'a'), /full-history search is unavailable/)
  await publishInitialGroupBook(host.home, 'group-r1', [records[0], { ...records[1], text: 'conflicting Ledger message' }])
  const stateBefore = readFileSync(join(host.home, 'state.json'), 'utf8')
  const result = await host.tool('read_group_chat', { group: 'Ops', seq: 1 }, 'a')
  assert.match(result, /need recovery review \(blocked\)/)
  assert.doesNotMatch(result, /keep original message/)
  assert.match(await host.tool('read_group_chat', { group: 'Ops' }, 'a'), /need recovery review \(blocked\)/)
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), stateBefore)
})

test('upstream #1317 group-rows endpoint resolves verified Ledger windows and ignores anchor/session rows', async t => {
  const records = [
    { seq: 1, who: 'User', text: 'First procurement question', time: 101 },
    { seq: 2, who: 'Writer', botId: 'b', text: 'First answer', time: 102 },
    { seq: 3, who: 'ChemClaw', event: 'anchor', id: 'round-two', from: 3 },
    { seq: 4, who: 'User', text: 'Second procurement question', time: 104 },
    { seq: 5, who: 'Writer', botId: 'b', text: 'Second answer', time: 105 },
    { seq: 6, who: 'ChemClaw', event: 'anchor', id: 'round-three', from: 6 },
    { seq: 7, who: 'User', text: 'Third question', time: 107 },
    { seq: 8, who: 'Chief', botId: 'a', text: 'Only the group Session saw this', session: true, time: 108 },
  ]
  const host = await start(t, { seq: records.length, log: records.filter(row => row.event !== 'anchor') })
  await publishInitialGroupBook(host.home, 'group-r1', records)
  const before = readFileSync(join(host.home, 'state.json'), 'utf8')
  const first = (await host.call('group-rows', { roomId: 'r1', from: 1 })).value
  assert.equal(first.status, 'aligned')
  assert.equal(first.open, false)
  assert.deepEqual(first.rows.map(row => row.text), ['First procurement question', 'First answer'])
  assert.deepEqual(first.rows.map(row => row.kind ?? 'bot'), ['user', 'bot'])
  const middle = (await host.call('group-rows', { roomId: 'r1', from: 3, anchor: 'round-two' })).value
  assert.equal(middle.open, false)
  assert.deepEqual(middle.rows.map(row => row.text), ['Second procurement question', 'Second answer'])
  const last = (await host.call('group-rows', { roomId: 'r1', from: 6, anchor: 'round-three' })).value
  assert.equal(last.open, true)
  assert.equal(last.active, false)
  assert.deepEqual(last.rows.map(row => row.text), ['Third question'])
  const bounded = (await host.call('group-rows', { roomId: 'r1', from: 2, to: 4 })).value
  assert.equal(bounded.open, false)
  assert.deepEqual(bounded.rows.map(row => row.text), ['First answer', 'Second procurement question'])
  const recent = await host.tool('read_group_chat', { group: 'Ops' }, 'a')
  assert.match(recent, /First procurement question/)
  assert.match(recent, /Third question/)
  assert.doesNotMatch(recent, /Only the group Session saw this/, 'group-Session-only lines must not leak into member history')
  assert.doesNotMatch(recent, /round-two|round-three/, 'Ledger round anchors are metadata, not visible chat')
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), before)
})

test('group-rows never presents unverified Ledger data as restored conversation rows', async t => {
  const first = { seq: 1, who: 'User', text: 'Saved user request' }
  const host = await start(t, { seq: 1, log: [first] })
  const none = (await host.call('group-rows', { roomId: 'r1', from: 1 })).value
  assert.equal(none.status, 'not-migrated')
  assert.deepEqual(none.rows, [])
  await publishInitialGroupBook(host.home, 'group-r1', [first, { seq: 2, who: 'Writer', botId: 'b', text: 'Unconfirmed reply' }])
  const before = readFileSync(join(host.home, 'state.json'), 'utf8')
  const unsafe = (await host.call('group-rows', { roomId: 'r1', from: 1 })).value
  assert.equal(unsafe.status, 'ledger-ahead')
  assert.equal(unsafe.requiresRecovery, true)
  assert.deepEqual(unsafe.rows, [])
  assert.equal(unsafe.open, false)
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), before)
  const invalid = (await host.call('group-rows', { roomId: 'r1', from: 0 })).value
  assert.deepEqual(invalid.rows, [])
  const backward = (await host.call('group-rows', { roomId: 'r1', from: 3, to: 1 })).value
  assert.deepEqual(backward.rows, [])
})

// 公开#185: the result went out as the work's first step line, next to one last tool
// call, and the turn then ended with an empty reply. Chief, which asked for the work,
// was never called to answer it.
const resultAsStep = async (t, ask) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  const first = host.round('c1', host.say(ask))
  if (ask.startsWith('@Chief')) {
    await settle(() => host.agentOf('ga').calls.length === 1)
    host.begin('ga')
    host.finish('ga', '@Writer 把文档整理好')
  }
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'pwsh', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.emit('gb', 'assistant/message', { message: { content: [{ type: 'text', text: '整理好了，在 docs/ 下。' }, { type: 'tool-call', id: 'k2', name: 'pwsh', arguments: '{}' }] } })
  host.emit('gb', 'tool/call', { callId: 'k2', name: 'pwsh', arguments: '{}' })
  await settle(() => host.agentOf('r1').calls.length === 1)
  const step = host.takePost()
  assert.deepEqual([step.source.progress, step.source.quiet, text(step)], [true, true, '[Group post from Writer]\n整理好了，在 docs/ 下。'])
  const stepRound = host.round('c2', step)
  await settle(() => stepRound() !== undefined)
  host.emit('gb', 'tool/result', { callId: 'k2' })
  host.finish('gb', '')
  return host
}

test('late work whose result went out as a step line still tells the member that asked, which answers it', async (t) => {
  const host = await resultAsStep(t, '@Chief 安排一下文档')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const done = host.takePost()
  assert.deepEqual([done.source.done, done.source.late, done.source.askedBy], [true, true, 'a'])
  const third = host.round('c3', done)
  await settle(() => host.agentOf('ga').calls.length === 2)
  const prompt = text(host.agentOf('ga').calls[1])
  assert.match(prompt, /Writer finished the work you asked for/)
  assert.match(prompt, /Writer: 整理好了，在 docs\/ 下。/)
  host.begin('ga')
  host.finish('ga', '收到，辛苦了。')
  await settle(() => third() !== undefined)
  assert.deepEqual(kinds(third()), [['done', 'Writer'], ['message', 'Chief']])
  assert.deepEqual(host.agentOf('gc').calls, [])
  const log = JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1.log.map(line => [line.who, line.kind ?? 'message'])
  assert.deepEqual(log.slice(-3), [['Writer', 'message'], ['Writer', 'done'], ['Chief', 'message']])
})

test('late work the user asked for directly ends without a post once its result is out', async (t) => {
  const host = await resultAsStep(t, '@Writer 把文档整理好')
  for (let i = 0; i < 20; i += 1) await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(host.agentOf('r1').calls, [])
})

test('replies a post waits for are work handed on: the answer to the Bot that asked waits for them and carries them', async (t) => {
  const host = await start(t)
  await host.tool('message_bot', { to: 'Chief', message: '让群里看一下文档' }, 'c')
  host.begin('a')
  const posted = await host.tool('post_to_group', { group: 'Ops', message: '@Writer 看一下文档', report_back: true }, 'a')
  assert.match(posted, /your answer goes to Tester once all of it is back\.$/)
  host.finish('a', '已经让 Writer 去看了。')
  const waiting = (await host.call('state', {})).value
  assert.equal(waiting.activity.a, 'waiting')
  assert.deepEqual(
    { bots: waiting.work.waiting.a.bots, rooms: waiting.work.waiting.a.rooms, for: waiting.work.waiting.a.for },
    { bots: [], rooms: ['r1'], for: ['c'] },
  )
  assert.equal(waiting.work.waiting.a.waits.length, 1)
  assert.equal(waiting.work.waiting.a.waits[0].room, 'r1')
  const done = host.round('c1', host.takePost())
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.finish('gb', '文档没问题。')
  await settle(() => done() !== undefined)
  await settle(() => host.agentOf('a').calls.length === 2)
  assert.deepEqual(host.agentOf('c').calls, [])
  const report = host.begin('a')
  assert.match(text(report), /^\[Group chat "Ops" · replies to your post · for the work Tester asked you for; your answer goes to Tester once everything you handed on is back\]/)
  host.finish('a', 'Writer 看过了，没问题。')
  await settle(() => host.agentOf('c').calls.length === 1)
  assert.equal(text(host.agentOf('c').calls[0]), '[Reply from Chief]\nWriter 看过了，没问题。\n\n[Handed back to Chief for this work]\n\nGroup "Ops":\nReplies to your post (oldest first):\nWriter: 文档没问题。')
})

test('a member called while still at earlier work lets the round go on at once', async (t) => {
  const host = await start(t)
  host.emit('gb', 'turn/start', { turn: 1 })
  const result = host.round('c1', host.say('@Writer 再看看这个'))
  await settle(() => result() !== undefined)
  assert.deepEqual(kinds(result()), [['working', 'Writer']])
  // A member at work has not run its turn here, and an event is not a message.
  assert.equal(result().replies[0].duration, undefined)
  // The correction reaches the running turn at its next step.
  assert.equal(host.agentOf('gb').inbox.nextTurn.length, 0)
  assert.equal(host.agentOf('gb').inbox.nextStep.length, 1)
  assert.match(text(host.agentOf('gb').inbox.nextStep[0]), /再看看这个/)
})

test('a steered group call keeps the later caller when the earlier work ends', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  const first = host.round('c1', host.say('@Writer 整理文档'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'work', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)

  await host.tool('post_to_group', { group: 'Ops', message: '@Writer 改用新模板' }, 'a')
  const second = host.round('c2', host.takePost())
  await settle(() => second() !== undefined)
  const inbox = host.agentOf('gb').inbox
  const correction = inbox.nextStep[0]
  assert.ok(correction)
  inbox.remove(correction.id)
  host.emit('gb', 'user/message', { content: correction.content, source: correction.source })
  host.finish('gb', '原来的工作完成了。')

  await settle(() => inbox.nextTurn.length === 1)
  const deferred = host.begin('gb')
  assert.equal(deferred.source.role, 'room')
  assert.equal(deferred.source.askedBy, 'a')
  assert.equal(deferred.source.roomId, 'r1')
  assert.match(text(deferred), /改用新模板/)
  host.finish('gb', '已换成新模板。')
  await settle(() => host.agentOf('r1').calls.some(message => message.source.askedBy === 'a'))
  const report = host.agentOf('r1').calls.find(message => message.source.askedBy === 'a')
  assert.match(text(report), /已换成新模板/)
})

test('a deferred group call retains the skill selected by the user', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  assert.equal((await host.call('capability-save', { name: 'specific', kind: 'skill', description: 'Specific skill', content: 'Selected workflow.' })).ok, true)
  const first = host.round('earlier-work', host.say('@Writer Review the earlier report'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'work', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  const result = host.round('skill-correction', host.say('@Writer /specific Prepare a report'))
  await settle(() => result() !== undefined)
  const inbox = host.agentOf('gb').inbox
  const correction = inbox.nextStep[0]
  assert.deepEqual(correction.source.skillNames, ['specific'])
  inbox.remove(correction.id)
  host.emit('gb', 'user/message', { content: correction.content, source: correction.source })
  host.finish('gb', 'Earlier work completed.')
  await settle(() => inbox.nextTurn.length === 1)
  const deferred = host.begin('gb')
  assert.equal(deferred.source.role, 'room')
  assert.equal(deferred.source.roomId, 'r1')
  assert.deepEqual(deferred.source.skillNames, ['specific'])
  host.finish('gb', 'Report ready.')
})

test('a quick team tool does not let the round go on', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  const result = host.round('c1', host.say('@Writer 谁在群里？'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'list_bots', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS * 2)
  await settle(() => true)
  assert.equal(result(), undefined)
  host.finish('gb', 'Chief、Tester 和我。')
  await settle(() => result() !== undefined)
  assert.deepEqual(kinds(result()), [['message', 'Writer']])
})

// Under PTC the model calls run_code, and the program dispatches the real tools.
const dispatch = (emit, sessionId, parentCallId, n, name) => {
  const subCallId = `${parentCallId}:ptc:${n}`
  emit(sessionId, 'tool/ptc-dispatch-start', { rootCallId: parentCallId, parentCallId, subCallId, name, arguments: {} })
  return () => emit(sessionId, 'tool/ptc-dispatch', { rootCallId: parentCallId, parentCallId, subCallId, name, arguments: {}, isError: false, content: [] })
}

test('a PTC program that runs only team tools does not let the round go on', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  const result = host.round('c1', host.say('@Writer 群里刚才说了什么？'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'run_code', arguments: '{"code":"await read_group_chat({})"}' })
  dispatch(host.emit, 'gb', 'k1', 1, 'read_group_chat')()
  dispatch(host.emit, 'gb', 'k1', 2, 'list_bots')()
  host.emit('gb', 'tool/result', { callId: 'k1' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS * 2)
  await settle(() => true)
  assert.equal(result(), undefined)
  host.finish('gb', '在讨论文档的结构。')
  await settle(() => result() !== undefined)
  assert.deepEqual(kinds(result()), [['message', 'Writer']])
})

test('work inside a PTC program lets the round go on after the grace', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  const result = host.round('c1', host.say('@Writer 整理文档'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'run_code', arguments: '{}' })
  dispatch(host.emit, 'gb', 'k1', 1, 'read_group_chat')()
  dispatch(host.emit, 'gb', 'k1', 2, 'write')
  const { value } = await host.call('state', {})
  assert.deepEqual(value.work.rooms.r1.map(entry => [entry.botId, entry.tool]), [['b', 'write']])
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => result() !== undefined)
  assert.deepEqual(kinds(result()), [['working', 'Writer']])
})

test('work the user asked for is left for the user to read, and the user\'s message resets the relay count', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t, { relays: 5 })
  const first = host.round('c1', host.say('@Writer 整理文档'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  // The user's message resets the count.
  assert.equal(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1.relays, 0)
  host.finish('gb', '好了。')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.deepEqual([post.source.late, post.source.askedBy, post.source.quiet], [true, undefined, undefined])
  const second = host.round('c2', post)
  await settle(() => second() !== undefined)
  assert.deepEqual(second().replies, [])
  assert.deepEqual([host.agentOf('ga').calls.length, host.agentOf('gc').calls.length], [0, 0])
})

test('a late post that calls a member counts into the relays, and parks past the limit', async (t) => {
  // Three members, so the default relay limit is 9: the eighth relay still runs.
  const host = await start(t, { relays: 8 })
  host.emit('gb', 'turn/start', { turn: 1 })
  host.emit('gb', 'user/message', { content: [{ type: 'text', text: 'go' }], source: { kind: 'bot', role: 'room', exchangeId: 'x1', roomId: 'r1', askedBy: 'a' } })
  host.finish('gb', '@Tester 看看这个')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.deepEqual([post.source.late, post.source.quiet], [true, undefined])
  const first = host.round('c2', post)
  await settle(() => host.agentOf('gc').calls.length === 1)
  host.begin('gc')
  host.finish('gc', '[PASS]')
  await settle(() => first() !== undefined)
  assert.equal(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1.relays, 9)

  // The next late call parks: the group pauses instead of running it, and nothing
  // is dropped — the Tester just gets no turn until the user goes on.
  host.emit('gb', 'turn/start', { turn: 2 })
  host.emit('gb', 'user/message', { content: [{ type: 'text', text: 'more' }], source: { kind: 'bot', role: 'room', exchangeId: 'x2', roomId: 'r1', askedBy: 'a' } })
  host.finish('gb', '@Tester 再看一个')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const second = host.round('c3', host.takePost())
  await settle(() => second() !== undefined)
  const saved = JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1
  assert.equal(saved.relays, 9, 'the parked call did not run')
  assert.deepEqual(saved.paused.map(entry => [entry.id, entry.name]), [['c', 'Tester']])
  assert.equal('lateRounds' in saved, false)
  assert.equal(host.agentOf('gc').calls.length, 1, 'the parked call never reached the Tester')
  assert.deepEqual(second().replies.filter(reply => reply.kind === 'paused').map(reply => [reply.names, reply.count]), [[['Tester'], 9]])
})

// #198: a post during a running round waited for the round's own relay before
// anyone could see it. It is written into the log and the running round at once,
// and the relay it still opens shows it again nowhere.
const logLines = host => JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1.log
const busyRound = async (t, room, services) => {
  const host = await start(t, room, services)
  const first = host.round('c1', host.say('@Writer 整理文档'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'pwsh', arguments: '{}' })
  await settle(() => true)
  return { host, first }
}

test('a post during a running round is in the log at once, once, and shows in the round', async (t) => {
  const { host, first } = await busyRound(t)
  await host.tool('post_to_group', { group: 'Ops', message: '@Tester 看一下文档' }, 'a')
  const during = logLines(host)
  const logged = during.at(-1)
  assert.deepEqual([logged.who, logged.botId, logged.text], ['Chief', 'a', '@Tester 看一下文档'])
  const post = host.takePost()
  assert.equal(post.source.logged, logged.seq)
  host.finish('gb', '整理好了。')
  await settle(() => first() !== undefined)
  assert.ok(first().replies.some(reply => reply.botId === 'a' && reply.text === '@Tester 看一下文档'))

  // The relay the post opened skips its line but still calls the member it named.
  const second = host.round('c2', post)
  await settle(() => host.agentOf('gc').calls.length === 1)
  assert.equal(host.begin('gc').source.askedBy, 'a')
  assert.match(text(host.agentOf('gc').calls[0]), /Chief: @Tester 看一下文档/)
  host.finish('gc', '看过了。')
  await settle(() => second() !== undefined)
  assert.equal(logLines(host).filter(line => line.text === '@Tester 看一下文档').length, 1)
})

test('a post during a running round with report_back reports only the round it opened', async (t) => {
  const { host, first } = await busyRound(t)
  await host.tool('post_to_group', { group: 'Ops', message: '@Tester 看一下文档', report_back: true }, 'a')
  const post = host.takePost()
  assert.equal(typeof post.source.logged, 'number')
  host.finish('gb', '整理好了。')
  await settle(() => first() !== undefined)
  const second = host.round('c2', post)
  await settle(() => host.agentOf('gc').calls.length === 1)
  host.begin('gc')
  host.finish('gc', '看过了。')
  await settle(() => second() !== undefined)
  await settle(() => host.agentOf('a').calls.length === 1)
  const report = host.agentOf('a').calls[0]
  assert.match(text(report), /Tester: 看过了。/)
  assert.doesNotMatch(text(report), /看一下文档/)
})

test('a group post whose required save fails never publishes a success reply or starts a relay', async t => {
  const { host, first } = await busyRound(t)
  takeGroupStateLock(host)
  await host.tool('post_to_group', { group: 'Ops', message: '@Tester 未落盘的任务' }, 'a').catch(() => {})
  const live = await progress(host)
  assert.equal(live.replies.some(reply => reply.text === '@Tester 未落盘的任务'), false)
  assert.equal(host.agentOf('r1').calls.length, 0)
  assert.equal(host.agentOf('gc').calls.length, 0)
  host.finish('gb', '[PASS]')
  await settle(() => first() !== undefined)
  assert.equal(first().code, 'PERSISTENCE_BLOCKED')
  assert.equal(logLines(host).some(line => line.text === '@Tester 未落盘的任务'), false)
})

test('a late reply during a running round is logged at once and not repeated', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  const first = host.round('c1', host.say('@Chief 安排一下文档'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer 把文档整理好')
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'pwsh', arguments: '{}' })
  // The round moves on without Writer; its result lands while a second round runs.
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  const second = host.round('c2', host.say('@Chief 再确认一下'))
  await settle(() => host.agentOf('ga').calls.length === 2)
  host.begin('ga')
  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.finish('gb', '整理好了，在 docs/ 下。')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.equal(post.source.late, true)
  assert.equal(typeof post.source.logged, 'number')
  assert.ok(logLines(host).some(line => line.who === 'Writer' && line.text === '整理好了，在 docs/ 下。'))
  host.finish('ga', '确认过了。')
  await settle(() => second() !== undefined)
  assert.ok(second().replies.some(reply => reply.botId === 'b' && reply.text === '整理好了，在 docs/ 下。'))

  // The relay it opens still calls the member that asked, and writes the line nowhere again.
  const third = host.round('c3', post)
  await settle(() => host.agentOf('ga').calls.length === 3)
  host.begin('ga')
  host.finish('ga', '[PASS]')
  await settle(() => third() !== undefined)
  assert.equal(logLines(host).filter(line => line.text === '整理好了，在 docs/ 下。').length, 1)
})

test('a member stopped during a running round is logged at once and not repeated', async (t) => {
  const host = await start(t)
  const first = host.round('c1', host.say('@Writer @Tester 整理文档'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'pwsh', arguments: '{}' })
  // The user stops Writer while its turn still runs inside the round.
  const stopped = await host.call('stop-member-work', { roomId: 'r1', botId: 'b' })
  assert.deepEqual([stopped.ok, stopped.value], [true, true])
  assert.equal(logLines(host).some(line => line.kind === 'stopped'), false, 'request is not a completed stop')
  host.emit('gb', 'turn/end', { turn: 1, reason: { kind: 'aborted' } })
  await settle(() => logLines(host).some(line => line.kind === 'stopped'))
  const last = logLines(host).at(-1)
  assert.deepEqual([last.who, last.botId, last.kind], ['Writer', 'b', 'stopped'])
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.equal(post.source.stopped, true)
  assert.equal(typeof post.source.logged, 'number')
  await settle(() => host.agentOf('gc').calls.length === 1)
  host.begin('gc')
  host.finish('gc', '在整理了。')
  await settle(() => first() !== undefined)
  assert.ok(first().replies.some(reply => reply.kind === 'stopped' && reply.botId === 'b'))

  // The relay the stopped post opens writes no second event line.
  const second = host.round('c2', post)
  await settle(() => second() !== undefined)
  assert.equal(logLines(host).filter(line => line.kind === 'stopped').length, 1)
})

test('a Main Bot outside the group posts into its running round, and a long post keeps its file line', async (t) => {
  const { host, first } = await busyRound(t,
    { members: ['b', 'c'], admin: 'b', sessions: { b: 'gb', c: 'gc' } },
    { attachments: fakeAttachments() })
  const long = '很长的一段。'.repeat(MESSAGE_INLINE_MAX)
  await host.tool('post_to_group', { group: 'Ops', message: long }, 'a')
  const line = logLines(host).at(-1)
  assert.deepEqual([line.who, line.botId], ['Chief', 'a'])
  assert.equal(line.files?.length, 1)
  assert.match(line.text, /\[File "Post from Chief\.txt"/)
  const post = host.takePost()
  assert.equal(typeof post.source.logged, 'number')
  host.finish('gb', '整理好了。')
  await settle(() => first() !== undefined)
  const second = host.round('c2', post)
  await settle(() => host.agentOf('gb').calls.length === 2)
  host.begin('gb')
  host.finish('gb', '收到，看一下。')
  await settle(() => second() !== undefined)
  assert.equal(logLines(host).filter(entry => entry.files?.length === 1).length, 1)
})

test('a post with no round running keeps the old way: queued, no logged mark', async (t) => {
  const host = await start(t)
  await host.tool('post_to_group', { group: 'Ops', message: '@Writer 看一下文档' }, 'a')
  const post = host.takePost()
  assert.equal(post.source.logged, undefined)
  const first = host.round('c1', post)
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.finish('gb', '看了。')
  await settle(() => first() !== undefined)
  assert.equal(logLines(host).filter(line => line.text === '@Writer 看一下文档').length, 1)
})

// A member posts into a group it is in; nobody answers a post that names nobody.
test('an ordinary member posts into its group from its own chat; nobody answers', async (t) => {
  const host = await start(t)
  const posted = await host.tool('post_to_group', { group: 'Ops', message: '文档有了新进展' }, 'b')
  assert.match(posted, /Nobody answers it: your post only calls the members you name with @Name\.$/)
  assert.equal(host.agentOf('r1').calls.length, 1)

  const first = host.round('c1', host.takePost())
  await settle(() => first() !== undefined)
  const lines = logLines(host).filter(line => line.text === '文档有了新进展')
  assert.equal(lines.length, 1)
  assert.equal(lines[0].botId, 'b')
  assert.deepEqual(host.agentOf('ga').calls, [])
  assert.deepEqual(host.agentOf('gb').calls, [])
  assert.deepEqual(host.agentOf('gc').calls, [])
})

test('a member post calls only the members it names', async (t) => {
  const host = await start(t)
  await host.tool('post_to_group', { group: 'Ops', message: '@Tester 看一下文档' }, 'b')
  const first = host.round('c1', host.takePost())
  await settle(() => host.agentOf('gc').calls.length === 1)
  assert.equal(host.begin('gc').source.askedBy, 'b')
  assert.match(text(host.agentOf('gc').calls[0]), /Writer: @Tester 看一下文档/)
  host.finish('gc', '看过了。')
  await settle(() => first() !== undefined)
  assert.deepEqual(host.agentOf('ga').calls, [])
  assert.deepEqual(host.agentOf('gb').calls.filter(call => call.source?.role !== 'post'), [])
})

test('a post from a Bot with brackets in its name reaches the group and its member unchanged', async (t) => {
  const host = await start(t)
  assert.equal((await host.call('update-bot', { id: 'b', name: 'A[B]C' })).ok, true)
  const body = '@Tester Check [notes](https://example.test)\n[Keep this line]'
  await host.tool('post_to_group', { group: 'Ops', message: body }, 'b')
  const post = host.takePost()
  assert.equal(post.source.senderName, 'A[B]C')
  assert.equal(text(post), `[Group post from A[B]C]\n${body}`)
  const round = host.round('c1', post)
  await settle(() => host.agentOf('gc').calls.length === 1)
  assert.ok(text(host.begin('gc')).includes(`A[B]C: ${body}`))
  host.finish('gc', 'Checked.')
  await settle(() => round() !== undefined)
  const [line] = logLines(host).filter(entry => entry.botId === 'b')
  assert.equal(line.who, 'A[B]C')
  assert.equal(line.text, body)
})

test('a member post that names only itself calls nobody', async (t) => {
  const host = await start(t)
  const rejected = await host.tool('post_to_group', { group: 'Ops', message: '@Writer 记一下', report_back: true }, 'b')
  assert.match(rejected, /Nobody would answer: your post only calls the members you name/)
  assert.equal(host.agentOf('r1').calls.length, 0)
  assert.equal(logLines(host).length, 0)

  const posted = await host.tool('post_to_group', { group: 'Ops', message: '@Writer 记一下' }, 'b')
  assert.match(posted, /Nobody answers it: your post only calls the members you name with @Name\.$/)
  const first = host.round('c1', host.takePost())
  await settle(() => first() !== undefined)
  assert.equal(logLines(host).filter(line => line.text === '@Writer 记一下').length, 1)
  assert.deepEqual(host.agentOf('ga').calls, [])
  assert.deepEqual(host.agentOf('gc').calls, [])
})

test('a member post with @all calls nobody', async (t) => {
  const host = await start(t)
  await host.tool('post_to_group', { group: 'Ops', message: '@all 看一下文档' }, 'b')
  const first = host.round('c1', host.takePost())
  await settle(() => first() !== undefined)
  assert.deepEqual(host.agentOf('ga').calls, [])
  assert.deepEqual(host.agentOf('gc').calls, [])
  assert.equal(logLines(host).filter(line => line.text === '@all 看一下文档').length, 1)
})

test('a member post that names nobody is rejected with report_back', async (t) => {
  const host = await start(t)
  const posted = await host.tool('post_to_group', { group: 'Ops', message: '快看文档', report_back: true }, 'b')
  assert.match(posted, /Nobody would answer: your post only calls the members you name/)
  assert.equal(host.agentOf('r1').calls.length, 0)
  assert.equal(logLines(host).length, 0)
  assert.deepEqual(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).works ?? {}, {})
})

test('a member post during a running round is logged at once and calls nobody next', async (t) => {
  const { host, first } = await busyRound(t)
  await host.tool('post_to_group', { group: 'Ops', message: '群里的进展' }, 'b')
  const during = logLines(host)
  const logged = during.at(-1)
  assert.deepEqual([logged.who, logged.botId, logged.text], ['Writer', 'b', '群里的进展'])
  const post = host.takePost()
  assert.equal(post.source.logged, logged.seq)
  host.finish('gb', '整理好了。')
  await settle(() => first() !== undefined)

  const second = host.round('c2', post)
  await settle(() => second() !== undefined)
  assert.equal(logLines(host).filter(line => line.text === '群里的进展').length, 1)
  assert.deepEqual(host.agentOf('ga').calls, [])
  assert.deepEqual(host.agentOf('gc').calls, [])
})

test('a member post that calls nobody does not pick the speakers over a user message', async (t) => {
  const host = await start(t)
  await host.tool('post_to_group', { group: 'Ops', message: '让群里注意' }, 'b')
  // Both land in the same relay; the user's message picks the speakers.
  host.emit('r1', 'user/message', host.takePost())
  const first = host.round('c1', host.say('检查一下文档'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '看过了。')
  await settle(() => first() !== undefined)
  assert.deepEqual(host.agentOf('gb').calls.filter(call => call.source?.role !== 'post'), [])
  assert.deepEqual(host.agentOf('gc').calls, [])
})

test('a member cannot post into a group it is not in', async (t) => {
  const host = await start(t, {}, undefined, {
    r2: { id: 'r2', name: 'Lab', members: ['a', 'c'], mode: 'admin', admin: 'a', named: true, sessions: {}, log: [], seq: 0, seen: {} },
  })
  const posted = await host.tool('post_to_group', { group: 'Lab', message: '看一下' }, 'b')
  assert.match(posted, /No group chat called "Lab" that you can see/)
  assert.equal(host.agentOf('r2').calls.length, 0)
  assert.equal(logLines(host).length, 0)
})

// Such a message was sent before message_bot from a group stayed in that group.
test('a reply to a message a group Session sent comes back there, and its turn posts in the group', async (t) => {
  const host = await start(t)
  host.emit('c', 'turn/start', { turn: 1 })
  host.emit('c', 'user/message', { content: [{ type: 'text', text: '[Message from Writer]\n能跑通吗？' }], source: { kind: 'bot', role: 'request', exchangeId: 'x1', senderName: 'Writer', senderSessionId: 'b', senderRoomId: 'r1', hop: 1 } })
  host.emit('c', 'assistant/message', { message: { content: [{ type: 'text', text: 'ok' }] } })
  host.emit('c', 'turn/end', { turn: 1, reason: { kind: 'completed' } })
  await settle(() => host.agentOf('gb').calls.length === 1)
  assert.deepEqual(host.agentOf('b').calls, [])
  assert.match(text(host.begin('gb')), /^\[Reply from Tester\]\nok/)
  host.finish('gb', 'Tester 说可以，我继续。')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.deepEqual([post.source.late, text(post)], [true, '[Group post from Writer]\nTester 说可以，我继续。'])
})

test('the user stops a member\'s work in a group, and the group shows it', async (t) => {
  const host = await start(t)
  assert.equal((await host.call('stop-member-work', { roomId: 'r1', botId: 'b' })).value, false)
  host.emit('gb', 'turn/start', { turn: 1 })
  assert.equal((await host.call('stop-member-work', { roomId: 'r1', botId: 'b' })).value, true)
  assert.deepEqual(host.agentOf('gb').cancelled, [{ kind: 'user' }])
  assert.deepEqual(logLines(host), [], 'no completed-stop notice while the tool remains active')
  host.emit('gb', 'turn/end', { turn: 1, reason: { kind: 'aborted' } })
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.deepEqual([post.source.stopped, post.source.quiet], [true, true])
  const result = host.round('c1', post)
  await settle(() => result() !== undefined)
  assert.deepEqual(kinds(result()), [['stopped', 'Writer']])
  const log = JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1.log
  assert.deepEqual(log.map(line => [line.who, line.kind]), [['Writer', 'stopped']])
})

// A non-cooperative tool keeps the Session active after cancel(). The UI must not
// announce a completed stop until DSH emits turn/end for that exact turn.
test('stop request stays pending during an in-flight tool and is idempotent', async t => {
  const host = await start(t)
  host.emit('gb', 'turn/start', { turn: 1 })
  host.emit('gb', 'tool/call', { callId: 'slow', name: 'chem_futures_history', arguments: '{}' })
  assert.equal((await host.call('stop-member-work', { roomId: 'r1', botId: 'b' })).value, true)
  assert.equal((await host.call('stop-member-work', { roomId: 'r1', botId: 'b' })).value, true)
  assert.deepEqual(host.agentOf('gb').cancelled, [{ kind: 'user' }])
  assert.equal(logLines(host).length, 0, 'tool is still running; no false completed-stop notice')
  const status = (await host.call('state', {})).value
  assert.equal(status.work.rooms.r1.some(entry => entry.botId === 'b'), true)
  host.emit('gb', 'tool/result', { callId: 'slow' })
  assert.equal(logLines(host).length, 0, 'tool result alone is not turn completion')
  host.emit('gb', 'turn/end', { turn: 1, reason: { kind: 'aborted' } })
  // With no round running, postToRoom queues the stop notice for the next relay.
  // It does not append the group log until that relay handles the message.
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.deepEqual([post.source.stopped, post.source.quiet], [true, true])
  const result = host.round('stop-confirmed', post)
  await settle(() => result() !== undefined)
  assert.deepEqual(kinds(result()), [['stopped', 'Writer']])
  assert.equal(logLines(host).filter(line => line.kind === 'stopped').length, 1)
})

test('a completed turn is not mislabeled stopped when a cancellation races it', async t => {
  const host = await start(t)
  host.emit('gb', 'turn/start', { turn: 1 })
  assert.equal((await host.call('stop-member-work', { roomId: 'r1', botId: 'b' })).value, true)
  host.emit('gb', 'turn/end', { turn: 1, reason: { kind: 'completed' } })
  assert.equal(logLines(host).some(line => line.kind === 'stopped'), false)
})

// Upstream #616: DSH's stop only covers the round, not lingering member turns.
test('stop all cancels this group round and its busy members, not private work', async t => {
  const host = await start(t)
  assert.equal((await host.call('stop-room-work', { roomId: 'r1' })).value, false)
  assert.equal((await host.call('stop-room-work', { roomId: 'unknown' })).value, false)
  host.emit('gb', 'turn/start', { turn: 1 }) // Writer is still working on earlier group work
  const first = host.round('stop-all', host.say('@Chief 看看进度'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.emit('c', 'turn/start', { turn: 1 }) // Tester's own private chat
  const response = await host.call('stop-room-work', { roomId: 'r1' })
  assert.deepEqual([response.ok, response.value], [true, true])
  for (const id of ['r1', 'ga', 'gb']) assert.deepEqual(host.agentOf(id).cancelled, [{ kind: 'user' }], id)
  for (const id of ['c', 'gc']) assert.deepEqual(host.agentOf(id).cancelled, [], id)
  assert.deepEqual(logLines(host).map(line => [line.who, line.kind]), [['User', undefined]])
  host.emit('ga', 'turn/end', { turn: 1, reason: { kind: 'aborted' } })
  host.emit('gb', 'turn/end', { turn: 1, reason: { kind: 'aborted' } })
  await settle(() => logLines(host).filter(line => line.kind === 'stopped').length === 2)
  await settle(() => first() !== undefined)
  assert.deepEqual(logLines(host).filter(line => line.kind === 'stopped').map(line => line.who).sort(), ['Chief', 'Writer'])
})

test('members still at work show in the team view and in the prompts of the others', async (t) => {
  const host = await start(t)
  host.emit('gb', 'turn/start', { turn: 1 })
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'pwsh', arguments: '{}' })
  const result = host.round('c1', host.say('@Tester 你怎么看'))
  await settle(() => host.agentOf('gc').calls.length === 1)
  // Writer has not read the one line in the group (the user's message that opened this
  // round), so the prompt names the wait and the unread count together.
  assert.match(text(host.agentOf('gc').calls[0]), /Still at work on what they were asked; each posts here when done: Writer \(1 min, with 1 group message\(s\) it has not read yet\)\./)
  host.begin('gc')
  const { value } = await host.call('state', {})
  assert.deepEqual(value.work.rooms.r1.map(entry => [entry.botId, entry.tool, entry.speaking]), [['b', 'pwsh', undefined], ['c', undefined, true]])
  host.finish('gc', '没问题。')
  await settle(() => result() !== undefined)
})

// #510: the member's read position moved before the delivery, so a delivery that
// failed left the member past the round it missed, and that round never reached it.
test('a member whose delivery failed sees the round it missed in its next prompt', async (t) => {
  const host = await start(t)
  // The delivery to Writer fails once; the Session is there, the message did not land.
  let failed = false
  host.ctx.sessions.flush = async (session) => {
    if (session?.id === 'gb' && !failed) {
      failed = true
      throw new Error('the session log could not be written')
    }
  }
  const first = host.round('c1', host.say('@Chief 安排一下文档'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer 把文档整理好')
  await settle(() => first() !== undefined)
  assert.deepEqual(kinds(first()), [['message', 'Chief'], ['failed', 'Writer']])
  // The failed delivery leaves the member where it was: it has read nothing yet.
  assert.equal(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1.seen.b, undefined)

  // Its next prompt carries the round it missed.
  const second = host.round('c2', host.say('@Writer 继续'))
  await settle(() => host.agentOf('gb').calls.length === 2)
  const prompt = text(host.agentOf('gb').calls[1])
  assert.match(prompt, /User: @Chief 安排一下文档/)
  assert.match(prompt, /Chief: @Writer 把文档整理好/)
  assert.match(prompt, /User: @Writer 继续/)

  // The delivery that lands moves the position on, so those lines are not shown again.
  host.begin('gb')
  host.finish('gb', '整理好了。')
  await settle(() => second() !== undefined)
  host.round('c3', host.say('@Writer 还有别的吗'))
  await settle(() => host.agentOf('gb').calls.length === 3)
  const later = text(host.agentOf('gb').calls[2])
  assert.doesNotMatch(later, /@Chief 安排一下文档/)
  assert.doesNotMatch(later, /@Writer 继续/)
})

// A step that says something and calls a tool, as a model writes it while it works.
const step = (host, sessionId, said, callId, name = 'pwsh', args = '{}') => {
  host.emit(sessionId, 'assistant/message', { message: { content: [{ type: 'text', text: said }, { type: 'tool-call', id: callId, name }] } })
  host.emit(sessionId, 'tool/call', { callId, name, arguments: args })
}
const progress = async host => (await host.call('room-progress', { roomId: 'r1' })).value[0]
const waitForRoundReplies = async (host, count) => {
  const until = Date.now() + 3000
  while (Date.now() < until) {
    const live = await progress(host)
    if (live?.replies?.length >= count) return live
    await realDelay(10)
  }
  assert.fail('committed round reply not visible before timeout')
}

test('what a member writes while it works shows in the round at once, and its @ calls members', async (t) => {
  const host = await start(t)
  const result = host.round('c1', host.say('@Writer 整理文档'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  step(host, 'gb', '收到，我先看看 docs/ 的结构。@Tester 你等下帮我验一下', 'k1', 'list_bots')
  const live = await waitForRoundReplies(host, 1)
  assert.deepEqual(live.replies.map(reply => [reply.name, reply.text]), [['Writer', '收到，我先看看 docs/ 的结构。@Tester 你等下帮我验一下']])
  assert.equal(live.speaking, 'b')
  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.finish('gb', '整理好了。')
  await settle(() => host.agentOf('gc').calls.length === 1)
  assert.match(text(host.begin('gc')), /Writer: 收到，我先看看 docs\/ 的结构。[\s\S]*Writer: 整理好了。/)
  host.finish('gc', '验过了。')
  await settle(() => result() !== undefined)
  assert.deepEqual(result().replies.map(reply => [reply.name, reply.text]), [['Writer', '收到，我先看看 docs/ 的结构。@Tester 你等下帮我验一下'], ['Writer', '整理好了。'], ['Tester', '验过了。']])
  const log = JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1.log
  assert.deepEqual(log.map(line => line.who), ['User', 'Writer', 'Writer', 'Tester'])
})

test('a member whose every message went out while it worked counts as posted, not passed', async (t) => {
  const host = await start(t)
  const result = host.round('c1', host.say('@Writer 看一下'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  step(host, 'gb', '我看一下。', 'k1', 'list_bots')
  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.emit('gb', 'turn/end', { turn: 1, reason: { kind: 'completed' } })
  await settle(() => result() !== undefined)
  assert.deepEqual([result().passed, result().replies.map(reply => reply.text)], [[], ['我看一下。']])
})

test('a member\'s messages carry how long its turn ran', async (t) => {
  const host = await start(t)
  const result = host.round('c1', host.say('@Writer 整理文档'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  step(host, 'gb', '收到，先看看。', 'k1', 'list_bots')
  const live = await waitForRoundReplies(host, 1)
  assert.equal(typeof live.replies[0].duration, 'number')
  assert.ok(live.replies[0].duration >= 0)
  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.finish('gb', '整理好了。')
  await settle(() => result() !== undefined)
  const messages = result().replies.filter(reply => reply.kind === undefined)
  assert.deepEqual(messages.map(reply => reply.text), ['收到，先看看。', '整理好了。'])
  for (const reply of messages) {
    assert.equal(typeof reply.duration, 'number')
    assert.ok(reply.duration >= 0)
  }
  assert.ok(result().replies.every(reply => reply.kind === undefined || reply.duration === undefined))
})

// Simulate another DSH host holding the group state lock. The current host
// must not treat a reply as committed, even if a model has already generated it.
const takeGroupStateLock = host => {
  const path = join(host.home, 'state.lock')
  rmSync(path, { force: true })
  writeFileSync(path, JSON.stringify({ host: 'another-machine', pid: 1, token: 'other-writer' }))
}

test('experimental #1351 registers a two-member Bot call in state before delivering either turn', async t => {
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  const result = host.round('batch-registration', host.say('@Chief coordinate procurement'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer @Tester verify purchasing inputs')
  await settle(() => host.agentOf('gb').calls.length === 1)
  const state = JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8'))
  const batches = Object.values(state.roomBatches ?? {})
  assert.equal(batches.length, 1, 'one Bot mention creates exactly one call batch')
  const batch = batches[0]
  assert.equal(batch.roomId, 'r1')
  assert.equal(batch.by, 'a')
  assert.deepEqual(batch.pending, ['b', 'c'])
  assert.deepEqual(batch.done, [])
  assert.deepEqual(batch.results, [])
  assert.equal(batch.answered, false)
  assert.equal(batch.worked, false)
  assert.equal(host.agentOf('gc').calls.length, 0, 'second member is not delivered before first completes')
  host.begin('gb')
  host.finish('gb', 'Writer checked the inputs.')
  await settle(() => host.agentOf('gc').calls.length === 1)
  const midway = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(midway.pending, ['c'], 'the first completed member is persisted before the second begins')
  assert.deepEqual(midway.done, ['Writer'])
  assert.deepEqual(midway.doneIds, ['b'])
  assert.ok(midway.results.some(entry => entry.name === 'Writer' && Number.isSafeInteger(entry.seq)))
  host.begin('gc')
  host.finish('gc', 'Tester checked the inputs.')
  await settle(() => result() !== undefined)
  const settled = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(settled.pending, [])
  assert.deepEqual(settled.done, ['Writer', 'Tester'])
  assert.deepEqual(settled.doneIds, ['b', 'c'])
  assert.equal(settled.answered, false, 'do not claim the caller has been awakened before recovery is wired')
})

test('experimental #1351 saves a Bot opening-post call batch before dispatching members', async t => {
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  host.emit('ga', 'turn/start', { turn: 1 })
  host.emit('ga', 'user/message', { content: [{ type: 'text', text: 'go' }],
    source: { kind: 'bot', role: 'room', exchangeId: 'opening', roomId: 'r1', hop: 0 } })
  step(host, 'ga', '@Writer @Tester verify an initial procurement question', 'initial-tool')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const result = host.round('bot-opening-post', host.takePost())
  await settle(() => host.agentOf('gb').calls.length === 1)
  const saved = JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8'))
  const batches = Object.values(saved.roomBatches ?? {})
  assert.equal(batches.length, 1)
  assert.equal(batches[0].by, 'a')
  assert.deepEqual(batches[0].pending, ['b', 'c'])
  assert.equal(host.agentOf('gc').calls.length, 0)
  host.begin('gb')
  host.finish('gb', 'Writer finished')
  await settle(() => host.agentOf('gc').calls.length === 1)
  const midway = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(midway.pending, ['c'])
  host.begin('gc')
  host.finish('gc', 'Tester finished')
  await settle(() => result() !== undefined)
  assert.deepEqual(Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0].pending, [])
})

test('experimental #1351 merges a repeated Bot call without losing completed siblings', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  const first = host.round('first-batch', host.say('@Chief coordinate procurement'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer @Tester check the supplier')
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'still-working', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => host.agentOf('gc').calls.length === 1)
  host.begin('gc')
  host.finish('gc', 'Tester verified the supplier')
  await settle(() => first() !== undefined)
  const prior = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)
    .find(batch => batch.by === 'a')
  assert.deepEqual(prior.pending, ['b'])
  assert.deepEqual(prior.doneIds, ['c'])
  assert.equal(prior.results.length, 1)

  await host.tool('post_to_group', { group: 'Ops', message: '@Writer revise the supplier list' }, 'a')
  const second = host.round('second-batch', host.takePost())
  await settle(() => Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)
    .some(batch => batch.by === 'a' && batch.key !== prior.key))
  const updated = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)
    .filter(batch => batch.by === 'a')
  assert.equal(updated.length, 1, 'one caller cannot leave two batches pending for Writer')
  assert.deepEqual(updated[0].pending, ['b'])
  assert.deepEqual(updated[0].doneIds, ['c'])
  assert.deepEqual(updated[0].done, ['Tester'])
  assert.deepEqual(updated[0].results, prior.results, 'the earlier Tester result survives the handover')
  assert.equal(updated[0].answered, false, 'no caller wake before a durable receipt')
  await settle(() => second() !== undefined)
})

test('experimental #1351 late result stays pending until the group Ledger admits its post', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  const first = host.round('late-batch-first', host.say('@Chief coordinate the supplier check'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer @Tester verify the supplier')
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'supplier-check', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => host.agentOf('gc').calls.length === 1)
  host.begin('gc')
  host.finish('gc', 'Tester checked the supplier')
  await settle(() => first() !== undefined)
  const previous = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(previous.pending, ['b'])
  assert.equal(previous.worked, true, 'the tool work is persisted without settling it')
  host.emit('gb', 'tool/result', { callId: 'supplier-check' })
  host.finish('gb', 'Writer finished the supplier check')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const queued = host.agentOf('r1').calls[0]
  assert.equal(queued.source.batch, previous.key)
  assert.equal(queued.source.batchEnd, true)
  assert.equal(queued.source.askedBy, 'a')
  assert.deepEqual(Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0].pending, ['b'],
    'DSH followup is not a committed Ledger result')
  const admitted = host.round('late-batch-committed', host.takePost())
  await settle(() => host.agentOf('ga').calls.length === 2)
  const saved = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(saved.pending, [])
  assert.deepEqual(saved.doneIds, ['c', 'b'])
  assert.equal(saved.results.length, 2)
  assert.equal(saved.results.at(-1).name, 'Writer')
  assert.ok(Number.isSafeInteger(saved.results.at(-1).seq))
  assert.equal(saved.answered, false, 'no automatic replay or unacknowledged wake')
  host.begin('ga')
  host.finish('ga', 'Thanks, both supplier checks are recorded')
  await settle(() => admitted() !== undefined)
})

test('experimental #1351 late @mention can call a Bot while other batch members still work', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  const first = host.round('mention-batch-first', host.say('@Chief verify supplier background'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer @Tester verify the supplier')
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'writer-work', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => host.agentOf('gc').calls.length === 1)
  host.begin('gc')
  host.emit('gc', 'tool/call', { callId: 'tester-work', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  const batch = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(batch.pending, ['b', 'c'])
  host.emit('gb', 'tool/result', { callId: 'writer-work' })
  host.finish('gb', '@Chief Please review the supplier anomaly')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.equal(post.source.batch, batch.key)
  assert.equal(post.source.quiet, undefined, 'a real @mention must not be swallowed by quiet partial-result logic')
  assert.equal(post.source.askedBy, undefined, 'other batch members still work; no automatic caller wake')
  const next = host.round('mention-batch-post', post)
  await settle(() => host.agentOf('ga').calls.length === 2)
  const saved = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(saved.pending, ['c'])
  assert.equal(saved.answered, true)
  host.begin('ga')
  host.finish('ga', 'Reviewed; continue checking')
  await settle(() => next() !== undefined)
})

test('experimental #1351 silent late PASS clears its own pending call without posting or replaying', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  const first = host.round('pass-pending', host.say('@Chief check the supplier'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer verify and PASS if there is no finding')
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'silent-check', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  const before = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(before.pending, ['b'])
  host.emit('gb', 'tool/result', { callId: 'silent-check' })
  host.finish('gb', '[PASS]')
  await settle(() => Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0].pending.length === 0)
  const settled = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(settled.done, [])
  assert.deepEqual(settled.results, [])
  assert.equal(host.agentOf('r1').calls.length, 0, 'silent PASS must not invent a reply or replay work')
})

test('experimental #1351 late failure settles only its caller after durable group admission', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  const first = host.round('failed-pending', host.say('@Chief check the supplier'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer check the supplier')
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'failing-check', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  const batch = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(batch.pending, ['b'])
  host.emit('gb', 'turn/end', { turn: 1, reason: { kind: 'error', error: { code: 'RATE_LIMIT', message: 'provider unavailable' } } })
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.equal(post.source.failed.code, 'RATE_LIMIT')
  assert.equal(post.source.batch, batch.key)
  assert.deepEqual(Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0].pending, ['b'],
    'the failure event has not been admitted or durably saved')
  const admitted = host.round('failed-admission', post)
  await settle(() => admitted() !== undefined)
  const persisted = Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0]
  assert.deepEqual(persisted.pending, [])
  assert.deepEqual(persisted.done, [])
  assert.deepEqual(persisted.results, [])
})

test('experimental #1351 confirmed member Stop settles its pending work only on group admission', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  const first = host.round('stopped-pending', host.say('@Chief check the supplier'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer check the supplier')
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'stopped-check', name: 'write', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  assert.deepEqual(Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0].pending, ['b'])
  assert.equal((await host.call('stop-member-work', { roomId: 'r1', botId: 'b' })).value, true)
  assert.deepEqual(Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0].pending, ['b'],
    'a cancellation request alone is not an acknowledged stop')
  host.emit('gb', 'turn/end', { turn: 1, reason: { kind: 'aborted' } })
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.equal(post.source.stopped, true)
  assert.deepEqual(Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0].pending, ['b'],
    'DSH delivery is not a required-save group receipt')
  const admitted = host.round('confirmed-stop-admission', post)
  await settle(() => admitted() !== undefined)
  assert.deepEqual(Object.values(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).roomBatches)[0].pending, [])
})

test('experimental group relay creates durable anchored windows without changing old reply display', async t => {
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  const first = host.round('anchored-first', host.say('@Writer first procurement request'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.finish('gb', 'First procurement reply')
  await settle(() => first() !== undefined)
  assert.equal(first().from, 1)
  assert.equal(typeof first().anchor, 'string')
  assert.match(await host.tool('read_group_chat', { group: 'Ops', seq: 1 }, 'a'),
    /no recoverable message 1/, 'an internal round anchor must not appear as a chat message')
  assert.deepEqual(first().replies.filter(line => !line.kind).map(line => line.text), ['First procurement reply'])
  const open = (await host.call('group-rows', { roomId: 'r1', from: first().from, anchor: first().anchor })).value
  assert.equal(open.status, 'aligned')
  assert.equal(open.open, false)
  assert.equal(first().to, 3)
  assert.deepEqual(open.rows.map(line => line.text), ['@Writer first procurement request', 'First procurement reply'])
  const second = host.round('anchored-second', host.say('@Writer second procurement request'))
  await settle(() => host.agentOf('gb').calls.length === 2)
  host.begin('gb')
  host.finish('gb', 'Second procurement reply')
  await settle(() => second() !== undefined)
  assert.ok(second().from > first().from)
  assert.notEqual(second().anchor, first().anchor)
  const earlier = (await host.call('group-rows', { roomId: 'r1', from: first().from, anchor: first().anchor })).value
  const later = (await host.call('group-rows', { roomId: 'r1', from: second().from, anchor: second().anchor })).value
  assert.equal(earlier.open, false)
  assert.equal(later.open, false)
  assert.equal(second().to, 7)
  assert.deepEqual(earlier.rows.map(line => line.text), ['@Writer first procurement request', 'First procurement reply'])
  assert.deepEqual(later.rows.map(line => line.text), ['@Writer second procurement request', 'Second procurement reply'])
  const book = await readLedger(host.home, 'group-r1')
  assert.deepEqual(book.records.filter(line => line.event === 'anchor').map(line => [line.id, line.from]),
    [[first().anchor, first().from], [second().anchor, second().from]])
  const state = JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1
  assert.deepEqual(state.log.map(line => line.seq), [2, 3, 6, 7])
  assert.equal(state.seq, 8)
  assert.deepEqual(book.records.filter(line => line.event === 'round').map(line => [line.id, line.from, line.to]),
    [[first().anchor, first().from, first().to], [second().anchor, second().from, second().to]])
  assert.match(await host.tool('read_group_chat', { group: 'Ops', seq: 4 }, 'a'), /no recoverable message 4/)
  assert.equal((await host.call('group-rows', { roomId: 'r1', from: 1, anchor: first().anchor })).value.open, false)
  assert.equal((await host.call('group-rows', { roomId: 'r1', from: 1, anchor: 'forged' })).value.status, 'unknown-anchor')
})

test('experimental #1317 writer fsyncs group user input and Bot reply before exposing success', async t => {
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  const result = host.round('ledger-round-durable', host.say('@Writer 请核对聚氨酯采购价格'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  const first = await readLedger(host.home, 'group-r1')
  assert.equal(first.records.length, 2)
  assert.equal(first.records[0].event, 'anchor')
  assert.match(first.records[1].text, /聚氨酯采购价格/)
  const saved = JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1
  assert.equal(saved.seq, 2, 'anchor and message must be durable before member delivery')
  assert.equal(saved.log[0].text, first.records[1].text)
  host.begin('gb')
  host.finish('gb', '采购建议已核对。')
  await settle(() => result() !== undefined)
  const book = await readLedger(host.home, 'group-r1')
  assert.equal(book.records.length, 4)
  assert.equal(book.records[2].text, '采购建议已核对。')
  assert.equal(book.records[3].event, 'round')
  assert.equal(result().to, 3)
  assert.equal(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1.seq, 4)
  assert.deepEqual(result().replies.filter(item => item.kind === undefined).map(item => item.text), ['采购建议已核对。'])
  assert.match(await host.tool('read_group_chat', { group: 'Ops', seq: 2 }, 'a'), /聚氨酯采购价格/)
})

test('experimental group writer refuses uncertain lock and never delivers unsaved user input', async t => {
  const host = await start(t, {}, undefined, undefined, { experimentalGroupLedger: true })
  const before = readFileSync(join(host.home, 'state.json'), 'utf8')
  takeGroupStateLock(host)
  const result = host.round('ledger-no-unsafe-replay', host.say('@Writer 不应执行'))
  await settle(() => result() !== undefined)
  assert.match(result().code, /PERSISTENCE|LEDGER/)
  assert.equal(host.agentOf('gb').calls.length, 0)
  assert.equal(await readLedger(host.home, 'group-r1'), undefined)
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), before)
})

test('default legacy Host refuses to append a group that already has a Ledger', async t => {
  const host = await start(t)
  const stateBefore = readFileSync(join(host.home, 'state.json'), 'utf8')
  await publishInitialGroupBook(host.home, 'group-r1', [])
  const result = host.round('no-legacy-double-writer', host.say('@Writer 数据一致性检查'))
  await settle(() => result() !== undefined)
  assert.equal(result().code, 'LEDGER_MIGRATION_REQUIRED')
  assert.equal(host.agentOf('gb').calls.length, 0)
  assert.deepEqual((await readLedger(host.home, 'group-r1')).records, [])
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), stateBefore)
})

test('a Ledger published during a legacy round blocks the next Bot delivery', async t => {
  const host = await start(t)
  const result = host.round('ledger-appears-mid-turn', host.say('@Writer 先核对这一项'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  await publishInitialGroupBook(host.home, 'group-r1', [
    { seq: 1, who: 'User', text: '@Writer 先核对这一项' },
  ])
  const before = readFileSync(join(host.home, 'state.json'), 'utf8')
  host.finish('gb', '@Tester 下一步请执行')
  await settle(() => result() !== undefined)
  assert.equal(result().code, 'LEDGER_MIGRATION_REQUIRED')
  assert.equal(host.agentOf('gc').calls.length, 0)
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), before)
})

test('a migrated group cannot be renamed or deleted by legacy roster operations', async t => {
  const host = await start(t)
  await publishInitialGroupBook(host.home, 'group-r1', [])
  const before = readFileSync(join(host.home, 'state.json'), 'utf8')
  const changed = await host.tool('update_group', { group: 'Ops', notice: 'should not change' }, 'a')
  assert.match(changed, /Could not update/)
  assert.match(changed, /Ledger book/)
  await assert.rejects(host.tool('delete_group', { group: 'Ops' }, 'a'), /Ledger book/)
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), before)
})

test('a final member answer whose required save fails is shown as a failure and never calls its @mentions', async t => {
  const host = await start(t)
  const result = host.round('save-failed-final', host.say('@Writer 检查一下'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  takeGroupStateLock(host)
  host.finish('gb', '@Tester 请直接执行')
  await settle(() => result() !== undefined)
  assert.deepEqual(result().replies.filter(reply => reply.kind === 'failed').map(reply => [reply.name, reply.code]), [['Writer', 'PERSISTENCE']])
  assert.equal(result().replies.some(reply => reply.name === 'Writer' && reply.kind === undefined), false)
  assert.equal(host.agentOf('gc').calls.length, 0)
  assert.deepEqual(result().failed, ['Writer'])
  assert.deepEqual(JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1.log.map(line => line.who), ['User'])
})

test('a failed in-progress member step does not publish or call another Bot after turn end', async t => {
  const host = await start(t)
  const result = host.round('save-failed-step', host.say('@Writer 检查一下'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  takeGroupStateLock(host)
  step(host, 'gb', '@Tester 帮我做完', 'k1', 'list_bots')
  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.finish('gb', '[PASS]')
  await settle(() => result() !== undefined)
  assert.deepEqual(result().replies.filter(reply => reply.kind === 'failed').map(reply => [reply.name, reply.code]), [['Writer', 'PERSISTENCE']])
  assert.equal(result().replies.some(reply => reply.name === 'Writer' && reply.kind === undefined), false)
  assert.equal(host.agentOf('gc').calls.length, 0)
})

const legacySidecarFixture = host => {
  // The first row remains referenced by the last good state.json. Appending
  // seq 61 rotates the preview past that row but must never erase its file.
  const long = '历史化工数据：'.repeat(TEXT_KEPT)
  const dir = join(host.home, 'group-lines', 'r1')
  mkdirSync(dir, { recursive: true })
  const file = join(dir, '1.txt')
  writeFileSync(file, long.slice(0, GROUP_LINE_READ))
  return { file, contents: long.slice(0, GROUP_LINE_READ) }
}
const sixtyLineRoom = () => {
  const long = '历史化工数据：'.repeat(TEXT_KEPT)
  const log = Array.from({ length: 60 }, (_, index) => index === 0
    ? { seq: 1, who: 'User', text: long.slice(0, TEXT_KEPT), length: long.length }
    : { seq: index + 1, who: 'User', text: 'previous message ' + (index + 1) })
  return { seq: 60, log }
}

test('legacy sidecar survives the sixty-message preview rotation after a successful group save', async t => {
  const host = await start(t, sixtyLineRoom())
  const { file, contents } = legacySidecarFixture(host)
  const result = host.round('sidecar-preserve-success', host.say('@Writer 消息编号61'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.finish('gb', '[PASS]')
  await settle(() => result() !== undefined)
  const durable = JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1
  assert.ok(durable.seq >= 61)
  assert.equal(durable.log[0].seq, 2, 'the bounded state preview should still rotate')
  assert.equal(readFileSync(file, 'utf8'), contents, 'the older sidecar must remain available')
})

test('legacy sidecar remains intact when the rolling group state fails to save', async t => {
  const host = await start(t, sixtyLineRoom())
  const { file, contents } = legacySidecarFixture(host)
  const before = readFileSync(join(host.home, 'state.json'), 'utf8')
  takeGroupStateLock(host)
  const result = host.round('sidecar-preserve-save-failure', host.say('@Writer 无法保存的新消息'))
  await settle(() => result() !== undefined)
  assert.equal(result().code, 'PERSISTENCE_BLOCKED')
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), before)
  assert.equal(readFileSync(file, 'utf8'), contents)
  assert.equal(host.agentOf('gb').calls.length, 0)
})

test('an identical existing long-text sidecar can be safely reused without truncation', async t => {
  const host = await start(t, sixtyLineRoom())
  const dir = join(host.home, 'group-lines', 'r1')
  mkdirSync(dir, { recursive: true })
  const message = '@Writer ' + '已保存的内容'.repeat(TEXT_KEPT)
  const sidecar = join(dir, '61.txt')
  writeFileSync(sidecar, message)
  const result = host.round('identical-sidecar', host.say(message))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.finish('gb', '[PASS]')
  await settle(() => result() !== undefined)
  assert.equal(result().code, undefined)
  assert.equal(readFileSync(sidecar, 'utf8'), message)
  const state = JSON.parse(readFileSync(join(host.home, 'state.json'), 'utf8')).rooms.r1
  assert.ok(state.seq >= 61)
  assert.equal(state.log.find(line => line.seq === 61)?.length, message.length)
})

test('legacy sidecar collision cannot overwrite older bytes or dispatch new Bot work', async t => {
  const host = await start(t, sixtyLineRoom())
  const dir = join(host.home, 'group-lines', 'r1')
  mkdirSync(dir, { recursive: true })
  const collision = join(dir, '61.txt')
  writeFileSync(collision, 'UNCOMMITTED_PREVIOUS_WRITE_DO_NOT_OVERWRITE')
  const before = readFileSync(join(host.home, 'state.json'), 'utf8')
  const longNewMessage = '@Writer ' + '化工价格数据'.repeat(TEXT_KEPT)
  host.emit('r1', 'user/message', host.say(longNewMessage))
  await assert.rejects(
    host.tool('group_relay', {}, 'r1', { callId: 'sidecar-collision', signal: new AbortController().signal }),
    /Conflicting existing long-text sidecar/,
  )
  assert.equal(readFileSync(collision, 'utf8'), 'UNCOMMITTED_PREVIOUS_WRITE_DO_NOT_OVERWRITE')
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), before)
  assert.equal(host.agentOf('gb').calls.length, 0)
  const rejected = JSON.parse(await host.tool('group_relay', {}, 'r1', { callId: 'sidecar-collision-retry' }))
  assert.equal(rejected.code, 'PERSISTENCE_BLOCKED')
})

test('a queued group message is not dispatched when its initial state save fails', async t => {
  const host = await start(t)
  const before = readFileSync(join(host.home, 'state.json'), 'utf8')
  takeGroupStateLock(host)
  const result = host.round('admission-denied', host.say('@Writer 不应执行'))
  await settle(() => result() !== undefined)
  assert.equal(result().code, 'PERSISTENCE_BLOCKED')
  assert.deepEqual(result().replies, [])
  assert.equal(host.agentOf('gb').calls.length, 0)
  assert.equal(host.agentOf('ga').calls.length, 0)
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), before)
  const next = host.round('admission-still-blocked', host.say('@Tester 也不应执行'))
  await settle(() => next() !== undefined)
  assert.equal(next().code, 'PERSISTENCE_BLOCKED')
  assert.equal(host.agentOf('gc').calls.length, 0)
})

test('a new user message during a round stays in the DSH inbox on save failure', async t => {
  const host = await start(t)
  const first = host.round('in-progress-admission', host.say('@Writer 先进行'), { withInbox: true })
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  const queued = {
    id: 'inbox-uncommitted-user',
    source: { kind: 'user' },
    content: [{ type: 'text', text: '@Tester 新增任务' }],
  }
  const inbox = host.agentOf('r1').inbox
  inbox.nextStep.push(queued)
  takeGroupStateLock(host)
  host.finish('gb', '[PASS]')
  await settle(() => first() !== undefined)
  assert.equal(first().code, 'PERSISTENCE_BLOCKED')
  assert.ok(inbox.nextStep.some(message => message.id === queued.id), 'failed admission must not remove the inbox message')
  assert.equal(host.agentOf('gc').calls.length, 0, 'a failed user message must not call Tester')
  assert.equal(logLines(host).some(line => line.text === '@Tester 新增任务'), false)
})

test('a room whose required save failed rejects later rounds without consuming or dispatching them', async t => {
  const host = await start(t)
  const original = host.round('first-failed', host.say('@Writer 初始任务'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  takeGroupStateLock(host)
  host.finish('gb', '未保存的回答')
  await settle(() => original() !== undefined)
  assert.equal(original().code, 'PERSISTENCE_BLOCKED')
  assert.equal(original().replies.some(reply => reply.code === 'PERSISTENCE'), true)
  const diskBefore = readFileSync(join(host.home, 'state.json'), 'utf8')
  const second = host.round('blocked-second', host.say('@Writer 再试一次'))
  await settle(() => second() !== undefined)
  assert.equal(second().code, 'PERSISTENCE_BLOCKED')
  assert.match(second().error, /blocked until restart/)
  assert.deepEqual(second().replies, [])
  assert.equal(host.agentOf('gb').calls.length, 1, 'no repeat delivery while state is uncertain')
  assert.equal(host.agentOf('gc').calls.length, 0)
  assert.equal(readFileSync(join(host.home, 'state.json'), 'utf8'), diskBefore)
})

test('a failed step save blocks a new round even when the member has finished', async t => {
  const host = await start(t)
  const original = host.round('first-step', host.say('@Writer 分析'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  takeGroupStateLock(host)
  step(host, 'gb', '正在分析', 'k1', 'list_bots')
  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.finish('gb', '[PASS]')
  await settle(() => original() !== undefined)
  assert.equal(original().code, 'PERSISTENCE_BLOCKED')
  const again = host.round('new-after-failed-step', host.say('@Writer 继续'))
  await settle(() => again() !== undefined)
  assert.equal(again().code, 'PERSISTENCE_BLOCKED')
  assert.equal(host.agentOf('gb').calls.length, 1)
})

test('after the round went on, lines a member writes close together reach the group as one message; only the result is answered', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  const first = host.round('c1', host.say('@Chief 安排一下文档'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga')
  host.finish('ga', '@Writer 把文档整理好')
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  step(host, 'gb', '收到，开始整理。', 'k1')
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  assert.deepEqual(kinds(first()), [['message', 'Chief'], ['message', 'Writer'], ['working', 'Writer']])

  host.emit('gb', 'tool/result', { callId: 'k1' })
  step(host, 'gb', '目录理好了。', 'k2')
  host.emit('gb', 'tool/result', { callId: 'k2' })
  step(host, 'gb', '正文改完了，在改索引。', 'k3')
  await settle(() => true)
  assert.deepEqual(host.agentOf('r1').calls, [])
  t.mock.timers.tick(ROOM_STEP_GAP_MS)
  await settle(() => host.agentOf('r1').calls.length === 1)
  const update = host.takePost()
  assert.deepEqual([update.source.progress, update.source.quiet, update.source.askedBy, text(update)], [true, true, undefined, '[Group post from Writer]\n目录理好了。\n\n正文改完了，在改索引。'])
  const quiet = host.round('c2', update)
  await settle(() => quiet() !== undefined)
  assert.deepEqual(quiet().replies, [])

  // A line still held when the work ends opens the result.
  host.emit('gb', 'tool/result', { callId: 'k3' })
  step(host, 'gb', '索引也改完了。', 'k4')
  host.emit('gb', 'tool/result', { callId: 'k4' })
  host.finish('gb', '整理好了，在 docs/ 下。')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const done = host.takePost()
  assert.deepEqual([done.source.late, done.source.askedBy, text(done)], [true, 'a', '[Group post from Writer]\n索引也改完了。\n\n整理好了，在 docs/ 下。'])
  t.mock.timers.tick(ROOM_STEP_GAP_MS)
  await settle(() => true)
  assert.deepEqual(host.agentOf('r1').calls, [])
})

test('a step that calls a member with @ after the round went on starts a round for that member', async (t) => {
  const host = await start(t)
  host.emit('gb', 'turn/start', { turn: 1 })
  host.emit('gb', 'user/message', { content: [{ type: 'text', text: 'go' }], source: { kind: 'bot', role: 'room', exchangeId: 'x1', roomId: 'r1', askedBy: 'a' } })
  step(host, 'gb', '@Tester 帮我跑一下测试', 'k1')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.deepEqual([post.source.progress, post.source.quiet], [true, undefined])
  const result = host.round('c1', post)
  await settle(() => host.agentOf('gc').calls.length === 1)
  assert.equal(host.begin('gc').source.askedBy, 'b')
  host.finish('gc', '测试过了。')
  await settle(() => result() !== undefined)
  assert.deepEqual(host.agentOf('ga').calls, [])
})

test('a step joins a round that is running in the group', async (t) => {
  const host = await start(t)
  host.emit('gb', 'turn/start', { turn: 1 })
  host.emit('gb', 'user/message', { content: [{ type: 'text', text: 'go' }], source: { kind: 'bot', role: 'room', exchangeId: 'x1', roomId: 'r1', hop: 0 } })
  const result = host.round('c1', host.say('@Tester 你怎么看'))
  await settle(() => host.agentOf('gc').calls.length === 1)
  step(host, 'gb', '索引改完了。', 'k1')
  await settle(() => true)
  host.begin('gc')
  host.finish('gc', '没问题。')
  await settle(() => result() !== undefined)
  assert.deepEqual(result().replies.map(reply => [reply.name, reply.text]), [['Writer', '索引改完了。'], ['Tester', '没问题。']])
  assert.deepEqual(host.agentOf('r1').calls, [])
})

test('a turn that a finished background job starts in a group Session posts to the group', async (t) => {
  const host = await start(t)
  host.emit('gb', 'turn/start', { turn: 1 })
  host.emit('gb', 'user/message', { content: [{ type: 'text', text: 'background job pwsh-3 finished' }], source: { kind: 'tool-jobs', form: 'notice' } })
  step(host, 'gb', '下载完了，开始解压。', 'k1')
  await settle(() => host.agentOf('r1').calls.length === 1)
  assert.equal(text(host.takePost()), '[Group post from Writer]\n下载完了，开始解压。')
  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.finish('gb', '解压好了。')
  await settle(() => host.agentOf('r1').calls.length === 1)
  const post = host.takePost()
  assert.deepEqual([post.source.late, post.source.askedBy, text(post)], [true, undefined, '[Group post from Writer]\n解压好了。'])
})

test('a fresh part\'s opening line stays out of the group', async (t) => {
  const host = await start(t)
  host.emit('gb', 'turn/start', { turn: 1 })
  host.emit('gb', 'user/message', { content: [{ type: 'text', text: '[Handoff · part 2]' }], source: { kind: 'bot', role: 'handoff', handoff: true, exchangeId: 'h1', hop: 0 } })
  host.emit('gb', 'assistant/message', { message: { content: [{ type: 'text', text: 'Noted. I have my handoff note and carry on from here.' }] } })
  host.emit('gb', 'user/message', { content: [{ type: 'text', text: 'background job pwsh-7 finished' }], source: { kind: 'tool-jobs', form: 'notice' } })
  host.finish('gb', 'Ghidra 解压好了。')
  await settle(() => host.agentOf('r1').calls.length === 1)
  assert.equal(text(host.takePost()), '[Group post from Writer]\nGhidra 解压好了。')
})

test('a private message to a group Session is answered privately, without steps in the group', async (t) => {
  const host = await start(t)
  host.emit('gb', 'turn/start', { turn: 1 })
  host.emit('gb', 'user/message', { content: [{ type: 'text', text: '[Message from Tester]\n能帮我看下吗' }], source: { kind: 'bot', role: 'request', senderSessionId: 'c', senderName: 'Tester', exchangeId: 'x1', hop: 0 } })
  step(host, 'gb', '我看一下。', 'k1')
  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.finish('gb', '看过了，没问题。')
  await settle(() => host.agentOf('c').calls.length === 1)
  assert.match(text(host.agentOf('c').calls[0]), /我看一下。\n\n看过了，没问题。/)
  assert.deepEqual(host.agentOf('r1').calls, [])
})

test('the team view says what a member is doing in the call\'s own words', async (t) => {
  const host = await start(t)
  host.emit('gb', 'turn/start', { turn: 1 })
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'pwsh', arguments: JSON.stringify({ command: 'iwr https://example.com/x.zip', description: 'Download  Ghidra 12.1.4\nand check its hash' }) })
  host.emit('gc', 'turn/start', { turn: 1 })
  host.emit('gc', 'tool/call', { callId: 'k2', name: 'read', arguments: JSON.stringify({ file_path: 'E:\\src\\tools\\dump.py' }) })
  const { value } = await host.call('state', {})
  assert.deepEqual(value.work.rooms.r1.map(entry => [entry.botId, entry.tool, entry.note, entry.target]), [['b', 'pwsh', 'Download Ghidra 12.1.4 and check its hash', undefined], ['c', 'read', undefined, 'dump.py']])
  assert.equal(value.work.bots.b.note, 'Download Ghidra 12.1.4 and check its hash')
  assert.deepEqual(value.work.bots.b.task, { name: 'pwsh', summary: 'Download Ghidra 12.1.4 and check its hash', running: true, failed: false })
  host.emit('gb', 'tool/result', { callId: 'k1' })
  const completed = (await host.call('state', {})).value.work.bots.b.task
  assert.equal(completed.summary, 'Download Ghidra 12.1.4 and check its hash')
  assert.equal(completed.running, false)
  // What the Bot said in the step that made the call comes with it.
  host.emit('ga', 'turn/start', { turn: 1 })
  step(host, 'ga', '先把 JDK\n下下来。', 'k3', 'pwsh', JSON.stringify({ description: 'Download JDK 21' }))
  const later = (await host.call('state', {})).value
  assert.deepEqual(['said', 'note'].map(key => later.work.bots.a[key]), ['先把 JDK 下下来。', 'Download JDK 21'])
})

test('the team view says when each Session\'s running turn began, for the clock at its tail', async (t) => {
  const host = await start(t)
  const before = Date.now()
  host.emit('gb', 'turn/start', { turn: 1 })
  host.emit('gb', 'tool/call', { callId: 'k1', name: 'pwsh', arguments: '{}' })
  const { value } = await host.call('state', {})
  // Group activity clocks also address the room id, because the activity row
  // subscribes by room id rather than the member's backing Session id.
  assert.deepEqual(Object.keys(value.work.turns), ['gb', 'r1'])
  assert.ok(value.work.turns.gb >= before && value.work.turns.gb <= Date.now())
  assert.equal(value.work.turns.gb, value.work.turns.r1)
  assert.equal(value.work.turns.gb, value.work.bots.b.since)
  host.emit('gb', 'tool/result', { callId: 'k1' })
  host.emit('gb', 'turn/end', { turn: 1, reason: { kind: 'completed' } })
  assert.deepEqual((await host.call('state', {})).value.work.turns, {})
})

// 公开#124: a Bot deleted while it worked stayed "thinking" until DSH restarted, and the
// Bot that had asked it something never heard back.
test('deleting a working Bot clears its activity and tells the Bots waiting for its reply', async (t) => {
  const host = await start(t)
  host.emit('b', 'turn/start', { turn: 1 })
  host.emit('b', 'user/message', { content: [{ type: 'text', text: '[Message from Chief]\nwrite the docs' }], source: { kind: 'bot', role: 'request', senderSessionId: 'a', senderName: 'Chief', exchangeId: 'x1', hop: 1 } })
  host.emit('b', 'tool/call', { callId: 'k1', name: 'pwsh', arguments: '{}' })
  // A second request that Writer has not read yet.
  host.agentOf('b').inbox.nextStep.push({ id: 'm2', source: { kind: 'bot', role: 'request', senderSessionId: 'c', senderName: 'Tester', exchangeId: 'x2', hop: 1 } })
  assert.equal((await host.call('state', {})).value.activity.b, 'working')

  const deleted = await host.call('delete-bot', { id: 'b' })
  assert.equal(deleted.ok, true)
  assert.equal((await host.call('state', {})).value.activity.b, undefined)
  await settle(() => host.agentOf('a').calls.length === 1 && host.agentOf('c').calls.length === 1)
  for (const [to, exchangeId] of [['a', 'x1'], ['c', 'x2']]) {
    const reply = host.agentOf(to).calls[0]
    assert.deepEqual([reply.source.role, reply.source.replyTo], ['reply', exchangeId])
    assert.equal(text(reply), '[Reply from Writer]\nWriter was deleted before it could answer your message.')
  }
  // The stopped turn ends after the delete; it brings nothing back.
  host.emit('b', 'turn/start', { turn: 2 })
  host.emit('b', 'turn/end', { turn: 1, reason: { kind: 'aborted' } })
  assert.equal((await host.call('state', {})).value.activity.b, undefined)
})


const deliveryChart = { type: 'chart', kind: 'line', categories: ['2026-10-26', '2026-10-27'], series: [{ name: 'Basis', values: [65, null] }], unit: '元/吨' }

test('a user-facing chart follows a non-admin answer before the group finishes, without entering peer context', async t => {
  const host = await start(t, { mode: 'everyone' })
  const result = host.round('chart-answer', host.say('展示已核实的价格'))
  await settle(() => host.agentOf('ga').calls.length === 1)
  host.begin('ga'); host.finish('ga', '先看 Writer 的数据。')
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  const reply = await host.tool('show_view', { audience: 'user', title: 'Verified basis', view: deliveryChart }, 'gb', { callId: 'view-b' })
  assert.match(reply, /staged/)
  const progress = async () => (await host.call('room-progress', { roomId: 'r1' })).value
  assert.equal((await progress())[0].replies.some(row => row.kind === 'view'), false)
  host.finish('gb', '这里是已核实的基差，今天的数据缺失。')
  await settle(() => host.agentOf('gc').calls.length === 1)
  assert.equal(result(), undefined, 'the next member is still working')
  const visible = (await progress())[0].replies
  assert.equal(visible.at(-1).kind, 'view')
  assert.equal(visible.at(-1).botId, 'b')
  assert.deepEqual(visible.at(-1).view, deliveryChart)
  const next = host.begin('gc')
  assert.doesNotMatch(text(next), /"series"|Verified basis/)
  host.finish('gc', '[PASS]')
  await settle(() => result() !== undefined)
  assert.equal(result().replies.filter(row => row.kind === 'view').length, 1)
  assert.equal(JSON.parse(JSON.stringify(result())).replies.at(-1).view.series[0].values[1], null)
})

test('an @ question can deliver finished metrics and charts without a user audience field; explicit team views remain hidden', async t => {
  const host = await start(t)
  const result = host.round('at-question', host.say('@Writer 基差呢'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  assert.match(await host.tool('show_view', { audience: 'team', title: 'Internal', view: deliveryChart }, 'gb'), /team-only/)
  assert.match(await host.tool('show_view', { title: 'Form', view: { type: 'options', id: 'x', options: [{ label: 'A' }] } }, 'gb'), /cannot submit/)
  assert.match(await host.tool('show_view', { title: 'Basis', view: deliveryChart }, 'gb', { callId: 'at-chart' }), /staged/)
  assert.match(await host.tool('show_view', { title: 'Basis readout', view: { type: 'metric', label: '基差', value: '+65 元/吨' } }, 'gb', { callId: 'at-metric' }), /staged/)
  host.finish('gb', '基差 +65 元/吨；次日缺失。')
  await settle(() => result() !== undefined)
  assert.deepEqual(kinds(result()), [['message', 'Writer'], ['view', 'Writer'], ['view', 'Writer']])
  assert.deepEqual(result().replies.filter(row => row.kind === 'view').map(row => row.title), ['Basis', 'Basis readout'])
  assert.equal(host.agentOf('ga').calls.length, 0)
})

test('one answer can deliver separate untitled charts and replace a revised named chart', async t => {
  const host = await start(t)
  const result = host.round('several-charts', host.say('@Writer 价格和基差'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  for (const callId of ['price', 'basis']) {
    await host.tool('show_view', { audience: 'user', view: deliveryChart }, 'gb', { callId })
  }
  await host.tool('show_view', { audience: 'user', title: 'Regional comparison', view: deliveryChart }, 'gb', { callId: 'regions' })
  await host.tool('show_view', { audience: 'user', title: 'Regional comparison', view: { ...deliveryChart, kind: 'bar' } }, 'gb', { callId: 'revised' })
  host.finish('gb', '已核实结果如下。')
  await settle(() => result() !== undefined)
  const views = result().replies.filter(row => row.kind === 'view')
  assert.deepEqual(views.map(view => view.id), ['price', 'basis', 'revised'])
  assert.equal(views.at(-1).view.kind, 'bar')
})

test('answers may deliver more than four views or metrics and combine chart and table presentations', async t => {
  const host = await start(t)
  const result = host.round('complete-business-answer', host.say('@Writer 给出完整数据'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  const metrics = { type: 'row', children: Array.from({ length: 5 }, (_, index) => ({ type: 'metric', label: `Indicator ${index}`, value: index })) }
  const detail = { type: 'stack', children: [deliveryChart, { type: 'table', columns: [{ key: 'basis', label: 'Basis' }], rows: [[65], ['No data']] }] }
  for (const [index, view] of [metrics, detail, deliveryChart, deliveryChart, deliveryChart].entries()) {
    assert.match(await host.tool('show_view', { audience: 'user', title: `Result ${index}`, view }, 'gb', { callId: `business-view-${index}` }), /staged/)
  }
  host.finish('gb', '完整数据已整理。')
  await settle(() => result() !== undefined)
  const views = result().replies.filter(row => row.kind === 'view')
  assert.equal(views.length, 5)
  assert.equal(views[0].view.children.length, 5)
  assert.deepEqual(views[1].view.children.map(node => node.type), ['chart', 'table'])
})

test('failed or cancelled answers discard staged cards and do not leak them into the next answer', async t => {
  const host = await start(t)
  for (const [index, reason] of [{ kind: 'aborted' }, { kind: 'error', error: { code: 'NETWORK', message: 'offline' } }].entries()) {
    const result = host.round(`bad-${index}`, host.say('@Writer 查数据'))
    await settle(() => host.agentOf('gb').calls.length === index + 1)
    host.begin('gb')
    await host.tool('show_view', { audience: 'user', title: 'Discarded', view: deliveryChart }, 'gb')
    host.emit('gb', 'turn/end', { turn: index + 1, reason })
    await settle(() => result() !== undefined)
    assert.equal(result().replies.some(row => row.kind === 'view'), false)
  }
  const next = host.round('clean', host.say('@Writer 再查'))
  await settle(() => host.agentOf('gb').calls.length === 3)
  host.begin('gb'); host.finish('gb', '没有可用数据。')
  await settle(() => next() !== undefined)
  assert.equal(next().replies.some(row => row.kind === 'view'), false)
})

test('a late completed answer carries its chart into the next relay once', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const host = await start(t)
  const first = host.round('long-chart', host.say('@Writer 查一下基差'))
  await settle(() => host.agentOf('gb').calls.length === 1)
  host.begin('gb')
  host.emit('gb', 'tool/call', { callId: 'work', name: 'read_file', arguments: '{}' })
  t.mock.timers.tick(ROOM_WORK_GRACE_MS)
  await settle(() => first() !== undefined)
  await host.tool('show_view', { audience: 'user', title: 'Late basis', view: deliveryChart }, 'gb', { callId: 'late-view' })
  host.finish('gb', '查询完成，先给可验证结果。')
  await settle(() => host.agentOf('r1').calls.length > 0)
  const post = host.takePost()
  assert.equal(post.source.views.length, 1)
  const second = host.round('late-delivery', post)
  await settle(() => second() !== undefined)
  assert.equal(second().replies.filter(row => row.kind === 'view').length, 1)
})
