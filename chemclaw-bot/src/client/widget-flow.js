import { createElement as h, useId, useRef } from 'react'
import { flowLevels } from '../shared/flow-view.js'
import { t } from './i18n.js'
import { useWidth } from './widget-chart.js'

const CARD_WIDTH = 256
const MIN_COLUMN_WIDTH = 176
const COLUMN_GAP = 26
const ROW_GAP = 62
const PADDING = 16
const EDGE_FONT = 12
const EDGE_LINE = 15

function glyphWidth(character) {
  if (character === ' ') return 0.35
  if (/^[MWmw@%&QG]$/u.test(character)) return 0.98
  return /^[\x20-\x7E]$/u.test(character) ? 0.72 : 1.08
}

function wrap(text, limit) {
  const lines = []
  let row = ''
  let width = 0
  for (const character of text.trim().replace(/\s+/gu, ' ')) {
    const size = glyphWidth(character)
    if (width + size > limit) {
      lines.push(row.trim())
      row = ''
      width = 0
    }
    row += character
    width += size
  }
  if (row.trim()) lines.push(row.trim())
  return lines
}

function layout(nodes, edges, available) {
  const levels = flowLevels(nodes, edges)
  const maxColumns = Math.max(...levels.map(level => level.length))
  const columnsAt = width => Math.max(1, Math.min(maxColumns, Math.floor((width + COLUMN_GAP) / (MIN_COLUMN_WIDTH + COLUMN_GAP))))
  const inner = Math.max(1, available - PADDING * 2)
  const ranks = new Map(levels.flatMap((level, rank) => level.map(node => [node.id, rank])))
  const routed = maxColumns > columnsAt(inner) || edges.some(edge => edge.feedback || ranks.get(edge.to) - ranks.get(edge.from) > 1)
  const rail = routed ? Math.min(64, Math.floor(inner / 6)) : 0
  const columns = columnsAt(inner - rail)
  const cardWidth = Math.min(CARD_WIDTH, Math.floor((inner - rail - (columns - 1) * COLUMN_GAP) / columns))
  const rowWidth = columns * (cardWidth + COLUMN_GAP) - COLUMN_GAP
  const width = rowWidth + PADDING * 2 + rail
  const rows = levels.flatMap(level => Array.from({ length: Math.ceil(level.length / columns) }, (_, i) => level.slice(i * columns, (i + 1) * columns)))
  const rowOf = new Map(rows.flatMap((row, i) => row.map(node => [node.id, i])))
  const exits = rows.map(() => 8)
  const entries = rows.map(() => 8)
  const incoming = new Map()
  let lanes = 0
  const paths = edges.map(edge => {
    const fromRow = rowOf.get(edge.from)
    const toRow = rowOf.get(edge.to)
    const label = edge.label ? wrap(edge.label, Math.min(168, cardWidth - 12) / EDGE_FONT) : []
    const port = incoming.get(edge.to) ?? 0
    incoming.set(edge.to, port + 1)
    if (!edge.feedback && toRow - fromRow === 1) return { edge, label, port }
    const labelRoom = Math.max(10, label.length * EDGE_LINE + 4)
    const entry = entries[toRow] + 5
    const exit = exits[fromRow] + (edge.feedback ? labelRoom : 10)
    entries[toRow] = entry + (edge.feedback ? 4 : labelRoom)
    exits[fromRow] = exit
    return { edge, label, port, entry, exit, lane: ++lanes }
  })
  const boxes = new Map()
  let y = Math.max(PADDING, entries[0] + 4)
  for (const [rank, level] of rows.entries()) {
    const row = level.map(node => {
      const label = wrap(node.label, (cardWidth - 24) / 15)
      const detail = node.detail ? wrap(node.detail, (cardWidth - 24) / 13) : []
      return { ...node, label, detail, height: Math.max(58, 22 + label.length * 20 + detail.length * 18) }
    })
    const height = Math.max(...row.map(node => node.height))
    const left = PADDING + (rowWidth - (row.length * (cardWidth + COLUMN_GAP) - COLUMN_GAP)) / 2
    for (const [i, node] of row.entries()) {
      boxes.set(node.id, { ...node, x: left + i * (cardWidth + COLUMN_GAP), y: y + (height - node.height) / 2, rowTop: y, rowBottom: y + height })
    }
    y += height + (rank + 1 === rows.length ? 0 : Math.max(ROW_GAP, exits[rank] + entries[rank + 1] + 12))
  }
  let bottom = y
  const connections = paths.map(({ edge, label, port, entry, exit, lane }) => {
    const from = boxes.get(edge.from)
    const to = boxes.get(edge.to)
    const x1 = from.x + cardWidth / 2
    const ports = incoming.get(edge.to)
    const portGap = Math.min(14, (cardWidth - 24) / Math.max(1, ports - 1))
    const x2 = to.x + cardWidth / 2 + (port - (ports - 1) / 2) * portGap
    const y1 = from.y + from.height
    const y2 = to.y - 5
    const start = from.rowBottom + 8
    const end = to.rowTop - 8
    const middle = (start + end) / 2
    const labelSpan = Math.max(0, label.length - 1) * EDGE_LINE
    let d, anchorX, labelTop
    if (lane) {
      const railX = PADDING + rowWidth + rail * (lane / (lanes + 1))
      const exitY = from.rowBottom + exit
      const entryY = to.rowTop - entry
      d = `M${x1} ${y1} V${exitY} H${railX} V${entryY} H${x2} V${y2}`
      anchorX = edge.feedback ? x1 : x2
      labelTop = (edge.feedback ? exitY : entryY) - 4 - labelSpan
      bottom = Math.max(bottom, exitY)
    } else {
      d = `M${x1} ${y1} V${start} C${x1} ${middle} ${x2} ${middle} ${x2} ${end} V${y2}`
      anchorX = (x1 + 3 * x2) / 4
      labelTop = middle + 2 - labelSpan / 2
    }
    const half = Math.max(0, ...label.map(line => [...line].reduce((sum, character) => sum + glyphWidth(character), 0))) * EDGE_FONT / 2
    const x = Math.max(PADDING + half, Math.min(width - PADDING - half, anchorX))
    return { ...edge, d, x, y: labelTop, label }
  })
  return { width, height: bottom + PADDING, cardWidth, boxes: [...boxes.values()], connections }
}

