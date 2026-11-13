// P0 ledger migration foundation: preview old ChemClaw group messages without
// changing state.json, group-lines/, Session logs, or any existing ledger.
// Not activated by the runtime until the migration PR has durable write gates.
import { createHash } from 'node:crypto'
import { isDeepStrictEqual } from 'node:util'
import { mkdir, open, readFile, rm } from 'node:fs/promises'
import { join } from 'node:path'

const SAFE_ID = /^[A-Za-z0-9_-]{1,160}$/

export function ledgerFilename(book) {
  const name = String(book)
  const safe = SAFE_ID.test(name) ? name : createHash('sha256').update(name).digest('hex')
  return safe + '.jsonl'
}

export function decodeLedger(text) {
  const source = String(text ?? '')
  const complete = source === '' || source.endsWith('\n')
  const lines = source.split('\n')
  const incompleteTail = complete ? '' : lines.pop()
  const records = []
  for (const [index, row] of lines.entries()) {
    if (row === '') continue
    let record
    try { record = JSON.parse(row) }
    catch { throw new Error('Ledger contains a corrupt complete line at ' + (index + 1)) }
    if (record === null || Array.isArray(record) || typeof record !== 'object') {
      throw new Error('Ledger contains a non-object record at ' + (index + 1))
    }
    records.push(record)
  }
  return { records, incompleteTail }
}

export async function readLedger(home, book) {
  const path = join(home, 'ledger', ledgerFilename(book))
  try {
    return decodeLedger(await readFile(path, 'utf8'))
  } catch (error) {
    if (error?.code === 'ENOENT') return undefined
    throw error
  }
}

function validRoom(room) {
  if (!room || typeof room.id !== 'string' || !SAFE_ID.test(room.id)) {
    throw new Error('Invalid legacy group id')
  }
  if (room.log !== undefined && !Array.isArray(room.log)) {
    throw new Error('Legacy group log is not an array')
  }
}

// A historical group archive can preserve the full message while state.json
// keeps only its beginning (and the original total length). Both represent the
// same row if their shared metadata agrees and one text is a prefix of the other.
function reconcileDuplicateRow(first, second, seq) {
  for (const key of new Set([...Object.keys(first), ...Object.keys(second)])) {
    if (key === 'text' || key === 'length') continue
    if (Object.hasOwn(first, key) && Object.hasOwn(second, key) &&
        !isDeepStrictEqual(first[key], second[key])) {
      throw new Error('Conflicting legacy group sequence ' + seq + ' (field ' + key + ')')
    }
  }
  const a = typeof first.text === 'string' ? first.text : ''
  const b = typeof second.text === 'string' ? second.text : ''
  if (!a.startsWith(b) && !b.startsWith(a)) {
    throw new Error('Conflicting legacy group sequence ' + seq + ' (text)')
  }
  const expectedA = Number.isSafeInteger(first.length) ? first.length : undefined
  const expectedB = Number.isSafeInteger(second.length) ? second.length : undefined
  if (expectedA !== undefined && expectedB !== undefined && expectedA !== expectedB) {
    throw new Error('Conflicting legacy group sequence ' + seq + ' (length)')
  }
  const expected = expectedA ?? expectedB
  const text = a.length >= b.length ? a : b
  if (expected !== undefined && text.length > expected) {
    throw new Error('Conflicting legacy group sequence ' + seq + ' (text exceeds length)')
  }
  return { ...first, ...second, text, ...(expected === undefined ? {} : { length: expected }) }
}

export async function previewLegacyRoom({ home, room, archivedRows = [] }) {
  validRoom(room)
  if (!Array.isArray(archivedRows)) throw new Error('Legacy archived rows must be an array')
  const warnings = []
  const bySeq = new Map()
  // Archived records, when explicitly supplied by the future historical-log
  // adapter, precede the latest rows in state.json. This function does not
  // guess the layout of archives that ChemClaw did not itself write.
  const older = archivedRows.map((line, index) => ({ line, index, source: 'archive' }))
  const recent = (room.log ?? []).map((line, index) => ({ line, index, source: 'state' }))
  for (const item of [...older, ...recent]) {
    const { line, index, source } = item
    if (!line || Array.isArray(line) || typeof line !== 'object') {
      throw new Error('Invalid legacy group row')
    }
    const legacyStart = Number.isSafeInteger(room.seq) && room.seq >= recent.length
      ? room.seq - recent.length + 1 : older.length + 1
    const seq = line.seq ?? (source === 'archive' ? index + 1 : legacyStart + index)
    if (!Number.isSafeInteger(seq) || seq < 1) throw new Error('Invalid legacy group sequence')
    if (bySeq.has(seq)) {
      const previous = bySeq.get(seq)
      bySeq.set(seq, { line: reconcileDuplicateRow(previous.line, line, seq), source: 'combined' })
      continue
    }
    bySeq.set(seq, { line, source })
  }
  const rows = []
  for (const [seq, item] of [...bySeq.entries()].sort(([a], [b]) => a - b)) {
    const line = item.line
    let text = typeof line.text === 'string' ? line.text : ''
    let incomplete = false
    if (Number.isSafeInteger(line.length) && line.length > text.length) {
      try {
        const long = await readFile(join(home, 'group-lines', room.id, String(seq) + '.txt'), 'utf8')
        if (long.length >= text.length) text = long
      } catch (error) {
        if (error?.code !== 'ENOENT') throw error
        warnings.push('Missing legacy long-text file for ' + room.id + '/' + seq)
      }
      if (line.length > text.length) {
        incomplete = true
        warnings.push('Legacy row ' + room.id + '/' + seq + ' is incomplete (' + text.length + '/' + line.length + ' characters recovered)')
      }
    }
    rows.push({ ...line, seq, text, ...(incomplete ? { legacyIncomplete: true } : {}) })
  }
  const last = rows.at(-1)?.seq ?? 0
  if (Number.isSafeInteger(room.seq) && room.seq < last) {
    throw new Error('Legacy group sequence is behind the recovered messages')
  }
  if (Number.isSafeInteger(room.seq) && room.seq > last) {
    warnings.push('Legacy group has a later sequence than the recovered log; newer/missing history must be checked separately')
  }
  if (rows.length > 0 && rows[0].seq > 1) {
    warnings.push('Legacy room.log starts after sequence 1; older history may be in Session or other archives')
  }
  for (let index = 1; index < rows.length; index += 1) {
    const previous = rows[index - 1].seq
    const current = rows[index].seq
    if (current > previous + 1) {
      warnings.push('Legacy group has missing messages between sequences ' + previous + ' and ' + current)
    }
  }
  return { book: 'group-' + room.id, rows, warnings }
}

// Explicit one-time initialization only. Exclusive no-clobber creation prevents
// importing twice and never overwrites any existing book or legacy source.
// A crash may leave an incomplete new book; readLedger reports its torn tail
// rather than silently accepting it, and the original old files remain intact.
export async function writeInitialLedger(home, book, records) {
  if (!Array.isArray(records)) throw new Error('Ledger records must be an array')
  const dir = join(home, 'ledger')
  const path = join(dir, ledgerFilename(book))
  await mkdir(dir, { recursive: true })
  const handle = await open(path, 'wx', 0o600)
  try {
    const content = records.map(record => {
      if (!record || Array.isArray(record) || typeof record !== 'object') {
        throw new Error('Ledger record must be an object')
      }
      return JSON.stringify(record) + '\n'
    }).join('')
    await handle.writeFile(content, 'utf8')
    await handle.sync()
  } catch (error) {
    await handle.close()
    await rm(path, { force: true })
    throw error
  }
  await handle.close()
  return path
}
