import { t } from './i18n.js'
import { installStyles } from './styles.js'
import { fallbackOverlappingDiagram, layoutGenuiDiagram } from './genui-diagram-layout.js'
import { FLOW_CSS } from './widget-flow.js'

const FIGURE = '[data-genui-diagram], [data-genui-svg], [data-chemclaw-flow-figure]'
const ARTIFACT = '[data-genui-artifact]'
const EXPORT = '[data-genui-export]'
const BUTTON = '.bt-genui-enlarge'
const ZOOM_LEVELS = [1, 1.5, 2, 3, 4]

const CSS = `
.bt-genui-previewable>img,.bt-genui-previewable>svg{cursor:zoom-in}
.bt-genui-enlarge{box-sizing:border-box;display:inline-grid;place-items:center;width:26px;height:26px;padding:0;border:0;border-radius:6px;background:transparent;color:var(--bt-ink-3);cursor:pointer}
.bt-genui-enlarge:is(:hover,:focus-visible){background:var(--bt-hover);color:var(--bt-ink)}
.bt-genui-figure-actions{display:flex;justify-content:flex-end;margin:8px 0 6px}
.bt-genui-diagram-fallback{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0;margin:8px 0}
.bt-genui-diagram-fallback button{font:inherit;color:var(--bt-ink);background:var(--bt-card);border:1px solid var(--bt-line);border-radius:8px;padding:4px 10px;cursor:pointer}
.bt-business-diagram{--dsw-alias-label-tertiary:var(--bt-ink-2)}
.bt-business-diagram [data-bt-diagram-node]{fill:color-mix(in srgb,var(--bt-ink-blue) 8%,var(--bt-main))}
.bt-business-diagram [data-bt-diagram-node][stroke-width="1"]{stroke:color-mix(in srgb,var(--bt-ink-blue) 60%,var(--bt-ink))}
.bt-genui-preview button{display:inline-grid;place-items:center;min-width:34px;height:34px;padding:0 8px;border:1px solid var(--bt-line-2);border-radius:8px;background:var(--bt-card);color:var(--bt-ink);font:inherit;cursor:pointer}
.bt-genui-preview button:hover{background:var(--bt-hover)}
.bt-genui-preview button:disabled{opacity:.4;cursor:default}
.bt-genui-preview{box-sizing:border-box;width:min(1400px,calc(100vw - 24px));height:calc(100dvh - 24px);max-width:none;max-height:none;padding:0;overflow:hidden;border:1px solid var(--bt-line-2);border-radius:16px;background:var(--bt-main);color:var(--bt-ink)}
.bt-genui-preview[open]{display:grid;grid-template-rows:auto minmax(0,1fr)}
.bt-genui-preview::backdrop{background:color-mix(in srgb,var(--bt-ink) 40%,transparent)}
body[data-ds-dark-theme] .bt-genui-preview::backdrop{background:color-mix(in srgb,var(--bt-main) 75%,transparent)}
.bt-genui-preview-bar{display:flex;align-items:center;gap:6px;padding:10px 14px;border-bottom:1px solid var(--bt-line-2)}
.bt-genui-preview-title{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px;font-weight:600}
.bt-genui-preview-scroll{overflow:auto;overscroll-behavior:contain}
.bt-genui-preview-stage{box-sizing:border-box;display:grid;place-items:center;width:max-content;min-width:100%;min-height:100%;padding:16px}
`

function graphicOf(figure) {
  const svg = figure.querySelector(':scope > svg[viewBox]')
  if (svg && svg.viewBox.baseVal.width > 0 && svg.viewBox.baseVal.height > 0) return svg
  const image = figure.querySelector(':scope > :is(img[src^="data:image/svg+xml,"], img[src^="data:image/svg+xml;"])')
  if (image?.naturalWidth > 0 && image.naturalHeight > 0) return image
}

