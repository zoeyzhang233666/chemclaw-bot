import { randomBytes } from 'node:crypto'

// Waits between attempts to open an IM connection when the network is down (#1119).
// The first wait is short so a brief drop recovers quickly; it grows to a cap and
// repeats, so a long outage is retried at a steady pace instead of a request loop.
export const RETRY_DELAYS_MS = [250, 500, 1_000, 2_000, 5_000, 15_000, 30_000]

export const retryDelay = attempt => RETRY_DELAYS_MS[Math.min(Math.max(attempt, 0), RETRY_DELAYS_MS.length - 1)]

// A wait a stopped adapter leaves behind: it does not hold the process, and every
// retry loop checks `stopped` once it returns.
export const retryWait = ms => new Promise((resolve) => {
  const timer = setTimeout(resolve, ms)
  timer.unref?.()
})

// The IM queue retains the same job across retries and reconnects. A successful
// prefix must stay delivered even if a later chunk fails or the handle restarts.
const acceptedChunks = new WeakMap()
const deliveryKeys = new WeakMap()

// Feishu and Discord accept a client token for deduplication. Every chunk gets
// its own token, and an attempt after a reconnect uses the original token.
export function deliveryKey(job, index = 0) {
  let key = deliveryKeys.get(job)
  if (key === undefined) {
    key = randomBytes(8).toString('hex')
    deliveryKeys.set(job, key)
  }
  return `${key}-${index}`
}

// An API without client deduplication may have accepted a message when its
// acknowledgement is lost. The queue must not retry that publish.
export async function sendOnce(publish) {
  try {
    return await publish()
  } catch (error) {
    if (error?.permanent || error?.stopped || error?.retryAfter !== undefined
        || (error?.status >= 400 && error.status < 500)) throw error
    throw Object.assign(new Error(error?.message ?? 'Message delivery is uncertain', { cause: error }), { unknown: true })
  }
}

export async function sendChunks(job, chunks, send) {
  const { count = 0, messageId: previousId } = acceptedChunks.get(job) ?? {}
  let messageId = previousId
  for (let index = count; index < chunks.length; index++) {
    messageId = await send(chunks[index], index === chunks.length - 1, messageId, index)
    acceptedChunks.set(job, { count: index + 1, messageId })
  }
  acceptedChunks.delete(job)
  return { messageId }
}
