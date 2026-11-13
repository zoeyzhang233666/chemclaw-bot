// P0 append-only group ledger writer, not yet connected to the live group runtime.
//
// A returned append Promise resolves only after the JSONL row has reached fsync
// AND the canonical ledger path has been verified. The caller must await it
// before delivering its corresponding group message. A failure poisons that
// book's queue: an uncertain write is never automatically retried.
//
// IMPORTANT: assertWriter must establish EXCLUSIVE ownership of state.lock.
// Legacy readOnly() === undefined is not sufficient if locking degraded.
//
// Performance: validate the entire book once per writer/book, then cache the
// last confirmed sequence, file identity and exact last-line bytes. Subsequent
// normal appends inspect only file metadata, a bounded tail and the new row.
// A restarted writer revalidates the whole book before its first write.
import { open } from 'node:fs/promises'
import { join } from 'node:path'
import { isDeepStrictEqual } from 'node:util'
import { decodeLedger, ledgerFilename, readLedger } from './ledger-foundation.js'

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
  for (let index = 0; index < records.length; index++) {
    if (records[index]?.seq !== index + 1) {
      throw new Error('The group ledger is not consecutive; cannot append')
    }
  }
}

function fingerprint(stats) {
  return {
    dev: stats.dev, ino: stats.ino, size: stats.size,
    mtimeNs: stats.mtimeNs, ctimeNs: stats.ctimeNs,
  }
}
function sameFile(a, b) {
  return a.dev === b.dev && a.ino === b.ino && a.size === b.size
}
function sameVersion(a, b) {
  return sameFile(a, b) && a.mtimeNs === b.mtimeNs && a.ctimeNs === b.ctimeNs
}
function byteOffset(stats) {
  const size = Number(stats.size)
  if (!Number.isSafeInteger(size) || size < 0) {
    throw new Error('Group ledger is too large to append safely')
  }
  return size
}
async function verifyTail(handle, offset, bytes) {
  if (bytes.length === 0) return
  const actual = Buffer.alloc(bytes.length)
  let n = 0
  while (n < bytes.length) {
    const result = await handle.read(actual, n, bytes.length - n, offset + n)
    if (result.bytesRead <= 0) throw new Error('Group ledger tail was not fully readable')
    n += result.bytesRead
  }
  if (!actual.equals(bytes)) throw new Error('Group ledger last record changed unexpectedly')
}

export function createDurableGroupLedger({ home, assertWriter, beforeWrite, loadBook = readLedger } = {}) {
  if (typeof home !== 'string' || !home) throw new Error('A group ledger home is required')
  if (typeof assertWriter !== 'function') {
    throw new Error('Ledger append requires an explicit exclusive-writer check')
  }
  if (typeof loadBook !== 'function') throw new Error('Ledger full-book reader is required')

  const queues = new Map()
  // A cache is retained only after an fsynced and canonically verified write.
  const confirmed = new Map()
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
      const cached = confirmed.get(book)
      let full
      if (!cached) {
        full = await loadBook(home, book)
        if (full === undefined) throw new Error('Group ledger is not initialized; import it before writing')
        if (full.incompleteTail !== '') {
          throw new Error('Group ledger has a truncated final line; inspect the disk before writing')
        }
        validateBook(full.records)
      }
      const last = cached ? cached.seq : full.records.length

      // Replays are rare; always check their durable historical record instead
      // of blindly trusting the cache, then return without re-delivering.
      if (record.seq <= last) {
        const replay = full ?? await loadBook(home, book)
        if (replay === undefined || replay.incompleteTail !== '' ||
            replay.records.length !== last || !isDeepStrictEqual(replay.records[record.seq - 1], record)) {
          throw new Error('Group ledger already has a different record at seq ' + record.seq)
        }
        return { seq: record.seq, reused: true }
      }
      if (record.seq !== last + 1) {
        throw new Error('Group ledger cannot skip from seq ' + last + ' to ' + record.seq)
      }

      // This hook is only for fault injection / preflight. A failure leaves the
      // book queue poisoned, and no caller is allowed to report a delivery.
      await beforeWrite?.(book, record)
      const path = join(home, 'ledger', ledgerFilename(book))
      // 'r+' refuses a deleted book instead of silently creating a new one.
      const handle = await open(path, 'r+')
      let writtenStat
      let offset
      const bytes = Buffer.from(line, 'utf8')
      try {
        const before = fingerprint(await handle.stat({ bigint: true }))
        offset = byteOffset(before)
        if (cached) {
          // Normal append path: O(last-record bytes), independent of history.
          if (!sameVersion(before, cached.file)) {
            throw new Error('Group ledger changed between verification and append')
          }
          await verifyTail(handle, offset - cached.tail.length, cached.tail)
        } else {
          // A new writer validates the complete existing file once. Re-opened
          // bytes must still agree with the read made before beforeWrite().
          const raw = await handle.readFile('utf8')
          const checked = decodeLedger(raw)
          if (checked.incompleteTail !== '' || !isDeepStrictEqual(checked.records, full.records) ||
              Buffer.byteLength(raw, 'utf8') !== offset) {
            throw new Error('Group ledger changed between verification and append')
          }
        }
        if ((await assertWriter(book)) !== true) {
          throw new Error('Exclusive writer lock lost before group ledger append')
        }
        let n = 0
        while (n < bytes.length) {
          const result = await handle.write(bytes, n, bytes.length - n, offset + n)
          if (result.bytesWritten <= 0) throw new Error('Group ledger write made no progress')
          n += result.bytesWritten
        }
        await handle.sync()
        writtenStat = fingerprint(await handle.stat({ bigint: true }))
        if (byteOffset(writtenStat) !== offset + bytes.length) {
          throw new Error('Group ledger size changed during append')
        }
      } finally {
        await handle.close()
      }
      // Check the current canonical path, not only a possibly orphaned fd.
      // Reading the exact newly written row is O(new-row bytes), not O(book).
      const verify = await open(path, 'r')
      let actual
      try {
        actual = fingerprint(await verify.stat({ bigint: true }))
        if (!sameFile(actual, writtenStat)) {
          throw new Error('Group ledger path changed or the appended record was not retained')
        }
        await verifyTail(verify, offset, bytes)
      } finally {
        await verify.close()
      }
      confirmed.set(book, { seq: record.seq, file: actual, tail: bytes })
      return { seq: record.seq, reused: false }
    })
    queues.set(book, job)
    return job
  }
  const written = book => queues.get(book) ?? Promise.resolve()
  const flush = book => book === undefined ? Promise.all([...queues.values()]) : written(book)
  return { append, written, flush }
}
