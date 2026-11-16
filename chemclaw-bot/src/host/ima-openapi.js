// Tencent ima OpenAPI adapter. Credentials stay in ChemClaw's secrets store and are
// sent only to https://ima.qq.com. The provider is not an MCP server.
import { createHash, createHmac } from 'node:crypto'
import { readFile, stat } from 'node:fs/promises'
import { basename, extname, resolve } from 'node:path'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { within } from './folders.js'

export const IMA_CLIENT_ID = 'IMA_CLIENT_ID'
export const IMA_API_KEY = 'IMA_API_KEY'
const API_ORIGIN = 'https://ima.qq.com'
const LIMIT = 512_000
const UPLOAD_LIMIT = 50 * 1024 * 1024

// Explicit allowlist: never let a model choose a URL or an undocumented deletion action.
// The legacy and new note list/search names are both present in published ima skills.
export const IMA_OPERATIONS = Object.freeze({
  'wiki.search_knowledge_base': false,
  'wiki.get_knowledge_base': false,
  'wiki.get_knowledge_list': false,
  'wiki.search_knowledge': false,
  'wiki.get_addable_knowledge_base_list': false,
  'wiki.get_media_info': false,
  'wiki.check_repeated_names': false,
  'wiki.import_urls': true,
  'wiki.add_knowledge': true,
  'wiki.create_folder': true,
  'wiki.rename_knowledge': true,
  'wiki.move_knowledge': true,
  'wiki.tag_add': true,
  'note.search_note_book': false,
  'note.list_note_folder_by_cursor': false,
  'note.list_note_by_folder_id': false,
  'note.search_note': false,
  'note.list_notebook': false,
  'note.list_note': false,
  'note.get_doc_content': false,
  'note.export_note': false,
  'note.import_doc': true,
  'note.append_doc': true,
  'note.update_note': true,
})

const string = value => typeof value === 'string' && value.trim().length > 0
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const brief = value => String(value ?? '').slice(0, 200)
const cleanImaError = (value, clientId, apiKey) => brief(value).replaceAll(clientId, '[secret:IMA_CLIENT_ID]').replaceAll(apiKey, '[secret:IMA_API_KEY]')

export async function callImaApi({ clientId, apiKey, operation, body = {}, request = globalThis.fetch, signal }) {
  if (!string(clientId) || !string(apiKey)) throw new Error('Connect your ima Client ID and API Key in Settings → Connectors first.')
  if (!Object.hasOwn(IMA_OPERATIONS, operation) && operation !== 'wiki.create_media') throw new Error('Unsupported ima operation (delete is not offered by the published OpenAPI).')
  if (!object(body)) throw new Error('ima request body must be a JSON object.')
  const [domain, method] = operation.split('.')
  const url = `${API_ORIGIN}/openapi/${domain}/v1/${method}`
  let response
  try {
    response = await request(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'ima-openapi-clientid': clientId, 'ima-openapi-apikey': apiKey },
      body: JSON.stringify(body),
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(25_000)]) : AbortSignal.timeout(25_000),
    })
  } catch {
    throw new Error('Could not reach ima OpenAPI.')
  }
  if (!response.ok) throw new Error(`ima OpenAPI returned HTTP ${response.status}.`)
  const raw = await response.text()
  if (raw.length > LIMIT) throw new Error('ima response too large; narrow the search.')
  let json
  try { json = JSON.parse(raw) } catch { throw new Error('ima OpenAPI returned invalid JSON.') }
  if (json?.code !== 0) throw new Error(`ima OpenAPI error ${brief(json?.code)}: ${cleanImaError(json?.msg ?? 'request rejected', clientId, apiKey)}`)
  if (!object(json.data) && !Array.isArray(json.data)) throw new Error('ima OpenAPI returned no data.')
  return json.data
}

