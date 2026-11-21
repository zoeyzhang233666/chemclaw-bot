import { ADVANCED_CHART_KINDS } from '../../shared/advanced-charts.js'
import { normalizeCandles } from '../../shared/candlestick.js'
import { advancedChartData, advancedChartOption } from '../../shared/chart-options.js'
import { asText, checkShownView, resolve, viewScope } from '../../shared/views.js'

const WIDTH = 560
const PAD = 24
const INNER = WIDTH - PAD * 2
const MAX_HEIGHT = 1600
const THEME = {
  ink: '#1f1e1b', muted: '#665f54', line: '#e2dcd0', card: '#f6f3eb',
  paper: '#faf9f5', up: '#ba4d43', down: '#23815e',
  colors: ['#bf593e', '#397caf', '#23815e', '#7854ad', '#a16324', '#a94d79'],
  font: 'PingFang SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif',
  narrow: true,
}

const escape = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;',
})[char])
const safeText = value => asText(value).toWellFormed().split('').filter(char => char >= ' ' || char === '\n' || char === '\t').join('')
const number = (value, lookup) => {
  const resolved = resolve(value, lookup)
  return Number.isFinite(resolved) ? resolved : null
}
const textOf = (value, lookup) => safeText(resolve(value, lookup))
const range = values => values.filter(Number.isFinite)

function sections(view) {
  return ['stack', 'row'].includes(view.type) ? view.children.flatMap(sections) : [view]
}

// Wrap CJK and long identifiers without depending on a browser or a specific installed font.
function wrap(text, width, size, maxLines) {
  const lines = []
  let row = '', used = 0
  for (const char of text) {
    const advance = char.codePointAt(0) > 0x2e7f ? size : size * 0.62
    if (char === '\n' || (row !== '' && used + advance > width)) {
      lines.push(row)
      row = ''
      used = 0
      if (lines.length === maxLines) {
        lines[lines.length - 1] = lines.at(-1).slice(0, -1) + '…'
        return lines
      }
    }
    if (char !== '\n') { row += char; used += advance }
  }
  lines.push(row)
  return lines
}

function textBlock(text, x, y, { size = 17, width = INNER, maxLines = 4, weight = 400, color = THEME.ink } = {}) {
  if (!text) return { svg: '', height: 0 }
  const lines = wrap(safeText(text), width, size, maxLines)
  const leading = size * 1.42
  return {
    svg: '<text font-family="' + THEME.font + '" font-size="' + size + '" font-weight="' + weight + '" fill="' + color + '">' +
      lines.map((line, index) => `<tspan x="${x}" y="${y + size + leading * index}">${escape(line)}</tspan>`).join('') + '</text>',
    height: Math.ceil(lines.length * leading),
  }
}

function metric(node, lookup) {
  const label = textBlock(node.label, 18, 12, { size: 15, width: INNER - 36, color: THEME.muted })
  const value = textBlock(textOf(node.value, lookup), 18, 12 + label.height, { size: 27, width: INNER - 36, weight: 600 })
  const note = textBlock(textOf(node.caption, lookup), 18, 17 + label.height + value.height, { size: 14, width: INNER - 36, color: THEME.muted })
  const height = 28 + label.height + value.height + note.height
  return {
    height,
    svg: `<rect width="${INNER}" height="${height}" rx="12" fill="${THEME.card}" stroke="${THEME.line}"/>${label.svg}${value.svg}${note.svg}`,
  }
}

