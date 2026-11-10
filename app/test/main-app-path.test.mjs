import assert from 'node:assert/strict'
import { renameSync, rmSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { tmpdir } from 'node:os'
import { isAbsolute, join, relative, resolve, sep } from 'node:path'
import { test } from 'node:test'
import { app, state } from './helpers/fake-electron.mjs'
import { state as hostState } from './helpers/fake-host-process.mjs'
import { startApp, waitFor, window } from './helpers/app-harness.mjs'
import { root, bundle } from './helpers/fake-app-path.mjs'
import { installHooks } from './helpers/register.mjs'

await installHooks()
registerHooks({
  resolve(specifier, context, next) {
    if (specifier === './app-path.mjs' && context.parentURL?.endsWith('/src/main.mjs')) {
      return { url: new URL('./helpers/fake-app-path.mjs', import.meta.url).href, shortCircuit: true }
    }
    return next(specifier, context)
  },
})

test('moving the app stops DSH before one native notice and quits without relaunching the stale path', async t => {
  t.after(() => {
    app.quit()
    const part = relative(resolve(tmpdir()), resolve(root))
    assert.ok(part && part !== '..' && !part.startsWith(`..${sep}`) && !isAbsolute(part))
    rmSync(root, { recursive: true, force: true })
  })
  await startApp()
  await waitFor(() => hostState.starts > 0, 'start the fake Host')
  hostState.release()
  await waitFor(() => window()?.loaded.some(url => url.startsWith('http:')), 'connect the window')
  const notices = []
  state.dialogAnswer = options => {
    notices.push({ stops: hostState.stops, message: options.message })
    return { response: 0 }
  }
  const win = window(), loads = win.loaded.length, dialogs = state.dialogs.length
  renameSync(bundle, join(root, 'Moved.app'))
  let prevented = 0
  for (let n = 0; n < 3; n++) win.webContents.emit('will-frame-navigate', { preventDefault: () => { prevented += 1 } })
  await waitFor(() => state.quits > 0, 'quit after the native notice')
  assert.equal(prevented, 3)
  assert.equal(win.webContents.stopped, true)
  assert.equal(win.visible, false)
  assert.equal(win.loaded.length, loads)
  assert.equal(hostState.stops, 1)
  assert.equal(notices.length, 1)
  assert.equal(notices[0].stops, 1)
  assert.match(notices[0].message, /moved or replaced/u)
  assert.equal(state.dialogs.length - dialogs, 1)
  assert.equal(state.relaunches.length, 0)
  assert.equal(win.webContents.listenerCount('will-frame-navigate'), 0)
})
