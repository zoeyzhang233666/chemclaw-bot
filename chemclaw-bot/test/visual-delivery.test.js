import assert from 'node:assert/strict'
import { test } from 'node:test'
import { install, hasInlineGenui, textOnlyRequested, VISUAL_NOTICE, requestedChartKinds, deliveredViewKinds, missingRequestedKinds, marketHistoryRequest, marketPriceVisual, redundantMarketSourceQuestion, multiAssetMarketRequest, genuiChartPayloadsUsable, nativeChartPayloadsUsable, mixedMarketVisualStatus, stripUnrenderedMixedViewText } from '../src/host/visual-delivery.js'
import { fakeContext } from './fake-ctx.js'
import { genuiFences, genuiMarkdown, repairGenuiGraphicFences, stripGraphicControlLines } from '../src/shared/genui-fences.js'

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
    assert.match(f.notices[0].content[0].text, /Keep the original prose and do not repeat research or external actions/)
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

const svgCode = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><path d="M0 0 L2 2"/></svg>'
const diagramFence = '```dsh-ui\n' + JSON.stringify({ items: [{ type: 'diagram', kind: 'flowchart', nodes: [{ id: 'a', label: '生产' }, { id: 'b', label: '销售' }], edges: [{ from: 'a', to: 'b' }] }] }) + '\n```'
const unsupportedGraphic = { type: 'svg', title: '未填写的矢量图' }

function installFixtureValidator(ctx) {
  ctx.tools.executable = name => name === 'validate_dsh_ui' ? {} : undefined
  ctx.tools.execute = async ({ calls }) => {
    const raw = JSON.parse(calls[0].arguments).spec
    let verdict = 'status=invalid'
    try {
      const parsed = JSON.parse(raw)
      if (parsed.items?.length && parsed.items.every(item => ['diagram', 'text', 'svg'].includes(item.type))) verdict = 'status=valid'
    } catch { /* bad syntax */ }
    return { results: [{ result: { isError: false, value: '[genui-validation]\n' + verdict } }] }
  }
}

const settleModelText = async (ctx, text) => {
  const hook = ctx.listeners.get('llm/stream')[0]
  const chunks = await Array.fromAsync(hook({ sessionId: 's' }, async function* () {
    yield { type: 'block-end', block: { type: 'text', text } }
  }))
  return chunks[0].block.text
}

test('duplicate broken graphics are withheld before display, with one bounded recovery', async () => {
  const f = setup()
  installFixtureValidator(f.ctx)
  f.start(); f.user('请画供应链流程图')
  const broken = genuiMarkdown(JSON.stringify({ items: [unsupportedGraphic] }))
  const invalidXml = genuiMarkdown(JSON.stringify({ items: [{ ...unsupportedGraphic, code: '<svg><text>销售</svg>' }] }))
  const response = await settleModelText(f.ctx, '核对生产再销售。\n\n' + broken + '\n\n' + invalidXml + '\n\n<chatml_chart_demo>')
  assert.equal(response, '核对生产再销售。')
  f.answer(response); f.stop()
  assert.match(f.notices[0].content[0].text, /Recover it once/)
  assert.equal(await settleModelText(f.ctx, broken), '')
  f.stop()
  assert.equal(f.notices.length, 1)
})

test('legacy inline flow is normalized and valid neighbors survive a rejected graphic', async () => {
  const f = setup()
  installFixtureValidator(f.ctx)
  f.start(); f.user('请画供应链流程图')
  const legacy = { type: 'flow', title: '生产和销售', nodes: [{ id: 'a', label: '生产' }, { id: 'b', label: '销售' }],
    edges: [{ from: 'a', to: 'b', label: '通常', uncertain: true }] }
  const original = genuiMarkdown(JSON.stringify({ items: [legacy, unsupportedGraphic] }))
  const result = await settleModelText(f.ctx, original)
  const [item] = JSON.parse([...genuiFences(result)][0].body).items
  assert.equal(item.type, 'diagram')
  assert.equal(item.edges[0].kind, 'dashed')
  assert.doesNotMatch(result, /未填写/)
  f.answer(result); f.stop()
  assert.deepEqual(f.notices, [])
})

