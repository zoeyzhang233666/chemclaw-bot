const UI_LANGUAGE = /^dsh-ui(?:[>`"'.,;:)\]】」』]+)?[ \t]*$/iu
const OPEN = /^ {0,3}(`{3,}|~{3,})([^\r\n]*)(?:\r?\n|$)/gmu
const SVG = /^\s*<svg\b[\s\S]*<\/svg>\s*$/iu
const COORDINATE_DIAGRAMS = new Set(['architecture', 'it-state', 'high-level', 'process', 'medallion', 'data-flow', 'dp-integration'])
const gridSize = value => Math.ceil(value / 4) * 4

function repairDiagramLayout(node) {
  if (node.type !== 'diagram' || !COORDINATE_DIAGRAMS.has(node.kind) || !Array.isArray(node.nodes)
    || node.nodes.length < 2 || !node.nodes.every(item => item && typeof item.label === 'string')) return false
  const nodes = node.nodes
  const validBox = box => ['x', 'y', 'w', 'h'].every(key => Number.isFinite(box[key]) && box[key] % 4 === 0)
    && box.x >= 8 && box.y >= 8 && box.w >= 64 && box.h >= 40
  const collide = (a, b) => a.x < b.x + b.w + 8 && b.x < a.x + a.w + 8 && a.y < b.y + b.h + 8 && b.y < a.y + a.h + 8
  if (nodes.every((box, index) => validBox(box) && !nodes.slice(0, index).some(peer => collide(box, peer)))) return false

  // Keep IDs, order, labels and all original edges. Invalid coordinates and
  // zone rectangles cannot be reused together with these boxes.
  const width = gridSize(Math.min(360, Math.max(144, ...nodes.map(item => Math.max(item.label.length * 11, (item.sub?.length ?? 0) * 9) + 24))))
  const columns = Math.min(3, Math.ceil(Math.sqrt(nodes.length)))
  node.nodes = nodes.map((item, index) => ({
    ...item, x: 32 + index % columns * (width + 56), y: 32 + Math.floor(index / columns) * 112, w: width, h: 64,
  }))
  delete node.zones
  return true
}

// Match the protocol outside ordinary Markdown code fences, including an
// unclosed fence while the model is still streaming it.
function* markdownFences(text) {
  const openings = new RegExp(OPEN)
  for (let opening; (opening = openings.exec(text));) {
    const ticks = opening[1]
    const closing = new RegExp(`^ {0,3}${ticks[0]}{${ticks.length},}[ \\t]*(?:\\r?$)`, 'gmu')
    const start = openings.lastIndex
    closing.lastIndex = start
    const match = closing.exec(text)
    const end = match?.index ?? text.length
    yield { language: opening[2].trimStart(), start: opening.index, body: text.slice(start, end).trimEnd(),
      end: match ? closing.lastIndex : end, closed: Boolean(match) }
    openings.lastIndex = match ? closing.lastIndex + 1 : text.length + 1
  }
}

export function* genuiFences(text) {
  for (const { language, ...fence } of markdownFences(text)) {
    if (UI_LANGUAGE.test(language)) yield fence
  }
}

export function stripGraphicControlLines(text) {
  if (!text.includes('chatml_chart_demo')) return text
  const clean = value => value.replace(/^[ \t]*<\/?chatml_chart_demo>[ \t]*(?:\r?\n|$)/gmu, '')
  let out = ''
  let offset = 0
  for (const fence of markdownFences(text)) {
    out += clean(text.slice(offset, fence.start)) + text.slice(fence.start, fence.end)
    offset = fence.end
  }
  return out + clean(text.slice(offset))
}

const isSvg = code => typeof code === 'string' && code.length <= 12_000 && SVG.test(code)

export function repairGenuiGraphic(body) {
  if (!/"(?:svg|diagram|flow)"/u.test(body)) return undefined
  let spec
  try { spec = JSON.parse(body) } catch { return undefined }
  let changed = false
  const repair = (node, depth = 0) => {
    if (node === null || typeof node !== 'object' || depth > 12) return
    if (node.type === 'svg' && isSvg(node.svg) && (node.code === undefined || isSvg(node.code))) {
      node.code ??= node.svg
      delete node.svg
      changed = true
    }
    if (node.type === 'flow' && Array.isArray(node.nodes) && Array.isArray(node.edges)
      && node.nodes.length && node.nodes.every(item => typeof item?.id === 'string' && typeof item?.label === 'string')) {
      const ids = new Set(node.nodes.map(item => item.id))
      if (ids.size === node.nodes.length && node.edges.every(edge => ids.has(edge?.from) && ids.has(edge?.to))) {
        node.type = 'diagram'
        node.kind = node.nodes.length > 4 ? 'architecture' : 'flowchart'
        node.title ??= node.caption
        delete node.caption
        node.nodes = node.nodes.map(item => ({
          id: item.id, label: item.label, description: item.description ?? item.detail, sub: item.sub,
        }))
        node.edges = node.edges.map(edge => ({
          from: edge.from, to: edge.to, label: edge.label, kind: edge.uncertain || edge.feedback ? 'dashed' : undefined,
        }))
        changed = true
      }
    }
    if (node.type === 'diagram' && node.kind === undefined && Array.isArray(node.nodes)) {
      node.kind = node.nodes.length > 4 || node.nodes.some(item => item?.x !== undefined) ? 'architecture' : 'flowchart'
      changed = true
    }
    if (repairDiagramLayout(node)) changed = true
    for (const key of ['items', 'children', 'tabs']) {
      if (Array.isArray(node[key])) for (const child of node[key]) repair(child, depth + 1)
    }
  }
  repair(spec)
  if (!changed) return undefined
  return JSON.stringify(['svg', 'diagram'].includes(spec.type) && !Array.isArray(spec.items) ? { items: [spec] } : spec)
}

export const genuiMarkdown = body => '```dsh-ui\n' + body + '\n```'

export function repairGenuiGraphicFences(text) {
  if (!/"(?:svg|diagram|flow)"/u.test(text)) return text
  let out = ''
  let offset = 0
  for (const fence of genuiFences(text)) {
    if (!fence.closed) continue
    const repaired = repairGenuiGraphic(fence.body)
    if (repaired === undefined) continue
    out += text.slice(offset, fence.start) + genuiMarkdown(repaired)
    offset = fence.end
  }
  return offset === 0 ? text : out + text.slice(offset)
}
