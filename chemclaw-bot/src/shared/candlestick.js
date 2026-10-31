// Data-only candlestick spec for ChemClaw's already-installed GenUI ECharts.
// This module never executes user-supplied JS or fetches external resources.
const field = (row, names) => names.find(name => Object.hasOwn(row, name) && row[name] !== undefined)?.let
const pick = (row, names) => {
  for (const name of names) if (Object.hasOwn(row, name) && row[name] !== undefined) return row[name]
  return undefined
}
const value = (raw, label, positive = true) => {
  const text = typeof raw === 'string' ? raw.trim().replaceAll(',', '') : raw
  const n = typeof text === 'number' ? text : typeof text === 'string' && text !== '' ? Number(text) : NaN
  if (!Number.isFinite(n) || (positive ? n <= 0 : n < 0)) throw new Error(`Invalid ${label}`)
  return n
}
const dateOf = raw => {
  const str = String(raw ?? '').trim()
  const date = /^\d{8}$/.test(str) ? `${str.slice(0, 4)}-${str.slice(4, 6)}-${str.slice(6, 8)}` : str
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(date)) ||
      new Date(date + 'T00:00:00Z').toISOString().slice(0, 10) !== date) throw new Error('Invalid candle date')
  return date
}
export function normalizeCandles(records) {
  if (!Array.isArray(records) || records.length < 2) throw new Error('At least two OHLC observations are required')
  const candles = records.map((row, index) => {
    if (row === null || typeof row !== 'object' || Array.isArray(row)) throw new Error(`Invalid candle row ${index}`)
    const date = dateOf(pick(row, ['date', 'time', '日期', '交易日期']))
    const open = value(pick(row, ['open', '开盘']), 'open')
    const high = value(pick(row, ['high', '最高']), 'high')
    const low = value(pick(row, ['low', '最低']), 'low')
    const close = value(pick(row, ['close', '收盘']), 'close')
    if (low > Math.min(open, close) || high < Math.max(open, close) || high < low)
      throw new Error(`Invalid OHLC relationship at ${date}`)
    const rawVolume = pick(row, ['volume', '成交量'])
    const volume = rawVolume === undefined || rawVolume === null || rawVolume === '' ? null : value(rawVolume, 'volume', false)
    return { date, open, high, low, close, volume }
  }).sort((a, b) => a.date.localeCompare(b.date))
  for (let i = 1; i < candles.length; i++) if (candles[i].date === candles[i - 1].date) throw new Error(`Duplicate candle date ${candles[i].date}`)
  return candles
}
const ma = (data, window) => data.map((row, i) => {
  if (i + 1 < window) return null
  let sum = 0
  for (let j = i - window + 1; j <= i; j++) sum += data[j].close
  return Number((sum / window).toFixed(6))
})
export function buildCandlestickSpec(records, { maxBars = 80, unit = '', source = '', symbol = '' } = {}) {
  if (!Number.isInteger(maxBars) || maxBars < 2 || maxBars > 80) throw new Error('maxBars must be an integer from 2 to 80')
  for (const [name, text] of Object.entries({ unit, source, symbol }))
    if (typeof text !== 'string' || text.length > 180) throw new Error(`Invalid ${name}`)
  const all = normalizeCandles(records)
  // Compute averages before choosing the displayed window, preserving prior history.
  const averages = [5, 10, 20].map(n => ({ n, data: ma(all, n) }))
  const offset = Math.max(0, all.length - maxBars)
  const rows = all.slice(offset)
  const dates = rows.map(row => row.date)
  const volumeAvailable = rows.every(row => row.volume !== null)
  const up = '#df5555', down = '#23a478'
  const volumeData = rows.map(row => ({ value: row.volume, itemStyle: { color: row.close >= row.open ? up : down } }))
  const priceSeries = [{
    name: 'OHLC', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
    data: rows.map(row => [row.open, row.close, row.low, row.high]),
    itemStyle: { color: up, color0: down, borderColor: up, borderColor0: down },
  }]
  for (const average of averages) if (all.length >= average.n) priceSeries.push({
    name: `MA${average.n}`, type: 'line', xAxisIndex: 0, yAxisIndex: 0, showSymbol: false,
    smooth: false, connectNulls: false, lineStyle: { width: 1.3 },
    data: average.data.slice(offset),
  })
  const axis = { type: 'category', data: dates, boundaryGap: true, axisLabel: { hideOverlap: true } }
  const price = { type: 'value', scale: true, splitLine: { show: true } }
  const hasVolume = volumeAvailable && rows.some(row => row.volume > 0)
  const option = {
    animation: false,
    legend: { type: 'scroll', top: 0 },
    tooltip: { trigger: 'axis', confine: true, renderMode: 'richText', axisPointer: { type: 'cross' } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: hasVolume
      ? [{ left: 56, right: 12, top: 42, height: '55%' }, { left: 56, right: 12, top: '76%', height: '12%' }]
      : [{ left: 56, right: 12, top: 42, bottom: 76 }],
    xAxis: hasVolume
      ? [{ ...axis, gridIndex: 0, axisLabel: { show: false } }, { ...axis, gridIndex: 1 }]
      : [{ ...axis, gridIndex: 0 }],
    yAxis: hasVolume
      ? [{ ...price, gridIndex: 0, name: unit }, { type: 'value', gridIndex: 1, scale: true, splitNumber: 2 }]
      : [{ ...price, gridIndex: 0, name: unit }],
    dataZoom: [
      { type: 'inside', xAxisIndex: hasVolume ? [0, 1] : [0], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: hasVolume ? [0, 1] : [0], bottom: 12, height: 18, start: 0, end: 100 },
    ],
    series: hasVolume ? [...priceSeries, { name: 'Volume', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumeData }] : priceSeries,
  }
  return {
    spec: { items: [{ type: 'echart', height: 420, option }] },
    meta: {
      symbol, source, unit, total: all.length, shown: rows.length, omitted: offset,
      firstDate: rows[0].date, lastDate: rows.at(-1).date,
      volumeShown: hasVolume, movingAverages: priceSeries.slice(1).map(series => series.name),
    },
  }
}
