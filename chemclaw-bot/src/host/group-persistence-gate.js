// An in-memory fail-closed gate for the legacy group room cache.
//
// The legacy appendRoom path updates room.seq/log before state.json is safely
// persisted. Once a required group save fails, that room's memory may be ahead
// of disk. Do not accept new group messages or dispatch Bot turns from it until
// a fresh Host has reloaded the durable state and its recovery has been checked.
//
// This does not repair/roll back a failed save or enable the Ledger cutover.
export function createGroupPersistenceGate() {
  const failures = new Map()
  const publicMessage = 'Group message persistence is uncertain; this room is blocked until restart and recovery inspection. No further Bot delivery was attempted.'

  function block(roomId, cause) {
    if (typeof roomId !== 'string' || roomId.length === 0) throw new TypeError('A room ID is required')
    if (!failures.has(roomId)) failures.set(roomId, cause ?? new Error('Required state save failed'))
    return failures.get(roomId)
  }

  function status(roomId) {
    if (!failures.has(roomId)) return undefined
    return { code: 'PERSISTENCE_BLOCKED', message: publicMessage }
  }

  function assertWritable(roomId) {
    const blocked = status(roomId)
    if (!blocked) return
    const error = new Error(blocked.message)
    error.code = blocked.code
    throw error
  }

  return { block, status, assertWritable }
}
