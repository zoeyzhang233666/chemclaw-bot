const SVG_NS = 'http://www.w3.org/2000/svg'
const PATH_NUMBER = '-?(?:\\d+(?:\\.\\d+)?|\\.\\d+)'
const PATH_START = new RegExp(`^M\\s+(${PATH_NUMBER})\\s+(${PATH_NUMBER})`, 'u')
const PATH_BEND = new RegExp(`Q\\s+(${PATH_NUMBER})\\s+(${PATH_NUMBER})\\s+${PATH_NUMBER}\\s+${PATH_NUMBER}`, 'gu')
const PATH_END = new RegExp(`(?:H\\s+(${PATH_NUMBER})|V\\s+(${PATH_NUMBER}))$`, 'u')
const connectorPoint = (x, y) => ({ x: Number(x), y: Number(y) })
const svgCoordinates = ({ x, y }) => `${x} ${y}`
const orthogonalLength = (a, b) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y)
const alongConnector = (from, to, length) => ({
  x: from.x + Math.sign(to.x - from.x) * length,
  y: from.y + Math.sign(to.y - from.y) * length,
})

export function roundDiagramConnector(path) {
  // GenUI emits two quadratic elbows for matching ports. Their control
  // points identify the original right angles even when the curve overshoots.
  const start = PATH_START.exec(path)
  const end = PATH_END.exec(path)
  const corners = [...path.matchAll(PATH_BEND)].map(match => connectorPoint(match[1], match[2]))
  if (!start || !end || corners.length !== 2) return path
  const first = connectorPoint(start[1], start[2])
  const last = connectorPoint(end[1] ?? corners[1].x, end[2] ?? corners[1].y)
  const points = [first, ...corners, last].filter((value, index, all) => index === 0 || orthogonalLength(value, all[index - 1]) > 0)
  if (points.some((value, index) => index && value.x !== points[index - 1].x && value.y !== points[index - 1].y)) return path
  let next = `M ${svgCoordinates(first)}`
  for (let index = 1; index < points.length - 1; index += 1) {
    const before = points[index - 1]
    const corner = points[index]
    const after = points[index + 1]
    if ((before.x === corner.x) === (corner.x === after.x)) continue
    const radius = Math.min(8, orthogonalLength(before, corner) / 2, orthogonalLength(corner, after) / 2)
    next += ` L ${svgCoordinates(alongConnector(corner, before, radius))} Q ${svgCoordinates(corner)} ${svgCoordinates(alongConnector(corner, after, radius))}`
  }
  return `${next} L ${svgCoordinates(last)}`
}

const boxesIntersect = (a, b, gap = 0) => a.x < b.x + b.width + gap && a.x + a.width + gap > b.x
  && a.y < b.y + b.height + gap && a.y + a.height + gap > b.y
const insideCanvas = (box, bounds) => box.x >= bounds.x + 4 && box.y >= bounds.y + 4
  && box.x + box.width <= bounds.x + bounds.width - 4 && box.y + box.height <= bounds.y + bounds.height - 4
const centeredBox = (x, y, width, height) => ({ x: x - width / 2, y: y - height / 2, width, height })

function lineSamples(path) {
  const length = path.getTotalLength()
  const count = Math.max(1, Math.min(200, Math.ceil(length / 5)))
  return Array.from({ length: count + 1 }, (_, index) => path.getPointAtLength(index * length / count))
}

function labelPosition(samples, width, height, blocked, bounds) {
  // Start near the middle of the connector and try both sides before moving
  // further alongConnector its path. Node rectangles and connector strokes stay clear.
  const order = [...samples.keys()].sort((a, b) => Math.abs(a - samples.length / 2) - Math.abs(b - samples.length / 2))
  for (const index of order) {
    const { x, y } = samples[index]
    const candidates = [centeredBox(x, y - height / 2 - 5, width, height), centeredBox(x, y + height / 2 + 5, width, height),
      centeredBox(x + width / 2 + 5, y, width, height), centeredBox(x - width / 2 - 5, y, width, height)]
    const clear = candidates.find(box => insideCanvas(box, bounds) && !blocked.some(other => boxesIntersect(box, other, 2)))
    if (clear) return clear
  }
}