test('standalone demo markers are removed outside examples only', () => {
  const example = '```html\n<chatml_chart_demo>\n```'
  assert.equal(stripGraphicControlLines('说明\n<chatml_chart_demo>\n' + example + '\n</chatml_chart_demo>'), '说明\n' + example + '\n')
})
const spotQuestion = '纯碱最近一个月现货价格'
const spotMetric = { type: 'metric', label: '纯碱现货', value: '1123 元/吨' }
const spotLine = { type: 'chart', kind: 'line', categories: ['2026-10-23', '2026-11-19'], series: [{ name: '轻质纯碱现货', values: [1118, 1123] }] }

test('a bare methanol quote still requires cards alongside the chart, and a single quote can use a card alone', () => {
  for (const native of [false, true]) {
    const f = setup({ native })
    f.start(); f.user('甲醇价格')
    f.rt.noteVisualDelivery('s', spotLine)
    f.answer('最新价格 2300 元/吨。'); f.stop()
    assert.match(f.notices[0].content[0].text, /deliver headline metric cards from verified evidence/)
    f.start(2); f.user('甲醇价格')
    f.answer('华东 2300 元/吨，华北 2150 元/吨。\n\n' + diagramFence); f.stop(2)
    assert.match(f.notices[1].content[0].text, /headline metric cards and the data chart/)
    f.start(3); f.user('甲醇价格'); f.answer('只核实到一笔同口径报价，2300 元/吨。')
    f.rt.noteVisualDelivery('s', spotMetric); f.stop(3)
    assert.equal(f.notices.length, 2)
  }
})

test('a public production gap continues research once without asking about the search route', async () => {
  const f = setup()
  f.ctx.tools.get = name => ['show_view', 'web_search'].includes(name) ? {} : undefined
  f.start(); f.user('沥青产量')
  const guard = f.ctx.listeners.get('tools/pre-execute')[0]
  const permission = { name: 'ask_user', agent: f.agent, arguments: { question: '是否需要我联网查找？' } }
  const allow = async () => ({ kind: 'allow' })
  assert.equal((await guard(permission, allow)).kind, 'deny')
  f.answer('数据中台没有沥青产量，联网检索需你确认。')
  f.stop(); f.stop()
  assert.equal(f.notices.length, 1)
  assert.match(f.notices[0].content[0].text, /Continue the same public data lookup now/)
  f.start(2); f.user('沥青产量，不要联网')
  assert.equal((await guard(permission, allow)).kind, 'allow')
  f.answer('库里没有数据。'); f.stop(2)
  assert.doesNotMatch(f.notices.at(-1).content[0].text, /Continue the same public data lookup now/)
  f.start(3); f.user('沥青产量')
  f.emit('tool/call', { name: 'web_search', callId: 'source' })
  f.answer('没有可核实的近月产量数据。'); f.stop(3)
  assert.doesNotMatch(f.notices.at(-1).content[0].text, /Continue the same public data lookup now/)
})

test('regional and producer output tables need their own comparisons', () => {
  const f = setup()
  const chart = (categories, values) => ({ type: 'chart', kind: 'hbar', categories, series: [{ values }] })
  const region = chart(['华东', '华北'], [123, 117])
  const producer = chart(['合成集团 A', '合成集团 B'], [100, 140])
  const prose = '## 分集团\n\n| 集团 | 产量（万吨） |\n| --- | --- |\n| A | 100 |\n| B | 140 |\n\n## 分地区\n\n| 地区 | 产量（万吨） |\n| --- | --- |\n| 华东 | 123 |\n| 华北 | 117 |'
  f.start(); f.user('沥青产量'); f.rt.noteVisualDelivery('s', { type: 'stack', children: [spotMetric, region] })
  f.answer(prose); f.stop()
  assert.match(f.notices[0].content[0].text, /the missing production comparisons.*separate bars.*producer-group and regional/)
  f.start(2); f.user('沥青产量')
  f.rt.noteVisualDelivery('s', { type: 'stack', children: [spotMetric, region, producer] })
  f.answer(prose); f.stop(2)
  assert.equal(f.notices.length, 1)
})

test('colliding GenUI boxes are placed on the grid without changing the model’s edges', () => {
  const nodes = ['上游', '跨区物流', '下游'].map((label, id) => ({ id: String(id), label, x: 0.4, y: 0.3, w: 48, h: 28 }))
  const edges = [{ from: '0', to: '1', label: '供给' }, { from: '1', to: '2', label: '运抵' }]
  const markdown = genuiMarkdown(JSON.stringify({ type: 'diagram', kind: 'architecture', nodes, edges }))
  const repaired = JSON.parse([...genuiFences(repairGenuiGraphicFences(markdown))][0].body).items[0]
  assert.deepEqual(repaired.edges, edges)
  assert.deepEqual(repaired.nodes.map(node => node.label), nodes.map(node => node.label))
  assert.equal(new Set(repaired.nodes.map(node => `${node.x},${node.y}`)).size, nodes.length)
  assert.match(repairGenuiGraphicFences(markdown), /"h":64/)
})