export function FlowView({ node }) {
  const id = useId()
  const figure = useRef(null)
  const available = useWidth(figure, 320)
  const { width, height, cardWidth, boxes, connections } = layout(node.nodes, node.edges, available)
  const names = new Map(node.nodes.map(step => [step.id, step.label]))
  const uncertain = t('Dashed connections are uncertain')
  const hasUncertain = connections.some(edge => edge.uncertain)
  const description = node.edges.map(edge => `${names.get(edge.from)} → ${names.get(edge.to)}${edge.label ? ` (${edge.label})` : ''}`).join('. ')
  return h('figure', { ref: figure, className: 'bt-flow' },
      h('svg', { 'data-chemclaw-flow': '', width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': t('Flow diagram'), 'aria-describedby': `${id}-desc` },
        h('desc', { id: `${id}-desc` }, `${description}${hasUncertain ? `. ${uncertain}` : ''}`),
        h('defs', null, [false, true].map(dashed => h('marker', { key: Number(dashed), id: `${id}-arrow-${Number(dashed)}`, markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: 'auto' },
          h('path', { d: 'M0 0 L8 4 L0 8 Z', className: dashed ? 'bt-flow-arrow-uncertain' : 'bt-flow-arrow' })))),
        connections.map((edge, index) => h('g', { key: index, className: 'bt-flow-connection', 'data-uncertain': edge.uncertain || undefined, 'data-feedback': edge.feedback || undefined },
          h('path', { d: edge.d, markerEnd: `url(#${id}-arrow-${Number(Boolean(edge.uncertain))})` }),
          edge.label.length > 0 && h('text', { x: edge.x, y: edge.y, textAnchor: 'middle' },
            edge.label.map((line, i) => h('tspan', { key: i, x: edge.x, dy: i === 0 ? 0 : EDGE_LINE }, line))))),
        boxes.map(step => h('g', { key: step.id, className: 'bt-flow-step', 'data-tone': step.tone ?? 'info' },
          h('title', null, [names.get(step.id), step.detail.join(' ')].filter(Boolean).join('\n')),
          h('rect', { x: step.x, y: step.y, width: cardWidth, height: step.height, rx: 12 }),
          h('text', { x: step.x + cardWidth / 2, y: step.y + 24, textAnchor: 'middle' },
            [...step.label, ...step.detail].map((line, i) => h('tspan', {
              key: i, x: step.x + cardWidth / 2, dy: i === 0 ? 0 : i < step.label.length ? 20 : 18,
              className: i < step.label.length ? 'bt-flow-label' : 'bt-flow-detail',
            }, line)))))),
    (node.caption || hasUncertain) && h('figcaption', null, [node.caption, hasUncertain && uncertain].filter(Boolean).join(' · ')))
}

export const FLOW_CSS = `
.bt-flow{width:100%;min-width:0;margin:4px 0 8px}
.bt-flow svg{display:block;max-width:100%;height:auto;margin-inline:auto;color:var(--bt-ink)}
.bt-flow figcaption{text-align:center;font-size:12px;line-height:1.5;color:var(--bt-ink-2);margin-top:6px;overflow-wrap:anywhere}
.bt-flow-step{--bt-flow-tone:var(--bt-accent)}
.bt-flow-step[data-tone=good]{--bt-flow-tone:var(--bt-green)}
.bt-flow-step[data-tone=warn]{--bt-flow-tone:var(--bt-star)}
.bt-flow-step[data-tone=bad]{--bt-flow-tone:var(--bt-danger)}
.bt-flow-step rect{fill:color-mix(in srgb,var(--bt-flow-tone) 10%,var(--bt-main));stroke:var(--bt-flow-tone);stroke-width:1.2}
.bt-flow-step text{fill:var(--bt-ink);font-family:inherit}
.bt-flow-label{font-size:15px;font-weight:650}
.bt-flow-detail{font-size:13px;fill:var(--bt-ink-2)}
.bt-flow-connection{--bt-flow-edge:var(--bt-ink-3)}
.bt-flow-connection[data-uncertain]{--bt-flow-edge:var(--bt-danger)}
.bt-flow-arrow{fill:var(--bt-ink-3)}
.bt-flow-arrow-uncertain{fill:var(--bt-danger)}
.bt-flow-connection path{fill:none;stroke:var(--bt-flow-edge);stroke-width:1.25}
.bt-flow-connection[data-uncertain] path{stroke-dasharray:5 4}
.bt-flow-connection text{font-size:${EDGE_FONT}px;fill:var(--bt-ink-2);stroke:var(--bt-main);stroke-width:3;paint-order:stroke;stroke-linejoin:round}
.bt-flow-connection[data-uncertain] text{fill:var(--bt-danger)}
`
