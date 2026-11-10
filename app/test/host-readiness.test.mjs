import assert from 'node:assert/strict'
import { test } from 'node:test'
import { checkTeamReady } from '../src/host-readiness.mjs'

test('transport readiness cannot hide a missing or failed required team plugin', async () => {
  await assert.rejects(checkTeamReady({ get: () => undefined }), /required ChemClaw team plugin/)
  await assert.rejects(checkTeamReady({ get: () => ({ check: async () => false }) }), /required ChemClaw team plugin/)
  await assert.rejects(checkTeamReady({ get: () => ({ check: async () => { throw new Error('mock team load failure') } }) }), /mock team load failure/)
})

test('desktop readiness waits for the team load to finish', async () => {
  let ready
  let done = false
  const pending = checkTeamReady({ get: () => ({ check: () => new Promise(resolve => { ready = resolve }) }) }).then(() => { done = true })
  await Promise.resolve()
  assert.equal(done, false)
  ready(true)
  await pending
  assert.equal(done, true)
})