test('spot history requires native metrics and a dated line even after a table or a relationship view', () => {
  const prose = '价格先涨后跌。1120 元/吨 → 1134 元/吨 → 1123 元/吨。'
  for (const native of [false, true]) for (const view of [
    { type: 'table', rows: [[1118], [1123]] },
    spotMetric,
    spotLine,
    { type: 'stack', children: [spotMetric, { ...spotLine, kind: 'hbar' }] },
    { type: 'stack', children: [spotMetric, { ...spotLine, categories: ['华东', '华北'] }] },
    { type: 'stack', children: [spotMetric, spotLine] },
  ]) {
    const f = setup({ native })
    f.start(); f.user(spotQuestion); f.answer(prose + '\n\n' + diagramFence)
    f.rt.noteVisualDelivery('s', view); f.stop(); f.stop()
    if (view.children?.includes(spotLine)) assert.deepEqual(f.notices, [])
    else {
      assert.equal(f.notices.length, 1)
      const notice = f.notices[0].content[0].text
      const missing = notice.match(/native show_view stack to deliver (.+) from verified/u)?.[1]
      assert.equal(missing, view.type === 'table' ? 'headline metric cards and the dated spot chart'
        : view === spotLine ? 'headline metric cards' : 'the dated spot chart')
      assert.doesNotMatch(notice, /dsh-ui type=diagram|explicitly requested svg/)
    }
  }
  const partial = setup()
  partial.start(); partial.user(spotQuestion)
  partial.answer('仅查到最新现货快照，1123 元/吨。'); partial.rt.noteVisualDelivery('s', spotMetric); partial.stop()
  assert.deepEqual(partial.notices, [])
})

test('asking to restore native cards and charts reuses the spot request without treating SVG as requested', () => {
  const f = setup()
  f.start(); f.user(spotQuestion); f.answer('1123 元/吨。')
  f.start(2); f.user('为什么刚才不再生成 ChemClaw 原生 UI 标签卡和数据图，表格不能替代这个')
  f.answer('上面有现货数据。'); f.stop(2)
  assert.match(f.notices[0].content[0].text, /headline metric cards and the dated spot chart/)
  assert.deepEqual(requestedChartKinds('请生成原生标签卡和数据图，而不是 SVG'), [])
})

test('a numeric answer with values only in the table still needs the native cards and chart', () => {
  const f = setup()
  f.start(); f.user('查询各地产能分布')
  f.answer('产能如下。\n\n| 地区 | 产能（万吨） |\n| --- | --- |\n| 甲地 | 120 |\n| 乙地 | 90 |')
  f.stop()
  assert.match(f.notices[0].content[0].text, /headline metric cards and the data chart/)
})

test('a data-only turn withdraws completed decorative GenUI diagrams and preserves supporting content', async () => {
  const f = setup()
  const hook = f.ctx.listeners.get('llm/stream')[0]
  const table = { type: 'table', columns: ['日期', '价格'], rows: [['11-19', 1123]] }
  const alias = { type: 'svg', title: '错误的报价关系图', svg: svgCode }
  const raw = '已核实价格。\n\n' + diagramFence + '\n\n' + genuiMarkdown(JSON.stringify({ items: [table, alias] }))
  const model = async function* () {
    yield { type: 'block-end', index: 0, block: { type: 'text', text: raw } }
  }
  const end = async () => (await Array.fromAsync(hook({ sessionId: 's', tools: [{ name: 'show_view' }] }, model)))[0].block.text
  f.start(); f.user(spotQuestion)
  assert.equal((await end()).replace(/\n{3,}/gu, '\n\n'), '已核实价格。\n\n' + genuiMarkdown(JSON.stringify({ items: [table] })).trimEnd())
  f.rt.noteVisualDelivery('s', { type: 'stack', children: [spotMetric, spotLine] })
  assert.match(await end(), /"type":"diagram"/)
  f.start(2); f.user('纯碱最近一个月现货价格，为什么价格会变化？请用 SVG 解释原因')
  assert.match(await end(), /错误的报价关系图/)
  f.start(3); f.user('纯碱最近一个月现货价格，需要多级表头的复杂数据表')
  const specialized = await end()
  assert.match(specialized, /错误的报价关系图/)
  assert.doesNotMatch(specialized, /"type":"diagram"/)
})

