import assert from 'node:assert/strict'
import { mkdtemp, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { IMA_OPERATIONS, callImaApi, cosUploadRequest, uploadImaFile } from '../src/host/ima-openapi.js'

const response = (data, code = 0) => ({ ok: true, status: 200, text: async () => JSON.stringify({ code, msg: 'ok', data }) })
const opts = { clientId: 'test-client-id', apiKey: 'test-api-key' }

test('ima request uses only the official domain, appropriate headers, JSON and allowlisted operation', async () => {
  let sent
  const result = await callImaApi({ ...opts, operation: 'wiki.search_knowledge_base', body: { query: 'SBS', cursor: '', limit: 5 },
    request: async (url, init) => { sent = { url, init }; return response({ info_list: [] }) } })
  assert.deepEqual(result.info_list, [])
  assert.equal(sent.url, 'https://ima.qq.com/openapi/wiki/v1/search_knowledge_base')
  assert.equal(sent.init.method, 'POST')
  assert.equal(sent.init.headers['ima-openapi-clientid'], opts.clientId)
  assert.equal(sent.init.headers['ima-openapi-apikey'], opts.apiKey)
  assert.deepEqual(JSON.parse(sent.init.body), { query: 'SBS', cursor: '', limit: 5 })
  assert.ok(Object.hasOwn(IMA_OPERATIONS, 'note.append_doc'))
  await assert.rejects(callImaApi({ ...opts, operation: 'wiki.delete_knowledge' }), /Unsupported ima/)
  await assert.rejects(callImaApi({ ...opts, operation: 'wiki.search_knowledge', body: [] }), /JSON object/)
})

test('ima errors hide credentials and do not expose upstream body for HTTP errors', async () => {
  await assert.rejects(callImaApi({ ...opts, operation: 'note.get_doc_content',
    request: async () => response({}, 20004) }), /ima OpenAPI error 20004/)
  await assert.rejects(callImaApi({ ...opts, operation: 'note.get_doc_content',
    request: async () => ({ ok: false, status: 401 }) }), /HTTP 401/)
  await assert.rejects(callImaApi({ ...opts, operation: 'note.get_doc_content',
    request: async () => response(null, 0) }), /no data/)
  let message
  try {
    await callImaApi({ ...opts, operation: 'note.get_doc_content',
      request: async () => ({ ok: true, text: async () => JSON.stringify({ code: 13, msg: opts.apiKey, data: {} }) }) })
  } catch (error) { message = error.message }
  assert.ok(!message.includes(opts.apiKey))
  assert.match(message, /\[secret:IMA_API_KEY\]/)
})

test('COS upload uses short-lived credentials only for COS, not in the URL', () => {
  const req = cosUploadRequest({
    secret_id: 'secret-id', secret_key: 'secret-key', token: 'temp-token',
    appid: '123456', bucket_name: 'sample-bucket', region: 'ap-guangzhou',
    cos_key: 'a/b.pdf', start_time: 100, expired_time: 700,
  }, Buffer.from('pdf'), 'application/pdf', 100)
  assert.equal(req.url, 'https://sample-bucket-123456.cos.ap-guangzhou.myqcloud.com/a/b.pdf')
  assert.match(req.init.headers.Authorization, /^q-sign-algorithm=sha1/)
  assert.equal(req.init.headers['x-cos-security-token'], 'temp-token')
  assert.ok(!req.url.includes('temp-token'))
})

test('upload checks duplicates and skips COS when same name already exists', async () => {
  const root = await mkdtemp(join(tmpdir(), 'chem-ima-'))
  try {
    await writeFile(join(root, 'sample.pdf'), '%PDF-test')
    const operations = []
    await assert.rejects(uploadImaFile({ ...opts, root, filePath: join(root, 'sample.pdf'), knowledgeBaseId: 'base',
      request: async (url) => { operations.push(url); return response({ results: [{ is_repeated: true }] }) } }), /already has a file/)
    assert.equal(operations.length, 1)
    assert.match(operations[0], /check_repeated_names/)
  } finally { await rm(root, { recursive: true, force: true }) }
})

test('upload performs official create_media -> COS put -> add_knowledge', async () => {
  const root = await mkdtemp(join(tmpdir(), 'chem-ima-'))
  try {
    await writeFile(join(root, 'sample.md'), '# hello')
    const urls = []
    const request = async (url, init) => {
      urls.push(url)
      if (url.includes('check_repeated_names')) return response({ results: [{ is_repeated: false }] })
      if (url.includes('create_media')) return response({ media_id: 'media1', cos_credential: {
        secret_id: 'id', secret_key: 'secret', token: 'tmp', region: 'ap-guangzhou',
        appid: '123456', bucket_name: 'test', cos_key: 'bucket/sample.md',
      } })
      if (url.includes('.myqcloud.com')) { assert.equal(init.method, 'PUT'); return { ok: true, status: 200 } }
      if (url.includes('add_knowledge')) {
        const body = JSON.parse(init.body)
        assert.equal(body.media_type, 7)
        assert.equal(body.file_info.file_name, 'sample.md')
        return response({ media_id: 'media1' })
      }
      throw new Error('Unexpected URL ' + url)
    }
    const value = await uploadImaFile({ ...opts, root, filePath: join(root, 'sample.md'), knowledgeBaseId: 'base', request })
    assert.deepEqual(urls.map(url => url.includes('.myqcloud.com') ? 'COS' : url.split('/').pop()),
      ['check_repeated_names', 'create_media', 'COS', 'add_knowledge'])
    assert.equal(value.media_id, 'media1')
    assert.ok(!JSON.stringify(value).includes('tmp'))
  } finally { await rm(root, { recursive: true, force: true }) }
})

test('upload blocks paths outside the working directory', async () => {
  const root = await mkdtemp(join(tmpdir(), 'chem-ima-'))
  const other = await mkdtemp(join(tmpdir(), 'chem-ima-out-'))
  try {
    await writeFile(join(other, 'outside.txt'), 'private')
    await assert.rejects(uploadImaFile({ ...opts, root, filePath: join(other, 'outside.txt'), knowledgeBaseId: 'base', request: () => {
      throw new Error('No requests allowed')
    } }), /working folder/)
  } finally {
    await rm(root, { recursive: true, force: true })
    await rm(other, { recursive: true, force: true })
  }
})
