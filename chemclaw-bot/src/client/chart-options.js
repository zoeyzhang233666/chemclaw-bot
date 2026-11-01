import { resolve } from '../shared/views.js'
import { normalizeCandles } from '../shared/candlestick.js'

const number = (value, lookup) => {
  const result = resolve(value, lookup)
  return typeof result === 'number' && Number.isFinite(result) ? result : null
}

export function advancedChartData(node, lookup) {
  if (node.kind === 'candlestick') {
    const bars = normalizeCandles(node.bars)
    return { ...node, bars, categories: bars.map(bar => bar.date), series: [], drawable: true }
  }
  const categories = node.categories.map(String)
  const series = (node.series ?? []).map(item => ({ name: item.name ?? '', values: item.values.map(value => number(value, lookup)) }))
  const data = { ...node, categories, series, xValues: node.xValues?.map(value => number(value, lookup)) }
  const values = series.flatMap(item => item.values)
  data.drawable = node.kind === 'sankey' || values.some(value => value !== null)
  if (['radar', 'funnel', 'treemap', 'gauge'].includes(node.kind) && values.some(value => value !== null && value < 0)) data.drawable = false
  if (node.kind === 'radar' && series.some(item => item.values.some((value, at) => value === null || value > node.maxima[at]))) data.drawable = false
  if (node.kind === 'gauge' && values.some(value => value === null || value > node.max)) data.drawable = false
  if (node.kind === 'scatter' && !series.some(item => item.values.some((value, at) => value !== null && data.xValues[at] !== null))) data.drawable = false
  return data
}

export function advancedChartTable(data, valueLabel, seriesLabel) {
  const { categories, series, unit = '' } = data
  if (data.kind === 'candlestick') {
    const volume = data.bars.every(bar => bar.volume !== null)
    return { columns: ['Date', 'Open', 'High', 'Low', 'Close', ...(volume ? ['Volume'] : [])],
      rows: data.bars.map(bar => [bar.date, bar.open, bar.high, bar.low, bar.close, ...(volume ? [bar.volume] : [])]) }
  }
  if (data.kind === 'sankey') return {
    columns: ['Source', 'Target', unit || valueLabel],
    rows: data.links.map(edge => [categories[edge.source], categories[edge.target], edge.value]),
  }
  const columns = ['', ...(data.kind === 'scatter' ? [data.xUnit || 'X'] : []),
    ...series.map((item, at) => `${item.name || (series.length === 1 ? valueLabel : `${seriesLabel} ${at + 1}`)}${unit ? ` (${unit})` : ''}`)]
  return { columns, rows: categories.map((label, at) => [label, ...(data.kind === 'scatter' ? [data.xValues[at]] : []), ...series.map(item => item.values[at])]) }
}

