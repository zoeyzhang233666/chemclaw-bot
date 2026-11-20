import { createElement as h, useId, useRef } from 'react'
import { flowLevels } from '../shared/flow-view.js'
import { roundedOrthogonalPath } from './genui-diagram-layout.js'
import { t } from './i18n.js'
import { useWidth } from './widget-chart.js'

const CARD_WIDTH = 256
const MIN_COLUMN_WIDTH = 176
const COLUMN_GAP = 26
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

function orderLevels(levels, edges, ranks) {
  const nearby = edges.filter(edge => ranks.get(edge.to) === ranks.get(edge.from) + 1)
  const positions = new Map()
  const index = level => level.forEach((node, i) => positions.set(node.id, (i + .5) / level.length))
  const score = () => {
    let cost = 0
    for (const [i, a] of nearby.entries()) {
      const from = positions.get(a.from)
      const to = positions.get(a.to)
      cost += Math.abs(from - to)
      for (const b of nearby.slice(i + 1)) {
        if (ranks.get(a.from) === ranks.get(b.from) && (from - positions.get(b.from)) * (to - positions.get(b.to)) < 0) cost += 4
      }
    }
    return cost
  }
  levels.forEach(index)
  let best = score()
  for (let pass = 0; pass < 4; pass += 1) {
    const sweep = pass % 2 === 0 ? levels : [...levels].reverse()
    for (const level of sweep) for (let i = 1; i < level.length; i += 1) {
      const left = level[i - 1]
      const right = level[i]
      level[i - 1] = right
      level[i] = left
      index(level)
      const cost = score()
      if (cost < best) best = cost
      else {
        level[i - 1] = left
        level[i] = right
        index(level)
      }
    }
  }
}

function bundles(routes) {
  const shared = []
  const remaining = new Set(routes)
  for (const side of ['from', 'to']) {
    const groups = new Map()
    for (const route of remaining) {
      if (route.long || route.edge.label) continue
      const key = `${route.edge[side]}:${Boolean(route.edge.uncertain)}`
      const group = groups.get(key) ?? []
      group.push(route)
      groups.set(key, group)
    }
    for (const group of groups.values()) {
      if (group.length < 2) continue
      shared.push({ group, split: side === 'from' })
      for (const route of group) remaining.delete(route)
    }
  }
  return { shared, remaining }
}

function placeTrack(tracks, left, right, height) {
  let track = tracks.find(row => row.uses.every(span => left >= span.right + 10 || right <= span.left - 10))
  if (!track) {
    track = { uses: [], height: 0, y: 0 }
    tracks.push(track)
  }
  track.uses.push({ left, right })
  track.height = Math.max(track.height, height)
  return track
}

const connector = (...pairs) => roundedOrthogonalPath(pairs.map(([x, y]) => ({ x, y })))
const measure = line => [...line].reduce((sum, character) => sum + glyphWidth(character), 0) * EDGE_FONT

