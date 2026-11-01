import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { normalizeCandles, buildCandlestickSpec } from '../src/shared/candlestick.js'
import { checkShownView, validateView } from '../src/shared/views.js'
import { advancedChartData, advancedChartOption, advancedChartTable, candlestickTooltip } from '../src/client/chart-options.js'
import { DICTIONARY } from '../src/client/i18n.js'

const bars = count => Array.from({ length: count }, (_, i) => {
  const date = new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 10)
  const close = 100 + i
  return { 日期: date, 开盘: close - 1, 最高: close + 2, 最低: close - 3, 收盘: close, 成交量: 1000 + i }
})
const chart = result => result.spec.items[0].option

test('AKShare Chinese OHLCV fields become a safe native ECharts candlestick, not a line chart', () => {
  const result = buildCandlestickSpec(bars(24), { symbol: '600309', unit: '元/股', source: 'AKShare' })
  const option = chart(result)
  assert.equal(result.spec.items[0].type, 'echart')
  assert.equal(option.series[0].type, 'candlestick')
  assert.deepEqual(option.series[0].data[0], [99, 100, 97, 102])
  assert.equal(option.series.at(-1).name, 'Volume')
  assert.deepEqual(result.meta.movingAverages, ['MA5', 'MA10', 'MA20'])
  assert.equal(option.series[1].data[3], null)
  assert.equal(option.series[1].data[4], 102)
  assert.equal(option.tooltip.renderMode, 'richText')
  assert.equal(option.dataZoom.length, 2)
  assert.equal(result.meta.source, 'AKShare')
  assert.equal(JSON.parse(JSON.stringify(result.spec)).items[0].option.series[0].type, 'candlestick')
})

test('sort daily candles and calculate MA on the whole series BEFORE trimming the chart window', () => {
  const rows = bars(95)
  const result = buildCandlestickSpec(rows.reverse(), { maxBars: 80 })
  assert.equal(result.meta.omitted, 15)
  assert.equal(result.meta.total, 95)
  assert.equal(result.meta.firstDate, rows[79].日期)
  const option = chart(result)
  assert.equal(option.series[1].data[0], 113)
  assert.equal(option.xAxis[0].data.length, 80)
  assert.equal(option.series[0].data.length, 80)
  assert.equal(option.series.at(-1).data.length, 80)
})

test('no volume means no invented zero volume panel', () => {
  const rows = bars(3).map(row => { const rest = { ...row }; delete rest.成交量; return rest })
  const result = buildCandlestickSpec(rows)
  assert.equal(result.meta.volumeShown, false)
  assert.equal(chart(result).grid.length, 1)
  assert.equal(chart(result).series.some(series => series.name === 'Volume'), false)
  assert.deepEqual(result.meta.movingAverages, [])
})

test('strict OHLCV validation rejects impossible prices and bad dates rather than fixing history', () => {
  const cases = [
    [r => { r[0].最高 = 50 }, /OHLC relationship/],
    [r => { r[0].最低 = 150 }, /OHLC relationship/],
    [r => { r[0].开盘 = 'invalid' }, /Invalid open/],
    [r => { r[0].收盘 = Infinity }, /Invalid close/],
    [r => { r[0].成交量 = -1 }, /Invalid volume/],
    [r => { r[0].日期 = '2026-02-30' }, /Invalid candle date/],
    [r => { r[1].日期 = r[0].日期 }, /Duplicate candle date/],
  ]
  for (const [change, message] of cases) {
    const rows = bars(3)
    change(rows)
    assert.throws(() => buildCandlestickSpec(rows), message)
  }
  assert.throws(() => normalizeCandles([]), /At least two/)
  assert.throws(() => buildCandlestickSpec(bars(3), { maxBars: 81 }), /maxBars/)
})

test('text-only and close-only cases remain outside the OHLC rendering path', () => {
  assert.throws(() => buildCandlestickSpec([{ date: '2026-01-01', close: 9 }, { date: '2026-01-02', close: 10 }]), /Invalid open/)
  const policy = readFileSync(new URL('../src/host/view-policy.js', import.meta.url), 'utf8')
  assert.match(policy, /candlestick/)
  assert.match(policy, /OHLC/)
  assert.match(policy, /echart/)
  assert.match(policy, /text-only/)
})

test('actual AKShare futures columns and midnight daily timestamps normalize to OHLC bars', () => {
  const foreign = [
    { date: '2026-10-29T00:00:00', open: 101, high: 105, low: 100, close: 103, volume: 180 },
    { date: '2026-10-30 00:00:00', open: 103, high: 106, low: 102, close: 104, volume: 210 },
  ]
  assert.deepEqual(chart(buildCandlestickSpec(foreign)).series[0].data, [[101, 103, 100, 105], [103, 104, 102, 106]])
  const china = [
    { '日期': '20261029', '开盘价': '101', '最高价': '105', '最低价': '100', '收盘价': '103', '成交量': '1,800' },
    { '日期': '20261030', '开盘价': '103', '最高价': '106', '最低价': '102', '收盘价': '104', '成交量': '2,100' },
  ]
  assert.deepEqual(chart(buildCandlestickSpec(china)).series[0].data, [[101, 103, 100, 105], [103, 104, 102, 106]])
  assert.throws(() => buildCandlestickSpec([{ ...foreign[0], date: '2026-10-29T08:00:00' }, foreign[1]]), /Invalid candle date/)
})

