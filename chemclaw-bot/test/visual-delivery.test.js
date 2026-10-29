import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install, hasInlineGenui, textOnlyRequested, VISUAL_NOTICE } from '../src/host/visual-delivery.js'
import { fakeContext } from './fake-ctx.js'

const content = text => [{ type: 'text', text }]
const fence = (panel = false) => '```dsh-ui\n' + JSON.stringify({ panel, items: [{ type: 'text', text: 'Result' }] }) + '\n```'
function setup({ native = false, history = [] } = {}) {
  const ctx = fakeContext()
  const notices = []
  const events = [...history]
  const session = { id: 's', header: { version: 4 }, snapshotEvents: () => events }
  const agent = { session, steer: notice => notices.push(notice) }
  const rt = { ctx, live: new Map(), state: { exchangeTurns: {}, questions: {}, views: {} }, chatOwners: new Map(native ? [] : [['s', 'bot']]), groupOwners: new Map(), roomOf: () => undefined, isBotSession: () => !native }
  install(rt)
  const emit = (type, data) => {
    const event = { type, data, seq: events.length + 1 }
    events.push(event)
    for (const listener of ctx.listeners.get('session/event')) listener(session, event)
  }
  const start = (turn = 1) => { rt.live.set('s', { turn }); emit('turn/start', { turn }) }
  const user = text => emit('user/message', { source: { kind: 'user' }, content: content(text) })
  const answer = text => emit('assistant/message', { message: { content: content(text) } })
  const stop = (turn = 1, aborted = false) => ctx.emit('agent/turn-stopping', { agent, turn, signal: { aborted } })
  return { ctx, rt, notices, session, agent, emit, start, user, answer, stop }
}

test('every plain final answer gets at most one same-turn correction, including conceptual and short answers', () => {
  for (const native of [false, true]) for (const reply of ['Basis is spot minus futures.', 'Done.', 'Hello.']) {
    const f = setup({ native })
    f.start(); f.user('Explain this'); f.answer(reply); f.stop(); f.stop()
    assert.equal(f.notices.length, 1)
    assert.match(f.notices[0].content[0].text, /turn=1/)
    assert.match(f.notices[0].content[0].text, /do not repeat the prose, research or external actions/)
    assert.equal(f.notices[0].source.form, 'notice')
    f.answer('Still only prose'); f.stop()
    assert.equal(f.notices.length, 1)
    f.start(2); f.user('Next question'); f.answer('Another short answer'); f.stop(2)
    assert.equal(f.notices.length, 2)
  }
})

test('first-pass GenUI or a successfully delivered show_view adds no correction', () => {
  for (const mode of ['genui', 'callback', 'result']) {
    const f = setup(); f.start(); f.user('Answer'); f.answer(mode === 'genui' ? fence() : 'Conclusion')
    if (mode === 'callback') f.rt.noteVisualDelivery('s')
    if (mode === 'result') {
      f.emit('tool/call', { name: 'show_view', callId: 'view' })
      f.emit('tool/result', { message: { content: [{ type: 'tool-result', toolCallId: 'view', content: content('The view is on screen.') }] } })
    }
    f.stop()
    assert.deepEqual(f.notices, [])
  }
})

test('failed show_view and unrelated successful tools are not delivery', () => {
  for (const result of ['Invalid view', 'Saved report']) {
    const f = setup(); f.start(); f.user('Answer'); f.answer('Conclusion')
    f.emit('tool/call', { name: result === 'Invalid view' ? 'show_view' : 'write', callId: 'c' })
    f.emit('tool/result', { message: { toolCallId: 'c', content: content(result) } })
    f.stop()
    assert.equal(f.notices.length, 1)
  }
})

test('native panels count only in native Agent mode; Bot panels get an inline reminder', () => {
  for (const native of [false, true]) {
    const f = setup({ native }); f.start(); f.user('Answer'); f.answer(fence(true)); f.stop()
    assert.equal(f.notices.length, native ? 0 : 1)
  }
  assert.equal(hasInlineGenui('```dsh-ui-dark\n{"items":[{}]}\n```'), false)
  assert.equal(hasInlineGenui(fence().replace('dsh-ui', 'DSH-UI>')), true)
})

test('malformed and incomplete GenUI fences are left to upstream repair without a competing correction', () => {
  for (const text of ['```dsh-ui\n{broken\n```', '```dsh-ui\n{"items":[]}', '```dsh-ui\n{"items":[]}\n```']) {
    const f = setup(); f.start(); f.user('Answer'); f.answer(text); f.stop()
    assert.deepEqual(f.notices, [])
  }
})