function sizeInlineGraphic(graphic) {
  const image = graphic instanceof HTMLImageElement
  const { width, height } = image ? { width: graphic.naturalWidth, height: graphic.naturalHeight } : graphic.viewBox.baseVal
  const simple = !image && graphic.querySelectorAll('g[role="button"]').length <= 3
  const compactHeight = image ? 400 : simple ? 360 : 620
  // A viewBox-only SVG can report the browser's 300px default intrinsic width.
  // Read the declared canvas without adding any of the image markup to the DOM.
  let canvasWidth = width
  if (image) {
    try {
      const svg = decodeURIComponent(graphic.src.slice(graphic.src.indexOf(',') + 1))
      const viewBox = /<svg\b[^>]*?\sviewBox\s*=\s*(["'])([^"']+)\1/u.exec(svg)?.[2]
      const dimensions = viewBox?.trim().split(/[\s,]+/u).map(Number)
      if (dimensions?.length === 4 && Number.isFinite(dimensions[2]) && dimensions[2] > 0) canvasWidth = dimensions[2]
    } catch { /* use the image's reported dimensions */ }
  }
  const preferredWidth = image ? Math.max(220, canvasWidth) : simple ? Math.min(width, 520) : width
  const limit = Math.min(preferredWidth, width / height * compactHeight)
  const original = { maxWidth: graphic.style.maxWidth, height: graphic.style.height }
  graphic.style.maxWidth = `min(100%, ${Math.round(Math.max(1, limit))}px)`
  graphic.style.height = 'auto'
  return () => { Object.assign(graphic.style, original) }
}

function button(label, glyph, action) {
  const node = document.createElement('button')
  node.type = 'button'
  node.textContent = glyph
  node.title = label
  node.setAttribute('aria-label', label)
  node.addEventListener('click', action)
  return node
}

function enlargeGlyph() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('width', '14')
  svg.setAttribute('height', '14')
  svg.setAttribute('viewBox', '0 0 16 16')
  svg.setAttribute('aria-hidden', 'true')
  const path = document.createElementNS(svg.namespaceURI, 'path')
  path.setAttribute('d', 'M9.5 3H13v3.5M13 3 9.3 6.7M6.5 13H3V9.5M3 13l3.7-3.7')
  path.setAttribute('fill', 'none')
  path.setAttribute('stroke', 'currentColor')
  path.setAttribute('stroke-width', '1.3')
  path.setAttribute('stroke-linecap', 'round')
  path.setAttribute('stroke-linejoin', 'round')
  svg.append(path)
  return svg
}

const SOFTWARE = /软件架构|系统架构|后端架构|前后端|微服务|数据库|缓存层|软件系统|\b(?:software architecture|system architecture|it architecture|microservices?|database|api gateway|frontend|backend|reverse proxy)\b/iu

function styleBusinessDiagram(figure, graphic) {
  if (graphic.localName !== 'svg' || figure.classList.contains('bt-business-diagram')) return
  const nodes = [...graphic.querySelectorAll('g[role="button"]')]
  const legend = graphic.lastElementChild
  // GenUI 0.16 places its generated technology legend in the trailing group.
  if (!legend?.matches('g[transform]:has(> g > line + text):has(> g > g > rect)') || !nodes.length
    || SOFTWARE.test(graphic.querySelector('title')?.textContent ?? '')
    || nodes.filter(node => SOFTWARE.test(node.getAttribute('aria-label') ?? '')).length >= 2) return
  const original = graphic.getAttribute('viewBox')
  const { x, y, width, height } = graphic.viewBox.baseVal
  const legendY = legend.transform.baseVal.getItem(0)?.matrix.f
  if (legendY > y && legendY < y + height) graphic.setAttribute('viewBox', `${x} ${y} ${width} ${legendY - y}`)
  legend.setAttribute('display', 'none')
  figure.classList.add('bt-business-diagram')
  for (const node of nodes) {
    const [ground, face] = node.firstElementChild?.children ?? []
    if (ground?.localName === 'rect' && face?.localName === 'rect' && face.getAttribute('fill') === ground.getAttribute('fill')) {
      face.setAttribute('data-bt-diagram-node', '')
    }
  }
  return () => {
    graphic.setAttribute('viewBox', original)
    legend.removeAttribute('display')
    figure.classList.remove('bt-business-diagram')
    graphic.querySelectorAll('[data-bt-diagram-node]').forEach(rect => rect.removeAttribute('data-bt-diagram-node'))
  }
}

function openPreview(graphic, opener, onClose) {
  const isImage = graphic instanceof HTMLImageElement
  const { width, height } = isImage ? { width: graphic.naturalWidth, height: graphic.naturalHeight } : graphic.viewBox.baseVal
  const dialog = document.createElement('dialog')
  dialog.className = 'bt-genui-preview'
  const title = isImage ? graphic.alt : graphic.querySelector(':scope > title')?.textContent
  const label = title || t('Enlarge graphic')
  dialog.setAttribute('aria-label', label)
  const header = document.createElement('div')
  header.className = 'bt-genui-preview-bar'
  const heading = document.createElement('div')
  heading.className = 'bt-genui-preview-title'
  heading.textContent = label
  const viewport = document.createElement('div')
  viewport.className = 'bt-genui-preview-scroll'
  viewport.tabIndex = 0
  viewport.setAttribute('aria-label', label)
  const stage = document.createElement('div')
  stage.className = 'bt-genui-preview-stage'
  const canvas = document.createElement('div')
  const style = getComputedStyle(graphic)
  const nativeFlow = graphic.hasAttribute('data-chemclaw-flow')
  canvas.style.fontFamily = style.fontFamily
  for (let index = 0; index < style.length; index += 1) {
    const name = style.item(index)
    if (name.startsWith('--dsl-g-') || name.startsWith('--dsw-') || nativeFlow && name.startsWith('--bt-')) canvas.style.setProperty(name, style.getPropertyValue(name))
  }
  // Isolate the diagram's marker IDs. Model-provided SVG stays an image.
  const copy = graphic.cloneNode(!isImage)
  const tinted = [...graphic.querySelectorAll('[data-bt-diagram-node]')]
  copy.querySelectorAll('[data-bt-diagram-node]').forEach((rect, index) => {
    const { fill, stroke } = getComputedStyle(tinted[index])
    Object.assign(rect.style, { fill, stroke })
  })
  for (const node of copy.querySelectorAll('[role="button"]')) {
    for (const name of ['role', 'tabindex', 'aria-pressed']) node.removeAttribute(name)
  }
  Object.assign(copy.style, { display: 'block', width: '100%', height: 'auto', maxWidth: 'none', maxHeight: 'none', boxSizing: 'border-box' })
  const shadow = canvas.attachShadow({ mode: 'open' })
  shadow.append(copy)
  if (nativeFlow) {
    const rules = document.createElement('style')
    rules.textContent = FLOW_CSS
    shadow.append(rules)
  }
  stage.append(canvas)
  viewport.append(stage)

  let level = 0
  const minus = button(t('Zoom out'), '−', () => resize(level - 1))
  const plus = button(t('Zoom in'), '+', () => resize(level + 1))
  const fit = button(t('Fit graphic'), t('Fit graphic'), () => resize(0))
  const close = button(t('Close'), '×', () => dialog.close())
  close.autofocus = true

  function resize(next) {
    const { scrollWidth, scrollHeight, scrollLeft, scrollTop, clientWidth, clientHeight } = viewport
    const x = (scrollLeft + clientWidth / 2) / scrollWidth
    const y = (scrollTop + clientHeight / 2) / scrollHeight
    const fitted = Math.min(clientWidth - 32, (clientHeight - 32) * width / height)
    level = Math.max(0, Math.min(next, ZOOM_LEVELS.length - 1))
    canvas.style.width = `${Math.max(1, fitted * ZOOM_LEVELS[level])}px`
    minus.disabled = fit.disabled = level === 0
    plus.disabled = level === ZOOM_LEVELS.length - 1
    viewport.scrollLeft = (x || .5) * viewport.scrollWidth - clientWidth / 2
    viewport.scrollTop = (y || .5) * viewport.scrollHeight - clientHeight / 2
  }

  header.append(heading, minus, fit, plus, close)
  dialog.append(header, viewport)
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close() })
  dialog.addEventListener('keydown', event => {
    const next = { '+': level + 1, '=': level + 1, '-': level - 1, '0': 0 }[event.key]
    if (next === undefined || event.altKey || event.ctrlKey || event.metaKey) return
    event.preventDefault()
    resize(next)
  })
  const observer = new ResizeObserver(() => resize(level))
  dialog.addEventListener('close', () => {
    observer.disconnect()
    dialog.remove()
    opener?.focus({ preventScroll: true })
    onClose()
  }, { once: true })
  document.body.append(dialog)
  dialog.showModal()
  resize(0)
  observer.observe(viewport)
  return dialog
}

