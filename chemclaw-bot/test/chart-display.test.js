import assert from 'node:assert/strict'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { runInNewContext } from 'node:vm'
import { build } from 'esbuild'

const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/client/widget-chart.js', import.meta.url))], bundle: true, format: 'cjs', platform: 'browser', write: false, external: ['react'], logLevel: 'silent' })
const values = []
let slot = 0
let effects = []
const module = { exports: {} }
runInNewContext(outputFiles[0].text, { module, exports: module.exports, require: () => ({
  createElement: (type, props, ...children) => ({ type, props: { ...props, children } }), Fragment: 'fragment',
  useState: initial => { const at = slot++; if (!(at in values)) values[at] = initial; return [values[at], next => { values[at] = typeof next === 'function' ? next(values[at]) : next }] },
  useRef: current => ({ current }), useId: () => 'chart', useEffect: effect => effects.push(effect), useLayoutEffect() {},
}) })
const { categoryTicks, lineSegments, chartData, chartCsv, WidgetChart } = module.exports
const plain = value => JSON.parse(JSON.stringify(value))
const dates = Array.from({ length: 57 }, (_, index) => new Date(Date.UTC(2026, 8, index + 1)).toISOString().slice(0, 10))
const nodes = node => !node || typeof node !== 'object' ? [] : Array.isArray(node) ? node.flatMap(nodes) : [node, ...nodes(node.props.children)]
const render = (node, props = {}) => { slot = 0; effects = []; return WidgetChart({ node, ...props }) }
const chart = { type: 'chart', kind: 'line', categories: dates, series: [{ name: 'Verified price', values: dates.map((_, at) => at === 20 ? null : 3000 + at * 10) }], unit: '元/吨' }

test('date labels remain readable on desktop and mobile while every observation remains hoverable', () => {
  for (const [width, limit] of [[680, 16], [230, 5]]) {
    const ticks = categoryTicks(dates, width)
    assert.ok(ticks.length <= limit)
    assert.equal(ticks[0].index, 0)
    assert.equal(ticks.at(-1).index, dates.length - 1)
    assert.ok(ticks.every(tick => /^\d{2}-\d{2}$/.test(tick.label)))
    assert.equal(new Set(ticks.map(tick => tick.index)).size, ticks.length)
  }
  const crossYear = categoryTicks(['2025-12-31', '2026-01-01', '2026-01-02'], 250)
  assert.ok(crossYear.every(tick => /^\d{4}-\d{2}-\d{2}$/.test(tick.label)))
  values.length = 0
  const tree = render(chart)
  const hits = nodes(tree).filter(node => node.props.className === 'bt-chart-hit')
  assert.equal(hits.length, dates.length)
  hits[20].props.onPointerEnter()
  const hovered = nodes(render(chart)).find(node => node.props.className === 'bt-chart-tip')
  assert.match(JSON.stringify(hovered), /2026-09-21/)
  assert.match(JSON.stringify(hovered), /No data/)
})

test('missing observations stay missing through rendering, CSV and discontinuous line segments', () => {
  const data = chartData({ categories: ['A', 'B', 'C', 'D', 'E'], series: [{ values: [0, null, 12, undefined, { '=': '1 / 0' }] }] })
  assert.deepEqual(plain(data.series[0].values), [0, null, 12, null, null])
  assert.deepEqual(plain(lineSegments([null, 0, 2, null, 4, null])), [[1, 2], [4]])
  assert.equal(chartCsv(data), ',Value\nA,0\nB,\nC,12\nD,\nE,')
  for (const kind of ['line', 'area', 'bar', 'hbar', 'donut']) {
    values.length = 0
    const tree = render({ ...chart, kind })
    assert.doesNotMatch(JSON.stringify(tree), /NaN|Infinity/)
    const lines = nodes(tree).filter(node => node.props.className === 'bt-chart-line')
    if (kind === 'line' || kind === 'area') assert.equal(lines.length, 2)
  }
})