test('Bot candlestick route contains source-specific OHLC retrieval and real inline GenUI instructions', () => {
  const policy = readFileSync(new URL('../src/host/view-policy.js', import.meta.url), 'utf8')
  assert.match(policy, /futures_foreign_hist/)
  assert.match(policy, /futures_zh_daily_sina/)
  assert.match(policy, /full-option/)
  assert.match(policy, /bars:/)
  assert.match(policy, /native show_view chart/)
  assert.match(policy, /20-40/)
})

test('native show_view accepts only real OHLC bars and rejects misleading close-only or arbitrary options', () => {
  const view = { type: 'chart', kind: 'candlestick', bars: bars(20), caption: 'AKShare / NYMEX CL / daily', unit: 'USD/barrel' }
  assert.deepEqual(validateView(view), { ok: true, interactive: false })
  assert.equal(checkShownView('WTI daily K-line', view).view.kind, 'candlestick')
  assert.match(validateView({ ...view, bars: bars(1) }).error, /2 to 50/)
  assert.match(validateView({ ...view, bars: bars(51) }).error, /2 to 50/)
  assert.match(validateView({ ...view, bars: bars(2).map(x => { const y = { ...x }; delete y.开盘; return y }) }).error, /Invalid open/)
  assert.match(validateView({ ...view, categories: ['2026-01-01'] }).error, /uses bars only/)
  assert.match(validateView({ ...view, option: { series: [{ type: 'line' }] } }).error, /unknown property/)
  assert.match(validateView({ ...view, bars: [{ ...bars(2)[0], script: 'bad' }, bars(2)[1]] }).error, /only date/)
})

test('native inline chart produces candlestick entities and volume with zoom and accurate OHLC order', () => {
  const view = { type: 'chart', kind: 'candlestick', bars: bars(24), caption: 'WTI', unit: 'USD/barrel' }
  const data = advancedChartData(view)
  const theme = { ink: '#121212', muted: '#777', line: '#ddd', card: '#fff', font: 'Arial', colors: ['#234', '#678'], up: '#aa5544', down: '#33aa77', narrow: false }
  const option = advancedChartOption(data, theme)
  assert.equal(option.series[0].type, 'candlestick')
  assert.deepEqual(option.series[0].data[0], [99, 100, 97, 102])
  assert.equal(option.series.at(-1).type, 'bar')
  assert.equal(option.series.at(-1).name, 'Volume')
  assert.equal(option.series[1].name, 'MA5')
  assert.equal(option.series[2].name, 'MA10')
  assert.equal(option.series[3].name, 'MA20')
  assert.deepEqual(option.dataZoom.map(item => item.type), ['inside', 'slider'])
  assert.equal(option.tooltip.trigger, 'axis')
  assert.equal(option.yAxis[0].scale, true)
  assert.equal(option.grid.length, 2)
  assert.equal(advancedChartTable(data, 'Value', 'Series').rows.length, 24)
  assert.equal(advancedChartTable(data, 'Value', 'Series').columns[1], 'Opening price')
  assert.equal(option.series.length, 5)
  const missingVolume = advancedChartOption(advancedChartData({ ...view, bars: bars(3).map(item => {
    const copy = { ...item }; delete copy.成交量; return copy
  }) }), theme)
  assert.equal(missingVolume.grid.length, 1)
  assert.equal(missingVolume.series.length, 1)
})

test('native loader and host tool advertise candlestick and no raw ECharts chart options', () => {
  const engine = readFileSync(new URL('../src/client/chart-engine.js', import.meta.url), 'utf8')
  const tools = readFileSync(new URL('../src/host/tools.js', import.meta.url), 'utf8')
  const policy = readFileSync(new URL('../src/host/view-policy.js', import.meta.url), 'utf8')
  assert.match(engine, /CandlestickChart/)
  assert.match(engine, /DataZoomSliderComponent/)
  assert.match(tools, /kind\?: bar\|hbar\|line\|area\|donut\|candlestick/)
  assert.match(policy, /ONE primary inline price visualization/)
  assert.match(policy, /DO NOT also emit HTML/)
})

test('native candle hover uses localized field names in the model-selected UI language', () => {
  for (const key of ['OHLC', 'Opening price', 'Closing price', 'Highest price', 'Lowest price', 'Trading volume', 'Trading date'])
    assert.equal(typeof DICTIONARY.zh[key], 'string')
  assert.equal(DICTIONARY.zh['Opening price'], '开盘价')
  assert.equal(DICTIONARY.zh['Highest price'], '最高价')
  const tooltip = candlestickTooltip([
    { seriesType: 'candlestick', axisValue: '2026-10-13', data: [93.16, 94.77, 91.70, 95.11] },
    { seriesType: 'line', seriesName: 'MA5', data: 91.932 },
    { seriesType: 'bar', seriesName: 'Volume', data: { value: 1000 } },
  ])
  assert.match(tooltip, /2026-10-13/)
  assert.match(tooltip, /Opening price.*93.16/)
  assert.match(tooltip, /Closing price.*94.77/)
  assert.match(tooltip, /Highest price.*95.11/)
  assert.match(tooltip, /Lowest price.*91.7/)
  assert.match(tooltip, /MA5.*91.932/)
  assert.match(tooltip, /Trading volume.*1,000/)
  const records = bars(7)
  const theme = { ink: '#222', muted: '#777', line: '#ddd', card: '#fff',
    colors: ['#bda', '#aac'], up: '#ff0000', down: '#00ff00', font: 'Arial', narrow: false }
  assert.equal(advancedChartOption(advancedChartData({ type: 'chart', kind: 'candlestick', bars: records }), theme).tooltip.formatter, candlestickTooltip)
})
