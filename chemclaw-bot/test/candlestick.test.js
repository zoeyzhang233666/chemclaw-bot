import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { normalizeCandles, buildCandlestickSpec } from '../src/shared/candlestick.js'

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
  const rows = bars(3).map(row => { const { 成交量, ...rest } = row; return rest })
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
