// Exercise the Electron supervisor with a failing DSH Host, without a display,
// network, actual browser or user data. Only the known Playwright frame assertion
// may trigger the one-run fallback instead of the fatal startup dialog.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { state } from './helpers/fake-electron.mjs'
import { state as hostState } from './helpers/fake-host-process.mjs'
import { startApp, waitFor } from './helpers/app-harness.mjs'
import { installHooks } from './helpers/register.mjs'

await installHooks()

test('FrameManager assertion restarts the app once in browser-safe mode without a fatal dialog', async () => {
  await startApp()
  await waitFor(() => hostState.starts > 0 && typeof hostState.failHost === 'function', 'start the fake Host')
  const crash = new Error('The DSH Host stopped (exit 1):\ndsh: fatal load failure: Error: Assertion error\n    at FrameManager.frameAttached')
  hostState.failHost(crash)
  hostState.failHost(crash) // A concurrent fatal IPC and close event must not restart twice.
  await waitFor(() => state.relaunches.length === 1, 'schedule a safe browser restart')
  assert.equal(state.relaunches.length, 1)
  assert.ok(state.relaunches[0].args.includes('--chemclaw-browser-safe-mode'))
  assert.deepEqual(state.dialogs, [])
  assert.ok(state.quits >= 1)
})