export function tableCsv(table) {
  const cell = value => {
    const text = value === null || value === undefined ? '' : String(value)
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  return [table.columns, ...table.rows].map(row => row.map(cell).join(',')).join('\n')
}

// Explicit options keep generated content out of executable and HTML formatter paths.
export function advancedChartOption(data, theme) {
  const { categories, series, unit = '' } = data
  const label = { color: theme.ink, fontFamily: theme.font, fontSize: 11 }
  const axis = { axisLabel: { color: theme.muted, fontSize: 10, hideOverlap: true }, axisLine: { lineStyle: { color: theme.line } }, splitLine: { lineStyle: { color: theme.line, type: 'dashed' } }, nameTextStyle: label }
  const legend = { type: 'scroll', top: 0, textStyle: { ...label, color: theme.muted }, itemWidth: 10, itemHeight: 10 }
  const base = {
    animation: false, color: theme.colors, backgroundColor: 'transparent',
    textStyle: { ...label, fontSize: 12 }, aria: { enabled: true },
    tooltip: { trigger: 'item', renderMode: 'richText', confine: true, backgroundColor: theme.card, borderColor: theme.line, textStyle: { ...label, fontSize: 12 } },
  }
  if (data.kind === 'candlestick') {
    const bars = data.bars
    const dates = bars.map(bar => bar.date)
    const volume = bars.every(bar => bar.volume !== null)
    const up = theme.up, down = theme.down
    const movingAverage = length => bars.map((_, at) => {
      if (at < length - 1) return null
      return Number((bars.slice(at + 1 - length, at + 1).reduce((sum, bar) => sum + bar.close, 0) / length).toFixed(6))
    })
    const means = [5, 10, 20].filter(n => bars.length >= n).map((n, at) => ({
      name: `MA${n}`, type: 'line', xAxisIndex: 0, yAxisIndex: 0,
      data: movingAverage(n), symbol: 'none', lineStyle: { width: 1.2 },
      itemStyle: { color: theme.colors[at % theme.colors.length] }, connectNulls: false,
    }))
    const candle = { name: 'OHLC', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
      data: bars.map(bar => [bar.open, bar.close, bar.low, bar.high]),
      itemStyle: { color: up, color0: down, borderColor: up, borderColor0: down },
    }
    const xAxis = { ...axis, type: 'category', boundaryGap: true, data: dates }
    const yAxis = { ...axis, type: 'value', name: unit, scale: true }
    return { ...base, tooltip: { ...base.tooltip, trigger: 'axis', axisPointer: { type: 'cross' } },
      axisPointer: { link: [{ xAxisIndex: volume ? [0, 1] : [0] }] },
      legend: means.length ? { ...legend, data: ['OHLC', ...means.map(item => item.name)] } : undefined,
      grid: volume
        ? [{ left: 64, right: 16, top: 48, height: '54%' }, { left: 64, right: 16, top: '76%', height: '10%' }]
        : [{ left: 64, right: 16, top: 48, bottom: 68 }],
      xAxis: volume
        ? [{ ...xAxis, gridIndex: 0, axisLabel: { show: false } }, { ...xAxis, gridIndex: 1 }]
        : [{ ...xAxis, gridIndex: 0 }],
      yAxis: volume
        ? [{ ...yAxis, gridIndex: 0 }, { ...axis, type: 'value', gridIndex: 1, scale: true, splitNumber: 2 }]
        : [{ ...yAxis, gridIndex: 0 }],
      dataZoom: [
        { type: 'inside', xAxisIndex: volume ? [0, 1] : [0], start: 0, end: 100 },
        { type: 'slider', xAxisIndex: volume ? [0, 1] : [0], bottom: 8, height: 20, start: 0, end: 100 },
      ],
      series: [candle, ...means, ...(volume ? [{
        name: 'Volume', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: bars.map(bar => ({ value: bar.volume, itemStyle: { color: bar.close >= bar.open ? up : down } })),
      }] : [])],
    }
  }
  if (data.kind === 'scatter') return { ...base, legend: series.length > 1 ? legend : undefined,
    grid: { left: 12, right: 16, top: series.length > 1 ? 38 : 20, bottom: 24, containLabel: true },
    xAxis: { ...axis, type: 'value', name: data.xUnit ?? '', nameLocation: 'middle', nameGap: 28, scale: true },
    yAxis: { ...axis, type: 'value', name: unit, scale: true },
    series: series.map(item => ({ type: 'scatter', name: item.name, symbolSize: 10,
      data: item.values.flatMap((value, at) => value === null || data.xValues[at] === null ? [] : [{ name: categories[at], value: [data.xValues[at], value] }]),
    })),
  }
  if (data.kind === 'radar') return { ...base, legend: series.length > 1 ? legend : undefined,
    radar: { center: ['50%', '54%'], radius: '62%', indicator: categories.map((name, at) => ({ name, max: data.maxima[at] })),
      axisName: { ...label, width: theme.narrow ? 64 : 120, overflow: 'truncate' },
      splitLine: { lineStyle: { color: theme.line } }, axisLine: { lineStyle: { color: theme.line } }, splitArea: { show: false } },
    series: [{ type: 'radar', symbolSize: 5, areaStyle: { opacity: 0.08 }, data: series.map(item => ({ name: item.name, value: item.values })) }],
  }
  if (data.kind === 'heatmap') {
    const known = series.flatMap(item => item.values).filter(value => value !== null)
    return { ...base, grid: { left: 8, right: 12, top: 12, bottom: 56, containLabel: true },
      xAxis: { ...axis, type: 'category', data: categories, splitArea: { show: false } },
      yAxis: { ...axis, type: 'category', data: series.map(item => item.name), splitArea: { show: false } },
      visualMap: { min: Math.min(...known), max: Math.max(...known), calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
        textStyle: label, inRange: { color: [theme.card, theme.colors[0]] } },
      series: [{ type: 'heatmap', data: series.flatMap((item, row) => item.values.flatMap((value, col) => value === null ? [] : [[col, row, value]])),
        itemStyle: { borderColor: theme.card, borderWidth: 2 }, label: { show: known.length <= 36, ...label } }],
    }
  }
  if (data.kind === 'sankey') return { ...base, series: [{ type: 'sankey', left: 8, right: theme.narrow ? 74 : 110, top: 12, bottom: 12,
    data: categories.map(name => ({ name })), links: data.links.map(edge => ({ source: categories[edge.source], target: categories[edge.target], value: edge.value })),
    label: { ...label, width: theme.narrow ? 64 : 100, overflow: 'truncate' }, nodeWidth: 14, nodeGap: 18,
    emphasis: { focus: 'adjacency' }, lineStyle: { color: 'source', opacity: 0.22, curveness: 0.5 },
  }] }
  if (data.kind === 'gauge') return { ...base, series: [{ type: 'gauge', min: 0, max: data.max,
    startAngle: 210, endAngle: -30, radius: '82%', center: ['50%', '58%'],
    progress: { show: true, width: 12, roundCap: true }, axisLine: { lineStyle: { width: 12, color: [[1, theme.line]] } },
    axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false }, pointer: { show: false },
    title: { ...label, offsetCenter: [0, '40%'] }, detail: { color: theme.ink, fontSize: 26, fontFamily: theme.font, formatter: `{value}${unit ? ` ${unit}` : ''}`, offsetCenter: [0, '0%'] },
    data: [{ name: categories[0], value: series[0].values[0] }],
  }] }
  const values = series[0].values.flatMap((value, at) => value === null ? [] : [{ name: categories[at], value }])
  if (data.kind === 'treemap') return { ...base, series: [{ type: 'treemap', data: values, roam: false, nodeClick: false,
    breadcrumb: { show: false }, left: 0, right: 0, top: 0, bottom: 0, label: { ...label, formatter: '{b}\n{c}' },
    itemStyle: { borderColor: theme.card, borderWidth: 3, gapWidth: 3 },
  }] }
  return { ...base, series: [{ type: 'funnel', data: values, sort: 'none', left: '14%', width: '65%', top: 12, bottom: 12, gap: 4,
    label: { ...label, position: 'inside', formatter: '{b}: {c}', overflow: 'truncate', width: theme.narrow ? 140 : 250 },
    itemStyle: { borderColor: theme.card, borderWidth: 1 },
  }] }
}
