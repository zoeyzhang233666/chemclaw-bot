import { DOMParser, XMLSerializer } from '@xmldom/xmldom'
import { genuiFences, repairGenuiGraphic } from '../../shared/genui-fences.js'

const SVG_NS = 'http://www.w3.org/2000/svg'
const ELEMENTS = new Set('svg g defs linearGradient radialGradient stop clipPath marker path rect circle ellipse line polyline polygon text tspan title desc'.split(' '))
const ATTRIBUTES = new Set(('id width height viewBox preserveAspectRatio x x1 x2 y y1 y2 cx cy r rx ry dx dy d points transform ' +
  'fill fill-opacity fill-rule stroke stroke-width stroke-linecap stroke-linejoin stroke-opacity stroke-dasharray opacity ' +
  'font-family font-size font-weight font-style text-anchor dominant-baseline letter-spacing ' +
  'offset stop-color stop-opacity gradientUnits gradientTransform fx fy clip-path clipPathUnits ' +
  'marker-start marker-mid marker-end markerWidth markerHeight markerUnits orient refX refY').split(' '))
const parser = new DOMParser({ onError: () => { throw new Error('Invalid SVG') } })
const serializer = new XMLSerializer()

export function extractImVisuals(reply) {
  const visuals = []
  let text = '', offset = 0
  for (const fence of genuiFences(reply)) {
    text += reply.slice(offset, fence.start)
    offset = fence.end
    if (visuals.length >= 8) continue
    let spec
    if (fence.closed && fence.body.length <= 60_000) {
      try { spec = JSON.parse(repairGenuiGraphic(fence.body) ?? fence.body) } catch { /* shown in the desktop if supported */ }
    }
    const items = Array.isArray(spec?.items) ? spec.items : [spec]
    for (const item of items.slice(0, 8 - visuals.length)) {
      if (item?.type === 'text' && typeof item.text === 'string') {
        text += '\n\n' + item.text.slice(0, 4000) + '\n'
        continue
      }
      const title = typeof item?.title === 'string' ? item.title.slice(0, 160) : ''
      visuals.push({ title, code: item?.type === 'svg' ? item.code : undefined })
    }
  }
  return { text: (text + reply.slice(offset)).trim(), visuals }
}

// Only static SVG primitives enter the native image decoder. No linked assets,
// HTML, CSS, event handlers, entities, scripts, filters or use/shadow trees.
export function sanitizeImSvg(code) {
  if (typeof code !== 'string' || code.length > 12_000 || /<!DOCTYPE|<!ENTITY/iu.test(code)) return undefined
  const root = parser.parseFromString(code, 'image/svg+xml').documentElement
  if (root?.localName !== 'svg' || (root.namespaceURI && root.namespaceURI !== SVG_NS)) return undefined
  const clean = root.ownerDocument.implementation.createDocument(SVG_NS, 'svg', null)
  let count = 0
  const copy = (node, target, depth = 0) => {
    if (depth > 16 || ++count > 500) throw new Error('SVG is too complex')
    for (const attribute of Array.from(node.attributes)) {
      const value = attribute.value
      if (attribute.namespaceURI || !ATTRIBUTES.has(attribute.name)) continue
      if (/[\\<>]/u.test(value) || (/url\s*\(/iu.test(value) && !/^url\(#[\w.-]+\)$/u.test(value))) continue
      target.setAttribute(attribute.name, value)
    }
    for (const child of Array.from(node.childNodes)) {
      if (child.nodeType === 3) target.appendChild(clean.createTextNode(child.data))
      if (child.nodeType !== 1 || !ELEMENTS.has(child.localName) || child.localName === 'svg'
        || (child.namespaceURI && child.namespaceURI !== SVG_NS)) continue
      const element = clean.createElementNS(SVG_NS, child.localName)
      copy(child, element, depth + 1)
      target.appendChild(element)
    }
  }
  copy(root, clean.documentElement)
  return count > 1 ? serializer.serializeToString(clean.documentElement) : undefined
}

export async function renderImSvg(code, redact) {
  const svg = sanitizeImSvg(code)
  if (!svg || redact(code) !== code || redact(svg) !== svg) return undefined
  const { default: sharp } = await import('sharp')
  const raster = sharp(Buffer.from(svg), { limitInputPixels: 8_000_000 })
  const data = await raster.resize({ width: 1120, height: 1600, fit: 'inside' }).png().toBuffer()
  return { data, mediaType: 'image/png', name: 'chemclaw-image.png' }
}
