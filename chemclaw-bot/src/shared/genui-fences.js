const UI_LANGUAGE = /^dsh-ui(?:[>`"'.,;:)\]】」』]+)?[ \t]*$/iu
const OPEN = /^ {0,3}(`{3,}|~{3,})([^\r\n]*)(?:\r?\n|$)/gmu
const SVG = /^\s*<svg\b[\s\S]*<\/svg>\s*$/iu

// Match the protocol outside ordinary Markdown code fences, including an
// unclosed fence while the model is still streaming it.
export function* genuiFences(text) {
  const openings = new RegExp(OPEN)
  for (let opening; (opening = openings.exec(text));) {
    const ticks = opening[1]
    const closing = new RegExp(`^ {0,3}${ticks[0]}{${ticks.length},}[ \\t]*(?:\\r?$)`, 'gmu')
    const start = openings.lastIndex
    closing.lastIndex = start
    const match = closing.exec(text)
    const end = match?.index ?? text.length
    if (UI_LANGUAGE.test(opening[2].trimStart())) yield { start: opening.index, body: text.slice(start, end).trimEnd(), end: match ? closing.lastIndex : end, closed: Boolean(match) }
    openings.lastIndex = match ? closing.lastIndex + 1 : text.length + 1
  }
}

const isSvg = code => typeof code === 'string' && code.length <= 12_000 && SVG.test(code)

export function repairGenuiSvg(body) {
  if (!body.includes('"svg"')) return undefined
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
    for (const key of ['items', 'children', 'tabs']) {
      if (Array.isArray(node[key])) for (const child of node[key]) repair(child, depth + 1)
    }
  }
  repair(spec)
  if (!changed) return undefined
  return JSON.stringify(spec.type === 'svg' && !Array.isArray(spec.items) ? { items: [spec] } : spec)
}

export const genuiMarkdown = body => '```dsh-ui\n' + body + '\n```'

export function repairGenuiSvgFences(text) {
  if (!text.includes('"svg"')) return text
  let out = ''
  let offset = 0
  for (const fence of genuiFences(text)) {
    if (!fence.closed) continue
    const repaired = repairGenuiSvg(fence.body)
    if (repaired === undefined) continue
    out += text.slice(offset, fence.start) + genuiMarkdown(repaired)
    offset = fence.end
  }
  return offset === 0 ? text : out + text.slice(offset)
}
