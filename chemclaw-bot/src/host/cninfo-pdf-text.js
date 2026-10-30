// Bounded best-effort PDF text extraction using the pdf-lib already shipped by ChemClaw.
// Only return page-numbered excerpts from page content streams; never invent OCR or page numbers.
import { PDFArray, PDFDict, PDFName, PDFRawStream, decodePDFRawStream } from 'pdf-lib'

const latin = bytes => Buffer.from(bytes).toString('latin1')
const nameOf = object => object?.toString?.().replace(/^\//, '') ?? ''
function hexUnicode(value) {
  const bytes = Buffer.from(value, 'hex')
  if (bytes.length % 2) return ''
  for (let i = 0; i + 1 < bytes.length; i += 2) { const old = bytes[i]; bytes[i] = bytes[i + 1]; bytes[i + 1] = old }
  return bytes.toString('utf16le')
}
function cmapping(text) {
  const map = new Map()
  for (const block of text.matchAll(/beginbfchar([\s\S]*?)endbfchar/g)) {
    for (const entry of block[1].matchAll(/<([a-fA-F0-9]+)>\s*<([a-fA-F0-9]+)>/g)) {
      map.set(entry[1].toUpperCase(), hexUnicode(entry[2]))
    }
  }
  for (const block of text.matchAll(/beginbfrange([\s\S]*?)endbfrange/g)) {
    for (const item of block[1].matchAll(/<([a-fA-F0-9]+)>\s*<([a-fA-F0-9]+)>\s*<([a-fA-F0-9]+)>/g)) {
      const begin = Number.parseInt(item[1], 16), end = Number.parseInt(item[2], 16)
      const initial = Number.parseInt(item[3], 16)
      if (end - begin > 1024) continue
      for (let offset = 0; offset <= end - begin; offset++) {
        const key = (begin + offset).toString(16).padStart(item[1].length, '0').toUpperCase()
        const value = (initial + offset).toString(16).padStart(item[3].length, '0')
        map.set(key, hexUnicode(value))
      }
    }
  }
  return map
}
function decoded(object) {
  if (!(object instanceof PDFRawStream)) return null
  try { return latin(decodePDFRawStream(object).decode()) } catch { return null }
}
function fontMaps(page) {
  const maps = new Map()
  try {
    const resource = page.node.normalizedEntries?.().Resources ?? page.node.Resources?.()
    const fonts = resource?.lookup?.(PDFName.of('Font'), PDFDict)
    for (const [fontName] of fonts?.entries?.() ?? []) {
      const font = fonts.lookup(fontName, PDFDict)
      const cmap = decoded(font?.lookup?.(PDFName.of('ToUnicode')))
      if (cmap) maps.set(nameOf(fontName), cmapping(cmap))
    }
  } catch { /* Unsupported resources: do not guess a font encoding. */ }
  return maps
}
function rawString(token) {
  if (token[0] === '<') return Buffer.from(token.slice(1, -1).replace(/\s/g, ''), 'hex')
  const chars = []
  const content = token.slice(1, -1)
  for (let i = 0; i < content.length; i++) {
    if (content[i] !== '\\') { chars.push(content.charCodeAt(i) & 255); continue }
    i++
    const char = content[i]
    if (char === undefined) break
    if (/[0-7]/.test(char)) {
      let oct = char
      for (let j = 0; j < 2 && /[0-7]/.test(content[i + 1] || ''); j++) oct += content[++i]
      chars.push(Number.parseInt(oct, 8) & 255)
    } else if (char === 'n') chars.push(10)
    else if (char === 'r') chars.push(13)
    else if (char === 't') chars.push(9)
    else if (char === '\n') continue
    else chars.push(char.charCodeAt(0) & 255)
  }
  return Buffer.from(chars)
}
function decodeToken(token, map) {
  const bytes = rawString(token)
  if (!bytes.length) return ''
  if (map?.size) {
    const units = []
    const length = [...map.keys()].some(key => key.length === 4) ? 2 : 1
    for (let i = 0; i + length <= bytes.length; i += length) {
      const key = bytes.subarray(i, i + length).toString('hex').toUpperCase()
      const decoded = map.get(key)
      if (decoded) units.push(decoded)
    }
    return units.join('')
  }
  // Only allow plain ASCII if there is no ToUnicode map, not guessed Chinese encodings.
  return [...bytes].map(v => v >= 32 && v < 127 ? String.fromCharCode(v) : v === 10 ? '\n' : '').join('')
}
function contentStreams(page) {
  try {
    const contents = page.node.lookup(PDFName.of('Contents'))
    if (contents instanceof PDFArray) {
      const streams = []
      for (let i = 0; i < contents.size(); i++) streams.push(contents.lookup(i))
      return streams
    }
    return [contents]
  } catch { return [] }
}
function pageText(page) {
  const fonts = fontMaps(page)
  let currentFont = ''
  const parts = []
  for (const stream of contentStreams(page)) {
    const content = decoded(stream)
    if (!content) continue
    for (const block of content.matchAll(/BT([\s\S]*?)ET/g)) {
      const token = /\/([A-Za-z0-9_.+-]+)\s+[\d.]+\s+Tf|(\((?:\\[\s\S]|[^\\)])*\)|<[A-Fa-f0-9\s]+>)\s*(?:Tj|'|")|\[([\s\S]*?)\]\s*TJ/g
      for (const hit of block[1].matchAll(token)) {
        if (hit[1]) currentFont = hit[1]
        else {
          const values = hit[2] ? [hit[2]] : [...hit[3].matchAll(/\((?:\\[\s\S]|[^\\)])*\)|<[A-Fa-f0-9\s]+>/g)].map(x => x[0])
          const text = values.map(value => decodeToken(value, fonts.get(currentFont))).join('')
          if (text.trim()) parts.push(text)
        }
      }
    }
  }
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}
export function extractPdfEvidence(document, { keyword = '', startPage = 1, maxPages = 25, maxHits = 12 } = {}) {
  const pageCount = document.getPageCount()
  const first = Math.max(1, Math.floor(Number(startPage) || 1))
  const last = Math.min(pageCount, first + Math.min(50, Math.max(1, Math.floor(Number(maxPages) || 25))) - 1)
  const wanted = String(keyword).trim().slice(0, 80)
  const hits = []
  let readablePages = 0
  for (let pageNo = first; pageNo <= last; pageNo++) {
    const text = pageText(document.getPage(pageNo - 1))
    if (!text) continue
    readablePages++
    if (!wanted) {
      hits.push({ page: pageNo, excerpt: text.slice(0, 700), type: 'page_start' })
    } else {
      let at = 0
      while (hits.length < maxHits && (at = text.indexOf(wanted, at)) !== -1) {
        hits.push({ page: pageNo, excerpt: text.slice(Math.max(0, at - 160), at + wanted.length + 220), type: 'literal_match' })
        at += wanted.length
      }
    }
    if (hits.length >= maxHits) break
  }
  return { status: readablePages ? 'partial_text' : 'unavailable', pageCount, examined: { start: first, end: last },
    readablePages, evidence: hits.slice(0, maxHits),
    note: readablePages ? 'Best-effort text-layer excerpts with page numbers; verify against the displayed original PDF, especially tables and units.' :
      'No extractable text layer in the inspected pages; do not invent OCR, page citations, figures or quotations.' }
}
