import assert from 'node:assert/strict'
import { test } from 'node:test'
import { app, state } from './helpers/fake-electron.mjs'
import { state as hostState } from './helpers/fake-host-process.mjs'
import { startApp, waitFor, window } from './helpers/app-harness.mjs'
import { installHooks } from './helpers/register.mjs'

await installHooks()

test('a crashed main renderer reconnects without replaying the launch token or restarting DSH', async t => {
  await startApp()
  t.after(() => { app.quit() })
  await waitFor(() => hostState.starts > 0, 'start the fake Host')
  hostState.release()
  await waitFor(() => window()?.loaded.some(url => url.startsWith('http:')), 'connect the window')
  const win = window()
  const loads = win.loaded.length
  const starts = hostState.starts
  const origin = new URL(win.url).origin
  win.webContents.emit('render-process-gone', {}, { reason: 'crashed', exitCode: 1 })
  await waitFor(() => win.loaded.length > loads, 'recover the renderer')
  assert.equal(win.loaded.at(-1), `${origin}/`)
  assert.equal(hostState.starts, starts)
  assert.equal(state.relaunches.length, 0)
})
