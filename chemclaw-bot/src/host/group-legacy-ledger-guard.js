// Fail-closed boundary between the unconverted legacy groups.js writer and
// any room that already has a durable Ledger book. Until groups.js explicitly
// uses the Ledger committer and delivery receipts, state-only writes would
// create two contradictory sources of truth.
//
// This probe is read-only: it NEVER imports, reconciles, deletes or replays.
import { lstatSync } from 'node:fs'
import { join } from 'node:path'
import { ledgerFilename } from './ledger-foundation.js'

const SAFE_ROOM = /^[A-Za-z0-9_-]{1,160}$/
const MIGRATION_MESSAGE = 'This group already has a Ledger book. Legacy group writes and Bot dispatch are disabled until verified Ledger migration; no automatic replay or recovery was attempted.'
const CHECK_MESSAGE = 'The group Ledger status could not be verified. Legacy writes and Bot dispatch are disabled to protect conversation history.'

export function createLegacyGroupLedgerGuard({ home } = {}) {
  if (typeof home !== 'string' || !home) throw new TypeError('Group Ledger home is required')

  function status(roomId) {
    if (typeof roomId !== 'string' || !SAFE_ROOM.test(roomId)) {
      return { code: 'LEDGER_CHECK_FAILED', message: CHECK_MESSAGE }
    }
    const path = join(home, 'ledger', ledgerFilename('group-' + roomId))
    try {
      // lstat also rejects a dangling Ledger symlink; following it with stat
      // would mistake its ENOENT target for a safely un-migrated room.
      lstatSync(path)
      // Even an incomplete or corrupt Ledger must not be bypassed: the
      // read-only recovery inspector decides what comes next, not this writer.
      return { code: 'LEDGER_MIGRATION_REQUIRED', message: MIGRATION_MESSAGE }
    } catch (error) {
      if (error?.code === 'ENOENT') return undefined
      return { code: 'LEDGER_CHECK_FAILED', message: CHECK_MESSAGE }
    }
  }

  function assertWritable(roomId) {
    const blocked = status(roomId)
    if (!blocked) return
    const error = new Error(blocked.message)
    error.code = blocked.code
    throw error
  }
  return { status, assertWritable }
}