test('explicit text-only preferences override the default for this answer', () => {
  for (const text of ['Text-only please', 'No charts', '只要文字', '不要可视化', '纯文字回答', '不用图表']) {
    assert.equal(textOnlyRequested(text), true)
    const f = setup(); f.start(); f.user(text); f.answer('Plain requested'); f.stop()
    assert.deepEqual(f.notices, [])
    f.start(2); f.user('Next answer'); f.answer('Next'); f.stop(2)
    assert.equal(f.notices.length, 1)
  }
})

test('cancelled, child, relay, hidden peer, delegation and bare handoff turns do not trigger correction', () => {
  const variants = [
    f => { f.session.header.parentSession = 'parent' },
    f => { f.rt.roomOf = () => ({}) },
    f => { f.rt.state.exchangeTurns.s = [1] },
    f => { f.rt.live.get('s').info = { role: 'request', audience: 'team' } },
    f => { f.rt.live.get('s').info = { handoff: true } },
    f => { f.rt.groupOwners.set('s', 'room'); f.rt.live.get('s').info = { role: 'room', askedBy: 'another-bot' } },
    f => { f.rt.state.questions.s = {} },
    f => { f.rt.state.views.s = {} },
  ]
  for (const alter of variants) {
    const f = setup(); f.start(); f.user('Answer'); f.answer('Internal'); alter(f); f.stop()
    assert.deepEqual(f.notices, [])
  }
  const f = setup(); f.start(); f.user('Answer'); f.answer('Cancelled'); f.stop(1, true)
  assert.deepEqual(f.notices, [])
})

test('direct user group replies get the same global check', () => {
  const f = setup(); f.start(); f.rt.chatOwners.clear(); f.rt.groupOwners.set('s', 'room')
  f.rt.live.get('s').info = { role: 'room' }
  f.emit('user/message', { source: { kind: 'bot', role: 'room' }, content: content('User: Explain') })
  f.answer('Explanation'); f.stop()
  assert.equal(f.notices.length, 1)
})

test('hot reload restores current-turn preferences, delivery and correction budget before the first live event', () => {
  for (const tail of [
    { type: 'user/message', data: { source: { kind: 'user' }, content: content('Text-only please') } },
    { type: 'user/message', data: { source: { kind: 'plugin:chemclaw-bot', form: 'notice' }, content: content(`${VISUAL_NOTICE} turn=3]`) } },
    { type: 'assistant/message', data: { message: { content: content(fence()) } } },
  ]) {
    const f = setup({ history: [{ type: 'turn/start', data: { turn: 3 } }, tail] })
    f.answer('Plain last step after reload'); f.stop(3)
    assert.deepEqual(f.notices, [])
  }
})

test('group text-only override reads this round rather than an earlier transcript', () => {
  for (const current of ['Text-only please', 'Explain this']) {
    const f = setup(); f.start(); f.rt.chatOwners.clear(); f.rt.groupOwners.set('s', 'room')
    f.rt.live.get('s').info = { role: 'room' }
    f.emit('user/message', { source: { kind: 'bot', role: 'room' }, content: content(`Earlier in the group, before this round (context only):\nUser: Text-only please\n\nThis round so far, starting with the new message (oldest first):\nUser: ${current}\n\nSpeaking order for this round: Bot.`) })
    f.answer('Plain'); f.stop()
    assert.equal(f.notices.length, current === 'Text-only please' ? 0 : 1)
  }
})

test('hot reload restores successful show_view results but does not inherit an earlier turn visual', () => {
  const history = [
    { type: 'turn/start', data: { turn: 1 } },
    { type: 'user/message', data: { source: { kind: 'user' }, content: content('Answer') } },
    { type: 'tool/call', data: { callId: 'v', name: 'show_view' } },
    { type: 'tool/result', data: { message: { toolCallId: 'v', content: content('The view is on screen.') } } },
  ]
  const f = setup({ history }); f.answer('Finished'); f.stop()
  assert.deepEqual(f.notices, [])
  f.start(2); f.user('New answer'); f.answer('New plain reply'); f.stop(2)
  assert.equal(f.notices.length, 1)
})

test('sessions do not share delivery state and disposal drops old state', () => {
  const f = setup(); f.start(); f.user('Answer'); f.answer('Plain')
  f.rt.noteVisualDelivery('other')
  f.stop(); assert.equal(f.notices.length, 1)
  f.ctx.emit('session/disposed', f.session)
  f.start(2); f.user('Again'); f.answer('Plain'); f.stop(2)
  assert.equal(f.notices.length, 2)
})
