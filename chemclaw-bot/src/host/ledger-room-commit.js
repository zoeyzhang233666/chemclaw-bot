// P0 group Ledger -> state cache commit adapter (NOT connected to groups.js yet).
//
// This is the seam for replacing groups.js's synchronous appendRoom. It applies
// a full group message to the durable JSONL book BEFORE exposing a bounded room
// cache or invoking state.json save. A rejected write must NOT be dispatched to
// any Bot, included in round replies, or presented as a successful send.
//
// The caller must pass rt.assertLedgerWriter and rt.save({ required: true });
// never use rt.readOnly() as writer authorization, and NEVER swallow save errors.
//
// The adapter is intentionally not a crash recovery or a re-delivery engine.
// Once a book is ahead of the saved room, it refuses new writes. The user must
// resolve uncertain delivery receipts before any state is reconciled.
import { randomUUID } from 'node:crypto'
import { link, mkdir, open, readFile, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { GROUP_LINE_READ, TEXT_KEPT } from './constants.js'
import { createDurableGroupLedger } from './ledger-append.js'
import { readLedger } from './ledger-foundation.js'
import { planGroupLedgerRecovery } from './ledger-recovery.js'
import { headOf } from './text.js'

const SAFE_ROOM = /^[A-Za-z0-9_-]{1,160}$/
const LOG_LIMIT = 60

function roomIdOf(room) {
  if (!room || typeof room.id !== 'string' || !SAFE_ROOM.test(room.id)) {
    throw new Error('A valid group room is required for a Ledger commit')
  }
  return room.id
}
function prepareLine(line) {
  if (!line || typeof line !== 'object' || Array.isArray(line) ||
      Object.hasOwn(line, 'seq') || Object.hasOwn(line, 'length') ||
      (line.text !== undefined && typeof line.text !== 'string')) {
    throw new Error('Group Ledger commit requires an unsequenced message with valid text')
  }
  const json = JSON.stringify(line)
  if (!json || typeof json !== 'string') throw new Error('Group Ledger message cannot be encoded')
  return JSON.parse(json)
}
function previewOf(record) {
  const text = record.text
  if (typeof text !== 'string' || text.length <= TEXT_KEPT) return { ...record }
  return { ...record, text: headOf(text, TEXT_KEPT), length: text.length }
}

// A legacy reader still expects group-lines/<room>/<seq>.txt for messages
// longer than TEXT_KEPT. Publish that truncated reading window by fsync + an
// atomic no-clobber link; the Ledger always retains the original full text.
// Do not delete old sidecars as part of a commit (they may be needed by an
// earlier saved state.json or a session after a crash).
async function publishReadingSidecar(home, roomId, seq, text) {
  if (text.length <= TEXT_KEPT) return
  const dir = join(home, 'group-lines', roomId)
  const path = join(dir, String(seq) + '.txt')
  const pending = path + '.pending-' + randomUUID()
  const contents = headOf(text, GROUP_LINE_READ)
  await mkdir(dir, { recursive: true })
  let created = false
  try {
    const fd = await open(pending, 'wx', 0o600)
    created = true
    try {
      await fd.writeFile(contents, 'utf8')
      await fd.sync()
    } finally {
      await fd.close()
    }
    try { await link(pending, path) } catch (error) {
      if (error?.code !== 'EEXIST') throw error
      const existing = await readFile(path, 'utf8')
      if (existing !== contents) throw new Error('Conflicting existing long-text sidecar for ' + roomId + '/' + seq)
    }
  } finally {
    if (created) await rm(pending, { force: true })
  }
}

export function createGroupLedgerCommitter({ home, assertWriter, saveState, beforeWrite } = {}) {
  if (typeof home !== 'string' || !home) throw new Error('Group Ledger home is required')
  if (typeof assertWriter !== 'function') throw new Error('A strict Ledger writer lock check is required')
  if (typeof saveState !== 'function') throw new Error('A required state-save callback is required')

  const ledger = createDurableGroupLedger({ home, assertWriter, beforeWrite })
  const queued = new Map()
  const verified = new Map()
  function commit(room, line) {
    const id = roomIdOf(room)
    const book = 'group-' + id
    // Fix the payload before joining the queue. A running Bot can otherwise
    // mutate a line while an earlier message waits for disk I/O.
    let original
    let inputError
    try { original = prepareLine(line) } catch (error) { inputError = error }
    const previous = queued.get(book) ?? Promise.resolve()
    const job = previous.then(async () => {
      if (inputError) throw inputError
      if ((await assertWriter(book)) !== true) {
        throw new Error('Exclusive writer lock not confirmed for group Ledger commit')
      }
      const known = verified.get(book)
      const seq = room.seq
      const logStamp = JSON.stringify(room.log ?? [])
      if (known) {
        if (known.room !== room || known.seq !== seq || known.logStamp !== logStamp) {
          throw new Error('Group state changed outside the committed Ledger writer')
        }
      } else {
        const verdict = planGroupLedgerRecovery({
          room, ledger: await readLedger(home, book),
        })
        if (verdict.status !== 'aligned') {
          throw new Error('Group Ledger is not aligned with saved room state (' +
            verdict.status + '); no automatic recovery or dispatch')
        }
      }
      const record = { ...original, seq: seq + 1 }
      await ledger.append(book, record)

      // A competing legacy appendRoom call can mutate the in-memory room even
      // inside one process. Detect it before overwriting any of its state.
      if (room.id !== id || room.seq !== seq || JSON.stringify(room.log ?? []) !== logStamp) {
        throw new Error('Legacy room state changed while Ledger was being fsynced')
      }
      if (typeof record.text === 'string') {
        await publishReadingSidecar(home, id, record.seq, record.text)
      }
      if ((await assertWriter(book)) !== true) {
        throw new Error('Exclusive writer lock lost before saving group cache')
      }
      // A long-text sidecar can await I/O, so re-check the room once more just
      // before changing anything visible or asking state.json to be saved.
      if (room.id !== id || room.seq !== seq || JSON.stringify(room.log ?? []) !== logStamp) {
        throw new Error('Legacy room state changed before group cache commit')
      }
      const preview = previewOf(record)
      room.seq = record.seq
      room.log = [...(room.log ?? []), preview].slice(-LOG_LIMIT)

      // This callback MUST await rt.save({ required: true }). Its rejection
      // poisons this room's queue, leaving the durable book ahead of disk state.
      // A fresh Host must run read-only recovery inspection, not automatically
      // redeliver the already-fsynced row.
      await saveState(room)
      verified.set(book, { room, seq: room.seq, logStamp: JSON.stringify(room.log) })
      return { seq: record.seq, record, preview }
    })
    queued.set(book, job)
    return job
  }
  const written = roomId => queued.get('group-' + roomId) ?? Promise.resolve()
  const flush = () => Promise.all([...queued.values()])
  return { commit, written, flush }
}
