import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install, hasInlineGenui, textOnlyRequested, VISUAL_NOTICE, requestedChartKinds, deliveredViewKinds, missingRequestedKinds, marketHistoryRequest, marketPriceVisual, redundantMarketSourceQuestion, multiAssetMarketRequest, genuiChartPayloadsUsable, nativeChartPayloadsUsable } from '../src/host/visual-delivery.js'
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

test('an explicit K-line follow-up is distinct from discussing K-line problems', () => {
  assert.deepEqual(requestedChartKinds('我想看k线图'), ['candlestick'])
  assert.deepEqual(requestedChartKinds('请给我WTI原油K线图'), ['candlestick'])
  assert.deepEqual(requestedChartKinds('为什么这里没有K线图'), [])
  assert.deepEqual(requestedChartKinds('能不能生成K线图？'), [])
  assert.deepEqual([...deliveredViewKinds({ type: 'echart', option: {
    series: [{ type: 'candlestick', data: [[100, 101, 99, 102]] }],
  } })], ['candlestick'])
})

test('close-only line does not satisfy explicitly requested K-line; real GenUI candles do', () => {
  const f = setup()
  f.start(); f.user('我想看K线图')
  f.answer('Here is a closing-price line.')
  f.rt.noteVisualDelivery('s', { type: 'chart', kind: 'line', categories: ['1', '2'], series: [{ values: [1, 2] }] })
  f.stop(); f.stop()
  assert.equal(f.notices.length, 1)
  assert.match(f.notices[0].content[0].text, /explicitly requested candlestick/)
  assert.match(f.notices[0].content[0].text, /do not synthesize bars/i)
  assert.match(f.notices[0].content[0].text, /Do not send another tool call/i)
  const good = setup()
  const ticks = String.fromCharCode(96).repeat(3)
  good.start(); good.user('我想看K线图')
  good.answer(ticks + 'dsh-ui\n' + JSON.stringify({ items: [{ type: 'echart', option: {
    xAxis: { type: 'category', data: ['2026-10-29', '2026-10-30'] },
    series: [{ type: 'candlestick', data: [[101, 103, 100, 105], [103, 102, 101, 105]] }],
  } }] }) + '\n' + ticks)
  good.stop()
  assert.equal(good.notices.length, 0)
})

test('explicit K-line intent propagates to host chart guard and resets next turn', () => {
  const f = setup()
  f.start(); f.user('我想看K线图')
  assert.equal(f.rt.requiresCandlestick('s'), true)
  f.start(2); f.user('只要文字介绍最新报价')
  assert.equal(f.rt.requiresCandlestick('s'), false)
})

test('ordinary historical stock/futures queries trigger one-shot OHLC-first selection', () => {
  const yes = [
    'WTI 原油期货最近一个月价格',
    '中石油最近一个月股价',
    '中国石油最近一个月股价走势',
    '查询中国石油股票最近一个月历史行情',
    '请看沪深股票最近20天价格',
    'Brent futures historical daily price',
    '股票价格',
  ]
  for (const question of yes) assert.equal(marketHistoryRequest(question), true, question)
  const no = [
    '华东地区甲醇现货最近一个月报价',
    '解释期货的概念',
    '为什么无法生成K线图？',
    '怎么修复股票K线图的渲染代码',
    'WTI现在多少钱',
    '中国石油企业注册地址',
    '只要文字介绍最新股票报价',
  ]
  for (const question of no) assert.equal(marketHistoryRequest(question), false, question)
})

test('ordinary price history refuses a premature line once, then permits honest close-only fallback', () => {
  const f = setup()
  f.start()
  f.user('中石油最近一个月股价')
  assert.equal(f.rt.requiresCandlestick('s'), false)
  assert.equal(f.rt.deferMarketHistoryLineOnce('s'), true)
  assert.equal(f.rt.deferMarketHistoryLineOnce('s'), false, 'must not retry indefinitely')
  f.start(2)
  f.user('WTI原油期货最近一个月价格')
  f.rt.noteVisualDelivery('s', { type: 'chart', kind: 'candlestick', bars: [{ date: '2026-10-29', open: 1, high: 3, low: 1, close: 2 }, { date: '2026-10-30', open: 2, high: 4, low: 1, close: 3 }] })
  assert.equal(f.rt.deferMarketHistoryLineOnce('s'), false, 'already delivered candles')
  f.start(3)
  f.user('只用纯文字回答股票历史价格')
  assert.equal(f.rt.deferMarketHistoryLineOnce('s'), false, 'text only wins')
  f.start(4)
  f.user('华东甲醇现货近一个月价格')
  assert.equal(f.rt.deferMarketHistoryLineOnce('s'), false, 'spot chemicals are not OHLC markets')
})