export function flowLayout(nodes, edges, available) {
  const levels = flowLevels(nodes, edges)
  const ranks = new Map(levels.flatMap((level, rank) => level.map(node => [node.id, rank])))
  orderLevels(levels, edges, ranks)
  const maxColumns = Math.max(...levels.map(level => level.length))
  const inner = Math.max(1, available - PADDING * 2)
  const columnsAt = width => Math.max(1, Math.min(maxColumns, Math.floor((width + COLUMN_GAP) / (MIN_COLUMN_WIDTH + COLUMN_GAP))))
  const needsRails = maxColumns > columnsAt(inner) || edges.some(edge => edge.feedback || ranks.get(edge.to) - ranks.get(edge.from) > 1)
  const railWidth = needsRails ? Math.min(52, Math.floor(inner / 8)) : 0
  const columns = columnsAt(inner - railWidth * 2)
  const cardWidth = Math.min(CARD_WIDTH, Math.floor((inner - railWidth * 2 - (columns - 1) * COLUMN_GAP) / columns))
  const rowWidth = columns * (cardWidth + COLUMN_GAP) - COLUMN_GAP
  const width = rowWidth + (PADDING + railWidth) * 2
  const rows = levels.flatMap(level => Array.from({ length: Math.ceil(level.length / columns) }, (_, i) => level.slice(i * columns, (i + 1) * columns)))
  const boxes = new Map()
  const lanes = Array.from({ length: rows.length + 1 }, () => [])
  for (const [row, items] of rows.entries()) {
    const left = (width - (items.length * (cardWidth + COLUMN_GAP) - COLUMN_GAP)) / 2
    for (const [i, item] of items.entries()) {
      const label = wrap(item.label, (cardWidth - 24) / 15)
      const detail = item.detail ? wrap(item.detail, (cardWidth - 24) / 13) : []
      const stage = item.stage ? wrap(item.stage, (cardWidth - 24) / 11) : []
      const textHeight = stage.length * 16 + label.length * 20 + detail.length * 18
      const x = left + i * (cardWidth + COLUMN_GAP)
      boxes.set(item.id, { ...item, label, detail, stage, textHeight, x, row, rank: ranks.get(item.id), center: x + cardWidth / 2 })
    }
  }
  const routes = edges.map(edge => {
    const from = boxes.get(edge.from)
    const to = boxes.get(edge.to)
    const label = edge.label ? wrap(edge.label, Math.min(174, cardWidth - 12) / EDGE_FONT) : []
    return { edge, from, to, label, long: to.row !== from.row + 1 || edge.feedback, x1: from.center, x2: to.center }
  })
  const { shared, remaining } = bundles(routes)
  // Use the same port for an entire trunk and independent ports for unrelated edges.
  for (const [side, other, key] of [['from', 'to', 'x1'], ['to', 'from', 'x2']]) {
    for (const box of boxes.values()) {
      const touching = [...remaining].filter(route => route[side] === box).map(route => [route])
      for (const { group, split } of shared) {
        if ((split ? 'from' : 'to') === side) {
          if (group[0][side] === box) touching.push(group)
        } else for (const route of group) if (route[side] === box) touching.push([route])
      }
      const peer = group => group.reduce((sum, route) => sum + route[other].center, 0) / group.length
      touching.sort((a, b) => peer(a) - peer(b))
      const gap = Math.min(15, (cardWidth - 28) / Math.max(1, touching.length - 1))
      for (const [i, group] of touching.entries()) {
        for (const route of group) route[key] = box.center + (i - (touching.length - 1) / 2) * gap
      }
    }
  }

  const sideRails = [[], []]
  const track = (gap, x1, x2, label) => {
    const labelWidth = label.length ? Math.ceil(Math.max(...label.map(measure))) + 14 : 0
    const labelHeight = label.length ? label.length * EDGE_LINE + 6 : 0
    const midpoint = Math.abs(x1 - x2) >= labelWidth + 14 ? (x1 + x2) / 2 : x2 + 8 + labelWidth / 2
    const x = Math.max(PADDING + labelWidth / 2, Math.min(width - PADDING - labelWidth / 2, midpoint))
    const bounds = labelWidth ? [x - labelWidth / 2, x + labelWidth / 2] : []
    const lane = placeTrack(lanes[gap], Math.min(x1, x2, ...bounds), Math.max(x1, x2, ...bounds), Math.max(12, labelHeight + 4))
    return { lane, x, labelWidth, labelHeight }
  }
  for (const route of [...remaining].sort((a, b) => Number(a.long) - Number(b.long))) {
    const { from, to, x1, x2, label } = route
    if (!route.long) {
      route.entry = track(to.row, x1, x2, label)
      continue
    }
    const first = Math.min(from.row + 1, to.row)
    const last = Math.max(from.row + 1, to.row)
    const options = sideRails.map((rail, side) => {
      const reusable = rail.findIndex(uses => uses.every(span => last < span.first || first > span.last))
      const index = reusable < 0 ? rail.length : reusable
      return { rail, side, index, cost: (side === 0 ? x1 + x2 : width * 2 - x1 - x2) + index * 44 }
    })
    const { rail, side, index } = options[0].cost <= options[1].cost ? options[0] : options[1]
    const uses = rail[index] ??= []
    uses.push({ first, last })
    route.rail = { side, index }
  }
  for (const route of remaining) {
    if (!route.long) continue
    const { side, index } = route.rail
    const inset = railWidth * (sideRails[side].length - index) / (sideRails[side].length + 1)
    const railX = side === 0 ? PADDING + inset : width - PADDING - inset
    route.railX = railX
    route.exit = track(route.from.row + 1, route.x1, railX, [])
    route.entry = track(route.to.row, railX, route.x2, route.label)
  }
  for (const bundle of shared) {
    const { group } = bundle
    const xs = group.flatMap(route => [route.x1, route.x2])
    bundle.left = Math.min(...xs)
    bundle.right = Math.max(...xs)
    bundle.track = track(group[0].to.row, bundle.left, bundle.right, [])
  }

  let y = PADDING
  for (const [i, tracks] of lanes.entries()) {
    if (tracks.length) {
      y += 15
      for (const lane of tracks) {
        lane.y = y + lane.height / 2
        y += lane.height
      }
      y += 15
    } else if (i > 0 && i < rows.length) y += 28
    if (i === rows.length) break
    const row = rows[i].map(item => boxes.get(item.id))
    const height = Math.max(58, ...row.map(box => box.textHeight + 24))
    for (const box of row) Object.assign(box, { y, height })
    y += height
  }
  const start = route => [route.x1, route.from.y + route.from.height]
  const end = route => [route.x2, route.to.y - 4]
  const connections = [...remaining].map(route => {
    const { entry, exit, railX, x1, x2 } = route
    const middle = entry.lane.y
    const points = exit ? [[x1, exit.lane.y], [railX, exit.lane.y], [railX, middle]] : [[x1, middle]]
    const d = connector(start(route), ...points, [x2, middle], end(route))
    return { ...route.edge, d, arrow: true, label: route.label, x: entry.x, y: middle, labelWidth: entry.labelWidth, labelHeight: entry.labelHeight }
  })
  for (const { group, split, left, right, track: row } of shared) {
    const first = group[0]
    const edge = first.edge
    const middle = row.lane.y
    const bus = connector([left, middle], [right, middle])
    const trunk = split ? connector(start(first), [first.x1, middle]) : connector([first.x2, middle], end(first))
    if (split) connections.push({ ...edge, d: `${trunk} ${bus}`, shared: true, label: [] })
    else {
      // Marker-end is applied to each subpath. Keep the bus and its one arrow separate.
      connections.push({ ...edge, d: bus, shared: true, label: [] }, { ...edge, d: trunk, arrow: true, label: [] })
    }
    for (const route of group) connections.push({ ...route.edge, label: [], arrow: split,
      d: split ? connector([route.x2, middle], end(route)) : connector(start(route), [route.x1, middle]) })
  }
  return { width, height: y + PADDING, cardWidth, boxes: [...boxes.values()], connections }
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
          h('path', { d: 'M1 1 L7 4 L1 7', className: dashed ? 'bt-flow-arrow-uncertain' : 'bt-flow-arrow' })))),
        connections.map((edge, index) => h('g', { key: index, className: 'bt-flow-connection', 'data-uncertain': edge.uncertain || undefined, 'data-feedback': edge.feedback || undefined, 'data-shared': edge.shared || undefined },
          h('path', { d: edge.d, markerEnd: edge.arrow ? `url(#${id}-arrow-${Number(Boolean(edge.uncertain))})` : undefined }))),
        connections.filter(edge => edge.label.length).map((edge, index) => h('g', { key: index, className: 'bt-flow-edge-label', 'data-uncertain': edge.uncertain || undefined },
          h('rect', { x: edge.x - edge.labelWidth / 2, y: edge.y - edge.labelHeight / 2, width: edge.labelWidth, height: edge.labelHeight, rx: 6 }),
          h('text', { x: edge.x, y: edge.y - (edge.label.length - 1) * EDGE_LINE / 2, textAnchor: 'middle', dominantBaseline: 'central' },
            edge.label.map((line, i) => h('tspan', { key: i, x: edge.x, dy: i === 0 ? 0 : EDGE_LINE }, line))))),
        boxes.map(step => h('g', { key: step.id, className: 'bt-flow-step', 'data-tone': step.tone, 'data-input': step.rank === 0 || undefined },
          h('title', null, [names.get(step.id), step.detail.join(' ')].filter(Boolean).join('\n')),
          h('rect', { x: step.x, y: step.y, width: cardWidth, height: step.height, rx: 12 }),
          h('text', { x: step.x + cardWidth / 2, y: step.y + (step.height - step.textHeight) / 2 + (step.stage.length ? 11 : 15), textAnchor: 'middle' },
            [...step.stage, ...step.label, ...step.detail].map((line, i) => h('tspan', {
              key: i, x: step.x + cardWidth / 2, dy: i === 0 ? 0 : i <= step.stage.length ? 16 : i < step.stage.length + step.label.length ? 20 : 18,
              className: i < step.stage.length ? 'bt-flow-stage' : i < step.stage.length + step.label.length ? 'bt-flow-label' : 'bt-flow-detail',
            }, line)))))),
    (node.caption || hasUncertain) && h('figcaption', null, [node.caption, hasUncertain && uncertain].filter(Boolean).join(' · ')))
}

