// P0 delivery receipt journal, not yet connected to ChemClaw's live group runtime.
//
// The group's message book and the separate receipts journal are not the same
// thing. A durable group message does not establish that its Bot recipient has
// seen it, and a successful DSH API return is not proof that tools finished.
//
// Protocol for future runtime integration:
// 1. Ensure the source group message has been fsynced in the group book.
// 2. Write an "attempt" record and await its fsync BEFORE calling DSH.
// 3. Call DSH once. If it returns, append an "api-returned" receipt and fsync.
// 4. After a crash, NEVER automatically retry an "attempt" without a receipt:
//    its delivery outcome is unknown. Even an "api-returned" receipt must not
//    cause replay, since subsequent Bot execution might already have occurred.
//
// An independent directory avoids colliding with the main group's book.
// The existing strict-lock + fsync Ledger writer is reused unchanged.
// No state.json, Session, inbox, round or live group delivery is modified.
import { createHash } from 'node:crypto'
import { join } from 'node:path'
import { createDurableGroupLedger } from './ledger-append.js'
import { readLedger } from './ledger-foundation.js'
import { publishInitialGroupBook } from './ledger-import.js'

const SAFE_ID = /^[A-Za-z0-9_-]{1,160}$/
const DELIVERY_STAGES = new Set(['attempt', 'api-returned'])
const DIGEST = /^[a-f0-9]{64}$/

function safeId(value, kind) {
  if (typeof value !== 'string' || !SAFE_ID.test(value)) {
    throw new Error('Invalid ' + kind + ' for group delivery journal')
  }
  return value
}
function positiveSeq(seq) {
  if (!Number.isSafeInteger(seq) || seq < 1) {
    throw new Error('Delivery receipt requires a positive group message sequence')
  }
  return seq
}
const bookOf = roomId => 'group-' + safeId(roomId, 'room id')
const receiptHome = home => join(home, 'delivery-receipts')

function verifyJournal(journal) {
  if (!journal) throw new Error('Delivery journal is not initialized')
  if (journal.incompleteTail !== '') {
    throw new Error('Delivery journal has an interrupted JSONL tail; no message may be resent')
  }
  const seen = new Map()
  for (let i = 0; i < journal.records.length; i++) {
    const entry = journal.records[i]
    if (!entry || typeof entry !== 'object' || Array.isArray(entry) ||
        entry.seq !== i + 1 || !DELIVERY_STAGES.has(entry.stage) ||
        typeof entry.deliveryId !== 'string' || !SAFE_ID.test(entry.deliveryId) ||
        typeof entry.recipientId !== 'string' || !SAFE_ID.test(entry.recipientId) ||
        !Number.isSafeInteger(entry.roomSeq) || entry.roomSeq < 1 ||
        typeof entry.sourceDigest !== 'string' || !DIGEST.test(entry.sourceDigest)) {
      throw new Error('Delivery journal is corrupt at sequence ' + (i + 1))
    }
    const earlier = seen.get(entry.deliveryId)
    if (entry.stage === 'attempt') {
      if (earlier) throw new Error('Delivery journal contains a repeated attempt for ' + entry.deliveryId)
      seen.set(entry.deliveryId, { ...entry, status: 'unknown' })
    } else {
      if (!earlier || earlier.status !== 'unknown' ||
          earlier.roomSeq !== entry.roomSeq || earlier.recipientId !== entry.recipientId ||
          earlier.sourceDigest !== entry.sourceDigest) {
        throw new Error('Delivery journal contains an unmatched API receipt for ' + entry.deliveryId)
      }
      seen.set(entry.deliveryId, { ...earlier, status: 'api-returned' })
    }
  }
  return seen
}

function verifyGroupLedger(book) {
  if (!book || book.incompleteTail !== '') {
    throw new Error('Group message Ledger is missing or has a damaged final record')
  }
  for (let index = 0; index < book.records.length; index++) {
    const record = book.records[index]
    if (!record || record.seq !== index + 1 ||
        record.legacyIncomplete === true ||
        (record.length !== undefined &&
          (typeof record.text !== 'string' || record.text.length !== record.length))) {
      throw new Error('Group message Ledger is incomplete or has inconsistent history')
    }
  }
}
function sourceDigest(record) {
  return createHash('sha256').update(JSON.stringify(record)).digest('hex')
}
async function requireDurableMessage(home, roomId, roomSeq) {
  const book = await readLedger(home, bookOf(roomId))
  verifyGroupLedger(book)
  const record = book.records[roomSeq - 1]
  if (!record || record.seq !== roomSeq) {
    throw new Error('Group message must be durable before recording a delivery attempt')
  }
  return sourceDigest(record)
}

