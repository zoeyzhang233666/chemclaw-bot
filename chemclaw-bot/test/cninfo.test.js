import assert from 'node:assert/strict'
import { test } from 'node:test'
import { PDFDocument } from 'pdf-lib'
import { searchCninfo, validatePdfUrl, fetchCninfoPdf, install } from '../src/host/cninfo.js'
import { install as installPublicData } from '../src/host/public-data.js'
import { fakeContext } from './fake-ctx.js'

const filing = (overrides = {}) => ({
  announcementId: '1225000001',
  secCode: '600309',
  secName: '万华化学',
  announcementTitle: '<em>万华化学</em>：关于建设新项目的公告',
  announcementContent: '包含项目与产能信息，请查阅 PDF 原文',
  announcementTime: Date.UTC(2026, 9, 29),
  adjunctUrl: 'finalpage/2026-10-30/1225000001.PDF',
  ...overrides,
})
const json = rows => new Response(JSON.stringify({ announcements: rows }), {
  status: 200, headers: { 'content-type': 'application/json' },
})

test('CNINFO title search sends form parameters, applies company and code filtering, and uses PDF disclosure date', async () => {
  const calls = []
  const result = await searchCninfo({
    company: '万华化学', code: '600309', keyword: '项目', begin: '2026-10-01', end: '2026-10-30', mode: 'title',
  }, { fetcher: async (url, init) => {
    calls.push({ url, init })
    return json([filing(), filing({ announcementId: 'bad', secCode: '000001' })])
  } })
  assert.equal(result.status, 'ok')
  assert.equal(result.results.length, 1)
  assert.equal(result.results[0].date, '2026-10-30')
  assert.equal(result.results[0].pdfUrl, 'https://static.cninfo.com.cn/finalpage/2026-10-30/1225000001.PDF')
  assert.ok(calls[0].url.startsWith('https://www.cninfo.com.cn/new/hisAnnouncement/query'))
  assert.ok(calls[0].init.body.includes('seDate=2026-10-01%7E2026-10-30'))
  assert.ok(calls[0].init.headers['X-Requested-With'])
  assert.equal(calls[0].init.redirect, 'error')
})

test('CNINFO full-text search filters relevance-ranked results by client dates', async () => {
  const result = await searchCninfo({ company: '万华化学', mode: 'full',
    begin: '2026-10-01', end: '2026-10-30' }, {
    fetcher: async () => json([
      filing(), filing({ announcementId: 'old', adjunctUrl: 'finalpage/2026-09-01/99.PDF' }),
      filing({ announcementId: 'other', secName: '其他公司' }),
    ]),
  })
  assert.equal(result.results.length, 1)
  assert.equal(result.results[0].id, '1225000001')
})

test('CNINFO mixed-mode keeps working mode when another mode fails and deduplicates filings', async () => {
  const calls = []
  const result = await searchCninfo({ company: '万华化学', mode: 'both' }, {
    fetcher: async (url) => {
      calls.push(url)
      if (url.includes('hisAnnouncement')) return new Response('unavailable', { status: 403 })
      return json([filing(), filing()])
    },
  })
  assert.equal(result.status, 'ok')
  assert.equal(result.results.length, 1)
  assert.equal(result.modes[0].status, 'error')
  assert.equal(result.modes[1].status, 'ok')
  assert.equal(calls.length, 3)
})

test('CNINFO does not report an API failure as a verified empty result', async () => {
  const response = await searchCninfo({ company: '万华化学', mode: 'title' }, { fetcher: async () => new Response('', { status: 429 }) })
  assert.equal(response.status, 'error')
  assert.match(response.notice, /do not state/)
  const empty = await searchCninfo({ company: '万华化学', mode: 'title' }, { fetcher: async () => json([]) })
  assert.equal(empty.status, 'no_match')
  await assert.rejects(searchCninfo({ company: '万华化学', begin: '2026-10-30' }), /both begin and end/)
})

test('untrusted CDN paths or caller-supplied URLs cannot redirect PDF fetch to other hosts', async () => {
  for (const value of [
    'https://evil.example/finalpage/2026-10-30/123.PDF',
    'http://static.cninfo.com.cn/finalpage/2026-10-30/123.PDF',
    'https://static.cninfo.com.cn/finalpage/2026-10-30/123.PDF?next=1',
    'https://static.cninfo.com.cn/finalpage/2026-10-30/../123.PDF',
  ]) assert.throws(() => validatePdfUrl(value), /PDF|CNINFO/)
  const response = await searchCninfo({ company: '万华化学', mode: 'title' }, {
    fetcher: async () => json([filing({ adjunctUrl: 'https://evil.example/payload' }), filing()]),
  })
  assert.equal(response.results.length, 1)
})

test('downloaded PDF is real, size-limited, and exposes a correct page count and attachment', async () => {
  const doc = await PDFDocument.create()
  doc.addPage([500, 700])
  doc.addPage([500, 700])
  const data = await doc.save()
  const seen = []
  const url = 'https://static.cninfo.com.cn/finalpage/2026-10-30/1225000001.PDF'
  const result = await fetchCninfoPdf(url, {
    fetcher: async (u, init) => { seen.push({ u, init }); return new Response(data, { status: 200, headers: { 'content-type': 'application/pdf' } }) },
    store: async info => ({ attachmentId: 'a1', name: info.name }),
  })
  assert.equal(result.pages, 2)
  assert.equal(result.textStatus, 'not_extracted')
  assert.equal(result.attachment.attachmentId, 'a1')
  assert.equal(seen[0].init.redirect, 'error')
  assert.equal(result.sha256.length, 64)
  await assert.rejects(fetchCninfoPdf(url, { fetcher: async () => new Response('not a pdf') }), /not a PDF/)
  await assert.rejects(fetchCninfoPdf(url, { fetcher: async () => new Response(data, { headers: { 'content-length': String(33 * 1024 * 1024) } }) }), /32 MB/)
})

test('CNINFO registers on the global DSH tool surface and appears in public research data without fetching on settings open', async () => {
  const ctx = fakeContext()
  const rt = { ctx, config: { cninfoFetch: async () => json([filing()]) } }
  installPublicData(rt)
  install(rt)
  assert.ok(ctx.registeredTools.has('chem_cninfo_search'))
  assert.ok(ctx.registeredTools.has('chem_cninfo_read_pdf'))
  const first = rt.publicDataStatus().find(source => source.name === '巨潮公告')
  assert.equal(first.state, 'unqueried')
  const result = JSON.parse(await ctx.registeredTools.get('chem_cninfo_search').execute({ company: '万华化学', mode: 'title' }, {}))
  assert.equal(result.status, 'ok')
  assert.equal(rt.publicDataStatus().find(source => source.name === '巨潮公告').state, 'ready')
  assert.equal((await rt.cninfoCheck()).state, 'ready')
})
