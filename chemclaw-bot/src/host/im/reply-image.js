import { constants } from 'node:fs'
import { open } from 'node:fs/promises'
import { basename } from 'node:path'
import { resolveArtifacts } from '../artifact-paths.js'

import { detectImageMediaType, FILE_LIMIT } from './platforms/media.js'

const MAX_IMAGE_BYTES = 10 * 1024 * 1024

async function readWorkspaceAttachment(rt, { sessionId, botId, path }, limit, { exact = false } = {}) {
  const { files } = await resolveArtifacts(rt, { sessionId, botId, values: [path], exact }, AbortSignal.timeout(5_000))
  if (files[path] === undefined) throw new Error('File is outside the conversation workspace or unavailable')
  const file = await open(files[path], constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK)
  try {
    const stat = await file.stat()
    if (!stat.isFile() || stat.size === 0 || stat.size > limit) throw new Error(`Attachment must be a non-empty file up to ${limit / (1024 * 1024)} MB`)
    const data = Buffer.alloc(stat.size)
    let offset = 0
    while (offset < data.length) {
      const { bytesRead } = await file.read(data, offset, data.length - offset, offset)
      if (bytesRead === 0) throw new Error('Attachment changed while reading')
      offset += bytesRead
    }
    const end = await file.stat()
    if (end.size !== stat.size || end.mtimeMs !== stat.mtimeMs) throw new Error('Attachment changed while reading')
    return { name: basename(files[path]), data }
  } finally {
    await file.close()
  }
}

export async function readReplyImage(rt, request) {
  const { name, data } = await readWorkspaceAttachment(rt, request, MAX_IMAGE_BYTES)
  const mime = detectImageMediaType(data)
  if (!mime) throw new Error('Unsupported IM image format')
  return { mime, name, bytes: data.toString('base64') }
}

export async function readReplyFile(rt, request) {
  const file = await readWorkspaceAttachment(rt, request, FILE_LIMIT, { exact: true })
  if (/\.(?:svg|html?)$/iu.test(file.name)) {
    const content = file.data.toString('utf8')
    if (rt.redactSecrets(content) !== content) throw new Error('Attachment contains a stored secret')
  }
  return file
}
