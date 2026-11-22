import { advancedChartOption as chartOption } from '../shared/chart-options.js'
import { t } from './i18n.js'

export { advancedChartData, advancedChartTable, tableCsv } from '../shared/chart-options.js'

// Trusted client-owned formatter; no model-authored executable code or HTML.
export function candlestickTooltip(params) {
  const points = Array.isArray(params) ? params : [params]
  const candle = points.find(point => point?.seriesType === 'candlestick')
  const values = candle?.data?.value ?? candle?.data
  if (!Array.isArray(values) || values.length < 4) return ''
  const print = value => typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: 6 }) : '-'
  const date = String(candle.axisValue ?? candle.name ?? '')
  const lines = [date,
    `${t('Opening price')}：${print(values[0])}`,
    `${t('Closing price')}：${print(values[1])}`,
    `${t('Highest price')}：${print(values[3])}`,
    `${t('Lowest price')}：${print(values[2])}`,
  ]
  for (const point of points) {
    if (point?.seriesType === 'line' && /^MA(?:5|10|20)$/.test(point.seriesName ?? ''))
      lines.push(`${point.seriesName}：${print(point.data)}`)
    if (point?.seriesType === 'bar' && point?.seriesName === 'Volume')
      lines.push(`${t('Trading volume')}：${print(point.data?.value ?? point.data)}`)
  }
  return lines.join('\n')
}

export function advancedChartOption(data, theme) {
  return chartOption(data, theme, { candleName: t('OHLC'), candleTooltip: candlestickTooltip })
}
