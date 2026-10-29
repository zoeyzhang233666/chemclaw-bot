import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { CHART_EXAMPLES } from '../dev/chart-examples.mjs'
import { checkShownView, normalizeView, validateView, viewScope, viewSummary } from '../src/shared/views.js'
import { advancedChartData, advancedChartOption, advancedChartTable, tableCsv } from '../src/client/chart-options.js'
import { install as installChartAssets } from '../src/host/chart-assets.js'
import { CHART_ENGINE_ROUTE } from '../src/shared/chart-engine.js'

const theme = { ink: 'ink', muted: 'muted', line: 'line', card: 'card', font: 'test-font', colors: ['accent', 'second'], narrow: false }
const clone = kind => structuredClone(CHART_EXAMPLES[kind])

test('all advanced views validate, replay, summarize and build data-only options', () => {
  for (const [kind, view] of Object.entries(CHART_EXAMPLES)) {
    assert.deepEqual(validateView(view), { ok: true, interactive: false }, kind)
    assert.deepEqual(checkShownView('Synthetic', view).view, view)
    assert.match(viewSummary(view), /chart/)
    const data = advancedChartData(view)
    assert.equal(data.drawable, true, kind)
    const option = advancedChartOption(data, theme)
    assert.equal(option.animation, false)
    assert.equal(option.tooltip.renderMode, 'richText')
    assert.deepEqual(option.color, theme.colors)
    assert.ok(option.series.length > 0)
    assert.doesNotMatch(JSON.stringify(option), /NaN|Infinity|undefined/)
    assert.ok(advancedChartTable(data, 'Value', 'Series').rows.length > 0)
    assert.equal(checkShownView('', { ...view, option: { tooltip: { formatter: 'script' } } }).error.includes('unknown property'), true)
  }
})

test('missing observations stay missing in plots, tables and CSV', () => {
  const scatter = advancedChartData(clone('scatter'))
  const scatterOption = advancedChartOption(scatter, theme)
  assert.equal(scatterOption.series[0].data.length, 3)
  const csv = tableCsv(advancedChartTable(scatter, 'Value', 'Series'))
  assert.match(csv, /Missing,30,$/)
  const heatmap = advancedChartOption(advancedChartData(clone('heatmap')), theme)
  assert.equal(heatmap.series[0].data.length, 8)
  const radar = clone('radar')
  radar.series[1].values[1] = null
  assert.equal(validateView(radar).ok, true)
  assert.equal(advancedChartData(radar).drawable, false)
  assert.match(tableCsv({ columns: ['A'], rows: [[null], ['a,"b\nc']] }), /A\n\n"a,""b\nc"/)
})

test('advanced constraints reject contradictory axes, illegal fields and oversized data', () => {
  const cases = [
    ['radar', view => { view.maxima[0] = 0 }, /maxima/],
    ['radar', view => { view.series[0].values[0] = 101 }, /maximum/],
    ['radar', view => { view.categories = ['one', 'two'] }, /3 to 12/],
    ['gauge', view => { view.max = 0 }, /max/],
    ['gauge', view => { view.series[0].values[0] = 101 }, /exceeds max/],
    ['funnel', view => { view.series[0].values[0] = -1 }, /non-negative/],
    ['treemap', view => { view.series.push(view.series[0]) }, /one series/],
    ['scatter', view => { view.xValues.pop() }, /xValues/],
    ['heatmap', view => { view.max = 5 }, /not supported/],
    ['heatmap', view => { view.categories = Array(81).fill('a') }, /80 labels/],
    ['heatmap', view => { view.series = Array(13).fill(view.series[0]) }, /12 series/],
  ]
  for (const [kind, change, pattern] of cases) {
    const view = clone(kind)
    change(view)
    assert.match(validateView(view).error, pattern)
  }
  assert.match(validateView({ type: 'chart', categories: ['a'], series: [{ values: [1] }], links: [] }).error, /not supported/)
})

test('sankey validates finite positive DAG edges and preserves flow evidence in history', () => {
  for (const [edge, pattern] of [
    [{ source: 0, target: 0, value: 2 }, /itself/],
    [{ source: 4, target: 0, value: 2 }, /cycle/],
    [{ source: 1, target: 9, value: 2 }, /category index/],
    [{ source: 1, target: 2, value: Infinity }, /positive number/],
    [{ source: 1, target: 2, value: -1 }, /positive number/],
    [{ source: 0, target: 1, value: 3 }, /duplicate/],
    [{ source: 1, target: 2, value: 3, url: 'https://example.com' }, /expected/],
  ]) {
    const view = clone('sankey')
    view.links.push(edge)
    assert.match(validateView(view).error, pattern)
  }
  assert.match(viewSummary(clone('sankey')), /Soda ash→Glass=70/)
  const wrapped = clone('sankey')
  wrapped.links[0] = { source: '0', target: '1', value: '70' }
  assert.equal(validateView(normalizeView(wrapped)).ok, true)
})

test('local formulas recalculate points and invalid domain values fall back without clamping', () => {
  const view = { type: 'stack', children: [
    { type: 'number', id: 'price', label: 'Price', value: 25 },
    { ...clone('scatter'), xValues: [{ '=': 'price * 2' }, 22, 16, null] },
    { ...clone('gauge'), series: [{ values: [{ '=': 'price' }] }] },
  ] }
  assert.equal(validateView(view).ok, true)
  const lookup = viewScope(view, { price: 110 })
  const scatter = advancedChartData(view.children[1], lookup)
  assert.equal(scatter.xValues[0], 220)
  assert.equal(advancedChartData(view.children[2], lookup).drawable, false)
})

test('chart engine is served as a fixed same-origin asset through the public Fetch API', async () => {
  let route
  installChartAssets({ ctx: { effect: effect => effect(), connection: { fetch: { register: entry => { route = entry } } } } })
  assert.equal(route.path, CHART_ENGINE_ROUTE)
  assert.deepEqual(route.methods, ['GET'])
  assert.equal(route.requestBody, 'buffered')
  const response = await route.fetch()
  assert.equal(response.headers.get('content-type'), 'text/javascript; charset=utf-8')
  assert.match(response.headers.get('cache-control'), /private/)
  assert.equal(response.headers.get('x-content-type-options'), 'nosniff')
  assert.equal(await response.text(), readFileSync(new URL('../runtime/chart-engine.js', import.meta.url), 'utf8'))
})

test('chart loader shares requests and retries a failed load without executing generated text', async () => {
  const source = readFileSync(new URL('../src/client/chart-loader.js', import.meta.url), 'utf8')
    .replace(/^import[^\n]+\n/, '').replace('export function', 'function') + '\nthis.load = loadChartEngine'
  const scripts = []
  const context = { window: {}, CHART_ENGINE_ROUTE, setTimeout: () => 1, clearTimeout() {},
    document: { createElement: () => ({ remove() {} }), head: { appendChild: script => scripts.push(script) } } }
  runInNewContext(source, context)
  const first = context.load()
  assert.equal(context.load(), first)
  assert.equal(scripts.length, 1)
  scripts[0].onerror()
  await assert.rejects(first, /unavailable/)
  const retry = context.load()
  assert.equal(scripts.length, 2)
  context.window.ChemClawChartEngine = { create() {} }
  scripts[1].onload()
  assert.equal(await retry, context.window.ChemClawChartEngine)
})