test('public OHLC requests do not require a user decision on data sources', () => {
  assert.equal(redundantMarketSourceQuestion('我这边没有股票行情接口，你想让我怎么查中石油股价？', [
    { label: '用网页搜索查询最近一个月股价' },
    { label: '查公告' },
    { label: '不用了' },
  ]), true)
  assert.equal(redundantMarketSourceQuestion('没有行情接口，要用什么获取股票价格？', [
    { label: '用 akshare' }, { label: '用网页' },
  ]), true)
  assert.equal(redundantMarketSourceQuestion('你想查哪只股票的价格？', [
    { label: '601857 中国石油' }, { label: '0857 中国石油' },
  ]), false, 'a genuine exchange/listing ambiguity is permitted')
  assert.equal(redundantMarketSourceQuestion('需要前复权还是不复权的历史数据？', [
    { label: '前复权' }, { label: '不复权' },
  ]), false)
})

test('a historical market turn accepts at most one price view, and resets on a new turn', () => {
  const f = setup()
  f.start(); f.user('WTI 原油期货最近一个月价格')
  assert.equal(f.rt.marketHistoryOf('s'), true)
  const metric = { type: 'metric', label: 'Last', value: 42 }
  const line = { type: 'chart', kind: 'line', categories: ['1', '2'], series: [{ values: [1, 2] }] }
  const candles = { type: 'chart', kind: 'candlestick', bars: [
    { date: '2026-10-29', open: 1, high: 3, low: 1, close: 2 },
    { date: '2026-10-30', open: 2, high: 4, low: 1, close: 3 },
  ] }
  assert.equal(marketPriceVisual(metric), false)
  assert.equal(marketPriceVisual(line), true)
  assert.equal(marketPriceVisual({ type: 'row', children: [metric, candles] }), true)
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', line), false)
  f.rt.noteVisualDelivery('s', metric)
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', line), false, 'indicators do not consume price chart slot')
  f.rt.noteVisualDelivery('s', candles)
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', line), true)
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', candles), true)
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', metric), false)
  assert.equal(f.rt.deferMarketHistoryLineOnce('s'), false)
  f.start(2); f.user('华东甲醇近一个月现货价')
  assert.equal(f.rt.marketHistoryOf('s'), false)
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', line), false)
  f.start(3); f.user('中石油最近一个月股价')
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', candles), false, 'new turn resets duplicate protection')
})

test('comparisons of two assets still allow independent market price charts', () => {
  assert.equal(multiAssetMarketRequest('比较 WTI 和 Brent 最近一个月期货价格'), true)
  assert.equal(multiAssetMarketRequest('Compare WTI versus Brent futures history'), true)
  assert.equal(multiAssetMarketRequest('中石油最近一个月股价'), false)
  const f = setup(); f.start(); f.user('比较 WTI 和 Brent 最近一个月期货价格')
  const chart = { type: 'chart', kind: 'candlestick', bars: [
    { date: '2026-10-29', open: 1, high: 3, low: 1, close: 2 },
    { date: '2026-10-30', open: 2, high: 4, low: 1, close: 3 },
  ] }
  f.rt.noteVisualDelivery('s', chart)
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', chart), false)
})

test('one market history source result selects K-line or permits only an honest fallback', () => {
  const f = setup()
  f.start(); f.user('中石油最近一个月股价')
  assert.equal(f.rt.marketOhlcStatus('s'), 'untried')
  f.rt.noteMarketOhlcSource('s', 'ready')
  assert.equal(f.rt.marketOhlcStatus('s'), 'ready')
  f.start(2); f.user('WTI原油期货最近一个月价格')
  assert.equal(f.rt.marketOhlcStatus('s'), 'untried')
  f.rt.noteMarketOhlcSource('s', 'unavailable')
  assert.equal(f.rt.marketOhlcStatus('s'), 'unavailable')
  f.start(3); f.user('甲醇现货价格')
  f.rt.noteMarketOhlcSource('s', 'ready')
  assert.equal(f.rt.marketOhlcStatus('s'), 'untried', 'spot prices must not inherit an exchange OHLC result')
})

test('a price view stays committed across model continuation turns, resets on the next real user request', () => {
  const f = setup()
  const line = { type: 'chart', kind: 'line', categories: ['x', 'y'], series: [{ values: [1, 2] }] }
  f.start(1); f.user('WTI 原油期货最近一个月价格')
  f.rt.noteMarketOhlcSource('s', 'ready')
  f.rt.noteVisualDelivery('s', { type: 'chart', kind: 'candlestick', bars: [
    { date: '2026-10-29', open: 1, high: 3, low: 1, close: 2 },
    { date: '2026-10-30', open: 2, high: 4, low: 1, close: 3 },
  ] })
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', line), true)
  f.start(2) // a model continuation, not a new user's question
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', line), true)
  assert.equal(f.rt.marketOhlcStatus('s'), 'ready')
  f.user('中石油最近一个月股价')
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', line), false)
  assert.equal(f.rt.marketOhlcStatus('s'), 'untried')
  f.start(3)
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', line), false)
})

