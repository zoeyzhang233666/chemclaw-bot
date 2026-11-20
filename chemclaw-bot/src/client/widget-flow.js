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

function orderLevels(levels, edges) {
  const incoming = new Map()
  for (const edge of edges) {
    if (edge.feedback) continue
    const sources = incoming.get(edge.to) ?? []
    sources.push(edge.from)
    incoming.set(edge.to, sources)
  }
  const positions = new Map()
  for (const level of levels) {
    const score = node => {
      const sources = incoming.get(node.id)
      return sources ? sources.reduce((sum, id) => sum + positions.get(id), 0) / sources.length : .5
    }
    level.sort((a, b) => score(a) - score(b))
    for (const [index, node] of level.entries()) positions.set(node.id, (index + .5) / level.length)
  }
  return levels
}

function joinAdjacentConnections(connections) {
  const consumed = new Set()
  const shared = []
  const intervals = new Map()
  for (const side of ['from', 'to']) {
    const lists = new Map()
    for (const edge of connections) {
      if (edge.lane || edge.label.length || consumed.has(edge)) continue
      const key = [edge[side], Boolean(edge.uncertain)].join(':')
      const group = lists.get(key) ?? []
      group.push(edge)
      lists.set(key, group)
    }
    for (const group of lists.values()) {
      if (group.length < 2) continue
      const first = group[0]
      const split = side === 'from'
      // Bundles can share a corridor, but their horizontal lines must not
      // accidentally connect separate branches to one another.
      const gap = first.start
      const used = intervals.get(gap) ?? []
      const xs = group.map(edge => split ? edge.x2 : edge.x1).concat(split ? first.x1 : first.centerX)
      const left = Math.min(...xs)
      const right = Math.max(...xs)
      const band = (.5 * (first.start + first.end))
      const y = [0, -10, 10, -20, 20].map(offset => band + offset)
        .find(candidate => candidate > first.start && candidate < first.end
          && !used.some(bus => bus.y === candidate && bus.right >= left && right >= bus.left))
      if (y === undefined) continue
      used.push({ y, left, right })
      intervals.set(gap, used)
      const feed = split ? `M${first.x1} ${first.y1} V${y}` : ''
      const end = split ? '' : `M${first.centerX} ${y} V${first.y2}`
      shared.push({ ...first, shared: true, arrow: !split, label: [], d: `${feed} M${left} ${y} H${right} ${end}` })
      for (const edge of group) {
        consumed.add(edge)
        shared.push({ ...edge, arrow: split,
          d: split ? `M${edge.x2} ${y} V${edge.y2}` : `M${edge.x1} ${edge.y1} V${y}` })
      }
    }
  }
  return connections.filter(edge => !consumed.has(edge)).concat(shared)
}

export function flowLayout(nodes, edges, available) {
  const levels = orderLevels(flowLevels(nodes, edges), edges)
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
      const stage = node.stage ? wrap(node.stage, (cardWidth - 24) / 11) : []
      return { ...node, label, detail, stage, height: Math.max(58, 22 + stage.length * 16 + label.length * 20 + detail.length * 18) }
    })
    const height = Math.max(...row.map(node => node.height))
    const left = PADDING + (rowWidth - (row.length * (cardWidth + COLUMN_GAP) - COLUMN_GAP)) / 2
    for (const [i, node] of row.entries()) {
      boxes.set(node.id, { ...node, rank: ranks.get(node.id), x: left + i * (cardWidth + COLUMN_GAP), y: y + (height - node.height) / 2, rowTop: y, rowBottom: y + height })
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
    return { ...edge, d, x, y: labelTop, label, lane, start, end, x1, x2, y1, y2, centerX: to.x + cardWidth / 2, arrow: true }
  })
  return { width, height: bottom + PADDING, cardWidth, boxes: [...boxes.values()], connections: joinAdjacentConnections(connections) }
}