test('a generated SVG alias is normalized while ordinary Markdown examples are preserved', async () => {
  const alias = { type: 'svg', title: '合成因果图', svg: svgCode }
  const raw = genuiMarkdown(JSON.stringify(alias))
  const ordinary = '````markdown\n' + raw + '\n````'
  const answer = ordinary + '\n\n正文\n\n' + raw
  const expected = ordinary + '\n\n正文\n\n' + genuiMarkdown(JSON.stringify({ items: [{ type: 'svg', title: '合成因果图', code: svgCode }] }))
  assert.equal(repairGenuiGraphicFences(answer), expected)
  assert.equal([...genuiFences(ordinary)].length, 0)
  const partial = '\n~~~dsh-ui\n{"items":'
  assert.deepEqual([...genuiFences(partial)].map(fence => [fence.body, fence.closed]), [['{"items":', false]])
  assert.equal(repairGenuiGraphicFences(partial), partial)
  const wrong = genuiMarkdown(JSON.stringify({ items: [{ type: 'svg', svg: '<svg>' }] }))
  assert.equal(repairGenuiGraphicFences(wrong), wrong)
  const f = setup()
  const hook = f.ctx.listeners.get('llm/stream')[0]
  const model = async function* () {
    yield { type: 'text-delta', index: 0, text: answer }
    yield { type: 'block-end', index: 0, block: { type: 'text', text: answer } }
  }
  const chunks = await Array.fromAsync(hook({ sessionId: 's' }, model))
  assert.equal(chunks[0].text, answer)
  assert.equal(chunks[1].block.text, expected)
  assert.equal((await Array.fromAsync(hook({ sessionId: 's', purpose: 'summary' }, model))).at(-1).block.text, answer)
})

test('a causal industry question accepts either GenUI vector format without a duplicate', () => {
  for (const graphic of [diagramFence, genuiMarkdown(JSON.stringify({ items: [{ type: 'svg', code: svgCode }] }))]) {
    const f = setup()
    f.start(); f.user('原油行情波动是什么原因，梳理传导路径'); f.answer('以下是原因。\n\n' + graphic); f.stop()
    assert.deepEqual(f.notices, [])
  }
})

test('capacity figures trigger one native metric repair and keep verified comparisons in the same stack', () => {
  const figures = '甲地产能 120 万吨/年，乙地产能 90 万吨/年。'
  for (const native of [false, true]) {
    const f = setup({ native })
    f.start(); f.user('查询各地产能分布'); f.answer(figures + '\n\n' + diagramFence); f.stop(); f.stop()
    assert.equal(f.notices.length, 1)
    assert.match(f.notices[0].content[0].text, /native show_view stack.*metric cards.*comparable verified observations/)
    assert.doesNotMatch(f.notices[0].content[0].text, /dsh-ui type=diagram/)
  }
  const ready = setup()
  ready.start(); ready.user('查询各地产能分布')
  ready.rt.noteVisualDelivery('s', { type: 'stack', children: [{ type: 'metric', label: '甲地产能', value: 120 }, {
    type: 'chart', kind: 'hbar', categories: ['甲地', '乙地'], series: [{ values: [120, 90] }],
  }] })
  ready.answer(figures); ready.stop()
  assert.deepEqual(ready.notices, [])
  for (const [question, answer] of [
    ['查询各地产能分布', '暂无可靠数字。'],
    ['为什么产能集中在沿海？', figures],
    ['查询各地产能分布，只用文字', figures],
  ]) {
    const f = setup()
    f.start(); f.user(question); f.answer(answer + '\n\n' + diagramFence); f.stop()
    assert.deepEqual(f.notices, [])
  }
})