export const FLOW_CSS = `
.bt-flow{width:100%;min-width:0;margin:4px 0 8px}
.bt-flow svg{display:block;max-width:100%;height:auto;margin-inline:auto;color:var(--bt-ink);background:color-mix(in srgb,var(--bt-main) 96%,var(--bt-ink));border-radius:12px;box-shadow:inset 0 0 0 1px var(--bt-line)}
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
.bt-flow-connection,.bt-flow-arrow{--bt-flow-edge:color-mix(in srgb,var(--bt-ink) 61%,var(--bt-main))}
.bt-flow-connection[data-uncertain],.bt-flow-arrow-uncertain{--bt-flow-edge:var(--bt-danger)}
.bt-flow-arrow,.bt-flow-arrow-uncertain,.bt-flow-connection path{fill:none;stroke:var(--bt-flow-edge);stroke-width:1.45;stroke-linecap:round;stroke-linejoin:round}
.bt-flow-connection[data-uncertain] path{stroke-dasharray:5 4}
.bt-flow-edge-label rect{fill:var(--bt-main);stroke:var(--bt-line);stroke-width:.75}
.bt-flow-edge-label text{font-size:${EDGE_FONT}px;font-weight:540;fill:var(--bt-ink)}
.bt-flow-edge-label[data-uncertain] text{fill:var(--bt-danger)}
`
