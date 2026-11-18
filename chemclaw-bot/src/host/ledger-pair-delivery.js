// DS-Bot #1358 pair exchange book, strict ChemClaw writer. This library is not
// enabled for production delivery until the complete pair/UI cutover is validated.
// The journal never replays an unknown DSH delivery after a crash.
import { createDurableGroupLedger } from './ledger-append.js'
import { readLedger } from './ledger-foundation.js'
import { publishInitialPairBook } from './ledger-import.js'

const SAFE_BOT = /^[A-Za-z0-9_-]{1,72}$/
const SAFE_MESSAGE = /^[A-Za-z0-9_-]{1,160}$/
const ROLES = new Set(['request', 'reply', 'stopped'])
const valid = (value, pattern, kind) => {
  if (typeof value !== 'string' || !pattern.test(value)) throw new Error('Invalid pair Ledger ' + kind)
  return value
}
export function pairBook(a, b) {
  const ids = [valid(a, SAFE_BOT, 'Bot id'), valid(b, SAFE_BOT, 'Bot id')].sort()
  if (ids[0] === ids[1]) throw new Error('A pair Ledger requires two different Bots')
  return 'pair-' + ids.join('-')
}

function verified(book) {
  if (book === undefined || book.incompleteTail !== '') {
    throw new Error('Pair Ledger missing or interrupted: no automatic replay')
  }
  const messages = new Map()
  const acknowledged = new Map()
  for (const [index, row] of book.records.entries()) {
    if (row?.seq !== index + 1) throw new Error('Pair Ledger sequence is inconsistent')
    valid(row.id, SAFE_MESSAGE, 'exchange id')
    if (row.event === undefined) {
      if (!ROLES.has(row.role) || typeof row.text !== 'string' ||
          typeof row.from !== 'string' || typeof row.to !== 'string') {
        throw new Error('Pair Ledger has an invalid message record')
      }
      messages.set(row.id, row)
      if (row.delivered === true) acknowledged.set(row.id, row.seq)
    } else if (row.event === 'delivered') {
      const latest = messages.get(row.id)
      if (latest === undefined || row.attemptSeq !== latest.seq ||
          typeof row.sessionId !== 'string') {
        throw new Error('Pair Ledger has a mismatched delivery receipt')
      }
      acknowledged.set(row.id, row.attemptSeq)
    } else throw new Error('Pair Ledger has an unknown event')
  }
  const delivered = [...messages.values()].filter(row => acknowledged.get(row.id) === row.seq)
  const uncertain = [...messages.values()].filter(row => acknowledged.get(row.id) !== row.seq)
  return { rows: book.records, messages, delivered, uncertain }
}

export function createPairDeliveryJournal({ home, assertWriter } = {}) {
  if (typeof home !== 'string' || home.length === 0) throw new Error('Pair Ledger home is required')
  if (typeof assertWriter !== 'function') throw new Error('Pair Ledger requires an exclusive-writer check')
  const ledger = createDurableGroupLedger({ home, assertWriter, bookKind: 'pair' })
  const pending = new Map()
  // Serialize even the seq allocation, not only writes to the JSONL file.
  const exclusive = (book, operation) => {
    const run = (pending.get(book) ?? Promise.resolve()).then(operation)
    pending.set(book, run.catch(() => {}))
    return run
  }
  const inspect = async (a, b) => {
    const book = pairBook(a, b)
    const file = await readLedger(home, book)
    return file === undefined ? undefined : verified(file)
  }
  const seed = (a, b, legacy = []) => exclusive(pairBook(a, b), async () => {
    if (!Array.isArray(legacy)) throw new Error('Pair Ledger legacy exchanges must be an array')
    const book = pairBook(a, b)
    const existing = await inspect(a, b)
    if (existing !== undefined) return { reused: true, imported: existing.delivered.length }
    if (await assertWriter(book) !== true) throw new Error('Pair Ledger exclusive writer not confirmed')
    const rows = legacy.filter(row => row?.from !== undefined && row?.to !== undefined &&
      pairBook(row.from, row.to) === book).map((row, index) => {
      valid(row.id, SAFE_MESSAGE, 'legacy exchange id')
      if (!ROLES.has(row.role) || typeof row.text !== 'string') throw new Error('Invalid legacy exchange')
      return { ...row, seq: index + 1, delivered: true }
    })
    const result = await publishInitialPairBook(home, book, rows)
    verified(await readLedger(home, book))
    return { ...result, imported: rows.length }
  })
  const begin = ({ a, b, id, from, to, role, text, ...optional }) => exclusive(pairBook(a, b), async () => {
    valid(id, SAFE_MESSAGE, 'exchange id')
    if (!ROLES.has(role) || typeof text !== 'string') throw new Error('Invalid pair Ledger message')
    if (pairBook(from, to) !== pairBook(a, b)) throw new Error('Pair Ledger has the wrong sender or receiver')
    const book = pairBook(a, b)
    const current = verified(await readLedger(home, book))
    if (current.messages.has(id)) throw new Error('Pair Ledger exchange was attempted already; cannot replay an uncertain delivery')
    const seq = current.rows.length + 1
    const record = { seq, id, from, to, role, text, time: Date.now(),
      ...(typeof optional.replyTo === 'string' ? { replyTo: optional.replyTo } : {}),
      ...(optional.audience === 'user' ? { audience: 'user' } : {}),
      ...(typeof optional.roomId === 'string' ? { roomId: optional.roomId } : {}),
    }
    await ledger.append(book, record)
    return { book, seq, id }
  })
  const delivered = ({ a, b, id, sessionId }) => exclusive(pairBook(a, b), async () => {
    const book = pairBook(a, b)
    valid(id, SAFE_MESSAGE, 'exchange id')
    if (typeof sessionId !== 'string' || sessionId === '') throw new Error('Pair Ledger requires recipient Session id')
    const current = verified(await readLedger(home, book))
    const attempt = current.messages.get(id)
    if (attempt === undefined) throw new Error('No recorded pair delivery attempt')
    if (current.delivered.some(row => row.id === id)) return { reused: true }
    await ledger.append(book, { seq: current.rows.length + 1, event: 'delivered',
      id, attemptSeq: attempt.seq, sessionId, time: Date.now() })
    return { reused: false }
  })
  return { seed, begin, delivered, inspect, written: ledger.written }
}
