// P0 append-only group ledger writer, not yet connected to the live group runtime.
//
// A returned append Promise resolves only after the JSONL row has reached fsync.
// The caller must await it BEFORE delivering the corresponding group message.
// A failed write poisons that book's queue; never pretend delivery was durable,
// auto-retry an uncertain write, or continue issuing messages on that book.
//
// IMPORTANT: assertWriter must prove ownership of the team's exclusive lock.
// readOnly() === undefined is NOT enough when store.js used its lockBroken fallback.
import { open } from 'node:fs/promises'
import { join } from 'node:path'
import { isDeepStrictEqual } from 'node:util'
import { ledgerFilename, readLedger } from './ledger-foundation.js'

const GROUP_BOOK = /^group-[A-Za-z0-9_-]{1,160}$/

function ensureRecord(record) {
  if (!record || Array.isArray(record) || typeof record !== 'object' ||
      !Number.isSafeInteger(record.seq) || record.seq < 1) {
    throw new Error('Group ledger record requires a positive integer seq')
  }
  const line = JSON.stringify(record)
  if (typeof line !== 'string') throw new Error('Group ledger record could not be encoded')
  return line + '\n'
}

function validateBook(records) {
  for (let i = 0; i < records.length; i++) {
    if (records[i]?.seq !== i + 1) {
      throw new Error('The group ledger is not consecutive; cannot append')
    }
  }
}

export function createDurableGroupLedger({ home, assertWriter, beforeWrite } = {}) {
  if (typeof home !== 'string' || !home) throw new Error('A group ledger home is required')
  if (typeof assertWriter !== 'function') {
    throw new Error('Ledger append requires an explicit exclusive-writer check')
  }
  // Keep failures here, not as catch(() => {}) promises: a broken book is closed
  // until the application explicitly recreates this writer after inspection.
  const queues = new Map()
  const append = (book, record) => {
    if (typeof book !== 'string' || !GROUP_BOOK.test(book)) {
      return Promise.reject(new Error('Only a safe group ledger book can be appended'))
    }
    const previous = queues.get(book) ?? Promise.resolve()
    const job = previous.then(async () => {
      if ((await assertWriter(book)) !== true) {
        throw new Error('Exclusive writer lock not confirmed; group ledger write refused')
      }
      const line = ensureRecord(record)
      const current = await readLedger(home, book)
      if (current === undefined) throw new Error('Group ledger is not initialized; import it before writing')
      if (current.incompleteTail !== '') {
        throw new Error('Group ledger has a truncated final line; inspect the disk before writing')
      }
      validateBook(current.records)
      const last = current.records.length
      if (record.seq <= last) {
        if (isDeepStrictEqual(current.records[record.seq - 1], record)) {
          return { seq: record.seq, reused: true }
        }
        throw new Error('Group ledger already has a different record at seq ' + record.seq)
      }
      if (record.seq !== last + 1) {
        throw new Error('Group ledger cannot skip from seq ' + last + ' to ' + record.seq)
      }
      // A failed hook here represents a rejected/failed write before the first
      // byte. Real I/O or fsync failures below also reject and poison this book.
      await beforeWrite?.(book, record)
      const handle = await open(join(home, 'ledger', ledgerFilename(book)), 'a')
      try {
        await handle.writeFile(line, 'utf8')
        await handle.sync()
      } finally {
        await handle.close()
      }
      // No side effect may be delivered by the caller until this resolves.
      return { seq: record.seq, reused: false }
    })
    queues.set(book, job)
    return job
  }
  const written = book => queues.get(book) ?? Promise.resolve()
  const flush = book => book === undefined ? Promise.all([...queues.values()]) : written(book)
  return { append, written, flush }
}