function basicOption(node, lookup) {
  const labels = node.categories.map(safeText)
  const data = node.series.map(item => ({ name: safeText(item.name), data: item.values.map(value => number(value, lookup)) }))
  if (range(data.flatMap(item => item.data)).length === 0) return undefined
  const horizontal = node.kind === 'hbar'
  const line = node.kind === 'line' || node.kind === 'area'
  const axis = { axisLabel: { fontSize: 13, color: THEME.muted, hideOverlap: true }, axisLine: { lineStyle: { color: THEME.line } } }
  const categories = { ...axis, type: 'category', boundaryGap: !line, data: labels }
  const values = { ...axis, type: 'value', scale: line, name: safeText(node.unit), nameTextStyle: { color: THEME.muted, fontSize: 13 },
    splitNumber: 4, splitLine: { lineStyle: { color: THEME.line, type: 'dashed' } } }
  if (node.kind === 'donut') {
    const slices = data[0].data.flatMap((value, i) => value > 0 ? [{ name: labels[i], value }] : [])
    return slices.length ? { series: [{ type: 'pie', radius: ['42%', '69%'], data: slices, label: { fontSize: 13 } }] } : undefined
  }
  return {
    grid: { left: horizontal ? 110 : 64, right: 22, top: data.length > 1 ? 58 : 38, bottom: 40 },
    xAxis: horizontal ? values : categories,
    yAxis: horizontal ? categories : values,
    ...(data.length > 1 ? { legend: { top: 0, textStyle: { color: THEME.muted, fontSize: 13 } } } : {}),
    series: data.map(item => ({
      ...item, type: line ? 'line' : 'bar', connectNulls: false, showSymbol: labels.length <= 10,
      lineStyle: { width: 2.5 }, ...(node.kind === 'area' ? { areaStyle: { opacity: 0.12 } } : {}),
    })),
  }
}

function chart(node, lookup, init) {
  const numbers = [
    ...(node.series ?? []).flatMap(item => item.values.map(value => number(value, lookup))),
    ...(node.xValues ?? []).map(value => number(value, lookup)),
    ...(node.links ?? []).map(edge => edge.value),
    ...(node.bars ?? []).flatMap(bar => Object.values(bar).map(Number)),
    ...(node.maxima ?? []), node.max,
  ]
  if (numbers.some(value => Math.abs(value) > 1e16)) return undefined
  let option
  if (ADVANCED_CHART_KINDS.includes(node.kind)) {
    const data = advancedChartData(node, lookup)
    if (data.drawable) option = advancedChartOption(data, THEME)
  } else option = basicOption(node, lookup)
  if (!option) return undefined
  const caption = textBlock(node.caption, 0, 0, { size: 16, color: THEME.muted })
  const height = node.kind === 'hbar' ? Math.min(640, 100 + node.categories.length * 25) : 304
  const renderer = init(null, null, { renderer: 'svg', ssr: true, width: INNER, height })
  try {
    renderer.setOption({ ...option, animation: false, tooltip: { show: false }, dataZoom: [], aria: { enabled: false },
      color: THEME.colors, textStyle: { fontFamily: THEME.font, color: THEME.ink } })
    return { height: caption.height + height, svg: `${caption.svg}<g transform="translate(0 ${caption.height})">${renderer.renderToSVGString()}</g>` }
  } finally {
    renderer.dispose()
  }
}

function table(node, lookup, lang) {
  const { columns, rows } = node
  if (columns.length === 0 || columns.length > 6) return undefined
  const width = INNER / columns.length
  const makeRow = (values, y, header) => {
    const cells = values.map((value, at) => textBlock(value, at * width + 8, y + 6, {
      size: 14, width: width - 16, maxLines: 3, weight: header ? 600 : 400,
    }))
    const height = Math.max(22, ...cells.map(cell => cell.height)) + 12
    const stripe = header ? `<rect width="${INNER}" y="${y}" height="${height}" rx="6" fill="${THEME.card}"/>` : ''
    return { height, svg: stripe + cells.map(cell => cell.svg).join('') +
      `<path d="M0 ${y + height}H${INNER}" stroke="${THEME.line}"/>` }
  }
  const caption = textBlock(node.caption, 0, 0, { size: 16, color: THEME.muted })
  let svg = caption.svg, height = caption.height
  const headers = columns.map(column => column.label)
  const preview = rows.slice(0, 12).map(row => columns.map((_, index) => textOf(row[index], lookup)))
  for (const [at, cells] of [headers, ...preview].entries()) {
    const stripe = makeRow(cells, height, at === 0)
    svg += stripe.svg
    height += stripe.height
  }
  if (rows.length > 12) {
    const note = textBlock(lang === 'zh' ? `显示前 12 行，共 ${rows.length} 行。完整表格见 ChemClaw。`
      : `Showing 12 of ${rows.length} rows. The full table is in ChemClaw.`, 0, height + 4, { size: 14, color: THEME.muted })
    svg += note.svg
    height += note.height + 4
  }
  return { svg, height }
}