export function FlowView({ node }) {
  const id = useId()
  const figure = useRef(null)
  const available = useWidth(figure, 320)
  const { width, height, cardWidth, boxes, connections } = flowLayout(node.nodes, node.edges, available)
  const names = new Map(node.nodes.map(step => [step.id, step.label]))
  const uncertain = t('Dashed connections are uncertain')
  const hasUncertain = connections.some(edge => edge.uncertain)
  const description = node.edges.map(edge => `${names.get(edge.from)} → ${names.get(edge.to)}${edge.label ? ` (${edge.label})` : ''}`).join('. ')
  return h('figure', { ref: figure, className: 'bt-flow', 'data-chemclaw-flow-figure': '' },
      h('svg', { 'data-chemclaw-flow': '', width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': t('Flow diagram'), 'aria-describedby': `${id}-desc` },
        h('title', null, node.caption || t('Flow diagram')),
        h('desc', { id: `${id}-desc` }, `${description}${hasUncertain ? `. ${uncertain}` : ''}`),
        h('defs', null, [false, true].map(dashed => h('marker', { key: Number(dashed), id: `${id}-arrow-${Number(dashed)}`, markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: 'auto' },
          h('path', { d: 'M0 0 L8 4 L0 8 Z', className: dashed ? 'bt-flow-arrow-uncertain' : 'bt-flow-arrow' })))),
        connections.map((edge, index) => h('g', { key: index, className: 'bt-flow-connection', 'data-uncertain': edge.uncertain || undefined, 'data-feedback': edge.feedback || undefined, 'data-shared': edge.shared || undefined },
          h('path', { d: edge.d, markerEnd: edge.arrow ? `url(#${id}-arrow-${Number(Boolean(edge.uncertain))})` : undefined }),
          edge.label.length > 0 && h('text', { x: edge.x, y: edge.y, textAnchor: 'middle' },
            edge.label.map((line, i) => h('tspan', { key: i, x: edge.x, dy: i === 0 ? 0 : EDGE_LINE }, line))))),
        boxes.map(step => h('g', { key: step.id, className: 'bt-flow-step', 'data-tone': step.tone, 'data-input': step.rank === 0 || undefined },
          h('title', null, [names.get(step.id), step.detail.join(' ')].filter(Boolean).join('\n')),
          h('rect', { x: step.x, y: step.y, width: cardWidth, height: step.height, rx: 12 }),
          h('text', { x: step.x + cardWidth / 2, y: step.y + 24, textAnchor: 'middle' },
            [...step.stage, ...step.label, ...step.detail].map((line, i) => h('tspan', {
              key: i, x: step.x + cardWidth / 2, dy: i === 0 ? 0 : i <= step.stage.length ? 16 : i < step.stage.length + step.label.length ? 20 : 18,
              className: i < step.stage.length ? 'bt-flow-stage' : i < step.stage.length + step.label.length ? 'bt-flow-label' : 'bt-flow-detail',
            }, line)))))),
    (node.caption || hasUncertain) && h('figcaption', null, [node.caption, hasUncertain && uncertain].filter(Boolean).join(' · ')))
}

export const FLOW_CSS = `
.bt-flow{width:100%;min-width:0;margin:4px 0 8px}
.bt-flow svg{display:block;max-width:100%;height:auto;margin-inline:auto;color:var(--bt-ink)}
.bt-flow figcaption{text-align:center;font-size:12px;line-height:1.5;color:var(--bt-ink-2);margin-top:6px;overflow-wrap:anywhere}
.bt-flow-step{--bt-flow-tone:var(--bt-ink-blue)}
.bt-flow-step[data-input],.bt-flow-step[data-tone=info]{--bt-flow-tone:var(--bt-accent)}
.bt-flow-step[data-tone=good]{--bt-flow-tone:var(--bt-green)}
.bt-flow-step[data-tone=warn]{--bt-flow-tone:var(--bt-star)}
.bt-flow-step[data-tone=bad]{--bt-flow-tone:var(--bt-danger)}
.bt-flow-step rect{fill:color-mix(in srgb,var(--bt-flow-tone) 8%,var(--bt-main));stroke:color-mix(in srgb,var(--bt-flow-tone) 56%,var(--bt-line));stroke-width:1.1}
.bt-flow-step text{fill:var(--bt-ink);font-family:inherit}
.bt-flow-label{font-size:15px;font-weight:650}
.bt-flow-stage{font-size:11px;fill:var(--bt-flow-tone);font-weight:600}
.bt-flow-detail{font-size:13px;fill:var(--bt-ink-2)}
.bt-flow-connection{--bt-flow-edge:var(--bt-ink-3)}
.bt-flow-connection[data-uncertain]{--bt-flow-edge:var(--bt-danger)}
.bt-flow-arrow{fill:var(--bt-ink-3)}
.bt-flow-arrow-uncertain{fill:var(--bt-danger)}
.bt-flow-connection path{fill:none;stroke:var(--bt-flow-edge);stroke-width:1.25;stroke-linecap:round;stroke-linejoin:round}
.bt-flow-connection[data-uncertain] path{stroke-dasharray:5 4}
.bt-flow-connection text{font-size:${EDGE_FONT}px;fill:var(--bt-ink-2);stroke:var(--bt-main);stroke-width:3;paint-order:stroke;stroke-linejoin:round}
.bt-flow-connection[data-uncertain] text{fill:var(--bt-danger)}
`
