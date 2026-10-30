// CNINFO (巨潮资讯) public corporate disclosures. No API key and no shell required.
// The endpoints are a public website interface, not a guaranteed official developer API.
import { createHash } from 'node:crypto'
import { PDFDocument } from 'pdf-lib'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { extractPdfEvidence } from './cninfo-pdf-text.js'

const API = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
const FULL = 'https://www.cninfo.com.cn/new/fulltextSearch/full'
const HOME = 'https://www.cninfo.com.cn/'
const CDN = 'https://static.cninfo.com.cn/'
const UA = 'Mozilla/5.0 (compatible; ChemClaw/0.2; research)'
const MAX_RESULTS = 90
const MAX_PDF_BYTES = 32 * 1024 * 1024
const output = { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] }
const iso = value => /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value + 'T00:00:00Z'))
const clean = text => String(text ?? '').replace(/<[^>]*>/g, ' ').replace(/&nbsp;/gi, ' ').replace(/\s+/g, ' ').trim()
const codeOf = value => String(value ?? '').match(/(?:^|\D)(\d{6})(?:\D|$)/)?.[1] ?? ''
const safeText = (value, limit = 100) => clean(value).slice(0, limit)
const clock = () => new Date().toISOString()
let nextRequestAt = 0
let requestLane = Promise.resolve()
async function pace(signal) {
  // The official website rate-limits bursts. Serialize public searches across Bots.
  let done
  const slot = new Promise(resolve => { done = resolve })
  const prior = requestLane
  requestLane = slot
  await prior
  try {
    const wait = Math.max(0, nextRequestAt - Date.now())
    if (wait) await new Promise(resolve => setTimeout(resolve, wait))
    signal?.throwIfAborted()
    nextRequestAt = Date.now() + 850
  } finally { done() }
}

