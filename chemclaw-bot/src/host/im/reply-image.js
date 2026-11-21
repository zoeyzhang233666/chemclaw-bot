import { constants } from 'node:fs'
import { open } from 'node:fs/promises'
import { resolveArtifacts } from '../artifact-paths.js'

import { detectImageMediaType } from './platforms/media.js'

const MAX_IMAGE_BYTES = 10 * 1024 * 1024

export async function readReplyImage(rt, { sessionId, botId, path }) {
  const { files } = await resolveArtifacts(rt, { sessionId, botId, values: [path] }, AbortSignal.timeout(5_000))
  if (files[path] === undefined) throw new Error('Image is outside the conversation workspace or unavailable')
  const file = await open(files[path], constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK)
  try {
    const stat = await file.stat()
    if (!stat.isFile() || stat.size === 0 || stat.size > MAX_IMAGE_BYTES) throw new Error('Image must be a file up to 10 MB')
    const size = stat.size
    const data = Buffer.alloc(size)
    const { bytesRead } = await file.read({ buffer: data, length: size })
    const bytes = data.subarray(0, bytesRead)
    const mime = detectImageMediaType(bytes)
    if (!mime) throw new Error('Unsupported IM image format')
    return { mime, bytes: bytes.toString('base64') }
  } finally {
    await file.close()
  }
}