const MEDIA = Object.freeze({
  pdf: [1, 'application/pdf'],
  doc: [3, 'application/msword'], docx: [3, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
  ppt: [4, 'application/vnd.ms-powerpoint'], pptx: [4, 'application/vnd.openxmlformats-officedocument.presentationml.presentation'],
  xls: [5, 'application/vnd.ms-excel'], xlsx: [5, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
  csv: [5, 'text/csv'], md: [7, 'text/markdown'], markdown: [7, 'text/markdown'],
  png: [9, 'image/png'], jpg: [9, 'image/jpeg'], jpeg: [9, 'image/jpeg'], webp: [9, 'image/webp'],
  txt: [13, 'text/plain'], xmind: [14, 'application/x-xmind'],
  mp3: [15, 'audio/mpeg'], m4a: [15, 'audio/x-m4a'], wav: [15, 'audio/wav'],
})
const hex = (alg, key, text) => createHmac(alg, key).update(text).digest('hex')
const sha1 = text => createHash('sha1').update(text).digest('hex')

export function cosUploadRequest(credential, data, mime, now = Math.floor(Date.now() / 1000)) {
  const { secret_id: id, secret_key: secret, token, region, appid, bucket_name: bucket, cos_key: key } = credential ?? {}
  if (![id, secret, token, region, appid, bucket, key].every(string)) throw new Error('ima did not supply complete temporary COS credentials.')
  if (!/^[a-z0-9-]+$/i.test(region) || !/^[a-z0-9-]+$/i.test(bucket) || !/^\d+$/.test(appid)) throw new Error('Unexpected COS bucket or region.')
  const bucketFull = bucket.endsWith(`-${appid}`) ? bucket : `${bucket}-${appid}`
  const host = `${bucketFull}.cos.${region}.myqcloud.com`
  const path = '/' + key.replace(/^\/+/, '').split('/').map(encodeURIComponent).join('/')
  const start = Math.max(now, Number(credential.start_time) || now)
  const end = Math.min(start + 600, Number(credential.expired_time) || start + 600)
  if (end <= start) throw new Error('ima COS upload credentials have expired.')
  const time = `${start};${end}`
  const http = `put\n${path}\n\nhost=${host}\n`
  const toSign = `sha1\n${time}\n${sha1(http)}\n`
  const signature = hex('sha1', hex('sha1', secret, time), toSign)
  const authorization = `q-sign-algorithm=sha1&q-ak=${id}&q-sign-time=${time}&q-key-time=${time}&q-header-list=host&q-url-param-list=&q-signature=${signature}`
  return {
    url: `https://${host}${path}`,
    init: { method: 'PUT', headers: { Authorization: authorization, 'x-cos-security-token': token, 'Content-Type': mime }, body: data },
  }
}

export async function uploadImaFile({ clientId, apiKey, filePath, root, knowledgeBaseId, folderId, allowDuplicate = false, request = globalThis.fetch, signal }) {
  if (!string(root) || !string(filePath) || !within(resolve(filePath), resolve(root))) throw new Error('Files can only be uploaded from the active Bot working folder.')
  if (!string(knowledgeBaseId)) throw new Error('Choose an ima knowledge base first.')
  const title = basename(filePath)
  const ext = extname(title).slice(1).toLowerCase()
  const format = MEDIA[ext]
  if (!format) throw new Error('ima does not support uploading this file type.')
  const details = await stat(filePath)
  if (!details.isFile() || details.size <= 0 || details.size > UPLOAD_LIMIT) throw new Error('Upload requires a nonempty file up to 50 MB.')
  const api = (operation, body) => callImaApi({ clientId, apiKey, operation, body, request, signal })
  const target = { knowledge_base_id: knowledgeBaseId, ...(folderId ? { folder_id: folderId } : {}) }
  if ([1, 3, 4, 5, 7, 9, 13, 14].includes(format[0])) {
    const duplicates = await api('wiki.check_repeated_names', { ...target, params: [{ name: title, media_type: format[0] }] })
    if (!allowDuplicate && duplicates.results?.some(row => row.is_repeated)) throw new Error('ima already has a file with this name. Choose another name or explicitly allow duplicates.')
  }
  const created = await api('wiki.create_media', { // Special internal step, never exposed as a model-callable operation.
    ...target, file_name: title, file_size: details.size, content_type: format[1], file_ext: ext,
  })
  const credential = created.cos_credential
  const data = await readFile(filePath)
  const put = cosUploadRequest(credential, data, format[1])
  let uploaded
  try { uploaded = await request(put.url, { ...put.init, signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(60_000)]) : AbortSignal.timeout(60_000) }) }
  catch { throw new Error('Could not upload the file to ima COS.') }
  if (!uploaded.ok) throw new Error(`ima COS upload returned HTTP ${uploaded.status}.`)
  const result = await api('wiki.add_knowledge', {
    ...target, media_type: format[0], media_id: created.media_id, title,
    file_info: { cos_key: credential.cos_key, file_size: details.size, last_modify_time: Math.floor(details.mtimeMs / 1000), file_name: title },
  })
  return { knowledge_base_id: knowledgeBaseId, media_id: result.media_id ?? created.media_id, title, status: 'uploaded' }
}