test('explicit SVG requests use the SVG component and automatic logic accepts a finished diagram', () => {
  assert.deepEqual(requestedChartKinds('请生成一张 SVG 流程图'), ['svg'])
  assert.deepEqual(requestedChartKinds('请用 GenUI diagram 画流程图'), ['diagram'])
  assert.deepEqual(requestedChartKinds('请生成 Mermaid 流程图'), ['mermaid'])
  const f = setup({ native: true })
  f.start(); f.user('请生成一张 SVG 流程图'); f.answer('这里是工作流程。'); f.stop(); f.stop()
  assert.equal(f.notices.length, 1)
  assert.match(f.notices[0].content[0].text, /dsh-ui type=svg/)
  const ready = setup({ native: true })
  ready.start(); ready.user('请生成流程图'); ready.answer('这里是工作流程。\n\n' + diagramFence)
  ready.stop()
  assert.equal(ready.notices.length, 0)
})

test('the automatic SVG check covers real-world logic questions even when some other visual was delivered', () => {
  const mermaid = '```dsh-ui\n' + JSON.stringify({ items: [{ type: 'mermaid', code: 'graph TD\nA-->B' }] }) + '\n```'
  for (const [question, answer] of [
    ['为什么会是这样分布的？', fence()],
    ['我想知道产业链结构', mermaid],
    ['解释一下这份材料', '原料 → 加工 → 销售\n\n' + fence()],
    ['说说你的看法', '三项约束改变了销售路径。\n- 原料\n- 生产\n- 通路\n\n' + fence()],
  ]) for (const native of [false, true]) {
    const f = setup({ native })
    f.start(); f.user(question); f.answer(answer); f.stop(); f.stop()
    assert.equal(f.notices.length, 1)
    assert.match(f.notices[0].content[0].text, /dsh-ui type=diagram/)
  }
  for (const question of ['你好！', '全球低硫燃料油产量分布', '请生成 Mermaid 流程图', '为什么这样分布？只用文字']) {
    const f = setup({ native: true })
    f.start(); f.user(question); f.answer(`影响路径：A → B → C\n\n${question.includes('Mermaid') ? mermaid : fence()}`); f.stop()
    assert.deepEqual(f.notices, [])
  }
  const fallback = setup({ native: true }); fallback.ctx.tools.get = name => name === 'show_view' ? {} : undefined
  fallback.start(); fallback.user('为什么有这样的分布'); fallback.answer(fence()); fallback.stop()
  assert.match(fallback.notices[0].content[0].text, /show_view type=flow/)
  const delivered = setup({ native: true })
  delivered.start(); delivered.user('请画 SVG 图')
  delivered.answer('```svg\n' + svgCode + '\n```'); delivered.stop()
  assert.deepEqual(delivered.notices, [])
})

test('an ordinary cross-section question automatically chooses the isolated GenUI SVG image', () => {
  const f = setup()
  f.start(); f.user('解释合成设备剖面结构'); f.answer(diagramFence); f.stop(); f.stop()
  assert.equal(f.notices.length, 1)
  assert.match(f.notices[0].content[0].text, /dsh-ui type=svg/)
  assert.doesNotMatch(f.notices[0].content[0].text, /explicitly requested svg/)
  const ready = setup()
  ready.start(); ready.user('解释合成设备剖面结构')
  ready.answer('```dsh-ui\n' + JSON.stringify({ items: [{ type: 'svg', code: svgCode }] }) + '\n```'); ready.stop()
  assert.deepEqual(ready.notices, [])
})