export function imViewSummary({ title, view }, lang) {
  const lookup = viewScope(view)
  const missing = lang === 'zh' ? '完整视图见 ChemClaw。' : 'Open ChemClaw to see the full view.'
  const lines = sections(view).flatMap(node => {
    if (node.type === 'metric') return `• ${node.label}  ${textOf(node.value, lookup)}`
    if (node.type === 'text' || node.type === 'callout') return textOf(node.text, lookup)
    if (node.type === 'html') return node.summary
    if (node.type === 'sources') return node.items.map(item => `${item.label} ${item.url}`)
    if (node.type === 'chart') {
      const chartTitle = node.caption || (lang === 'zh' ? '图表' : 'Chart')
      const bars = node.kind === 'candlestick' ? normalizeCandles(node.bars) : undefined
      const labels = bars ? bars.map(bar => bar.date) : node.categories
      const data = bars
        ? [{ name: lang === 'zh' ? '收盘' : 'Close', values: bars.map(bar => bar.close) }] : node.series ?? []
      return [chartTitle, ...data.slice(0, 6).flatMap(item => {
        const points = item.values.flatMap((value, at) => {
          const resolved = number(value, lookup)
          return resolved === null ? [] : [`${labels[at]} ${resolved}`]
        })
        const ends = points.length > 1 ? `${points[0]} → ${points.at(-1)}` : points[0]
        return ends ? `• ${[item.name, ends, node.unit].filter(Boolean).join(' ')}` : []
      })]
    }
    if (node.type === 'table') return [
      node.caption, node.columns.map(column => column.label).join(' · '),
      ...node.rows.slice(0, 3).map(row => node.columns.map((_, at) => textOf(row[at], lookup)).join(' · ')),
    ]
    return []
  })
  const body = [title, ...lines].filter(Boolean).join('\n')
  return [body.length > 1100 ? body.slice(0, 1100).trimEnd() + '…' : body, missing].filter(Boolean).join('\n')
}

export async function renderImViewImage(card, lang, redact = text => text) {
  const checked = checkShownView(card.title, card.view)
  if (checked.error || checked.interactive) return undefined
  const nodes = sections(checked.view)
  if (!nodes.some(node => ['chart', 'metric', 'table'].includes(node.type))) return undefined
  const [charts, sharp] = await Promise.all([import('echarts'), import('sharp').then(module => module.default)])
  const heading = textBlock(checked.title, 0, 0, { size: 25, maxLines: 3, weight: 650 })
  const lookup = viewScope(checked.view)
  let content = heading.svg
  let height = heading.height ? heading.height + 14 : 0
  for (const node of nodes) {
    let part
    if (node.type === 'metric') part = metric(node, lookup)
    if (node.type === 'chart') part = chart(node, lookup, charts.init)
    if (node.type === 'table') part = table(node, lookup, lang)
    if (node.type === 'text' || node.type === 'callout') part = textBlock(textOf(node.text, lookup), 0, 0)
    if (node.type === 'html') part = textBlock(node.summary, 0, 0)
    if (node.type === 'sources') {
      const label = lang === 'zh' ? '来源' : 'Sources'
      part = textBlock(`${label} · ${node.items.map(item => item.label).join(' · ')}`, 0, 0, { size: 14, color: THEME.muted })
    }
    if (['chart', 'table'].includes(node.type) && !part) return undefined
    if (!part?.height) continue
    content += `<g transform="translate(0 ${height})">${part.svg}</g>`
    height += part.height + 12
    if (height + PAD * 2 > MAX_HEIGHT) return undefined
  }
  height += PAD * 2 - 12
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${height}">` +
    `<rect width="${WIDTH}" height="${height}" fill="${THEME.paper}"/><g transform="translate(${PAD} ${PAD})">${content}</g></svg>`
  if (redact(svg) !== svg) return undefined
  const data = await sharp(Buffer.from(svg), { density: 144, limitInputPixels: WIDTH * MAX_HEIGHT * 4 }).png().toBuffer()
  return { data, mediaType: 'image/png', name: 'chemclaw-view.png' }
}