export function layoutGenuiDiagram(svg) {
  const paths = [...svg.querySelectorAll('path[marker-end]')]
  if (!paths.length) return undefined
  const originalViewBox = svg.getAttribute('viewBox')
  const { x, y, width, height } = svg.viewBox.baseVal
  const bounds = { x, y, width, height }
  const nodes = [...svg.querySelectorAll('g[role="button"]')].map(node => {
    const rect = node.firstElementChild?.firstElementChild
    return { name: node.getAttribute('aria-label'), box: rect?.getBBox?.() ?? node.getBBox() }
  })
  const restore = []
  const overlay = document.createElementNS(SVG_NS, 'g')
  overlay.setAttribute('data-bt-diagram-labels', '')
  overlay.setAttribute('pointer-events', 'none')
  svg.lastElementChild.before(overlay)
  const lines = paths.map(path => {
    const original = path.getAttribute('d')
    if (original) path.setAttribute('d', roundDiagramConnector(original))
    path.setAttribute('stroke-linecap', 'round')
    path.setAttribute('stroke-linejoin', 'round')
    restore.push(() => {
      if (original) path.setAttribute('d', original)
      path.removeAttribute('stroke-linecap')
      path.removeAttribute('stroke-linejoin')
    })
    return lineSamples(path)
  })
  const blocked = nodes.map(node => node.box).concat(lines.flatMap(samples => samples.map(({ x, y }) => centeredBox(x, y, 4, 4))))
  let extraHeight = 0
  let extraWidth = 0
  const nodeAt = p => nodes.find(({ box }) => p.x >= box.x - 1 && p.x <= box.x + box.width + 1 && p.y >= box.y - 1 && p.y <= box.y + box.height + 1)?.name
  for (const [index, path] of paths.entries()) {
    const label = path.nextElementSibling
    const text = label?.querySelector('text')
    const surface = label?.querySelector('rect')
    if (!text || !surface) continue
    const measure = text.getBBox()
    if (!measure.width || !measure.height) continue
    const samples = lines[index]
    const size = { width: measure.width + 10, height: measure.height + 6 }
    const box = labelPosition(samples, size.width, size.height, blocked, bounds)
    const copy = label.cloneNode(true)
    const plate = copy.querySelector('rect')
    const caption = copy.querySelector('text')
    caption.setAttribute('dominant-baseline', 'central')
    caption.setAttribute('text-anchor', 'middle')
    caption.setAttribute('fill', 'var(--dsw-alias-label-primary, currentColor)')
    let position = box
    if (!position) {
      const from = nodeAt(samples[0])
      const to = nodeAt(samples.at(-1))
      if (from && to) caption.textContent = `${from} → ${to} · ${caption.textContent}`
      overlay.append(copy)
      const rowWidth = Math.max(size.width, caption.getBBox().width + 10)
      extraWidth = Math.max(extraWidth, rowWidth + 16 - width)
      position = { x: x + 8, y: y + height + extraHeight + 5, width: rowWidth, height: size.height }
      extraHeight += size.height + 6
    }
    for (const [attr, value] of Object.entries(position)) plate.setAttribute(attr, value)
    caption.setAttribute('x', position.x + position.width / 2)
    caption.setAttribute('y', position.y + position.height / 2)
    overlay.append(copy)
    blocked.push(position)
    label.setAttribute('visibility', 'hidden')
    restore.push(() => label.removeAttribute('visibility'))
  }
  if (!overlay.childElementCount) overlay.remove()
  if (extraHeight) svg.setAttribute('viewBox', `${x} ${y} ${width + extraWidth} ${height + extraHeight + 6}`)
  return () => {
    overlay.remove()
    if (extraHeight) svg.setAttribute('viewBox', originalViewBox)
    for (const reset of restore) reset()
  }
}