export function installGenuiPreview() {
  const styles = installStyles(CSS, 'genui-preview')
  const controls = new Map()
  let dialog
  const prepare = figure => {
    const graphic = figure && graphicOf(figure)
    if (!graphic) return
    let entry = controls.get(figure)
    if (entry?.graphic !== graphic) {
      entry?.restore?.()
      const control = entry?.control ?? button(t('Enlarge graphic'), '', event => {
        event.stopPropagation()
        const current = graphicOf(figure)
        if (!dialog && current) dialog = openPreview(current, control, () => { dialog = undefined })
      })
      if (!entry) {
        control.className = BUTTON.slice(1)
        control.setAttribute('aria-haspopup', 'dialog')
        control.append(enlargeGlyph())
      }
      const fallback = graphic.localName === 'svg' ? fallbackOverlappingDiagram(graphic) : undefined
      if (fallback) {
        control.remove()
        entry?.strip?.remove()
        controls.set(figure, { control, graphic, restore: fallback, fallback: true })
        return
      }
      const restoreStyle = styleBusinessDiagram(figure, graphic)
      const nativeFlow = graphic.hasAttribute('data-chemclaw-flow')
      const restoreLayout = graphic.localName === 'svg' && !nativeFlow ? layoutGenuiDiagram(graphic) : undefined
      const restoreSize = nativeFlow ? undefined : sizeInlineGraphic(graphic)
      const restore = () => { restoreSize?.(); restoreLayout?.(); restoreStyle?.() }
      entry = { control, graphic, strip: entry?.strip, restore }
      controls.set(figure, entry)
      figure.classList.add('bt-genui-previewable')
    }
    if (entry.fallback) return
    const download = figure.closest(ARTIFACT)?.querySelector(`:scope > ${EXPORT} > button[aria-haspopup="menu"]`)
    if (download) {
      if (entry.control.parentElement !== download.parentElement) download.before(entry.control)
      entry.strip?.remove()
      entry.strip = undefined
    } else if (!entry.control.isConnected) {
      entry.strip = document.createElement('div')
      entry.strip.className = 'bt-genui-figure-actions'
      entry.strip.append(entry.control)
      figure.append(entry.strip)
    }
  }
  const drop = (figure, entry) => {
    entry.control.remove()
    entry.strip?.remove()
    entry.restore?.()
    figure.classList.remove('bt-genui-previewable')
    controls.delete(figure)
  }
  const click = event => {
    if (event.defaultPrevented || !(event.target instanceof Element)
      || event.target.closest('button, a, [role="button"]') || window.getSelection()?.type === 'Range') return
    const graphic = event.target.closest('svg, img')
    const figure = graphic?.closest(FIGURE)
    if (figure && graphic === graphicOf(figure)) controls.get(figure)?.control.click()
  }
  const load = event => {
    if (event.target instanceof HTMLImageElement) prepare(event.target.closest(FIGURE))
  }
  const observer = new MutationObserver(records => {
    if (records.some(record => record.removedNodes.length)) {
      for (const [figure, entry] of controls) if (!figure.isConnected) drop(figure, entry)
    }
    for (const { addedNodes } of records) for (const node of addedNodes) {
      if (!(node instanceof Element) || node.closest(`${BUTTON}, .bt-genui-preview`)) continue
      prepare(node.closest(FIGURE))
      if (node.closest(EXPORT)) node.closest(ARTIFACT)?.querySelectorAll(FIGURE).forEach(prepare)
      node.querySelectorAll(FIGURE).forEach(prepare)
    }
  })
  document.querySelectorAll(FIGURE).forEach(prepare)
  observer.observe(document.body, { childList: true, subtree: true })
  document.addEventListener('load', load, true)
  document.addEventListener('click', click)
  return () => {
    observer.disconnect()
    document.removeEventListener('click', click)
    document.removeEventListener('load', load, true)
    dialog?.close()
    for (const [figure, entry] of controls) drop(figure, entry)
    styles.remove()
  }
}
