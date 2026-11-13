// First migration stage only: read legacy group archives and publish an initial
// complete group book without exposing partial writes. The live group runtime
// continues using its old format until later migration stages are reviewed.
// This helper must run while the team's existing single-writer lock is held.
import { createHash, randomUUID } from 'node:crypto'
import { link, mkdir, open, readFile, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { decodeLedger, ledgerFilename, previewLegacyRoom, readLedger } from './ledger-foundation.js'

const SAFE_ROOM = /^[A-Za-z0-9_-]{1,160}$/
const OLD_FILENAME = /^[A-Za-z0-9_-]{1,128}$/

function roomIdOf(room) {
  const id = room?.id
  if (typeof id !== 'string' || !SAFE_ROOM.test(id)) throw new Error('Invalid legacy group id')
  return id
}

// Legacy group-log.js used a 32-character hash for IDs longer than 128 chars.
// This name is NOT the new ledgerFilename (which uses 64 hash characters).
export function legacyGroupLogFilename(roomId) {
  if (typeof roomId !== 'string' || !SAFE_ROOM.test(roomId)) throw new Error('Invalid legacy group id')
  const name = OLD_FILENAME.test(roomId) ? roomId : createHash('sha256').update(roomId).digest('hex').slice(0, 32)
  return name + '.jsonl'
}

export async function readLegacyGroupLog(home, roomId) {
  const path = join(home, 'group-logs', legacyGroupLogFilename(roomId))
  let contents
  try { contents = await readFile(path, 'utf8') }
  catch (error) {
    if (error?.code === 'ENOENT') return { found: false, rows: [], truncatedTail: false }
    throw error
  }
  const { records, incompleteTail } = decodeLedger(contents)
  for (const record of records) {
    if (!Number.isSafeInteger(record.seq) || record.seq < 1) {
      throw new Error('Legacy group archive contains an invalid sequence')
    }
  }
  return { found: true, rows: records, truncatedTail: incompleteTail !== '' }
}

export async function planLegacyGroupImport({ home, room }) {
  roomIdOf(room)
  const archive = await readLegacyGroupLog(home, room.id)
  const preview = await previewLegacyRoom({ home, room, archivedRows: archive.rows })
  const warnings = [...preview.warnings]
  if (archive.truncatedTail) warnings.push('Legacy group archive ends with an interrupted JSONL record')
  if (!Number.isSafeInteger(room.seq) || room.seq < 0) warnings.push('Legacy room sequence is not verified')
  const rows = preview.rows
  const latest = rows.at(-1)?.seq ?? 0
  if (rows.length === 0 && room.seq !== 0) warnings.push('Legacy room has a sequence but no recoverable messages')
  if (rows.length > 0 && rows[0].seq !== 1) warnings.push('Legacy group has an unverified historical prefix')
  if (room.seq !== latest) warnings.push('Legacy room sequence differs from recovered message count')
  const ready = warnings.length === 0
  return { book: preview.book, rows, warnings, ready, legacyArchiveFound: archive.found }
}

function serializeRows(records) {
  if (!Array.isArray(records)) throw new Error('Ledger records must be an array')
  let expected = 1
  const lines = []
  for (const row of records) {
    if (!row || typeof row !== 'object' || Array.isArray(row) || row.seq !== expected) {
      throw new Error('Initial group ledger records must have consecutive sequences starting at 1')
    }
    const text = JSON.stringify(row)
    if (typeof text !== 'string') throw new Error('Could not serialize ledger record')
    lines.push(text + '\n')
    expected++
  }
  return lines.join('')
}

async function verifyExisting(path, contents) {
  const actual = await readFile(path, 'utf8')
  const { incompleteTail } = decodeLedger(actual)
  if (incompleteTail !== '' || actual !== contents) {
    throw new Error('An existing group ledger differs from this verified import; do not overwrite it')
  }
  return { reused: true }
}

// The temp file is fully written, synced and closed BEFORE becoming visible at
// its final name. Hard-link creation is atomic and fails if another writer won.
// Unlike writing directly to a wx target, a crash cannot leave a complete-looking
// prefix of the group's history published under the canonical book filename.
// Orphaned .pending- files are never read as books and may be cleaned manually.
export async function publishInitialGroupBook(home, book, records) {
  if (typeof book !== 'string' || !book.startsWith('group-')) {
    throw new Error('Only a group book may be initialized through this importer')
  }
  const contents = serializeRows(records)
  const dir = join(home, 'ledger')
  await mkdir(dir, { recursive: true })
  const path = join(dir, ledgerFilename(book))
  const pending = path + '.pending-' + randomUUID()
  let created = false
  try {
    const handle = await open(pending, 'wx', 0o600)
    created = true
    try {
      await handle.writeFile(contents, 'utf8')
      await handle.sync()
    } finally {
      await handle.close()
    }
    try {
      await link(pending, path)
    } catch (error) {
      if (error?.code !== 'EEXIST') throw error
      return { path, ...(await verifyExisting(path, contents)) }
    }
    const confirmed = await readLedger(home, book)
    if (confirmed?.incompleteTail !== '' || confirmed.records.length !== records.length) {
      throw new Error('The newly published ledger did not pass a read-back check')
    }
    return { path, reused: false }
  } finally {
    if (created) await rm(pending, { force: true })
  }
}

// Read all known old sources first. Refuse to publish a partial import: no
// missing prefix, internal gap, damaged long-text file, or truncated archive.
export async function seedLegacyGroupLedger({ home, room }) {
  const plan = await planLegacyGroupImport({ home, room })
  if (!plan.ready) {
    throw new Error('Legacy group import is incomplete; source files stay untouched: ' + plan.warnings.join('; '))
  }
  return { ...(await publishInitialGroupBook(home, plan.book, plan.rows)), rows: plan.rows.length }
}