const output = { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] }
const serialize = value => {
  const text = JSON.stringify(value)
  return text.length > 65_000 ? `${text.slice(0, 65_000)}… [truncated; narrow the query]` : text
}

export function install(rt) {
  const { ctx } = rt
  const credentials = () => ({ clientId: rt.secretValue(IMA_CLIENT_ID), apiKey: rt.secretValue(IMA_API_KEY) })
  const request = rt.config.imaFetch ?? globalThis.fetch
  ctx.tools.register(defineTool({
    name: 'ima_openapi',
    description: 'Access the connected user’s Tencent ima knowledge bases and notes via official OpenAPI. Read: list/search knowledge bases and notes, read document content. Write: import web/WeChat URLs, create/append/edit notes, create/move/rename/tag knowledge entries. Use ONLY for a user-requested action. Do not guess target IDs. For file bytes use ima_upload_file. Deletion is not supported. Each operation uses a JSON object as body_json. Never put credentials in this input.',
    parameters: {
      operation: { type: 'string', required: true, enum: Object.keys(IMA_OPERATIONS), description: 'Official endpoint prefixed with wiki. or note.' },
      body_json: { type: 'string', required: true, description: 'A JSON object with endpoint parameters, e.g. {"query":"SBS","cursor":"","limit":20} for wiki.search_knowledge_base; for wiki.import_urls use {"knowledge_base_id":"id","folder_id":"id","urls":["https://..."]}; for note.import_doc use {"content_format":1,"content":"# Title"}. Folder ID equals base ID for root import.' },
    }, output,
    async execute(args, exec) {
      if (IMA_OPERATIONS[args.operation] && rt.readOnly()) throw new Error(rt.readOnly())
      let body
      try { body = JSON.parse(args.body_json) } catch { throw new Error('body_json must be valid JSON.') }
      const result = await callImaApi({ ...credentials(), operation: args.operation, body, request, signal: exec.signal })
      // Temporary COS credentials and protected media headers must not enter the model context.
      if (args.operation === 'wiki.get_media_info' && result.url_info?.headers) {
        return serialize({ ...result, url_info: { ...result.url_info, headers: '[authorization headers hidden; use ima client for protected files]' } })
      }
      return serialize(result)
    },
  }))
  ctx.tools.register(defineTool({
    name: 'ima_upload_file',
    description: 'Upload an existing local file from the active Bot working folder to the user’s ima knowledge base using ima OpenAPI and its temporary COS upload credentials. Only on explicit user request. Supported: PDF, Office, Markdown, image, TXT, audio, XMind. Repeated names are rejected unless explicitly requested. No delete.',
    parameters: {
      file_path: { type: 'string', required: true, description: 'Absolute path of a file inside your current Bot working folder' },
      knowledge_base_id: { type: 'string', required: true },
      folder_id: { type: 'string', description: 'Target folder ID; omit to upload to root' },
      allow_duplicate: { type: 'boolean', description: 'Only true after user explicitly permits an existing filename duplicate' },
    }, output,
    async execute(args, exec) {
      if (rt.readOnly()) throw new Error(rt.readOnly())
      const bot = rt.botOf(rt.selfOf(exec.agent?.id))
      const root = bot?.workDir || rt.config.workspace || ctx.workspaceRegistry.get?.(rt.state.workspaceId)?.path
      return serialize(await uploadImaFile({
        ...credentials(), filePath: args.file_path, root,
        knowledgeBaseId: args.knowledge_base_id, folderId: args.folder_id,
        allowDuplicate: args.allow_duplicate === true, request, signal: exec.signal,
      }))
    },
  }))
}
