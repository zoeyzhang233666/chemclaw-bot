import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createGroupPersistenceGate } from '../src/host/group-persistence-gate.js'

test('a failed room save blocks further writing only in that room', () => {
  const gate = createGroupPersistenceGate()
  const diskFull = new Error('disk full')
  gate.assertWritable('r1')
  gate.block('r1', diskFull)
  assert.deepEqual(gate.status('r1'), {
    code: 'PERSISTENCE_BLOCKED',
    message: 'Group message persistence is uncertain; this room is blocked until restart and recovery inspection. No further Bot delivery was attempted.',
  })
  assert.throws(() => gate.assertWritable('r1'), error => error.code === 'PERSISTENCE_BLOCKED')
  assert.doesNotThrow(() => gate.assertWritable('r2'))
  assert.equal(gate.status('r2'), undefined)
})

test('later failures cannot clear a blocked room or hide the first cause', () => {
  const gate = createGroupPersistenceGate()
  const error = new Error('lost writer lock')
  assert.equal(gate.block('r1', error), error)
  assert.equal(gate.block('r1', new Error('temporary recovery')), error)
  assert.throws(() => gate.assertWritable('r1'), /blocked until restart/)
})

test('a new Host creates a fresh gate without silently unblocking the old Host', () => {
  const oldGate = createGroupPersistenceGate()
  oldGate.block('r1', new Error('uncertain write'))
  const freshGate = createGroupPersistenceGate()
  freshGate.assertWritable('r1')
  assert.throws(() => oldGate.assertWritable('r1'), /blocked until restart/)
})

test('invalid room IDs cannot be recorded as failed writes', () => {
  const gate = createGroupPersistenceGate()
  assert.throws(() => gate.block('', new Error('oops')), /room ID is required/)
  assert.throws(() => gate.block(undefined), /room ID is required/)
})
