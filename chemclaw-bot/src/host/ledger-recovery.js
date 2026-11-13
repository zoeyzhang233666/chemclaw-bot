// P0: read-only crash-recovery preview for an fsynced group Ledger whose
// state.json room may not have been saved before the Host exited.
//
// This module NEVER writes state.json, replays a Bot turn, re-delivers a user
// message, or changes Session/approval state. A durable Ledger record proves
// persistence, NOT whether a recipient already saw or acted upon that message.
// The live group runtime must not adopt this preview until it has an explicit
// no-duplicate-delivery protocol and durable sidecar/visible-log integration.
import { isDeepStrictEqual } from 'node:util'
import { readLedger } from './ledger-foundation.js'
import { TEXT_KEPT } from './constants.js'
import { headOf } from './text.js'

const ROOM_ID = /^[A-Za-z0-9_-]{1,160}$/
const ROOM_LOG_MAX = 60

function roomSequence(room) {
  if (!room || typeof room.id !== 'string' || !ROOM_ID.test(room.id)) {
    throw new Error('Invalid group id for Ledger recovery')
  }
  if (!Number.isSafeInteger(room.seq) || room.seq < 0 ||
      (room.log !== undefined && !Array.isArray(room.log))) {
    throw new Error('Invalid saved group sequence or log')
  }
  return room.seq
}

function blocked(stateSeq, ledgerSeq, reason) {
  return {
    status: 'blocked', stateSeq, ledgerSeq, reason,
    unconfirmedRecords: [], previewLog: [], longTextSidecarsNeeded: [],
    mustNotRedispatch: true,
  }
}

function verifyFullBook(ledger) {
  if (!ledger || !Array.isArray(ledger.records)) return 'Ledger records are unavailable'
  if (ledger.incompleteTail !== '') return 'Ledger has an interrupted final record'
  for (let index = 0; index < ledger.records.length; index++) {
    const record = ledger.records[index]
    if (!record || typeof record !== 'object' || Array.isArray(record) ||
        record.seq !== index + 1) {
      return 'Ledger contains a gap, duplicate, or invalid sequence at ' + (index + 1)
    }
    if (record.legacyIncomplete === true ||
        (record.length !== undefined && (!Number.isSafeInteger(record.length) ||
          record.length !== (typeof record.text === 'string' ? record.text.length : 0)))) {
      return 'Ledger contains an incomplete message at ' + (index + 1)
    }
  }
  return undefined
}

// The saved room log stores at most TEXT_KEPT characters of long lines.
// Verify that its shorter copy matches the durable full message; never use a
// matching sequence alone as evidence that the messages are the same.
function roomLineAgrees(saved, durable) {
  if (!saved || typeof saved !== 'object' || Array.isArray(saved) ||
      saved.seq !== durable.seq) return false
  for (const key of Object.keys(saved)) {
    if (key === 'text' || key === 'length') continue
    if (!Object.hasOwn(durable, key) || !isDeepStrictEqual(saved[key], durable[key])) {
      return false
    }
  }
  if (saved.text !== undefined &&
      (typeof saved.text !== 'string' || typeof durable.text !== 'string' ||
       !durable.text.startsWith(saved.text))) return false
  if (saved.text === undefined && durable.text !== undefined && durable.text !== '') return false
  if (saved.length !== undefined &&
      (!Number.isSafeInteger(saved.length) || typeof durable.text !== 'string' ||
       saved.length !== durable.text.length)) return false
  return true
}

// Preview records in the same bounded layout as room.log. This is NOT a
// persistent materialization: long-message group-lines files must be written
// under a separate confirmed writer protocol before a room adopts this view.
function shortLog(records) {
  return records.map(record => {
    if (typeof record.text !== 'string' || record.text.length <= TEXT_KEPT) {
      return { ...record }
    }
    const length = record.text.length
    return { ...record, text: headOf(record.text, TEXT_KEPT), length }
  })
}

export function planGroupLedgerRecovery({ room, ledger }) {
  const stateSeq = roomSequence(room)
  if (ledger === undefined) {
    return {
      status: 'not-migrated', stateSeq, ledgerSeq: null,
      unconfirmedRecords: [], previewLog: [], longTextSidecarsNeeded: [],
      mustNotRedispatch: true,
    }
  }
  const records = ledger.records
  const ledgerSeq = Array.isArray(records) ? records.length : null
  const invalid = verifyFullBook(ledger)
  if (invalid) return blocked(stateSeq, ledgerSeq, invalid)
  if (stateSeq > ledgerSeq) {
    return blocked(stateSeq, ledgerSeq, 'state.json is ahead of the durable Ledger; do not discard saved messages')
  }

  const persisted = room.log ?? []
  // room.log is the latest contiguous window of at most 60 records. A gap in
  // that retained window may represent unsaved/partially repaired state and
  // must not be misclassified as synchronized merely because each remaining
  // sequence happens to match the book.
  if (persisted.length > ROOM_LOG_MAX) {
    return blocked(stateSeq, ledgerSeq, 'Saved room.log exceeds its bounded history window')
  }
  let expected = stateSeq - persisted.length + 1
  for (const saved of persisted) {
    if (!Number.isSafeInteger(saved?.seq) || saved.seq !== expected ||
        !roomLineAgrees(saved, records[saved.seq - 1])) {
      return blocked(stateSeq, ledgerSeq, 'Saved room.log is inconsistent with durable Ledger history')
    }
    expected++
  }
  if (stateSeq > 0 && persisted.length === 0) {
    return blocked(stateSeq, ledgerSeq, 'Saved room has a nonzero sequence but no verifiable recent log')
  }
  if (persisted.length > 0 && persisted.at(-1).seq !== stateSeq) {
    return blocked(stateSeq, ledgerSeq, 'Saved room.log does not end at the saved room sequence')
  }
  if (stateSeq === ledgerSeq) {
    return {
      status: 'aligned', stateSeq, ledgerSeq,
      unconfirmedRecords: [], previewLog: [], longTextSidecarsNeeded: [],
      mustNotRedispatch: true,
    }
  }

  const unconfirmedRecords = records.slice(stateSeq).map(record => ({ ...record }))
  const recent = records.slice(-ROOM_LOG_MAX)
  return {
    status: 'ledger-ahead', stateSeq, ledgerSeq,
    // "unconfirmed" means receipt/delivery status is UNKNOWN, not that the
    // message should be sent or executed again.
    unconfirmedRecords,
    previewLog: shortLog(recent),
    longTextSidecarsNeeded: recent
      .filter(record => typeof record.text === 'string' && record.text.length > TEXT_KEPT)
      .map(record => record.seq),
    mustNotRedispatch: true,
    requiresDeliveryReview: true,
  }
}

export async function inspectGroupLedgerRecovery(home, room) {
  roomSequence(room)
  return planGroupLedgerRecovery({ room, ledger: await readLedger(home, 'group-' + room.id) })
}
