import assert from 'node:assert/strict'
import { test } from 'node:test'
import { init } from 'echarts/core'
import '../src/client/chart-engine.js'
import { advancedChartData, advancedChartOption } from '../src/client/chart-options.js'

// The SVG runtime test protects against a blank plot with valid-looking axes.
test('actual native candlestick renderer draws candle shapes, not only axes', () => {
  const bars = Array.from({ length: 24 }, (_, index) => {
    const date = new Date(Date.UTC(2026, 9, 1 + index)).toISOString().slice(0, 10)
    const open = 90 + index
    const close = open + (index % 2 === 0 ? 2 : -2)
    return { date, open, high: Math.max(open, close) + 1, low: Math.min(open, close) - 1, close, volume: 100 + index }
  })
  const data = advancedChartData({ type: 'chart', kind: 'candlestick', bars, unit: 'USD/barrel' })
  const option = advancedChartOption(data, {
    ink: '#222', muted: '#777', line: '#ddd', card: '#fff', font: 'Arial',
    colors: ['#4567aa', '#9977bb', '#aa9933'], up: '#e46750', down: '#22a678', narrow: false,
  })
  const chart = init(null, null, { renderer: 'svg', ssr: true, width: 900, height: 450 })
  try {
    chart.setOption(option)
    const svg = chart.renderToSVGString()
    assert.match(svg, /<svg\b/)
    assert.match(svg, /#e46750/i, 'up candles must render in red')
    assert.match(svg, /#22a678/i, 'down candles must render in green')
    assert.ok((svg.match(/<path\b/g) ?? []).length > 24, 'must draw multiple SVG shapes and candles')
  } finally {
    chart.dispose()
  }
})