export async function inspectGroupDeliveries(home, roomId) {
  const book = bookOf(roomId)
  const journal = await readLedger(receiptHome(home), book)
  if (!journal) return { status: 'not-initialized', entries: [], mustNotRedispatch: true }
  try {
    const byId = verifyJournal(journal)
    const group = await readLedger(home, book)
    verifyGroupLedger(group)
    for (const receipt of byId.values()) {
      const record = group.records[receipt.roomSeq - 1]
      if (!record || record.seq !== receipt.roomSeq) {
        throw new Error('Delivery journal references a missing group message')
      }
      if (receipt.sourceDigest !== sourceDigest(record)) {
        throw new Error('Delivery journal source message changed since attempt')
      }
    }
    return {
      status: 'ready',
      entries: [...byId.values()].map(entry => ({
        deliveryId: entry.deliveryId, roomSeq: entry.roomSeq,
        recipientId: entry.recipientId, status: entry.status,
      })),
      mustNotRedispatch: true,
    }
  } catch (error) {
    return {
      status: 'blocked', reason: String(error.message ?? error),
      entries: [], mustNotRedispatch: true,
    }
  }
}

export function createGroupDeliveryJournal({ home, assertWriter } = {}) {
  if (typeof home !== 'string' || !home) throw new Error('Delivery journal home is required')
  if (typeof assertWriter !== 'function') {
    throw new Error('Delivery journal needs an exclusive-writer check')
  }
  const root = receiptHome(home)
  const durable = createDurableGroupLedger({ home: root, assertWriter })
  // The outer queue ensures concurrent begin/accept calls first inspect the
  // previous durable event, assign a unique journal seq, then append in order.
  const queues = new Map()
  function run(roomId, action) {
    const book = bookOf(roomId)
    const prior = queues.get(book) ?? Promise.resolve()
    const job = prior.then(() => action(book))
    queues.set(book, job)
    return job
  }
  async function journalFor(roomId) {
    const journal = await readLedger(root, bookOf(roomId))
    return { journal, seen: verifyJournal(journal) }
  }
  const ensureWriter = async book => {
    if ((await assertWriter(book)) !== true) {
      throw new Error('Exclusive writer lock not confirmed for delivery journal')
    }
  }

  const initialize = roomId => run(roomId, async book => {
    await ensureWriter(book)
    // A genuinely empty new group is allowed; a damaged or discontinuous
    // source book must never receive delivery receipts.
    verifyGroupLedger(await readLedger(home, book))
    return publishInitialGroupBook(root, book, [])
  })

  const begin = async ({ roomId, roomSeq, deliveryId, recipientId }) => {
    bookOf(roomId)
    positiveSeq(roomSeq)
    safeId(deliveryId, 'delivery id')
    safeId(recipientId, 'recipient id')
    return run(roomId, async book => {
      await ensureWriter(book)
      const digest = await requireDurableMessage(home, roomId, roomSeq)
      const { journal, seen } = await journalFor(roomId)
      if (seen.has(deliveryId) || [...seen.values()].some(item =>
        item.roomSeq === roomSeq && item.recipientId === recipientId)) {
        throw new Error('Delivery already attempted for this message/recipient; a retry could duplicate Bot work')
      }
      const event = { seq: journal.records.length + 1, stage: 'attempt',
        deliveryId, roomSeq, recipientId, sourceDigest: digest }
      await durable.append(book, event)
      return { status: 'attempt-recorded', roomSeq, deliveryId }
    })
  }

  const markApiReturned = async ({ roomId, roomSeq, deliveryId, recipientId }) => {
    bookOf(roomId)
    positiveSeq(roomSeq)
    safeId(deliveryId, 'delivery id')
    safeId(recipientId, 'recipient id')
    return run(roomId, async book => {
      await ensureWriter(book)
      const digest = await requireDurableMessage(home, roomId, roomSeq)
      const { journal, seen } = await journalFor(roomId)
      const earlier = seen.get(deliveryId)
      if (!earlier || earlier.roomSeq !== roomSeq || earlier.recipientId !== recipientId ||
          earlier.sourceDigest !== digest) {
        throw new Error('Cannot accept a missing or mismatched delivery attempt')
      }
      if (earlier.status === 'api-returned') return { status: 'api-returned', reused: true }
      await durable.append(book, { seq: journal.records.length + 1,
        stage: 'api-returned', deliveryId, roomSeq, recipientId, sourceDigest: digest })
      return { status: 'api-returned', reused: false }
    })
  }

  // Intended for future DSH integration. Never treat an API return as proof of
  // successful Bot reasoning/tool execution; the receipt means only API returned.
  const dispatchOnce = async ({ roomId, roomSeq, deliveryId, recipientId, send }) => {
    if (typeof send !== 'function') throw new Error('A delivery callback is required')
    await begin({ roomId, roomSeq, deliveryId, recipientId })
    const response = await send()
    await markApiReturned({ roomId, roomSeq, deliveryId, recipientId })
    return response
  }

  return {
    initialize, begin, markApiReturned, dispatchOnce,
    inspect: roomId => inspectGroupDeliveries(home, roomId),
    written: roomId => durable.written(bookOf(roomId)),
  }
}
