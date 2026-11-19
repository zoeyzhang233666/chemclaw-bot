import { createElement as h, useId } from 'react'
import { flowLevels } from '../shared/flow-view.js'
import { t } from './i18n.js'

const CARD_WIDTH = 256
const COLUMN_GAP = 36
const ROW_GAP = 66
const PADDING = 16

function wrap(text, limit) {
  const lines = []
  let row = ''
  let width = 0
  for (const character of text.trim().replace(/\s+/gu, ' ')) {
    const size = /^[\x20-\x7E]$/u.test(character) ? 0.55 : 1
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

function layout(nodes, edges) {
  const levels = flowLevels(nodes, edges)
  const rowWidth = Math.max(...levels.map(level => level.length)) * (CARD_WIDTH + COLUMN_GAP) - COLUMN_GAP
  const boxes = new Map()
  let y = PADDING
  for (const [rank, level] of levels.entries()) {
    const row = level.map(node => {
      const label = wrap(node.label, 15)
      const detail = node.detail ? wrap(node.detail, 16) : []
      return { ...node, rank, label, detail, height: Math.max(58, 22 + label.length * 20 + detail.length * 18) }
    })
    const height = Math.max(...row.map(node => node.height))
    const left = PADDING + (rowWidth - (row.length * (CARD_WIDTH + COLUMN_GAP) - COLUMN_GAP)) / 2
    for (const [i, node] of row.entries()) {
      boxes.set(node.id, { ...node, x: left + i * (CARD_WIDTH + COLUMN_GAP), y: y + (height - node.height) / 2, rowTop: y, rowBottom: y + height })
    }
    y += height + ROW_GAP
  }
  const baseWidth = rowWidth + PADDING * 2
  let width = baseWidth
  const connections = edges.map(edge => {
    const from = boxes.get(edge.from)
    const to = boxes.get(edge.to)
    const x1 = from.x + CARD_WIDTH / 2
    const x2 = to.x + CARD_WIDTH / 2
    const y1 = from.y + from.height
    const y2 = to.y - 5
    const start = from.rowBottom + 8
    const end = to.rowTop - 8
    const middle = (start + end) / 2
    if (edge.feedback) {
      width += 22
      return { ...edge, d: `M${x1} ${y1} V${start + 12} H${width} V${end - 5} H${x2} V${y2}`, x: (x1 + width) / 2, y: start + 5 }
    }
    if (to.rank - from.rank === 1) {
      return { ...edge, d: `M${x1} ${y1} V${start} C${x1} ${middle} ${x2} ${middle} ${x2} ${end} V${y2}`, x: (x1 + x2) / 2, y: middle - 7 }
    }
    width += 14
    return { ...edge, d: `M${x1} ${y1} V${start + 12} H${width} V${end - 12} H${x2} V${y2}`, x: x1, y: start + 6 }
  })
  return { width: width === baseWidth ? width : width + PADDING, height: y - ROW_GAP + PADDING, boxes: [...boxes.values()], connections }
}

export function FlowView({ node }) {
  const id = useId()
  const { width, height, boxes, connections } = layout(node.nodes, node.edges)
  const names = new Map(node.nodes.map(step => [step.id, step.label]))
  const uncertain = t('Dashed connections are uncertain')
  const hasUncertain = connections.some(edge => edge.uncertain)
  const description = node.edges.map(edge => `${names.get(edge.from)} → ${names.get(edge.to)}${edge.label ? ` (${edge.label})` : ''}`).join('. ')
  return h('figure', { className: 'bt-flow' },
    h('div', { className: 'bt-flow-scroll', tabIndex: width > 310 ? 0 : undefined },
      h('svg', { 'data-chemclaw-flow': '', width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': t('Flow diagram'), 'aria-describedby': `${id}-desc` },
        h('desc', { id: `${id}-desc` }, `${description}${hasUncertain ? `. ${uncertain}` : ''}`),
        h('defs', null, [false, true].map(dashed => h('marker', { key: Number(dashed), id: `${id}-arrow-${Number(dashed)}`, markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: 'auto' },
          h('path', { d: 'M0 0 L8 4 L0 8 Z', className: dashed ? 'bt-flow-arrow-uncertain' : 'bt-flow-arrow' })))),
        connections.map((edge, index) => h('g', { key: index, className: 'bt-flow-connection', 'data-uncertain': edge.uncertain || undefined, 'data-feedback': edge.feedback || undefined },
          h('path', { d: edge.d, markerEnd: `url(#${id}-arrow-${Number(Boolean(edge.uncertain))})` }),
          edge.label && h('text', { x: edge.x, y: edge.y, textAnchor: 'middle' }, edge.label))),
        boxes.map(step => h('g', { key: step.id, className: 'bt-flow-step', 'data-tone': step.tone ?? 'info' },
          h('title', null, [names.get(step.id), step.detail.join(' ')].filter(Boolean).join('\n')),
          h('rect', { x: step.x, y: step.y, width: CARD_WIDTH, height: step.height, rx: 12 }),
          h('text', { x: step.x + CARD_WIDTH / 2, y: step.y + 24, textAnchor: 'middle' },
            [...step.label, ...step.detail].map((line, i) => h('tspan', {
              key: i, x: step.x + CARD_WIDTH / 2, dy: i === 0 ? 0 : i < step.label.length ? 20 : 18,
              className: i < step.label.length ? 'bt-flow-label' : 'bt-flow-detail',
            }, line))))))),
    (node.caption || hasUncertain) && h('figcaption', null, [node.caption, hasUncertain && uncertain].filter(Boolean).join(' · ')))
}

export const FLOW_CSS = `
.bt-flow{min-width:0;margin:4px 0 8px}
.bt-flow-scroll{overflow-x:auto}
.bt-flow-scroll svg{display:block;margin-inline:auto;max-width:none;color:var(--bt-ink)}
.bt-flow figcaption{text-align:center;font-size:12px;line-height:1.5;color:var(--bt-ink-2);margin-top:6px}
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
.bt-flow-connection text{font-size:11px;fill:var(--bt-flow-edge);stroke:var(--bt-main);stroke-width:3;paint-order:stroke;stroke-linejoin:round}
`