test('zoom changes visible points and reset restores them; the data table still carries the whole source', () => {
  values.length = 0
  let actions
  const first = render(chart, { registerChart: (_key, value) => { actions = value } })
  effects.forEach(effect => effect())
  const start = nodes(first).find(node => node.props['aria-label'] === 'Range start')
  start.props.onKeyDown({ key: 'End', preventDefault() {} })
  for (let at = 0; at < 15; at += 1) {
    nodes(render(chart)).find(node => node.props['aria-label'] === 'Range start').props.onKeyDown({ key: 'ArrowLeft', preventDefault() {} })
  }
  const zoomed = render(chart)
  assert.equal(nodes(zoomed).filter(node => node.props.className === 'bt-chart-hit').length, 17)
  assert.match(JSON.stringify(zoomed), /2026-10-11/)
  actions.toggleTable()
  const table = nodes(render(chart)).find(node => typeof node.type === 'function' && node.type.name === 'ChartTable')
  const rows = nodes(table.type(table.props)).filter(node => node.type === 'tr')
  assert.equal(rows.length, 58, 'the header and all observations remain in the table after zooming')
  assert.match(JSON.stringify(rows[21]), /No data/)
  actions.toggleTable()
  const reset = nodes(zoomed).find(node => node.type === 'button' && node.props.children.includes('Show all'))
  reset.props.onClick()
  assert.equal(nodes(render(chart)).filter(node => node.props.className === 'bt-chart-hit').length, 57)
})

test('the overview has one movable selection with two handles; dragging and keyboard movement keep the range bounded', () => {
  values.length = 0
  const trackBox = { getBoundingClientRect: () => ({ left: 0, width: 560 }) }
  const target = { closest: () => trackBox, setPointerCapture() {} }
  const pointer = x => ({ button: 0, pointerId: 1, clientX: x, currentTarget: target, preventDefault() {}, stopPropagation() {} })
  const drag = (label, x, next) => {
    const tree = render(chart)
    const handle = nodes(tree).find(node => node.props['aria-label'] === label)
    handle.props.onPointerDown(pointer(x))
    const track = nodes(tree).find(node => node.props.className === 'bt-chart-range-track')
    track.props.onPointerMove(pointer(next))
    track.props.onPointerUp(pointer(next))
  }
  const selection = () => nodes(render(chart)).find(node => node.props['aria-label'] === 'Move range').props['aria-valuetext']
  assert.equal(nodes(render(chart)).filter(node => node.type === 'input').length, 0)
  assert.equal(nodes(render(chart)).filter(node => node.props.className === 'bt-chart-overview').length, 1)
  drag('Range start', 0, 200)
  assert.equal(selection(), `${dates[20]} – ${dates[56]}`)
  drag('Move range', 300, 200)
  assert.equal(selection(), `${dates[10]} – ${dates[46]}`)
  drag('Range end', 460, 300)
  assert.equal(selection(), `${dates[10]} – ${dates[30]}`)
  drag('Move range', 200, -500)
  assert.equal(selection(), `${dates[0]} – ${dates[20]}`)
  nodes(render(chart)).find(node => node.props['aria-label'] === 'Move range').props.onKeyDown({ key: 'End', preventDefault() {} })
  assert.equal(selection(), `${dates[36]} – ${dates[56]}`)
})

test('keyboard navigation preserves full dates and visits every observation, including a gap', () => {
  values.length = 0
  for (let at = 0; at < dates.length; at += 1) {
    const svg = nodes(render(chart)).find(node => node.props.className === 'bt-chart-svg')
    svg.props.onKeyDown({ key: 'ArrowRight', preventDefault() {} })
    const tip = nodes(render(chart)).find(node => node.props.className === 'bt-chart-tip')
    assert.match(JSON.stringify(tip), new RegExp(dates[at]))
    if (at === 20) assert.match(JSON.stringify(tip), /No data/)
  }
})
