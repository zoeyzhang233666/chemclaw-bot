import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install, hasInlineGenui, textOnlyRequested, VISUAL_NOTICE, requestedChartKinds, deliveredViewKinds, missingRequestedKinds } from '../src/host/visual-delivery.js'
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

test('requested chart detection distinguishes instructions from discussions and does not invent data requirements', () => {
  assert.deepEqual(requestedChartKinds('请生成一张热力图，并用时间轴展示主要事件。'), ['heatmap', 'timeline'])
  assert.deepEqual(requestedChartKinds('Create a Sankey and a heatmap.'), ['heatmap', 'sankey'])
  for (const question of ['为什么热力图没有显示？', '热力图是什么？', '请解释热力图的概念', '帮我检查热力图没有显示的问题', '修复生成桑基图失败的问题', 'Explain how Sankey diagrams work']) {
    assert.deepEqual(requestedChartKinds(question), [], question)
  }
  assert.deepEqual(missingRequestedKinds(['heatmap', 'timeline'], new Set(['heatmap'])), ['timeline'])
})

test('recursive view-kind detection covers stacked ECharts nodes and GenUI timeline nodes', () => {
  const kinds = deliveredViewKinds({ type: 'stack', children: [
    { type: 'chart', kind: 'line', categories: ['A'], series: [{ values: [1] }] },
    { type: 'chart', kind: 'heatmap', categories: ['A'], series: [{ values: [1] }] },
    { type: 'timeline', events: [{ label: 'Start' }] },
  ] })
  assert.deepEqual([...kinds], ['line', 'heatmap', 'timeline'])
  assert.deepEqual([...deliveredViewKinds(undefined)], [])
})

test('an explicitly requested advanced chart cannot be satisfied by an unrelated successful line chart', () => {
  const f = setup(); f.start(); f.user('请绘制热力图'); f.answer('Only the price trend is shown.')
  f.rt.noteVisualDelivery('s', { type: 'chart', kind: 'line' })
  f.stop(); f.stop()
  assert.equal(f.notices.length, 1)
  assert.match(f.notices[0].content[0].text, /explicitly requested heatmap/)
  assert.match(f.notices[0].content[0].text, /do not repeat existing prose/)
  f.answer('Added the heatmap'); f.rt.noteVisualDelivery('s', { type: 'chart', kind: 'heatmap' })
  f.stop()
  assert.equal(f.notices.length, 1, 'one correction is the strict upper bound')
})

test('multiple requested kinds only repair the missing one, and a complete grouped view needs no correction', () => {
  for (const withTimeline of [false, true]) {
    const f = setup(); f.start(); f.user('请生成热力图，并用时间轴展示事件')
    f.answer('Here are the results.' + (withTimeline
      ? '\n' + '```dsh-ui\n' + JSON.stringify({ items: [{ type: 'timeline', events: [{ title: 'Start' }] }] }) + '\n```'
      : ''))
    f.rt.noteVisualDelivery('s', { type: 'chart', kind: 'heatmap' })
    f.stop()
    assert.equal(f.notices.length, withTimeline ? 0 : 1)
    if (!withTimeline) {
      assert.match(f.notices[0].content[0].text, /requested timeline/)
      assert.doesNotMatch(f.notices[0].content[0].text, /requested heatmap,/)
    }
  }
})

test('a valid GenUI timeline counts as delivery; panel-only GenUI is not sufficient in Bot mode', () => {
  for (const panel of [false, true]) {
    const f = setup(); f.start(); f.user('请用时间轴展示关键事件')
    f.answer('Result\n' + '```dsh-ui\n' + JSON.stringify({ panel, items: [{ type: 'timeline', events: [{ title: 'Start' }] }] }) + '\n```')
    f.stop()
    assert.equal(f.notices.length, panel ? 1 : 0)
  }
})

test('view kinds survive a normal tool result and a hot-reload event replay', () => {
  const history = [
    { type: 'turn/start', data: { turn: 1 } },
    { type: 'user/message', data: { source: { kind: 'user' }, content: content('请用桑基图展示流量') } },
    { type: 'tool/call', data: { callId: 'v', name: 'show_view', args: { view: { type: 'chart', kind: 'sankey' } } } },
    { type: 'tool/result', data: { message: { toolCallId: 'v', content: content('The view is on screen.') } } },
  ]
  const f = setup({ history }); f.answer('Flow diagram'); f.stop()
  assert.equal(f.notices.length, 0)
  f.start(2); f.user('请用热力图展示区域情况')
  f.emit('tool/call', { name: 'show_view', callId: 'a', args: { view: { type: 'chart', kind: 'line' } } })
  f.emit('tool/result', { message: { toolCallId: 'a', content: content('The view is staged for a group reply.') } })
  f.answer('There is one line chart'); f.stop(2)
  assert.equal(f.notices.length, 1)
  assert.match(f.notices[0].content[0].text, /heatmap/)
})

test('ordinary questions, text-only and cancelled turns never force multiple charts', () => {
  const plain = setup(); plain.start(); plain.user('分析近期供需'); plain.answer('Summary')
  plain.rt.noteVisualDelivery('s', { type: 'chart', kind: 'line' }); plain.stop()
  assert.equal(plain.notices.length, 0)
  const text = setup(); text.start(); text.user('请绘制热力图，但只要纯文字回答'); text.answer('Summary'); text.stop()
  assert.equal(text.notices.length, 0)
  const cancelled = setup(); cancelled.start(); cancelled.user('请绘制热力图'); cancelled.answer('Summary')
  cancelled.rt.noteVisualDelivery('s', { type: 'chart', kind: 'line' }); cancelled.stop(1, true)
  assert.equal(cancelled.notices.length, 0)
})

test('disabling advanced charts prevents misleading requests to render an unavailable ECharts kind', () => {
  const f = setup(); f.rt.state.prefs = { advancedCharts: false }
  f.start(); f.user('请生成热力图'); f.answer('The regional data is tabulated.')
  f.rt.noteVisualDelivery('s', { type: 'table' })
  f.stop()
  assert.equal(f.notices.length, 0)
  const time = setup(); time.rt.state.prefs = { advancedCharts: false }
  time.start(); time.user('请用时间轴展示关键事件'); time.answer('A summary')
  time.rt.noteVisualDelivery('s', { type: 'table' })
  time.stop()
  assert.equal(time.notices.length, 1)
  assert.match(time.notices[0].content[0].text, /timeline/)
})