test('spot price class persists through model continuations and resets on the next human turn', () => {
  const f = setup()
  f.start(1); f.user('原油现货价格')
  assert.equal(f.rt.marketQuoteIntentOf('s'), 'spot')
  assert.equal(f.rt.explicitSpotRequestOf('s'), true)
  assert.equal(f.rt.marketHistoryOf('s'), false)
  assert.equal(f.rt.requiresCandlestick('s'), false)
  f.start(2)
  assert.equal(f.rt.explicitSpotRequestOf('s'), true)
  f.user('纯碱现货近一个月走势')
  assert.equal(f.rt.marketQuoteIntentOf('s'), 'spot')
  assert.equal(f.rt.marketHistoryOf('s'), false)
  f.start(3); f.user('纯碱期货最近一个月价格')
  assert.equal(f.rt.marketQuoteIntentOf('s'), 'futures')
  assert.equal(f.rt.explicitSpotRequestOf('s'), false)
  assert.equal(f.rt.marketHistoryOf('s'), true)
  f.start(4); f.user('比较现货和期货价差')
  assert.equal(f.rt.marketQuoteIntentOf('s'), 'mixed')
  assert.equal(f.rt.explicitSpotRequestOf('s'), false)
})

test('empty or misnamed ECharts data is not a successful inline GenUI view', () => {
  const blank = [
    { type: 'echart', option: { xAxis: { data: ['2026-10-01'] }, series: [{ type: 'line', values: [1200] }] } },
    { type: 'echart', option: { series: [{ type: 'line', data: [] }] } },
    { type: 'echart', preset: 'line', series: [] },
  ]
  for (const item of blank) {
    const ticks = String.fromCharCode(96).repeat(3)
    const output = ticks + 'dsh-ui\n' + JSON.stringify({ items: [item] }) + '\n' + ticks
    assert.equal(hasInlineGenui(output), false)
    const f = setup(); f.start(); f.user('纯碱最近一个月现货价'); f.answer(output); f.stop()
    assert.equal(f.notices.length, 1)
    assert.match(f.notices[0].content[0].text, /native show_view line chart/)
    f.stop()
    assert.equal(f.notices.length, 1, 'one bounded correction, no repeated loop')
  }
  assert.equal(genuiChartPayloadsUsable([{ type: 'echart', option: { series: [{ type: 'line', data: [1, 2] }] } }]), true)
  assert.equal(genuiChartPayloadsUsable([{ type: 'echart', option: { dataset: { source: [['date', 'price'], ['2026-10-01', 1200]] }, series: [{ type: 'line' }] } }]), true)
  assert.equal(genuiChartPayloadsUsable([{ type: 'timeline', events: [{ title: 'Start' }] }]), true)
})

test('all-missing native data is rejected while real gaps and formulas remain valid', () => {
  const chart = values => ({ type: 'chart', kind: 'line', categories: ['Oct 1', 'Oct 2'], series: [{ values }] })
  assert.equal(nativeChartPayloadsUsable(chart([null, null])), false)
  assert.equal(nativeChartPayloadsUsable(chart([1200, null])), true)
  assert.equal(nativeChartPayloadsUsable(chart([{ '=': 'price' }, null])), true)
  assert.equal(nativeChartPayloadsUsable({ type: 'stack', children: [chart([null, null]), { type: 'metric', label: 'Last', value: 1200 }] }), false)
  assert.equal(nativeChartPayloadsUsable({ type: 'chart', kind: 'candlestick', bars: [] }), true, 'candlestick schema is validated separately')
})

test('a spot/futures basis overlay bypasses OHLC-first and permits dated native line views', () => {
  const f = setup()
  const spotVsFutures = { type: 'chart', kind: 'line', categories: ['2026-10-28', '2026-10-29'],
    series: [{ name: '乙二醇现货·华东', values: [3800, 3820] },
      { name: '乙二醇期货·EG主力', values: [3760, 3770] }] }
  f.start(); f.user('乙二醇现货与盘面叠加走势图，看看基差')
  assert.equal(f.rt.marketQuoteIntentOf('s'), 'mixed')
  assert.equal(f.rt.explicitSpotRequestOf('s'), false, 'spot-only ban must not reject labeled futures leg')
  assert.equal(f.rt.marketHistoryOf('s'), false, 'do not force futures K-lines for a mixed-line chart')
  assert.equal(multiAssetMarketRequest('乙二醇现货与盘面叠加走势图，看看基差'), true)
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', spotVsFutures), false)
  f.rt.noteVisualDelivery('s', spotVsFutures)
  assert.equal(f.rt.marketPriceViewAlreadyCommitted('s', spotVsFutures), false)
  f.start(2)
  assert.equal(f.rt.marketQuoteIntentOf('s'), 'mixed', 'maintain mixed intent through model continuation')
  assert.equal(f.rt.marketHistoryOf('s'), false)
  f.user('乙二醇现货价格，不要期货')
  assert.equal(f.rt.marketQuoteIntentOf('s'), 'spot', 'new real user question resets comparison')
  assert.equal(f.rt.explicitSpotRequestOf('s'), true)
})