test('Mermaid validation redirects an ordinary human diagram before the fence is published', async () => {
  const f = setup({ native: true })
  const policy = f.ctx.listeners.get('tools/pre-execute')[0]
  const exec = { name: 'validate_dsh_ui', agent: f.agent, arguments: { spec: { items: [{ type: 'row', items: [{ type: 'mermaid', code: 'graph TD\nA-->B' }] }] } } }
  const next = async () => ({ kind: 'allow' })
  f.start(); f.user('我想知道产业链结构')
  const redirect = await policy(exec, next)
  assert.equal(redirect.kind, 'deny')
  assert.match(redirect.reason, /dsh-ui type=diagram/)
  assert.deepEqual(await policy({ ...exec, arguments: { spec: { items: [{ type: 'text', text: 'Mermaid' }] } } }, next), { kind: 'allow' })
  f.start(2); f.user('请生成 Mermaid 流程图')
  assert.deepEqual(await policy(exec, next), { kind: 'allow' })
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

test('absence of a local validator does not start competing repairs of malformed GenUI fences', () => {
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
  f.start(2); f.rt.live.get('s').info = { role: 'room' }
  f.emit('user/message', { source: { kind: 'bot', role: 'room' }, content: content('This round so far (oldest first):\nUser: 我想知道产业链结构\n\nPlease reply.') })
  f.answer(fence()); f.stop(2)
  assert.equal(f.notices.length, 2)
  assert.match(f.notices[1].content[0].text, /dsh-ui type=diagram/)
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
    assert.match(f.notices[0].content[0].text, /native show_view stack to deliver headline metric cards and the dated spot chart/)
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

test('mixed-market completion requires a shared-date overlay AND basis, not unrelated price charts', () => {
  const dates = ['2026-10-28', '2026-10-29', '2026-10-30']
  const overlay = { type: 'chart', kind: 'line', categories: dates, series: [
    { name: '甲醇现货·华东', values: [2400, 2420, 2430] },
    { name: '甲醇期货·MA主力', values: [2380, 2390, 2420] },
  ] }
  const basis = { type: 'chart', kind: 'line', categories: dates, series: [{ name: '基差（现货减期货）', values: [20, 30, 10] }] }
  assert.deepEqual(mixedMarketVisualStatus({ type: 'stack', children: [overlay, basis] }), { overlay: true, basis: true, complete: true })
  assert.equal(mixedMarketVisualStatus(overlay).complete, false)
  assert.equal(mixedMarketVisualStatus({ type: 'stack', children: [overlay, { ...basis, series: [{ name: '基差', values: [20, 300, 10] }] }] }).complete, false, 'basis must equal dated physical spot minus futures')
  assert.equal(mixedMarketVisualStatus({ type: 'stack', children: [
    { type: 'chart', kind: 'line', categories: dates, series: [{ name: '甲醇期货·MA主力', values: [2380, 2390, 2420] }] },
    { type: 'chart', kind: 'hbar', categories: ['华东', '华北'], series: [{ name: '甲醇现货价', values: [2400, 2420] }] },
    { type: 'metric', label: '基差', value: 20 },
  ] }).complete, false)
  assert.equal(mixedMarketVisualStatus({ type: 'stack', children: [
    { ...overlay, series: [{ name: '现货', values: [2400, null, null] }, overlay.series[1]] }, basis,
  ] }).complete, false)
})

test('raw group UI JSON/fences do not count as mixed-market visual delivery', () => {
  const raw = JSON.stringify({ type: 'stack', children: [{ type: 'chart', kind: 'line', categories: ['Oct'], series: [] }] }, null, 2)
  const ticks = String.fromCharCode(96).repeat(3)
  const fenced = '图表：\n' + ticks + 'dsh-ui\n' + JSON.stringify({ items: [{ type: 'text', text: 'Not rendered in group' }] }) + '\n' + ticks
  assert.equal(stripUnrenderedMixedViewText(raw), '')
  assert.equal(stripUnrenderedMixedViewText(raw.slice(0, 35), true), '')
  assert.equal(stripUnrenderedMixedViewText(fenced), '图表：')
  assert.equal(stripUnrenderedMixedViewText('解释：现货价应减期货价。'), '解释：现货价应减期货价。')
  assert.equal(stripUnrenderedMixedViewText('{"volume": 25}'), '{"volume": 25}')
  for (const reply of [raw, fenced]) {
    const f = setup(); f.start(); f.user('甲醇现货和期货价格叠加看基差'); f.answer(reply); f.stop()
    assert.equal(f.notices.length, 1)
    assert.match(f.notices[0].content[0].text, /ONE native show_view stack/)
    f.stop(); assert.equal(f.notices.length, 1)
  }
})

test('complete native spot-futures+basis stack satisfies a mixed-market turn', () => {
  const f = setup()
  f.start(); f.user('甲醇现货和期货价格叠加看基差')
  const dates = ['2026-10-28', '2026-10-29']
  const full = { type: 'stack', children: [
    { type: 'chart', kind: 'line', categories: dates, series: [
      { name: '甲醇现货', values: [2400, 2420] },
      { name: '甲醇期货 MA0', values: [2380, 2390] },
    ] },
    { type: 'chart', kind: 'line', categories: dates, series: [{ name: '基差', values: [20, 30] }] },
  ] }
  f.answer('同一日期现货和期货比较如下。'); f.rt.noteVisualDelivery('s', full); f.stop()
  assert.equal(f.notices.length, 0)
  f.start(2); f.user('甲醇现货最近一个月价格')
  assert.equal(f.rt.marketQuoteIntentOf('s'), 'spot')
  f.answer('只能找到当日现货报价。'); f.stop(2)
  assert.equal(f.notices.length, 1)
})