function range(begin, end) {
  if (begin && !iso(begin) || end && !iso(end) || begin && end && begin > end) throw new Error('Use YYYY-MM-DD and an ascending date range')
  return begin && end ? begin + '~' + end : ''
}
function pdfUrl(path) {
  // Never turn an untrusted website response into an arbitrary network request.
  if (!/^finalpage\/\d{4}-\d{2}-\d{2}\/[A-Za-z0-9_-]+\.pdf$/i.test(String(path ?? ''))) return null
  return CDN + path
}
export function validatePdfUrl(value) {
  let url
  try { url = new URL(value) } catch { throw new Error('Invalid CNINFO PDF URL') }
  if (url.origin !== 'https://static.cninfo.com.cn' || url.search || url.hash || !pdfUrl(url.pathname.replace(/^\//, ''))) {
    throw new Error('Only HTTPS CNINFO /finalpage/.../*.PDF links are allowed')
  }
  return url.href
}
function normalise(row) {
  const path = row?.adjunctUrl
  const day = String(path ?? '').match(/finalpage\/(\d{4}-\d{2}-\d{2})\//)?.[1]
  const timestamp = Number(row?.announcementTime)
  return {
    id: String(row?.announcementId ?? ''),
    code: String(row?.secCode ?? ''),
    company: clean(row?.secName),
    title: clean(row?.announcementTitle),
    date: day ?? (Number.isFinite(timestamp) && timestamp > 0 ? new Date(timestamp).toISOString().slice(0, 10) : null),
    pdfUrl: pdfUrl(path),
    snippet: safeText(row?.announcementContent, 280),
  }
}
function timeout(signal, ms) {
  return signal ? AbortSignal.any([signal, AbortSignal.timeout(ms)]) : AbortSignal.timeout(ms)
}
async function requestJson(url, options, fetcher, signal) {
  let last
  for (let attempt = 0; attempt < 2; attempt++) {
    let response
    try {
      if (fetcher === globalThis.fetch) await pace(signal)
      response = await fetcher(url, { ...options, redirect: 'error', signal: timeout(signal, 18000) })
      if ([403, 429, 500, 502, 503, 504].includes(response.status)) {
        last = new Error('CNINFO temporarily unavailable (HTTP ' + response.status + ')')
        if (attempt === 0) continue
      }
      if (!response.ok) throw new Error('CNINFO HTTP ' + response.status)
      const body = await response.text()
      if (body.length > 3_000_000) throw new Error('CNINFO returned an oversized response')
      const data = JSON.parse(body)
      if (!data || !Array.isArray(data.announcements)) throw new Error('CNINFO returned an unexpected response format; zero results cannot be confirmed')
      // CNINFO sometimes silently returns an empty first response under rate limiting.
      if (data.announcements.length === 0 && attempt === 0) continue
      return data
    } catch (error) {
      last = error
      if (signal?.aborted) throw error
    }
  }
  throw last
}
export async function searchCninfo(args, { fetcher = globalThis.fetch, signal } = {}) {
  const company = safeText(args.company, 80)
  const keyword = safeText(args.keyword, 80)
  const code = codeOf(args.code)
  if (!company && !code && !keyword) throw new Error('Provide a company name, a stock code or a keyword')
  if (args.code && !code) throw new Error('Stock code must contain six digits')
  const begin = args.begin || ''
  const end = args.end || ''
  range(begin, end)
  if (Boolean(begin) !== Boolean(end)) throw new Error('Provide both begin and end, or neither')
  const pages = Math.max(1, Math.min(3, Math.floor(Number(args.pages) || 1)))
  const mode = ['title', 'full', 'both'].includes(args.mode) ? args.mode : 'both'
  // Full-text search is relevance-ranked; API date filters have been observed to be ignored.
  // Its response is filtered by date locally, and completeness is not claimed.
  const terms = [...new Set([company, keyword].filter(Boolean))]
  const fullTerm = terms.join(' ') || code
  const titleTerm = keyword || company || code
  const all = []
  const attempts = []
  const modes = mode === 'both' ? ['title', 'full'] : [mode]
  for (const kind of modes) {
    try {
      for (let page = 1; page <= pages; page++) {
        let url, options
        if (kind === 'title') {
          url = API
          const fields = new URLSearchParams({ pageNum: String(page), pageSize: '30', column: 'szse', tabName: 'fulltext',
            plate: '', stock: '', searchkey: titleTerm, secid: '', category: '', trade: '',
            seDate: range(begin, end), sortName: '', sortType: '', isHLtitle: 'true' })
          options = { method: 'POST', body: fields.toString(), headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            Accept: 'application/json, text/javascript, */*; q=0.01', Referer: HOME + 'new/fulltextSearch?keyWord=', Origin: HOME.slice(0, -1),
            'X-Requested-With': 'XMLHttpRequest', 'User-Agent': UA } }
        } else {
          url = FULL + '?' + new URLSearchParams({ searchkey: fullTerm, isfulltext: 'true', sortName: 'nothing',
            sortType: 'desc', pageNum: String(page), pageSize: '30' })
          options = { headers: { Accept: 'application/json', Referer: HOME, 'X-Requested-With': 'XMLHttpRequest', 'User-Agent': UA } }
        }
        const data = await requestJson(url, options, fetcher, signal)
        const items = data.announcements.map(normalise).filter(item => {
          if (begin && item.date && (item.date < begin || item.date > end)) return false
          if (company && !item.company.includes(company) && !company.includes(item.company)) return false
          if (code && item.code !== code) return false
          return Boolean(item.id && item.title && item.pdfUrl)
        })
        all.push(...items)
        if (data.announcements.length < 30 || all.length >= MAX_RESULTS) break
      }
      attempts.push({ mode: kind, status: 'ok' })
    } catch (error) {
      if (signal?.aborted) throw error
      attempts.push({ mode: kind, status: 'error', message: String(error?.message ?? error).slice(0, 170) })
    }
  }
  const distinct = [...new Map(all.map(row => [row.id || row.pdfUrl, row])).values()]
    .sort((a, b) => String(b.date).localeCompare(String(a.date))).slice(0, MAX_RESULTS)
  const success = attempts.some(item => item.status === 'ok')
  return { status: !success ? 'error' : distinct.length ? 'ok' : 'no_match',
    provider: 'CNINFO', source: HOME, retrievedAt: clock(), company, code, keyword, begin: begin || null, end: end || null,
    modes: attempts, truncated: all.length >= MAX_RESULTS, results: distinct,
    notice: !success ? 'CNINFO query failed; do not state there are no announcements.' :
      'Results are a bounded sample, not a completeness guarantee. Check listed-company identity and read the original PDF before using numbers.' }
}
export async function fetchCninfoPdf(value, { fetcher = globalThis.fetch, signal, store, keyword, startPage, maxPages } = {}) {
  const url = validatePdfUrl(value)
  const response = await fetcher(url, { headers: { Accept: 'application/pdf', 'User-Agent': UA, Referer: HOME },
    redirect: 'error', signal: timeout(signal, 30000) })
  if (!response.ok) throw new Error('CNINFO PDF HTTP ' + response.status)
  const size = Number(response.headers?.get?.('content-length') || 0)
  if (size > MAX_PDF_BYTES) throw new Error('CNINFO PDF exceeds the 32 MB download limit')
  // Read incrementally so a missing Content-Length cannot bypass the cap.
  const chunks = []
  let bytes = 0
  if (response.body?.getReader) {
    const reader = response.body.getReader()
    try {
      while (true) {
        const part = await reader.read()
        if (part.done) break
        bytes += part.value.byteLength
        if (bytes > MAX_PDF_BYTES) throw new Error('CNINFO PDF exceeds the 32 MB download limit')
        chunks.push(Buffer.from(part.value))
      }
    } finally { await reader.cancel().catch(() => {}) }
  } else {
    const data = Buffer.from(await response.arrayBuffer())
    bytes = data.length
    if (bytes > MAX_PDF_BYTES) throw new Error('CNINFO PDF exceeds the 32 MB download limit')
    chunks.push(data)
  }
  const data = Buffer.concat(chunks)
  if (data.subarray(0, 5).toString() !== '%PDF-') throw new Error('CNINFO response was not a PDF')
  const pdf = await PDFDocument.load(data, { updateMetadata: false })
  const extracted = extractPdfEvidence(pdf, { keyword, startPage, maxPages })
  const ref = store ? await store({ name: url.split('/').at(-1), data }) : null
  return { status: 'downloaded', source: url, retrievedAt: clock(), sha256: createHash('sha256').update(data).digest('hex'),
    bytes, pages: pdf.getPageCount(), attachment: ref, extraction: extracted,
    notice: 'Evidence excerpts are best-effort text-layer extraction, not OCR; verify figures, page references and tables against the PDF original.' }
}
export function install(rt) {
  const last = { state: 'unqueried' }
  rt.cninfoStatus = () => ({ name: '巨潮公告', coverage: 'A股上市公司公告检索、PDF 原件下载；免 Key。可用性以实际连接测试为准。', ...last })
  const track = (state, error) => { last.state = state; last.checkedAt = clock(); delete last.error; if (error) last.error = String(error).slice(0, 180) }
  rt.cninfoCheck = async () => {
    try {
      const result = await searchCninfo({ company: '万华化学', mode: 'title', pages: 1 }, { fetcher: rt.config.cninfoFetch })
      if (result.status === 'error') throw new Error(result.modes.map(item => item.message).filter(Boolean).join('; ') || 'CNINFO unavailable')
      track('ready')
    } catch (error) { track('error', error?.message ?? error) }
    return rt.cninfoStatus()
  }
  rt.ctx.tools.register(defineTool({ name: 'chem_cninfo_resolve_company',
    description: 'Find potential A-share listed securities identities and stock codes through CNINFO announcement metadata. Candidates are evidence-based but not an exhaustive registry; verify group, subsidiary, and listed company distinctions.',
    parameters: { query: { type: 'string', required: true, description: 'Listed company name, abbreviation or 6-digit securities code' } }, output,
    execute: async (args, exec) => {
      const query = safeText(args.query, 80)
      if (!query) throw new Error('Provide a company name or six-digit stock code')
      const result = await searchCninfo({ keyword: query, mode: 'both', pages: 1 }, { fetcher: rt.config.cninfoFetch, signal: exec.signal })
      const code = codeOf(query)
      const candidates = [...new Map(result.results.filter(row =>
        code ? row.code === code : row.company.includes(query) || query.includes(row.company)
      ).map(row => [row.code, { code: row.code, company: row.company, exampleAnnouncement: row.title,
        disclosedAt: row.date, source: row.pdfUrl }])).values()].slice(0, 15)
      if (result.status === 'error') track('error', result.modes.map(item => item.message).filter(Boolean).join('; '))
      else track('ready')
      return JSON.stringify({ status: result.status, query, candidates, retrievedAt: result.retrievedAt,
        notice: 'Candidate security codes from public announcement metadata; not a definitive corporate registry. Absence does not prove an enterprise is unlisted.' })
    },
  }))
  rt.ctx.tools.register(defineTool({ name: 'chem_cninfo_search',
    description: 'Search CNINFO official A-share company announcement metadata, title and full text, dates and original PDF URLs. For current company expansions, production capacity, financial filings, significant events or risks use this evidence source before relying on news. Distinguish no results from errors. Read the PDF before citing numbers.',
    parameters: { company: { type: 'string', description: 'Listed company name; do not confuse with holding group or subsidiaries' },
      code: { type: 'string', description: 'Optional six-digit stock code' }, keyword: { type: 'string', description: 'Announcement topic or material keyword' },
      begin: { type: 'string', description: 'Optional YYYY-MM-DD, requires end' }, end: { type: 'string', description: 'Optional YYYY-MM-DD, requires begin' },
      pages: { type: 'number', description: '1 to 3 pages per mode' }, mode: { type: 'string', enum: ['title', 'full', 'both'] } }, output,
    execute: async (args, exec) => {
      const result = await searchCninfo(args, { fetcher: rt.config.cninfoFetch, signal: exec.signal })
      if (result.status === 'error') track('error', result.modes.map(item => item.message).filter(Boolean).join('; '))
      else track('ready')
      return JSON.stringify(result)
    },
  }))
  rt.ctx.tools.register(defineTool({ name: 'chem_cninfo_read_pdf',
    description: 'Download an original CNINFO disclosure PDF and extract bounded best-effort text-layer excerpts with page numbers. Scanned PDFs or unsupported fonts may have no readable text; never invent page evidence or figures. Verify extracted numbers against the original.' ,
    parameters: { url: { type: 'string', required: true, description: 'Exact HTTPS static.cninfo.com.cn/finalpage/...PDF URL from announcement search' },
      keyword: { type: 'string', description: 'Optional exact word to find in PDF page text' },
      startPage: { type: 'number', description: '1-based first page; default 1' }, maxPages: { type: 'number', description: 'Pages to inspect; default 25, up to 50' } }, output,
    execute: async (args, exec) => {
      const store = rt.ctx.get?.('attachments')?.saveFile
      const attachmentService = rt.ctx.get?.('attachments')
      const result = await fetchCninfoPdf(args.url, { fetcher: rt.config.cninfoFetch, signal: exec.signal,
        store: typeof store === 'function' ? detail => attachmentService.saveFile(detail) : undefined,
        keyword: args.keyword, startPage: args.startPage, maxPages: args.maxPages })
      track('ready')
      return JSON.stringify(result)
    },
  }))
}
